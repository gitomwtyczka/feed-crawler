"""
Webhook client for delivering articles to SaaS.

Sends new articles to the main SaaS application via REST API.
Supports retry with exponential backoff and local buffering.

On start: operates in OFFLINE mode (no webhook, just local DB storage).
Enable by setting SAAS_WEBHOOK_URL and SAAS_WEBHOOK_API_KEY in .env.
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime
from typing import TYPE_CHECKING

import httpx
from dotenv import load_dotenv

from .models import Article

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

load_dotenv()

logger = logging.getLogger(__name__)

# ── Config ──
WEBHOOK_URL = os.getenv("SAAS_WEBHOOK_URL", "")
WEBHOOK_API_KEY = os.getenv("SAAS_WEBHOOK_API_KEY", "")
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds


def is_webhook_enabled() -> bool:
    """Check if webhook delivery is configured."""
    return bool(WEBHOOK_URL and WEBHOOK_API_KEY)


async def send_article(article_data: dict) -> bool:
    """Send a single article to SaaS via webhook.

    Args:
        article_data: Dict with article fields matching SaaS ingest schema.

    Returns:
        True if delivered successfully, False otherwise.
    """
    if not is_webhook_enabled():
        logger.debug("Webhook disabled — article stored locally only")
        return False

    headers = {
        "Authorization": f"Bearer {WEBHOOK_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "FeedCrawler/1.0",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    WEBHOOK_URL,
                    json=article_data,
                    headers=headers,
                    timeout=30,
                )
                if response.status_code in (200, 201):
                    logger.info("Article delivered to SaaS: %s", article_data.get("title", "")[:60])
                    return True

                logger.warning(
                    "Webhook attempt %d/%d failed: HTTP %d",
                    attempt, MAX_RETRIES, response.status_code,
                )

        except Exception as e:
            logger.warning(
                "Webhook attempt %d/%d error: %s",
                attempt, MAX_RETRIES, e,
            )

        if attempt < MAX_RETRIES:
            backoff = RETRY_BACKOFF_BASE ** attempt
            logger.info("Retrying in %ds...", backoff)
            await asyncio.sleep(backoff)

    logger.error("Failed to deliver article after %d attempts: %s", MAX_RETRIES, article_data.get("title", ""))
    return False


def mark_as_sent(db: Session, article: Article) -> None:
    """Mark article as sent to SaaS in local DB."""
    article.sent_to_saas = True
    article.sent_at = datetime.utcnow()
    db.commit()


def get_unsent_articles(db: Session, limit: int = 100) -> list[Article]:
    """Get articles that haven't been sent to SaaS yet.

    Args:
        db: SQLAlchemy session.
        limit: Max articles to return.

    Returns:
        List of unsent Article objects.
    """
    return (
        db.query(Article)
        .filter(Article.sent_to_saas == False)  # noqa: E712
        .order_by(Article.fetched_at.asc())
        .limit(limit)
        .all()
    )


def article_to_webhook_payload(article: Article) -> dict:
    """Convert Article model to webhook payload dict."""
    return {
        "source": "feed-crawler",
        "feed_name": article.feed.name if article.feed else "",
        "title": article.title,
        "url": article.url,
        "summary": article.summary or "",
        "content": article.content or "",
        "author": article.author or "",
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "fetched_at": article.fetched_at.isoformat() if article.fetched_at else None,
        "departments": [dept.slug for dept in article.departments],
    }
