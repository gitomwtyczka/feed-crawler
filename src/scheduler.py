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
        # Match by name OR rss_url (avoid UNIQUE constraint violations)
        existing = db.query(Feed).filter(Feed.name == src_cfg.name).first()
        if not existing and src_cfg.rss_url:
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


# ── Backoff & health helpers ──

MAX_CONSECUTIVE_ERRORS = 10  # auto-disable after this many
BACKOFF_BASE_MINUTES = 5     # backoff = 2^errors * base (capped at 24h)
BACKOFF_MAX_MINUTES = 60 * 24  # 24 hours
BATCH_SIZE = 50              # feeds per batch
BATCH_PAUSE_SECONDS = 1.0    # pause between batches


def _compute_backoff_until(errors: int) -> datetime:
    """Compute next allowed fetch time with exponential backoff."""
    from datetime import timedelta

    minutes = min(BACKOFF_BASE_MINUTES * (2 ** errors), BACKOFF_MAX_MINUTES)
    return datetime.utcnow() + timedelta(minutes=minutes)


def _is_feed_due(feed: Feed, now: datetime) -> bool:
    """Check if a feed is ready to be fetched (respects interval + backoff)."""
    from datetime import timedelta

    # In backoff?
    if feed.backoff_until and now < feed.backoff_until:
        return False

    # Never fetched → fetch now
    if not feed.last_fetched:
        return True

    # Check fetch interval
    interval = timedelta(minutes=feed.fetch_interval or 30)
    return now >= feed.last_fetched + interval


def _update_feed_health(db: Session, feed: Feed, success: bool) -> None:
    """Update feed error tracking and apply backoff on failure."""
    if success:
        feed.consecutive_errors = 0
        feed.backoff_until = None
    else:
        feed.consecutive_errors = (feed.consecutive_errors or 0) + 1
        feed.backoff_until = _compute_backoff_until(feed.consecutive_errors)

        if feed.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            feed.is_active = False
            logger.warning(
                "Auto-disabled feed '%s' after %d consecutive errors",
                feed.name, feed.consecutive_errors,
            )


# ── Single fetch cycle ──


async def run_fetch_cycle(sources_path: str = "config/sources.yaml", departments_path: str = "config/departments.yaml") -> dict:
    """Run a single fetch cycle for all active feeds.

    Features:
    - Per-feed interval scheduling (skips feeds not yet due)
    - Exponential backoff on errors (2^n * 5 min, max 24h)
    - Auto-disable feeds after 10 consecutive errors
    - Staggered batching (50 feeds per batch with pause)

    Returns summary dict with counts.
    """
    db = SessionLocal()
    try:
        # Ensure config is synced
        sync_config_to_db(db, sources_path, departments_path)

        now = datetime.utcnow()

        # Get active feeds that are due for fetching
        active_feeds = db.query(Feed).filter(Feed.is_active).all()
        due_feeds = [f for f in active_feeds if _is_feed_due(f, now)]

        if not due_feeds:
            logger.info("No feeds due for fetching (total active: %d)", len(active_feeds))
            return {"feeds": len(active_feeds), "feeds_fetched": 0, "articles_new": 0, "errors": 0, "skipped": len(active_feeds)}

        logger.info(
            "Starting fetch cycle: %d due / %d active feeds (batch size: %d)",
            len(due_feeds), len(active_feeds), BATCH_SIZE,
        )

        # Filter RSS/Atom feeds only (scrapers handled separately)
        rss_feeds = [f for f in due_feeds if f.rss_url]

        total_new = 0
        total_errors = 0
        disabled_count = 0

        # ── Staggered batching ──
        for batch_idx in range(0, len(rss_feeds), BATCH_SIZE):
            batch = rss_feeds[batch_idx:batch_idx + BATCH_SIZE]
            batch_num = batch_idx // BATCH_SIZE + 1
            total_batches = (len(rss_feeds) + BATCH_SIZE - 1) // BATCH_SIZE

            if total_batches > 1:
                logger.info("Batch %d/%d: %d feeds", batch_num, total_batches, len(batch))

            feed_dicts = [{"rss_url": f.rss_url, "name": f.name} for f in batch]

            # Fetch batch
            results = await fetch_batch(feed_dicts)

            # Process results with health tracking
            for feed_obj, result in zip(batch, results):
                is_success = result.status == "success"

                # Create fetch log
                fetch_log = FetchLog(
                    feed_id=feed_obj.id,
                    started_at=datetime.utcnow(),
                    status=result.status,
                    articles_found=len(result.articles),
                    error_message=result.error_message or None,
                )

                if is_success:
                    new_count = store_articles(db, result, feed_obj)
                    fetch_log.articles_new = new_count
                    total_new += new_count
                else:
                    total_errors += 1

                fetch_log.finished_at = datetime.utcnow()
                feed_obj.last_fetched = datetime.utcnow()
                db.add(fetch_log)

                # Update health tracking (backoff / auto-disable)
                was_active = feed_obj.is_active
                _update_feed_health(db, feed_obj, is_success)
                if was_active and not feed_obj.is_active:
                    disabled_count += 1

            db.commit()

            # Pause between batches to respect servers
            if batch_idx + BATCH_SIZE < len(rss_feeds):
                await asyncio.sleep(BATCH_PAUSE_SECONDS)

        # Deliver new articles to SaaS via webhook (if configured)
        from .webhook import (
            article_to_webhook_payload,
            get_unsent_articles,
            is_webhook_enabled,
            mark_as_sent,
            send_article,
        )

        if is_webhook_enabled() and total_new > 0:
            unsent = get_unsent_articles(db, limit=50)
            delivered = 0
            for article in unsent:
                payload = article_to_webhook_payload(article)
                success = await send_article(payload)
                if success:
                    mark_as_sent(db, article)
                    delivered += 1
            if delivered:
                logger.info("Webhook: delivered %d/%d articles to SaaS", delivered, len(unsent))

        summary = {
            "feeds": len(active_feeds),
            "feeds_fetched": len(due_feeds),
            "articles_new": total_new,
            "errors": total_errors,
            "skipped": len(active_feeds) - len(due_feeds),
            "disabled": disabled_count,
        }
        logger.info(
            "Fetch cycle complete: %d/%d feeds fetched, %d new articles, %d errors, %d skipped, %d disabled",
            summary["feeds_fetched"], summary["feeds"], summary["articles_new"],
            summary["errors"], summary["skipped"], summary["disabled"],
        )
        return summary

    finally:
        db.close()


# ── Scheduled continuous mode ──


def run_scheduled(interval_minutes: int = 10) -> None:
    """Run crawler in continuous scheduled mode.

    Fetches all feeds every `interval_minutes`.
    Runs ISBNews auth fetch alongside RSS feeds.
    Sends Discord notifications on errors and daily summaries.

    Args:
        interval_minutes: Minutes between fetch cycles (default: 10)
    """
    import signal
    import sys

    from apscheduler.schedulers.blocking import BlockingScheduler

    from .discord_notifier import send_discord

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    init_db()
    logger.info("Feed Crawler starting (scheduled mode, interval=%dmin)", interval_minutes)

    scheduler = BlockingScheduler()

    def _cycle_job():
        """Single fetch cycle job for APScheduler."""
        from .crawl_state import is_crawl_enabled

        if not is_crawl_enabled():
            logger.info("Crawl disabled via admin panel — skipping cycle")
            return

        try:
            result = asyncio.run(run_fetch_cycle())

            # Discord notification on errors
            if result["errors"] > 0:
                send_discord(
                    title="⚠️ Feed Crawler — errors",
                    description=(
                        f"**Cycle complete**: {result['feeds']} feeds\n"
                        f"**New articles**: {result['articles_new']}\n"
                        f"**Errors**: {result['errors']}"
                    ),
                    level="warning",
                )

            # Success summary (quiet mode — only if new articles)
            if result["articles_new"] > 0:
                logger.info(
                    "Cycle: %d new articles from %d feeds (%d errors)",
                    result["articles_new"], result["feeds"], result["errors"],
                )

        except Exception as e:
            logger.exception("Fetch cycle failed: %s", e)
            send_discord(
                title="🔴 Feed Crawler — cycle FAILED",
                description=f"```{e!s}```",
                level="error",
            )

    def _isbnews_job():
        """ISBNews auth fetch job (separate, aggressive interval)."""
        try:
            from .auth_fetcher import fetch_authenticated_source

            articles = asyncio.run(fetch_authenticated_source("isbnews"))
            if articles:
                # Store ISBNews articles in DB
                db = SessionLocal()
                try:
                    feed = db.query(Feed).filter(Feed.name == "ISBNews").first()
                    if feed:
                        new_count = 0
                        for art in articles:
                            article_hash = compute_hash(art["url"], art["title"])
                            existing = get_existing_by_hash(db, article_hash)
                            if not existing:
                                from .models import Article as ArticleModel

                                new_art = ArticleModel(
                                    feed_id=feed.id,
                                    title=art["title"],
                                    url=art["url"],
                                    content=art.get("content", ""),
                                    published_at=datetime.utcnow(),
                                    hash=article_hash,
                                )
                                db.add(new_art)
                                new_count += 1
                        db.commit()
                        if new_count > 0:
                            logger.info("ISBNews: %d new dispatches stored", new_count)
                finally:
                    db.close()

        except Exception as e:
            logger.exception("ISBNews fetch failed: %s", e)

    # Graceful shutdown
    def _shutdown(signum, frame):
        logger.info("Shutting down (signal %d)...", signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Schedule jobs
    scheduler.add_job(_cycle_job, "interval", minutes=interval_minutes, id="rss_cycle")
    scheduler.add_job(_isbnews_job, "interval", minutes=5, id="isbnews_cycle")

    # Run first cycle immediately
    _cycle_job()
    send_discord(
        title="🟢 Feed Crawler started",
        description=f"Scheduled mode: RSS every {interval_minutes}min, ISBNews every 5min",
        level="info",
    )

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Crawler stopped")


# ── CLI Entry point ──


def main() -> None:
    """CLI entry point.

    Usage:
        python -m src.scheduler           # single fetch cycle
        python -m src.scheduler --daemon   # continuous scheduled mode
        python -m src.scheduler --daemon --interval 5  # custom interval
    """
    import argparse

    parser = argparse.ArgumentParser(description="Feed Crawler")
    parser.add_argument("--daemon", action="store_true", help="Run in continuous scheduled mode")
    parser.add_argument("--interval", type=int, default=10, help="Minutes between cycles (default: 10)")
    args = parser.parse_args()

    if args.daemon:
        run_scheduled(interval_minutes=args.interval)
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        init_db()
        logger.info("Feed Crawler (single cycle mode)")
        result = asyncio.run(run_fetch_cycle())
        logger.info("Result: %s", result)


if __name__ == "__main__":
    main()

