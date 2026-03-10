"""
Discord Webhook Notifier for Feed Crawler.

Pattern matches SaaS backend (crimson-void/backend/discord_notifier.py):
- Fire-and-forget via background thread
- Rich embeds with emoji categories
- Graceful degradation if webhook not configured

Categories:
  🔄 Fetch cycle summary
  ⚠️ Feed error / timeout
  🔴 System error
  📊 Daily digest
"""

import logging
import os
import threading
from datetime import datetime

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_CRAWLER_WEBHOOK_URL", "")
APP_NAME = "FeedCrawler"


def _send(content: str = None, embeds: list = None):
    """Fire-and-forget POST to Discord webhook. Runs in background thread."""
    url = DISCORD_WEBHOOK_URL
    if not url:
        logger.debug("DISCORD_CRAWLER_WEBHOOK_URL not set — skipping notification")
        return

    def _post():
        try:
            payload = {}
            if content:
                payload["content"] = content
            if embeds:
                payload["embeds"] = embeds
            res = requests.post(
                url,
                json=payload,
                headers={"User-Agent": f"{APP_NAME}/1.0"},
                timeout=5,
            )
            if res.status_code not in (200, 204):
                logger.warning("Discord webhook returned %d: %s", res.status_code, res.text[:200])
        except Exception as e:
            logger.warning("Discord webhook error: %s", e)

    threading.Thread(target=_post, daemon=True).start()


# ─── Notification functions ───


def notify_fetch_cycle_complete(
    feeds_total: int,
    feeds_ok: int,
    feeds_error: int,
    articles_new: int,
    duration_seconds: float = 0,
):
    """Summary after a fetch cycle completes."""
    color = 0x00D166 if feeds_error == 0 else 0xFEE75C  # green or yellow
    _send(embeds=[{
        "title": "🔄 Fetch cycle zakończony",
        "color": color,
        "fields": [
            {"name": "Feeds (OK/Error)", "value": f"✅ {feeds_ok} / ❌ {feeds_error}", "inline": True},
            {"name": "Nowe artykuły", "value": str(articles_new), "inline": True},
            {"name": "Czas trwania", "value": f"{duration_seconds:.1f}s", "inline": True},
        ],
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": APP_NAME},
    }])


def notify_feed_error(feed_name: str, feed_url: str, error: str, error_type: str = "error"):
    """Single feed fetch failed (error or timeout)."""
    emoji = "⏱️" if error_type == "timeout" else "⚠️"
    _send(embeds=[{
        "title": f"{emoji} Błąd feedu: {feed_name}",
        "color": 0xFEE75C,  # yellow
        "fields": [
            {"name": "Feed", "value": f"`{feed_name}`", "inline": True},
            {"name": "Typ", "value": error_type.upper(), "inline": True},
            {"name": "URL", "value": feed_url[:200], "inline": False},
            {"name": "Error", "value": f"```{error[:400]}```"},
        ],
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": APP_NAME},
    }])


def notify_feed_recovered(feed_name: str, articles_found: int):
    """Feed that was previously failing is now working again."""
    _send(embeds=[{
        "title": f"✅ Feed odzyskany: {feed_name}",
        "color": 0x00D166,
        "fields": [
            {"name": "Feed", "value": f"`{feed_name}`", "inline": True},
            {"name": "Artykuły", "value": str(articles_found), "inline": True},
        ],
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": APP_NAME},
    }])


def notify_system_error(component: str, error: str):
    """Critical system error (DB, scheduler, etc.)."""
    _send(embeds=[{
        "title": "🔴 BŁĄD SYSTEMOWY — Feed Crawler",
        "color": 0xED4245,
        "fields": [
            {"name": "Komponent", "value": f"`{component}`", "inline": True},
            {"name": "Error", "value": f"```{error[:500]}```"},
        ],
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": APP_NAME},
    }])


def notify_webhook_delivery_failed(article_title: str, saas_url: str, error: str):
    """Failed to deliver article to SaaS via webhook."""
    _send(embeds=[{
        "title": "📤❌ Webhook delivery failed",
        "color": 0xED4245,
        "fields": [
            {"name": "Artykuł", "value": article_title[:100], "inline": False},
            {"name": "SaaS URL", "value": saas_url[:200], "inline": False},
            {"name": "Error", "value": f"```{error[:300]}```"},
        ],
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": APP_NAME},
    }])


def notify_daily_digest(
    cycles_today: int,
    articles_total: int,
    feeds_active: int,
    feeds_failing: list[str] = None,
    departments_summary: dict = None,
):
    """Daily summary report."""
    failing_text = ", ".join(f"`{f}`" for f in (feeds_failing or [])[:10]) or "Brak ✅"
    dept_text = "—"
    if departments_summary:
        dept_text = "\n".join(f"• **{k}**: {v}" for k, v in departments_summary.items())

    _send(embeds=[{
        "title": "📊 Dzienny raport — Feed Crawler",
        "color": 0x5865F2,
        "fields": [
            {"name": "🔄 Cykli dziś", "value": str(cycles_today), "inline": True},
            {"name": "📰 Nowe artykuły", "value": str(articles_total), "inline": True},
            {"name": "📡 Aktywne feedy", "value": str(feeds_active), "inline": True},
            {"name": "❌ Feedy z błędami", "value": failing_text, "inline": False},
            {"name": "📂 Artykuły wg działów", "value": dept_text[:1000], "inline": False},
        ],
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": f"{APP_NAME} · Raport dzienny"},
    }])


def notify_new_department_sources(department: str, sources_count: int):
    """New sources added to a department."""
    _send(embeds=[{
        "title": f"📂 Nowe źródła w dziale: {department}",
        "color": 0x57F287,
        "fields": [
            {"name": "Dział", "value": department, "inline": True},
            {"name": "Liczba źródeł", "value": str(sources_count), "inline": True},
        ],
        "timestamp": datetime.utcnow().isoformat(),
        "footer": {"text": APP_NAME},
    }])
