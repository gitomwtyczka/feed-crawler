"""
Google News PL Feed Discovery — extracts Polish media sources from Google News RSS,
discovers their RSS feeds, and adds them to the database.

Google News aggregates hundreds of Polish portals — we use it as a source discovery engine.

Run: python discover_google_news_pl.py

[crawler-oracle 01] — aggressive PL infosphere expansion
"""

import sys
sys.path.insert(0, ".")

import re
import logging
from urllib.parse import urlparse

import httpx
import feedparser
from src.database import SessionLocal
from src.models import Feed

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Google News PL RSS feeds by category ──

GOOGLE_NEWS_PL_FEEDS = [
    # Main Polish news
    "https://news.google.com/rss?hl=pl&gl=PL&ceid=PL:pl",
    # Search queries for Polish topics (returns PL sources)
    "https://news.google.com/rss/search?q=polska&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=polityka+polska&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=gospodarka+polska&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=technologia&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=sport+polska&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=kultura+polska&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=biznes+polska&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=zdrowie+polska&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=nauka+polska&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=edukacja+polska&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=prawo+polska&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=nieruchomości+polska&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=motoryzacja+polska&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=energetyka+polska&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=samorząd+gmina&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=Warszawa&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=Kraków&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=Wrocław&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=Gdańsk&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=Poznań&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=Łódź&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=Katowice&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=Lublin&hl=pl&gl=PL&ceid=PL:pl",
    "https://news.google.com/rss/search?q=Szczecin&hl=pl&gl=PL&ceid=PL:pl",
]

# Common RSS feed paths to probe
RSS_PATHS = [
    "/feed", "/feed/", "/rss", "/rss/", "/rss.xml",
    "/atom.xml", "/feed.xml", "/index.xml",
    "/?feed=rss2", "/feeds/posts/default",
    "/blog/feed", "/news/feed", "/news/rss",
]

# Domains to skip (aggregators, social, non-news)
SKIP_DOMAINS = {
    "news.google.com", "google.com", "youtube.com", "facebook.com",
    "twitter.com", "x.com", "instagram.com", "tiktok.com",
    "wikipedia.org", "linkedin.com", "reddit.com",
}


def extract_domains_from_google_news() -> dict[str, str]:
    """Pull Google News PL RSS and extract unique source domains."""
    domains = {}  # domain -> source_name

    headers = {
        "User-Agent": "FeedCrawler/1.0 (Polish Media Monitor)",
        "Accept": "application/rss+xml, application/xml, text/xml",
    }

    for gn_url in GOOGLE_NEWS_PL_FEEDS:
        try:
            resp = httpx.get(gn_url, timeout=15, follow_redirects=True, headers=headers)
            if resp.status_code != 200:
                logger.warning("Google News returned %d for %s", resp.status_code, gn_url)
                continue

            parsed = feedparser.parse(resp.text)
            for entry in parsed.entries:
                # Google News entries have source info
                source_name = None
                source_url = None

                # Try to get source from entry
                if hasattr(entry, "source") and hasattr(entry.source, "title"):
                    source_name = entry.source.title
                    if hasattr(entry.source, "href"):
                        source_url = entry.source.href

                # Fallback: extract domain from link
                if entry.get("link"):
                    link = entry["link"]
                    # Google News wraps URLs — try to get real URL
                    if "news.google.com" in link:
                        # Extract from redirect URL if possible
                        pass
                    else:
                        parsed_url = urlparse(link)
                        domain = parsed_url.netloc.lower()
                        if domain.startswith("www."):
                            domain = domain[4:]

                        if domain and domain not in SKIP_DOMAINS:
                            if domain not in domains:
                                name = source_name or domain.split(".")[0].title()
                                domains[domain] = name

            logger.info("  Scanned: %s → %d entries", gn_url.split("?q=")[-1][:30] if "?q=" in gn_url else "main", len(parsed.entries))

        except Exception as e:
            logger.warning("Failed to fetch %s: %s", gn_url, e)

    return domains


def find_rss_feed(domain: str) -> str | None:
    """Probe common RSS paths for a domain. Returns RSS URL or None."""
    base_urls = [f"https://{domain}", f"https://www.{domain}"]
    headers = {"User-Agent": "FeedCrawler/1.0"}

    for base in base_urls:
        for path in RSS_PATHS:
            rss_url = f"{base}{path}"
            try:
                resp = httpx.get(rss_url, timeout=8, follow_redirects=True, headers=headers)
                if resp.status_code == 200:
                    # Verify it's actually RSS/XML
                    ct = resp.headers.get("content-type", "")
                    text = resp.text[:500]
                    if ("xml" in ct or "rss" in ct or "atom" in ct or
                        "<rss" in text or "<feed" in text or "<channel" in text):
                        # Parse to verify
                        parsed = feedparser.parse(resp.text)
                        if len(parsed.entries) > 0:
                            return rss_url
            except Exception:
                continue

    return None


def discover_and_add():
    """Main discovery pipeline: Google News → domains → RSS → database."""
    db = SessionLocal()
    try:
        # Get existing feeds
        existing_domains = set()
        for feed in db.query(Feed).all():
            if feed.rss_url:
                parsed = urlparse(feed.rss_url)
                d = parsed.netloc.lower()
                if d.startswith("www."):
                    d = d[4:]
                existing_domains.add(d)
            if feed.url:
                parsed = urlparse(feed.url)
                d = parsed.netloc.lower()
                if d.startswith("www."):
                    d = d[4:]
                existing_domains.add(d)

        logger.info("Existing domains in DB: %d", len(existing_domains))

        # Step 1: Extract domains from Google News
        logger.info("\n=== Step 1: Extracting domains from Google News PL ===")
        domains = extract_domains_from_google_news()
        logger.info("Found %d unique domains from Google News", len(domains))

        # Step 2: Filter out already-known domains
        new_domains = {d: n for d, n in domains.items() if d not in existing_domains}
        logger.info("New domains (not in DB): %d", len(new_domains))

        # Step 3: Probe for RSS feeds
        logger.info("\n=== Step 2: Probing for RSS feeds ===")
        added = 0
        probed = 0
        for domain, source_name in sorted(new_domains.items()):
            probed += 1
            logger.info("  [%d/%d] Probing %s (%s)...", probed, len(new_domains), domain, source_name)
            rss_url = find_rss_feed(domain)
            if rss_url:
                # Determine tier based on domain
                tier = 4  # default
                if domain.endswith(".pl") or domain.endswith(".com.pl"):
                    tier = 3  # Polish domain = higher tier

                feed = Feed(
                    name=source_name,
                    url=f"https://{domain}",
                    rss_url=rss_url,
                    feed_type="rss",
                    source_tier=tier,
                    language="pl",
                    fetch_interval=30,
                    is_active=True,
                )
                db.add(feed)
                added += 1
                logger.info("  ✅ Added: %s → %s", source_name, rss_url)
            else:
                logger.debug("  ❌ No RSS: %s", domain)

        db.commit()

        logger.info("\n=== Results ===")
        logger.info("Google News domains found: %d", len(domains))
        logger.info("Already in DB: %d", len(domains) - len(new_domains))
        logger.info("New domains probed: %d", len(new_domains))
        logger.info("Successfully added: %d", added)

        return {
            "google_news_domains": len(domains),
            "already_known": len(domains) - len(new_domains),
            "new_probed": len(new_domains),
            "added": added,
        }

    finally:
        db.close()


if __name__ == "__main__":
    print("\n🔎 Google News PL — Feed Discovery")
    print("=" * 50)
    print(f"Scanning {len(GOOGLE_NEWS_PL_FEEDS)} Google News categories...\n")
    results = discover_and_add()
    print(f"\n📊 Final: {results}")
