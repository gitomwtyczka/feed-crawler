"""
Feed Evaluator — quality scoring for discovered feeds.

Evaluates feeds based on:
- Activity: how frequently new articles appear
- Content quality: article length, has title, has summary
- Uniqueness: how different from existing feeds in our DB
- Reliability: HTTP status, response time, valid RSS

Score range: 0-100 (higher = better candidate for adding)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import feedparser
import httpx

logger = logging.getLogger(__name__)


@dataclass
class FeedScore:
    """Quality evaluation of a feed."""
    url: str
    title: str = ""
    overall_score: int = 0

    # Sub-scores (0-25 each, total 100)
    activity_score: int = 0      # How active is the feed
    quality_score: int = 0       # Content quality
    reliability_score: int = 0   # Technical reliability
    uniqueness_score: int = 0    # Novelty vs existing feeds

    # Metrics
    articles_count: int = 0
    avg_article_length: int = 0
    articles_per_day: float = 0.0
    response_time_ms: int = 0
    has_summaries: bool = False
    last_publish_date: str = ""
    language: str = ""
    recommendation: str = ""     # add, maybe, skip

    sample_titles: list[str] | None = None
    sample_links: list[str] | None = None


async def evaluate_feed(url: str, existing_urls: set[str] | None = None) -> FeedScore:
    """Evaluate a single feed's quality.

    Args:
        url: RSS/Atom feed URL
        existing_urls: Set of URLs already in our database (for uniqueness check)

    Returns:
        FeedScore with detailed quality metrics
    """
    score = FeedScore(url=url)
    existing_urls = existing_urls or set()

    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": "Mozilla/5.0 (compatible; FeedCrawler/1.0; +https://impresjapr.pl)"},
            follow_redirects=True,
        ) as client:
            # ── Reliability check ──
            import time
            t0 = time.monotonic()
            resp = await client.get(url, timeout=15)
            score.response_time_ms = int((time.monotonic() - t0) * 1000)

            if resp.status_code == 429:
                # Rate limited — not our fault, give partial score
                score.reliability_score = 12
                score.recommendation = "maybe"
                score.title = "(Rate limited — spróbuj później)"
                score.overall_score = 12
                return score

            if resp.status_code == 403:
                # Forbidden — server blocks us
                score.reliability_score = 5
                score.recommendation = "maybe"
                score.title = "(Serwer blokuje — możliwy WAF/bot protection)"
                score.overall_score = 5
                return score

            if resp.status_code not in (200, 301, 302):
                score.reliability_score = 0
                score.recommendation = "skip"
                return score

            # Fast response = reliable
            if score.response_time_ms < 500:
                score.reliability_score = 25
            elif score.response_time_ms < 2000:
                score.reliability_score = 18
            elif score.response_time_ms < 5000:
                score.reliability_score = 10
            else:
                score.reliability_score = 5

            # ── Parse feed ──
            parsed = feedparser.parse(resp.text[:200000])
            feed_info = parsed.get("feed", {})
            entries = parsed.get("entries", [])

            score.title = feed_info.get("title", "Unknown")
            score.language = feed_info.get("language", "")
            score.articles_count = len(entries)

            if not entries:
                score.activity_score = 0
                score.quality_score = 0
                score.recommendation = "skip"
                score.overall_score = score.reliability_score
                return score

            # ── Activity score ──
            # Check publication dates
            dates = []
            for entry in entries:
                pub = entry.get("published_parsed") or entry.get("updated_parsed")
                if pub:
                    try:
                        dt = datetime(*pub[:6])
                        dates.append(dt)
                    except (ValueError, TypeError):
                        pass

            if dates:
                dates.sort(reverse=True)
                score.last_publish_date = dates[0].strftime("%Y-%m-%d")

                # Calculate articles per day
                if len(dates) >= 2:
                    span = (dates[0] - dates[-1]).total_seconds() / 86400
                    if span > 0:
                        score.articles_per_day = round(len(dates) / span, 1)

                # Activity scoring
                now = datetime.utcnow()
                freshness = (now - dates[0]).days

                if freshness <= 1:
                    score.activity_score = 25  # Published today/yesterday
                elif freshness <= 7:
                    score.activity_score = 20  # Last week
                elif freshness <= 30:
                    score.activity_score = 12  # Last month
                else:
                    score.activity_score = 3   # Stale
            else:
                score.activity_score = 10  # Can't determine, assume moderate

            # ── Quality score ──
            total_length = 0
            has_summary_count = 0
            for entry in entries[:20]:  # Sample first 20
                summary = entry.get("summary", "")
                content = ""
                if entry.get("content"):
                    content = entry["content"][0].get("value", "")

                text = summary or content
                total_length += len(text)
                if len(summary) > 50:
                    has_summary_count += 1

            avg_len = total_length // min(len(entries), 20) if entries else 0
            score.avg_article_length = avg_len
            score.has_summaries = has_summary_count > len(entries[:20]) / 2

            if avg_len > 500:
                score.quality_score = 25
            elif avg_len > 200:
                score.quality_score = 18
            elif avg_len > 50:
                score.quality_score = 12
            else:
                score.quality_score = 5

            # ── Uniqueness score ──
            final_url = str(resp.url)
            if final_url in existing_urls or url in existing_urls:
                score.uniqueness_score = 0  # Already have it
            else:
                # Check domain overlap
                from urllib.parse import urlparse
                domain = urlparse(url).netloc
                domain_count = sum(1 for u in existing_urls if domain in u)
                if domain_count == 0:
                    score.uniqueness_score = 25  # New domain
                elif domain_count <= 2:
                    score.uniqueness_score = 15  # Few feeds from domain
                else:
                    score.uniqueness_score = 8   # Many feeds from domain

            # ── Sample titles + links ──
            score.sample_titles = [e.get("title", "")[:80] for e in entries[:5]]
            score.sample_links = [e.get("link", "") for e in entries[:5]]

            # ── Overall ──
            score.overall_score = (
                score.activity_score
                + score.quality_score
                + score.reliability_score
                + score.uniqueness_score
            )

            # Recommendation
            if score.overall_score >= 70:
                score.recommendation = "add"
            elif score.overall_score >= 40:
                score.recommendation = "maybe"
            else:
                score.recommendation = "skip"

    except Exception as e:
        logger.error("Evaluation failed for %s: %s", url, e)
        score.recommendation = "error"

    return score


async def evaluate_batch(
    feed_urls: list[str],
    existing_urls: set[str] | None = None,
) -> list[FeedScore]:
    """Evaluate multiple feeds sequentially (rate-limited).

    Returns list of FeedScore sorted by overall score (desc).
    """
    import asyncio

    scores = []
    for url in feed_urls:
        s = await evaluate_feed(url, existing_urls)
        scores.append(s)
        await asyncio.sleep(0.5)  # Rate limit

    scores.sort(key=lambda s: s.overall_score, reverse=True)
    return scores
