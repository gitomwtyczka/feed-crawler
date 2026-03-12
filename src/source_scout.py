"""
Source Scout — automatic feed discovery engine.

Runs periodically (every 6h) to discover and add new RSS sources by:
1. Link mining: extract unique domains from recently fetched articles,
   probe common RSS paths (/feed, /rss, /atom.xml, etc.)
2. HTML auto-discovery: check <link rel="alternate" type="application/rss+xml">
3. Google News source extraction: from GNews articles, find original source RSS

Language auto-classification based on TLD and known patterns.

Usage:
    python -m src.source_scout          # run discovery
    python -m src.source_scout --dry    # preview only
"""

from __future__ import annotations

import logging
import re
import sys
from urllib.parse import urlparse

import httpx

sys.path.insert(0, "/app")

from src.database import SessionLocal
from src.models import LANGUAGES, Feed
from src.source_tiers import classify_feed

logger = logging.getLogger(__name__)

# Common RSS paths to probe on discovered domains
RSS_PATHS = [
    "/feed",
    "/feed/",
    "/rss",
    "/rss/",
    "/rss.xml",
    "/atom.xml",
    "/feed.xml",
    "/index.xml",
    "/feeds/posts/default",  # Blogger
    "/blog/feed",
    "/news/feed",
    "/news/rss",
    "/?feed=rss2",  # WordPress
]

# TLD → language mapping
TLD_LANG = {
    ".pl": "pl", ".com.pl": "pl",
    ".co.uk": "en", ".com": "en", ".org": "en", ".io": "en", ".us": "en",
    ".de": "de", ".at": "de", ".ch": "de",
    ".fr": "fr", ".be": "fr",
    ".es": "es", ".mx": "es", ".ar": "es", ".co": "es",
    ".it": "it",
    ".pt": "pt", ".br": "pt", ".com.br": "pt",
}

# Skip these domains (too generic, social media, etc.)
SKIP_DOMAINS = {
    "google.com", "news.google.com", "youtube.com", "twitter.com", "x.com",
    "facebook.com", "instagram.com", "linkedin.com", "tiktok.com",
    "reddit.com", "t.co", "bit.ly", "ow.ly", "dlvr.it",
    "apple.com", "play.google.com", "apps.apple.com",
    "wikipedia.org", "wikimedia.org",
    "amazon.com", "ebay.com",
}

# Max domains to probe per cycle (respect servers)
MAX_PROBE_PER_CYCLE = 100


def _detect_language(domain: str) -> str | None:
    """Detect language from domain TLD."""
    for tld, lang in sorted(TLD_LANG.items(), key=lambda x: -len(x[0])):
        if domain.endswith(tld):
            return lang
    return "en"  # default


def _extract_domains_from_articles(db, hours_back: int = 24, limit: int = 500) -> set[str]:
    """Extract unique domains from recently fetched articles."""
    from datetime import datetime, timedelta

    from src.models import Article

    since = datetime.utcnow() - timedelta(hours=hours_back)
    articles = (
        db.query(Article.url)
        .filter(Article.fetched_at >= since)
        .filter(Article.url.isnot(None))
        .order_by(Article.fetched_at.desc())
        .limit(limit)
        .all()
    )

    domains = set()
    for (url,) in articles:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
            if domain and domain not in SKIP_DOMAINS:
                domains.add(domain)
        except Exception:
            pass

    return domains


def _get_existing_domains(db) -> set[str]:
    """Get domains of already-known feeds."""
    existing = set()
    for (url,) in db.query(Feed.rss_url).filter(Feed.rss_url.isnot(None)).all():
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            existing.add(domain)
        except Exception:
            pass
    for (url,) in db.query(Feed.url).filter(Feed.url.isnot(None)).all():
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            existing.add(domain)
        except Exception:
            pass
    return existing


def _try_rss_autodiscovery(base_url: str, timeout: float = 8.0) -> list[str]:
    """Try to find RSS feed URLs on a page via HTML <link> tags and common paths."""
    discovered = []

    try:
        resp = httpx.get(base_url, timeout=timeout, follow_redirects=True,
                        headers={"User-Agent": "Mozilla/5.0 FeedCrawler/1.0"})
        if resp.status_code != 200:
            return []

        content_type = resp.headers.get("content-type", "")

        # If the response is already RSS/XML, it's a feed!
        if "xml" in content_type or "rss" in content_type or "atom" in content_type:
            discovered.append(base_url)
            return discovered

        # Parse HTML for <link rel="alternate" type="application/rss+xml">
        html = resp.text[:50000]  # limit parsing
        link_pattern = re.compile(
            r'<link[^>]+type=["\']application/(rss\+xml|atom\+xml)["\'][^>]*href=["\']([^"\']+)["\']',
            re.IGNORECASE,
        )
        alt_pattern = re.compile(
            r'<link[^>]+href=["\']([^"\']+)["\'][^>]*type=["\']application/(rss\+xml|atom\+xml)["\']',
            re.IGNORECASE,
        )

        for match in link_pattern.finditer(html):
            href = match.group(2)
            if href.startswith("/"):
                href = base_url.rstrip("/") + href
            discovered.append(href)

        for match in alt_pattern.finditer(html):
            href = match.group(1)
            if href.startswith("/"):
                href = base_url.rstrip("/") + href
            discovered.append(href)

    except Exception:
        pass

    return list(set(discovered))


def _probe_common_rss_paths(domain: str, timeout: float = 5.0) -> str | None:
    """Try common RSS paths on a domain."""
    base = f"https://{domain}"

    for path in RSS_PATHS:
        url = base + path
        try:
            resp = httpx.head(url, timeout=timeout, follow_redirects=True,
                            headers={"User-Agent": "Mozilla/5.0 FeedCrawler/1.0"})
            ct = resp.headers.get("content-type", "")
            if resp.status_code == 200 and ("xml" in ct or "rss" in ct or "atom" in ct):
                return url
        except Exception:
            continue

    return None


def run_discovery(dry_run: bool = False, hours_back: int = 24) -> dict:
    """Run a source discovery cycle.

    1. Extract domains from recently fetched articles
    2. Filter out already-known domains
    3. Try RSS auto-discovery on new domains
    4. Add discovered feeds to database
    """
    db = SessionLocal()
    stats = {"domains_found": 0, "domains_new": 0, "feeds_discovered": 0, "feeds_added": 0}

    try:
        # 1. Get domains from articles
        article_domains = _extract_domains_from_articles(db, hours_back=hours_back)
        stats["domains_found"] = len(article_domains)

        # 2. Filter out known domains
        known_domains = _get_existing_domains(db)
        new_domains = article_domains - known_domains
        stats["domains_new"] = len(new_domains)

        logger.info(
            "Source Scout: %d domains from articles, %d new (not in feed DB)",
            stats["domains_found"], stats["domains_new"],
        )

        if not new_domains:
            logger.info("No new domains to probe")
            return stats

        # 3. Probe new domains for RSS feeds
        existing_urls = set()
        for (url,) in db.query(Feed.rss_url).filter(Feed.rss_url.isnot(None)).all():
            existing_urls.add(url.lower().rstrip("/"))

        probed = 0
        for domain in sorted(new_domains):
            if probed >= MAX_PROBE_PER_CYCLE:
                logger.info("Reached max probe limit (%d)", MAX_PROBE_PER_CYCLE)
                break

            probed += 1
            base_url = f"https://{domain}"

            # Try HTML auto-discovery first
            feeds = _try_rss_autodiscovery(base_url)

            # If no feeds found, try common paths
            if not feeds:
                rss_url = _probe_common_rss_paths(domain)
                if rss_url:
                    feeds = [rss_url]

            for feed_url in feeds:
                if feed_url.lower().rstrip("/") in existing_urls:
                    continue

                stats["feeds_discovered"] += 1
                lang = _detect_language(domain)
                tier = classify_feed(feed_url, domain)
                name = domain.replace("www.", "").split(".")[0].title()

                if not dry_run:
                    db.add(Feed(
                        name=f"[Scout] {name}",
                        rss_url=feed_url,
                        url=base_url,
                        feed_type="rss",
                        source_tier=tier,
                        language=lang,
                        is_active=True,
                        fetch_interval=15 if lang == "pl" else 45,
                    ))
                    stats["feeds_added"] += 1
                    existing_urls.add(feed_url.lower().rstrip("/"))

                    logger.info(
                        "  ✅ Discovered: %s → %s [%s] (tier %d)",
                        domain, feed_url[:80], lang, tier,
                    )

        if not dry_run and stats["feeds_added"] > 0:
            db.commit()
            logger.info("💾 Committed %d new feeds", stats["feeds_added"])

    except Exception:
        logger.exception("Source Scout failed")
        db.rollback()
    finally:
        db.close()

    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    dry_run = "--dry" in sys.argv
    hours = 48 if "--48h" in sys.argv else 24

    print(f"\n🔍 Source Scout — {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"   Scanning articles from last {hours}h for new domains...")
    print("=" * 50)

    stats = run_discovery(dry_run=dry_run, hours_back=hours)

    print(f"\n📊 Results:")
    print(f"  Domains from articles: {stats['domains_found']}")
    print(f"  New (not in feed DB): {stats['domains_new']}")
    print(f"  RSS feeds discovered: {stats['feeds_discovered']}")
    print(f"  Feeds added to DB:    {stats['feeds_added']}")
