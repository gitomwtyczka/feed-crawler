"""
Feed fetch scheduler.

Orchestrates periodic fetching of all configured feeds.
Uses APScheduler for interval-based scheduling.
Supports graceful shutdown via SIGTERM/SIGINT.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from .config_loader import load_departments, load_sources
from .database import SessionLocal, init_db
from .dedup import compute_hash, get_existing_by_hash
from .feed_parser import FetchResult, fetch_batch
from .models import (
    Article,
    ArticleDepartment,
    Department,
    Feed,
    FeedDepartment,
    FetchLog,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ── DB Sync: config → database ──


def sync_config_to_db(db: Session, sources_path: str = "config/sources.yaml", departments_path: str = "config/departments.yaml") -> None:
    """Synchronize YAML config to database (idempotent).

    Creates or updates Feed and Department records.
    """
    # Sync departments
    dept_configs = load_departments(departments_path)
    for dept_cfg in dept_configs:
        existing = db.query(Department).filter(Department.slug == dept_cfg.slug).first()
        if not existing:
            dept = Department(name=dept_cfg.name, slug=dept_cfg.slug, description=dept_cfg.description)
            db.add(dept)
            logger.info("Created department: %s", dept_cfg.slug)
    db.commit()

    # Sync sources
    source_configs = load_sources(sources_path)
    for src_cfg in source_configs:
        existing = db.query(Feed).filter(Feed.rss_url == src_cfg.rss_url).first()
        if not existing:
            feed = Feed(
                name=src_cfg.name,
                url=src_cfg.url,
                rss_url=src_cfg.rss_url,
                feed_type=src_cfg.feed_type,
                fetch_interval=src_cfg.fetch_interval,
            )
            db.add(feed)
            db.flush()  # get feed.id

            # Link to departments
            for dept_slug in src_cfg.departments:
                dept = db.query(Department).filter(Department.slug == dept_slug).first()
                if dept:
                    fd = FeedDepartment(feed_id=feed.id, department_id=dept.id)
                    db.add(fd)

            logger.info("Created feed: %s → %s", src_cfg.name, src_cfg.departments)

    db.commit()


# ── Article storage ──


def store_articles(db: Session, result: FetchResult, feed: Feed) -> int:
    """Store fetched articles to DB with deduplication.

    Returns number of new articles stored.
    """
    new_count = 0

    # Get feed's departments for tagging articles
    dept_ids = [fd.department_id for fd in db.query(FeedDepartment).filter(FeedDepartment.feed_id == feed.id).all()]

    for raw in result.articles:
        article_hash = compute_hash(raw.url, raw.title)

        # Check for existing
        existing = get_existing_by_hash(db, article_hash)
        if existing:
            # Article exists — ensure it's tagged with all departments
            existing_dept_ids = {
                ad.department_id
                for ad in db.query(ArticleDepartment).filter(ArticleDepartment.article_id == existing.id).all()
            }
            for dept_id in dept_ids:
                if dept_id not in existing_dept_ids:
                    db.add(ArticleDepartment(article_id=existing.id, department_id=dept_id))
            continue

        # New article
        article = Article(
            feed_id=feed.id,
            title=raw.title,
            url=raw.url,
            summary=raw.summary,
            content=raw.content,
            author=raw.author,
            published_at=raw.published_at,
            hash=article_hash,
        )
        db.add(article)
        db.flush()

        # Tag with departments
        for dept_id in dept_ids:
            db.add(ArticleDepartment(article_id=article.id, department_id=dept_id))

        new_count += 1

    db.commit()
    return new_count


# ── Single fetch cycle ──


async def run_fetch_cycle(sources_path: str = "config/sources.yaml", departments_path: str = "config/departments.yaml") -> dict:
    """Run a single fetch cycle for all active feeds.

    Returns summary dict with counts.
    """
    db = SessionLocal()
    try:
        # Ensure config is synced
        sync_config_to_db(db, sources_path, departments_path)

        # Get active feeds
        active_feeds = db.query(Feed).filter(Feed.is_active).all()
        if not active_feeds:
            logger.warning("No active feeds found")
            return {"feeds": 0, "articles_new": 0, "errors": 0}

        logger.info("Starting fetch cycle: %d active feeds", len(active_feeds))

        # Prepare batch
        feed_dicts = [{"rss_url": f.rss_url, "name": f.name} for f in active_feeds]

        # Fetch all feeds
        results = await fetch_batch(feed_dicts)

        # Process results
        total_new = 0
        total_errors = 0

        for feed_obj, result in zip(active_feeds, results):
            # Create fetch log
            fetch_log = FetchLog(
                feed_id=feed_obj.id,
                started_at=datetime.utcnow(),
                status=result.status,
                articles_found=len(result.articles),
                error_message=result.error_message or None,
            )

            if result.status == "success":
                new_count = store_articles(db, result, feed_obj)
                fetch_log.articles_new = new_count
                total_new += new_count
            else:
                total_errors += 1

            fetch_log.finished_at = datetime.utcnow()
            feed_obj.last_fetched = datetime.utcnow()
            db.add(fetch_log)

        db.commit()

        summary = {
            "feeds": len(active_feeds),
            "articles_new": total_new,
            "errors": total_errors,
        }
        logger.info(
            "Fetch cycle complete: %d feeds, %d new articles, %d errors",
            summary["feeds"], summary["articles_new"], summary["errors"],
        )
        return summary

    finally:
        db.close()


# ── CLI Entry point ──


def main() -> None:
    """CLI entry point: run a single fetch cycle."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    init_db()
    logger.info("Feed Crawler starting (single cycle mode)")

    result = asyncio.run(run_fetch_cycle())
    logger.info("Result: %s", result)


if __name__ == "__main__":
    main()
