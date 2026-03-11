"""
Google Trends integration — Early Warning System.

Fetches trending topics from Google Trends (Poland) and correlates
them with crawler's article database to detect emerging stories.

Usage:
    trends = fetch_trending_topics()
    correlated = correlate_with_articles(trends, db)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import desc, func

logger = logging.getLogger(__name__)


@dataclass
class TrendTopic:
    """A trending topic from Google Trends."""

    title: str
    traffic: str  # e.g. "200K+", "50K+"
    article_count: int = 0  # How many articles we have about this
    tier_breakdown: dict[int, int] = field(default_factory=dict)
    sample_articles: list[dict] = field(default_factory=list)
    coverage_status: str = ""  # "covered", "partial", "missing"


def _fetch_via_google_news_rss(limit: int = 20) -> list[TrendTopic]:
    """Fallback: scrape trending topics from Google News PL RSS."""
    import xml.etree.ElementTree as ET

    import httpx

    topics = []
    try:
        url = "https://news.google.com/rss?hl=pl&gl=PL&ceid=PL:pl"
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        if resp.status_code == 200:
            root = ET.fromstring(resp.text)  # noqa: S314
            seen = set()
            for item in root.iter("item"):
                title_el = item.find("title")
                if title_el is not None and title_el.text:
                    # Google News titles often have " - Source" suffix
                    raw = title_el.text.strip()
                    clean = raw.rsplit(" - ", 1)[0].strip()
                    # Extract key phrases (first 5 significant words)
                    words = [w for w in clean.split() if len(w) > 3][:5]
                    key = " ".join(words[:3]).lower()
                    if key and key not in seen:
                        seen.add(key)
                        topics.append(TrendTopic(
                            title=clean[:100],
                            traffic="google_news",
                        ))
                        if len(topics) >= limit:
                            break
        logger.info("Fetched %d topics from Google News RSS (fallback)", len(topics))
    except Exception:
        logger.exception("Google News RSS fallback also failed")
    return topics


def fetch_trending_topics(geo: str = "PL", limit: int = 20) -> list[TrendTopic]:
    """Fetch current trending topics from Google Trends.

    Falls back to Google News RSS if pytrends is rate-limited.
    """
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="pl-PL", tz=60, timeout=(10, 25))
        trending = pytrends.trending_searches(pn="poland")

        topics = []
        for _i, row in trending.head(limit).iterrows():
            topic_title = str(row[0]).strip()
            if topic_title:
                topics.append(TrendTopic(
                    title=topic_title,
                    traffic="trending",
                ))

        logger.info("Fetched %d trending topics from Google Trends (geo=%s)", len(topics), geo)
        return topics

    except Exception:
        logger.warning("pytrends failed (likely rate-limited), using Google News RSS fallback")
        return _fetch_via_google_news_rss(limit=limit)


def fetch_realtime_trends(geo: str = "PL", limit: int = 20) -> list[TrendTopic]:
    """Fetch realtime trending searches (hot topics right now).

    Falls back to regular trending_searches if realtime is unavailable.
    """
    try:
        from pytrends.request import TrendReq

        pytrends = TrendReq(hl="pl-PL", tz=60, timeout=(10, 25))

        try:
            # Try realtime trends first
            rt = pytrends.realtime_trending_searches(pn="PL")
            topics = []
            if rt is not None and not rt.empty:
                for _, row in rt.head(limit).iterrows():
                    title = str(row.get("title", row.iloc[0])).strip()
                    if title:
                        topics.append(TrendTopic(title=title, traffic="realtime"))
                if topics:
                    return topics
        except Exception:
            logger.debug("Realtime trends unavailable, falling back")

        # Fallback to daily trending
        return fetch_trending_topics(geo=geo, limit=limit)

    except Exception:
        logger.exception("Failed to fetch realtime trends")
        return []


def correlate_with_articles(
    topics: list[TrendTopic],
    db,
    hours_back: int = 72,
) -> list[TrendTopic]:
    """Correlate trending topics with articles in our database.

    For each topic, search for matching articles and calculate coverage.
    """
    from .models import Article, Feed

    since = datetime.utcnow() - timedelta(hours=hours_back)

    for topic in topics:
        # Search for articles matching this topic
        search_terms = topic.title.strip().split()
        if not search_terms:
            continue

        ts_query = " & ".join(search_terms)

        try:
            rows = (
                db.query(
                    Article.id,
                    Article.title,
                    Article.url,
                    Article.published_at,
                    Feed.source_tier,
                    Feed.name.label("feed_name"),
                )
                .join(Feed, Article.feed_id == Feed.id)
                .filter(
                    func.to_tsvector(
                        "simple",
                        func.coalesce(Article.title, "") + " " + func.coalesce(Article.summary, ""),
                    ).op("@@")(func.to_tsquery("simple", ts_query)),
                )
                .filter(Article.fetched_at >= since)
                .order_by(desc(Article.published_at))
                .limit(10)
                .all()
            )

            topic.article_count = len(rows)

            # Tier breakdown
            tier_counts: dict[int, int] = {}
            samples = []
            for art_id, art_title, art_url, pub_at, tier, feed_name in rows:
                tier_counts[tier] = tier_counts.get(tier, 0) + 1
                if len(samples) < 3:
                    samples.append({
                        "id": art_id,
                        "title": art_title,
                        "url": art_url,
                        "published_at": pub_at,
                        "feed_name": feed_name,
                        "source_tier": tier,
                    })

            topic.tier_breakdown = tier_counts
            topic.sample_articles = samples

            # Coverage status
            if topic.article_count == 0:
                topic.coverage_status = "missing"
            elif topic.article_count < 3:
                topic.coverage_status = "partial"
            else:
                topic.coverage_status = "covered"

        except Exception:
            logger.exception("Failed to correlate topic: %s", topic.title)
            topic.coverage_status = "error"

    return topics
