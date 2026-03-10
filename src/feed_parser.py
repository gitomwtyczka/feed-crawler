"""
Async RSS/Atom feed parser.

Fetches feeds concurrently with httpx + feedparser.
Supports batch fetching with semaphore-limited concurrency.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime

import feedparser
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Configuration ──
FETCH_TIMEOUT = int(os.getenv("FETCH_TIMEOUT_SECONDS", "30"))
FETCH_CONCURRENCY = int(os.getenv("FETCH_CONCURRENCY", "20"))
USER_AGENT = os.getenv("USER_AGENT", "FeedCrawler/1.0")


# ── Data classes ──


@dataclass
class RawArticle:
    """Parsed article from a feed, before dedup/storage."""

    title: str
    url: str
    summary: str = ""
    content: str = ""
    author: str = ""
    published_at: datetime | None = None
    feed_name: str = ""
    feed_url: str = ""
    departments: list[str] = field(default_factory=list)


@dataclass
class FetchResult:
    """Result of fetching a single feed."""

    feed_url: str
    feed_name: str
    articles: list[RawArticle]
    status: str = "success"  # success | error | timeout
    error_message: str = ""
    fetch_duration_ms: int = 0


# ── Parsing ──


def _parse_date(entry: dict) -> datetime | None:
    """Extract publication date from feedparser entry."""
    for date_field in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = entry.get(date_field)
        if parsed:
            try:
                return datetime(*parsed[:6])
            except (TypeError, ValueError):
                continue
    return None


def _extract_content(entry: dict) -> str:
    """Extract best available content from feedparser entry."""
    # Try content field first (usually full HTML)
    if "content" in entry and entry["content"]:
        return entry["content"][0].get("value", "")
    # Fall back to summary
    return entry.get("summary", "")


def parse_feed_xml(xml_content: str, feed_name: str = "", feed_url: str = "") -> list[RawArticle]:
    """Parse RSS/Atom XML content into list of RawArticle.

    Args:
        xml_content: Raw XML string from the feed.
        feed_name: Name of the feed source (for tagging).
        feed_url: URL of the feed (for tagging).

    Returns:
        List of parsed RawArticle objects.
    """
    parsed = feedparser.parse(xml_content)
    articles = []

    for entry in parsed.entries:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()

        if not title or not link:
            logger.warning("Skipping entry without title or link in feed %s", feed_name)
            continue

        article = RawArticle(
            title=title,
            url=link,
            summary=entry.get("summary", "").strip(),
            content=_extract_content(entry),
            author=entry.get("author", "").strip(),
            published_at=_parse_date(entry),
            feed_name=feed_name,
            feed_url=feed_url,
        )
        articles.append(article)

    return articles


# ── Async fetching ──


async def fetch_single_feed(
    client: httpx.AsyncClient,
    url: str,
    feed_name: str = "",
    timeout: int = FETCH_TIMEOUT,
) -> FetchResult:
    """Fetch and parse a single RSS/Atom feed.

    Args:
        client: httpx async client for connection pooling.
        url: RSS/Atom feed URL.
        feed_name: Human-readable name for logging.
        timeout: Request timeout in seconds.

    Returns:
        FetchResult with parsed articles or error info.
    """
    start = time.monotonic()

    try:
        response = await client.get(url, timeout=timeout)

        if response.status_code != 200:
            elapsed = int((time.monotonic() - start) * 1000)
            logger.warning("Feed %s returned HTTP %d", feed_name, response.status_code)
            return FetchResult(
                feed_url=url,
                feed_name=feed_name,
                articles=[],
                status="error",
                error_message=f"HTTP {response.status_code}",
                fetch_duration_ms=elapsed,
            )

        xml_content = response.text
        articles = parse_feed_xml(xml_content, feed_name=feed_name, feed_url=url)
        elapsed = int((time.monotonic() - start) * 1000)

        logger.info("Feed %s: %d articles in %dms", feed_name, len(articles), elapsed)
        return FetchResult(
            feed_url=url,
            feed_name=feed_name,
            articles=articles,
            status="success",
            fetch_duration_ms=elapsed,
        )

    except httpx.TimeoutException:
        elapsed = int((time.monotonic() - start) * 1000)
        logger.warning("Feed %s timed out after %ds", feed_name, timeout)
        return FetchResult(
            feed_url=url,
            feed_name=feed_name,
            articles=[],
            status="timeout",
            error_message=f"Timeout after {timeout}s",
            fetch_duration_ms=elapsed,
        )
    except Exception as e:
        elapsed = int((time.monotonic() - start) * 1000)
        logger.exception("Feed %s fetch error: %s", feed_name, e)
        return FetchResult(
            feed_url=url,
            feed_name=feed_name,
            articles=[],
            status="error",
            error_message=str(e),
            fetch_duration_ms=elapsed,
        )


async def fetch_batch(
    feeds: list[dict],
    concurrency: int = FETCH_CONCURRENCY,
) -> list[FetchResult]:
    """Fetch multiple feeds concurrently with semaphore-limited concurrency.

    Args:
        feeds: List of dicts with keys: 'rss_url', 'name'.
        concurrency: Max concurrent HTTP requests.

    Returns:
        List of FetchResult for each feed.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def _limited_fetch(client: httpx.AsyncClient, feed: dict) -> FetchResult:
        async with semaphore:
            return await fetch_single_feed(
                client=client,
                url=feed["rss_url"],
                feed_name=feed.get("name", feed["rss_url"]),
            )

    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=10)
    async with httpx.AsyncClient(
        limits=limits,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:
        tasks = [_limited_fetch(client, feed) for feed in feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert exceptions to error FetchResults
    final_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.exception("Unexpected error fetching feed %s: %s", feeds[i].get("name"), result)
            final_results.append(FetchResult(
                feed_url=feeds[i]["rss_url"],
                feed_name=feeds[i].get("name", ""),
                articles=[],
                status="error",
                error_message=str(result),
            ))
        else:
            final_results.append(result)

    return final_results
