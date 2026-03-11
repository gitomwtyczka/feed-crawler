"""
Feed Scout — automatic RSS/Atom feed discovery.

Discovers RSS/Atom feeds from websites by:
1. Checking common RSS URL patterns (/feed, /rss, /atom.xml, etc.)
2. Parsing HTML <link> tags with type="application/rss+xml"
3. Scanning sitemaps for feed endpoints
4. Google search for "site:domain.com RSS feed"

Usage:
    from src.feed_scout import discover_feeds
    feeds = await discover_feeds("https://example.com")
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)

# Common RSS/Atom URL patterns to try
COMMON_FEED_PATHS = [
    "/feed",
    "/feed/",
    "/rss",
    "/rss.xml",
    "/atom.xml",
    "/feed.xml",
    "/feeds/posts/default",  # Blogger
    "/index.xml",            # Hugo
    "/blog/feed",
    "/news/feed",
    "/feed/atom",
    "/feed/rss",
    "/?feed=rss2",           # WordPress
    "/wp-json/wp/v2/posts",  # WordPress REST API
    "/sitemap.xml",
]

# Content-Type patterns that indicate RSS/Atom
FEED_CONTENT_TYPES = [
    "application/rss+xml",
    "application/atom+xml",
    "application/xml",
    "text/xml",
    "application/rdf+xml",
]


@dataclass
class DiscoveredFeed:
    """A discovered RSS/Atom feed."""
    url: str
    title: str = ""
    feed_type: str = ""          # rss, atom, json
    source_domain: str = ""
    discovery_method: str = ""   # link_tag, common_path, sitemap
    article_count: int = 0
    sample_titles: list[str] = field(default_factory=list)
    sample_links: list[str] = field(default_factory=list)
    is_valid: bool = False
    error: str = ""


async def _check_url_is_feed(client: httpx.AsyncClient, url: str) -> DiscoveredFeed | None:
    """Check if a URL is a valid RSS/Atom feed."""
    try:
        resp = await client.get(url, timeout=12, follow_redirects=True)
        if resp.status_code not in (200, 301, 302):
            return None

        content_type = resp.headers.get("content-type", "").lower()
        text = resp.text[:5000]  # Only check first 5KB

        # Check content type or content patterns
        is_feed = any(ct in content_type for ct in FEED_CONTENT_TYPES)
        is_feed = is_feed or "<rss" in text or "<feed" in text or "<channel>" in text
        is_feed = is_feed or '"version"' in text and '"items"' in text  # JSON Feed

        if not is_feed:
            return None

        # Parse basic info
        import feedparser
        parsed = feedparser.parse(resp.text[:50000])  # limit parse size

        if not parsed.get("feed"):
            return None

        title = parsed.feed.get("title", "Unknown Feed")
        feed_type = "atom" if "<feed" in text else "rss"
        entries = parsed.get("entries", [])

        return DiscoveredFeed(
            url=str(resp.url),  # use final URL after redirects
            title=title,
            feed_type=feed_type,
            source_domain=urlparse(url).netloc,
            article_count=len(entries),
            sample_titles=[e.get("title", "")[:80] for e in entries[:5]],
            sample_links=[e.get("link", "") for e in entries[:5]],
            is_valid=True,
        )
    except Exception:
        return None


async def _discover_from_html(client: httpx.AsyncClient, base_url: str) -> list[DiscoveredFeed]:
    """Discover feeds from HTML <link> tags."""
    feeds = []
    try:
        resp = await client.get(base_url, timeout=10, follow_redirects=True)
        if resp.status_code != 200:
            return feeds

        # Find <link rel="alternate" type="application/rss+xml" href="...">
        pattern = r'<link[^>]+type=["\']application/(rss|atom)\+xml["\'][^>]*>'
        for match in re.finditer(pattern, resp.text, re.IGNORECASE):
            tag = match.group(0)
            href_match = re.search(r'href=["\']([^"\']+)["\']', tag)
            title_match = re.search(r'title=["\']([^"\']+)["\']', tag)

            if href_match:
                feed_url = urljoin(base_url, href_match.group(1))
                feed = await _check_url_is_feed(client, feed_url)
                if feed:
                    feed.discovery_method = "link_tag"
                    feed.title = title_match.group(1) if title_match else feed.title
                    feeds.append(feed)

    except Exception as e:
        logger.debug("HTML discovery failed for %s: %s", base_url, e)

    return feeds


async def _discover_from_common_paths(client: httpx.AsyncClient, base_url: str) -> list[DiscoveredFeed]:
    """Try common RSS/Atom URL patterns."""
    feeds = []
    parsed = urlparse(base_url)
    base = f"{parsed.scheme}://{parsed.netloc}"

    async def _try_path(path: str) -> DiscoveredFeed | None:
        url = urljoin(base, path)
        feed = await _check_url_is_feed(client, url)
        if feed:
            feed.discovery_method = "common_path"
        return feed

    # Check paths concurrently (with semaphore to be nice)
    sem = asyncio.Semaphore(3)

    async def _limited(path: str) -> DiscoveredFeed | None:
        async with sem:
            await asyncio.sleep(0.3)  # Be nice
            return await _try_path(path)

    results = await asyncio.gather(*[_limited(p) for p in COMMON_FEED_PATHS])
    feeds.extend([f for f in results if f])

    return feeds


async def discover_feeds(url: str) -> list[DiscoveredFeed]:
    """Discover all RSS/Atom feeds from a given URL.

    Tries multiple discovery methods:
    1. HTML <link> tags
    2. Common RSS URL patterns

    Returns deduplicated list of discovered feeds.
    """
    logger.info("Discovering feeds from: %s", url)

    async with httpx.AsyncClient(
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        follow_redirects=True,
    ) as client:
        # Run discovery methods
        html_feeds = await _discover_from_html(client, url)
        path_feeds = await _discover_from_common_paths(client, url)

        # Deduplicate by URL
        seen = set()
        all_feeds = []
        for feed in html_feeds + path_feeds:
            if feed.url not in seen:
                seen.add(feed.url)
                all_feeds.append(feed)

    logger.info("Discovered %d feeds from %s", len(all_feeds), url)
    return all_feeds


async def discover_feeds_batch(urls: list[str]) -> dict[str, list[DiscoveredFeed]]:
    """Discover feeds from multiple URLs.

    Returns dict mapping input URL to list of discovered feeds.
    """
    results = {}
    for url in urls:
        try:
            feeds = await discover_feeds(url)
            results[url] = feeds
        except Exception as e:
            logger.error("Discovery failed for %s: %s", url, e)
            results[url] = []
        await asyncio.sleep(1)  # Rate limit between domains

    return results


# ── Known news domains to scout ──

POLISH_NEWS_DOMAINS = [
    "https://www.bankier.pl",
    "https://www.money.pl",
    "https://www.pap.pl",
    "https://www.tvn24.pl",
    "https://www.polsatnews.pl",
    "https://www.rp.pl",
    "https://www.gazetaprawna.pl",
    "https://www.wprost.pl",
    "https://www.newsweek.pl",
    "https://www.onet.pl",
    "https://www.wp.pl",
    "https://www.interia.pl",
    "https://www.se.pl",
    "https://www.fakt.pl",
    "https://www.natemat.pl",
    "https://www.tokfm.pl",
    "https://biznes.interia.pl",
    "https://next.gazeta.pl",
    "https://forsal.pl",
    "https://www.obserwatorfinansowy.pl",
    "https://stooq.pl",
    "https://www.investing.com",
    "https://www.parkiet.com",
]

INTERNATIONAL_NEWS_DOMAINS = [
    "https://www.reuters.com",
    "https://apnews.com",
    "https://www.aljazeera.com",
    "https://www.bbc.com",
    "https://www.theguardian.com",
    "https://www.nytimes.com",
    "https://www.washingtonpost.com",
    "https://www.ft.com",
    "https://www.economist.com",
    "https://www.politico.eu",
    "https://www.euronews.com",
    "https://www.dw.com",
    "https://www.france24.com",
    "https://techcrunch.com",
    "https://arstechnica.com",
    "https://www.wired.com",
    "https://www.theverge.com",
    "https://www.axios.com",
    "https://www.vox.com",
    "https://www.foreignaffairs.com",
]

TECH_DOMAINS = [
    "https://news.ycombinator.com",
    "https://www.infoworld.com",
    "https://devblogs.microsoft.com",
    "https://engineering.fb.com",
    "https://blog.google",
    "https://aws.amazon.com/blogs",
    "https://openai.com/blog",
    "https://deepmind.google/blog",
    "https://research.google",
    "https://www.technologyreview.com",
]

ALL_SCOUT_DOMAINS = POLISH_NEWS_DOMAINS + INTERNATIONAL_NEWS_DOMAINS + TECH_DOMAINS
