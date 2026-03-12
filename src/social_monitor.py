"""
Social Media Monitor — tracks mentions across social platforms.

Phase 1: YouTube comments via Data API v3 (free, 10K quota/day)
Phase 2: X/Twitter via unofficial API / scraping
Phase 3: Facebook pages via Graph API (requires App Review)

Usage:
    python -m src.social_monitor              # run monitoring cycle
    python -m src.social_monitor --youtube    # YouTube only
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta
from urllib.parse import quote_plus

import httpx

sys.path.insert(0, "/app")

from src.database import SessionLocal

logger = logging.getLogger(__name__)

# ── Configuration ──

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
YOUTUBE_SEARCH_LIMIT = 50  # results per keyword
TWITTER_BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN", "")

# Default Polish keywords to monitor on social media
SOCIAL_KEYWORDS_PL = [
    "monitoring mediów", "media monitoring",
    "agencja PR", "PR agency",
    "komunikacja korporacyjna", "corporate communications",
    "clipping", "press clipping",
    "analiza mediów", "media analysis",
    "IMM", "Brand24", "Newspoint",
]


class SocialMention:
    """Lightweight representation of a social media mention."""

    def __init__(self, platform: str, author: str, text: str, url: str,
                 published_at: datetime | None = None,
                 engagement: dict | None = None):
        self.platform = platform
        self.author = author
        self.text = text
        self.url = url
        self.published_at = published_at or datetime.utcnow()
        self.engagement = engagement or {}

    def to_dict(self):
        return {
            "platform": self.platform,
            "author": self.author,
            "text": self.text[:500],
            "url": self.url,
            "published_at": self.published_at.isoformat(),
            "engagement": self.engagement,
        }


# ── YouTube Data API v3 ──


def search_youtube(keyword: str, max_results: int = YOUTUBE_SEARCH_LIMIT,
                   published_after: datetime | None = None) -> list[SocialMention]:
    """Search YouTube for videos matching a keyword. Returns mentions."""
    if not YOUTUBE_API_KEY:
        logger.warning("YOUTUBE_API_KEY not set, skipping YouTube search")
        return []

    mentions = []
    params = {
        "part": "snippet",
        "q": keyword,
        "type": "video",
        "order": "date",
        "maxResults": min(max_results, 50),
        "key": YOUTUBE_API_KEY,
        "relevanceLanguage": "pl",
    }

    if published_after:
        params["publishedAfter"] = published_after.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        resp = httpx.get(
            "https://www.googleapis.com/youtube/v3/search",
            params=params,
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning("YouTube API error %d: %s", resp.status_code, resp.text[:200])
            return []

        data = resp.json()
        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            video_id = item.get("id", {}).get("videoId", "")
            mentions.append(SocialMention(
                platform="youtube",
                author=snippet.get("channelTitle", ""),
                text=f"{snippet.get('title', '')} — {snippet.get('description', '')[:200]}",
                url=f"https://www.youtube.com/watch?v={video_id}",
                published_at=datetime.fromisoformat(
                    snippet.get("publishedAt", "").replace("Z", "+00:00")
                ).replace(tzinfo=None) if snippet.get("publishedAt") else None,
            ))

    except Exception as e:
        logger.exception("YouTube search failed for '%s': %s", keyword, e)

    return mentions


def get_youtube_comments(video_id: str, max_results: int = 20) -> list[SocialMention]:
    """Get top comments for a YouTube video."""
    if not YOUTUBE_API_KEY:
        return []

    comments = []
    try:
        resp = httpx.get(
            "https://www.googleapis.com/youtube/v3/commentThreads",
            params={
                "part": "snippet",
                "videoId": video_id,
                "maxResults": max_results,
                "order": "relevance",
                "key": YOUTUBE_API_KEY,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return []

        data = resp.json()
        for item in data.get("items", []):
            snippet = item["snippet"]["topLevelComment"]["snippet"]
            comments.append(SocialMention(
                platform="youtube_comment",
                author=snippet.get("authorDisplayName", ""),
                text=snippet.get("textDisplay", "")[:500],
                url=f"https://www.youtube.com/watch?v={video_id}",
                published_at=datetime.fromisoformat(
                    snippet.get("publishedAt", "").replace("Z", "+00:00")
                ).replace(tzinfo=None) if snippet.get("publishedAt") else None,
                engagement={"likes": snippet.get("likeCount", 0)},
            ))

    except Exception as e:
        logger.exception("YouTube comments failed for %s: %s", video_id, e)

    return comments


# ── X/Twitter Search (API v2 Basic or scraping fallback) ──


def search_twitter(keyword: str, max_results: int = 20,
                   hours_back: int = 24) -> list[SocialMention]:
    """Search X/Twitter for recent tweets matching keyword."""
    mentions = []

    # Try official API first
    if TWITTER_BEARER_TOKEN:
        mentions = _twitter_api_search(keyword, max_results, hours_back)
    
    # Fallback: Nitter RSS scraping
    if not mentions:
        mentions = _twitter_nitter_fallback(keyword, max_results)

    return mentions


def _twitter_api_search(keyword: str, max_results: int,
                        hours_back: int) -> list[SocialMention]:
    """Search using X API v2 (requires Basic tier, $200/month)."""
    mentions = []
    try:
        since = datetime.utcnow() - timedelta(hours=hours_back)
        resp = httpx.get(
            "https://api.twitter.com/2/tweets/search/recent",
            params={
                "query": f"{keyword} lang:pl",
                "max_results": min(max_results, 100),
                "tweet.fields": "created_at,author_id,public_metrics",
                "start_time": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            headers={"Authorization": f"Bearer {TWITTER_BEARER_TOKEN}"},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning("X API error %d: %s", resp.status_code, resp.text[:200])
            return []

        data = resp.json()
        for tweet in data.get("data", []):
            metrics = tweet.get("public_metrics", {})
            mentions.append(SocialMention(
                platform="twitter",
                author=tweet.get("author_id", ""),
                text=tweet.get("text", ""),
                url=f"https://x.com/i/status/{tweet['id']}",
                published_at=datetime.fromisoformat(
                    tweet.get("created_at", "").replace("Z", "+00:00")
                ).replace(tzinfo=None) if tweet.get("created_at") else None,
                engagement={
                    "likes": metrics.get("like_count", 0),
                    "retweets": metrics.get("retweet_count", 0),
                    "replies": metrics.get("reply_count", 0),
                },
            ))

    except Exception as e:
        logger.exception("X API search failed for '%s': %s", keyword, e)

    return mentions


def _twitter_nitter_fallback(keyword: str, max_results: int) -> list[SocialMention]:
    """Fallback: search via Nitter RSS feeds (free, no API needed)."""
    mentions = []
    nitter_instances = [
        "nitter.privacydev.net",
        "nitter.poast.org",
    ]

    for instance in nitter_instances:
        try:
            url = f"https://{instance}/search/rss?f=tweets&q={quote_plus(keyword)}"
            resp = httpx.get(url, timeout=10, follow_redirects=True,
                           headers={"User-Agent": "Mozilla/5.0 FeedCrawler/1.0"})
            if resp.status_code != 200:
                continue

            # Parse RSS manually (simple XML)
            import re as re_mod
            items = re_mod.findall(r"<item>(.*?)</item>", resp.text, re_mod.DOTALL)
            for item in items[:max_results]:
                title = re_mod.search(r"<title>(.*?)</title>", item)
                link = re_mod.search(r"<link>(.*?)</link>", item)
                creator = re_mod.search(r"<dc:creator>(.*?)</dc:creator>", item)

                if title and link:
                    mentions.append(SocialMention(
                        platform="twitter",
                        author=creator.group(1) if creator else "",
                        text=title.group(1)[:500],
                        url=link.group(1).replace(instance, "x.com"),
                    ))

            if mentions:
                break  # got results from this instance

        except Exception:
            continue

    return mentions


# ── Main monitoring cycle ──


def run_social_monitoring(keywords: list[str] | None = None,
                         hours_back: int = 24) -> dict:
    """Run one social media monitoring cycle."""
    kws = keywords or SOCIAL_KEYWORDS_PL
    stats = {"youtube": 0, "twitter": 0, "total_mentions": 0}
    all_mentions = []

    since = datetime.utcnow() - timedelta(hours=hours_back)

    for keyword in kws:
        # YouTube
        yt_mentions = search_youtube(keyword, published_after=since)
        stats["youtube"] += len(yt_mentions)
        all_mentions.extend(yt_mentions)

        # Twitter/X
        tw_mentions = search_twitter(keyword, hours_back=hours_back)
        stats["twitter"] += len(tw_mentions)
        all_mentions.extend(tw_mentions)

    stats["total_mentions"] = len(all_mentions)
    logger.info("Social monitor: %d YouTube, %d Twitter mentions for %d keywords",
                stats["youtube"], stats["twitter"], len(kws))

    # Store high-value mentions (those with significant engagement)
    notable = [m for m in all_mentions
               if m.engagement.get("likes", 0) > 5
               or m.engagement.get("retweets", 0) > 2]

    if notable:
        try:
            from src.discord_notifier import send_discord
            top = notable[0]
            send_discord(
                title=f"📱 Social mention — {top.platform}",
                description=(
                    f"**Author**: {top.author}\n"
                    f"**Text**: {top.text[:200]}...\n"
                    f"**URL**: {top.url}\n"
                    f"**Engagement**: {top.engagement}"
                ),
                level="info",
            )
        except Exception:
            pass

    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("\n📱 Social Media Monitor — single cycle")
    print("=" * 50)

    if "--youtube" in sys.argv:
        print("YouTube only mode")
        results = search_youtube("monitoring mediów Polska")
        for m in results[:10]:
            print(f"  🎬 {m.author}: {m.text[:80]}...")
    else:
        stats = run_social_monitoring()
        print(f"\n📊 Results: {stats}")
