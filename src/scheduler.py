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
        try:
            db.flush()

            # Tag with departments
            for dept_id in dept_ids:
                db.add(ArticleDepartment(article_id=article.id, department_id=dept_id))
            db.commit()
            new_count += 1
        except Exception:
            db.rollback()
            logger.debug("Failed to store article: %s", raw.title[:60] if raw.title else "?")

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

    def _scout_job():
        """Source Scout — auto-discover new feeds from article domains."""
        try:
            from .source_scout import run_discovery

            stats = run_discovery(dry_run=False, hours_back=48)
            if stats["feeds_added"] > 0:
                send_discord(
                    title="🔍 Source Scout — nowe źródła",
                    description=(
                        f"**Domeny z artykułów**: {stats['domains_found']}\n"
                        f"**Nowe domeny**: {stats['domains_new']}\n"
                        f"**Odkryte feedy RSS**: {stats['feeds_discovered']}\n"
                        f"**Dodane do bazy**: {stats['feeds_added']}"
                    ),
                    level="info",
                )
                logger.info("Source Scout: +%d new feeds", stats["feeds_added"])
        except Exception as e:
            logger.exception("Source Scout failed: %s", e)

    def _broadcast_job():
        """TV/Radio broadcast monitor — capture + transcribe + keyword match."""
        try:
            from .tv_radio_monitor import run_monitoring_cycle, seed_stations

            # Seed stations on first run
            seed_stations()
            run_monitoring_cycle()
        except Exception as e:
            logger.exception("Broadcast monitor failed: %s", e)

    def _social_job():
        """Social media monitor — YouTube + X/Twitter keyword search."""
        try:
            from .social_monitor import run_social_monitoring

            stats = run_social_monitoring()
            if stats["total_mentions"] > 0:
                logger.info("Social: %d mentions (%d YT, %d TW)",
                           stats["total_mentions"], stats["youtube"], stats["twitter"])
        except Exception as e:
            logger.exception("Social monitor failed: %s", e)

    def _ai_enrich_job():
        """AI enrichment — classify + keywords + sentiment via Bielik.

        Bielik produces better structured output than Gemini for extraction tasks.
        Gemini truncates to 1 line, Bielik returns full 3-line analysis.
        ~23s per article on Vultr 2 vCPU.
        """
        try:
            from .ai_router import _post_sync, check_router_health

            # Check router is up
            health = check_router_health()
            if not health:
                logger.warning("AI Router offline, skipping enrichment")
                return

            db = SessionLocal()
            try:
                # Only process recent PL articles (last 24h)
                from datetime import timedelta
                cutoff = datetime.utcnow() - timedelta(hours=24)

                articles = (
                    db.query(Article)
                    .join(Feed, Article.feed_id == Feed.id)
                    .filter(
                        Article.ai_processed.is_(False),
                        Article.fetched_at >= cutoff,
                        Feed.language == "pl",  # Only Polish articles
                    )
                    .order_by(Article.fetched_at.desc())
                    .limit(3)  # Small batch — Bielik ~23s per article
                    .all()
                )

                if not articles:
                    return

                enriched = 0
                for article in articles:
                    try:
                        text = f"{article.title}. {(article.summary or '')[:300]}"

                        # No task hint — routes to Bielik which handles structured extraction better
                        result = _post_sync("/ask", {
                            "prompt": (
                                f"Przeanalizuj ten polski artykuł prasowy:\n\n"
                                f"\"{text}\"\n\n"
                                f"Odpowiedz DOKŁADNIE w tym formacie (każda linia osobno):\n"
                                f"KATEGORIA: [jedna z: polityka, gospodarka, sport, technologia, "
                                f"kultura, nauka, zdrowie, społeczeństwo, prawo, energetyka, inne]\n"
                                f"SŁOWA KLUCZOWE: [max 5 słów kluczowych po przecinku]\n"
                                f"SENTYMENT: [positive, negative, neutral]"
                            ),
                            "max_tokens": 200,
                        })

                        if result and result.get("response"):
                            resp = result["response"]
                            for line in resp.split("\n"):
                                line = line.strip().replace("**", "")  # Strip Bielik markdown bold
                                low = line.upper()
                                if "KATEGORIA" in low and ":" in line:
                                    val = line.split(":", 1)[1].strip().strip("*").lower()
                                    if val:
                                        article.ai_category = val[:100]
                                elif "KLUCZOWE" in low and ":" in line:
                                    val = line.split(":", 1)[1].strip().strip("*")
                                    if val:
                                        article.ai_keywords = val[:500]
                                elif "SENTYMENT" in low and ":" in line:
                                    val = line.split(":", 1)[1].strip().strip("*").lower()
                                    if val:
                                        article.ai_sentiment = val[:20]

                        article.ai_processed = True
                        enriched += 1

                        # Reprint detection (after AI enrichment)
                        try:
                            from .reprint_detector import classify_article as classify_reprint
                            rp = classify_reprint(article, db)
                            article.reprint_type = rp["type"]
                            article.original_article_id = rp["original_id"]
                            article.similarity_score = rp["score"]
                        except Exception as rp_err:
                            logger.debug("Reprint detection failed: %s", rp_err)
                            article.reprint_type = "original"

                        logger.info("🧠 AI: '%s...' → %s / %s [%s %.0f%%]",
                                  article.title[:35],
                                  article.ai_category,
                                  article.ai_sentiment,
                                  article.reprint_type,
                                  (article.similarity_score or 0) * 100)

                    except Exception as e:
                        logger.warning("AI enrich failed for article %d: %s", article.id, e)
                        article.ai_processed = True  # Avoid infinite retry

                db.commit()
                if enriched > 0:
                    logger.info("🧠 AI enriched %d/%d articles", enriched, len(articles))

            finally:
                db.close()

        except Exception as e:
            logger.exception("AI enrichment failed: %s", e)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    # Schedule interval jobs
    scheduler.add_job(_cycle_job, "interval", minutes=interval_minutes, id="rss_cycle")
    scheduler.add_job(_isbnews_job, "interval", minutes=5, id="isbnews_cycle")
    scheduler.add_job(_scout_job, "interval", hours=2, id="source_scout")
    scheduler.add_job(_broadcast_job, "interval", minutes=2, id="broadcast_monitor")
    scheduler.add_job(_social_job, "interval", minutes=30, id="social_monitor")
    scheduler.add_job(_ai_enrich_job, "interval", minutes=5, id="ai_enrichment")

    # One-shot initial triggers (non-blocking — scheduler handles them)
    from datetime import timedelta
    now = datetime.utcnow()
    scheduler.add_job(_cycle_job, "date", run_date=now + timedelta(seconds=5), id="initial_cycle")
    scheduler.add_job(_scout_job, "date", run_date=now + timedelta(seconds=15), id="initial_scout")
    scheduler.add_job(_ai_enrich_job, "date", run_date=now + timedelta(seconds=10), id="initial_ai")

    send_discord(
        title="🟢 Feed Crawler started",
        description=(
            f"RSS {interval_minutes}min, ISBNews 5min, Scout 2h, "
            f"Broadcast 2min, Social 30min, AI Enrich 5min"
        ),
        level="info",
    )

    # BlockingScheduler.start() runs event loop — processes jobs in background threads
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

