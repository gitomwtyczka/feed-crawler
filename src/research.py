"""
Ask Crawl — AI-powered research module.

Prompt-based research with full-text search + source tier gradation.
Uses PostgreSQL tsvector for search and Google Gemini for AI summaries.

Usage:
    results = await research("alzheimer ostatni rok", db)
    # Returns articles grouped by tier with optional AI summary
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from dotenv import load_dotenv
from sqlalchemy import desc, func

from .models import SOURCE_TIERS, Article, Feed

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")


@dataclass
class ResearchResult:
    """Result from a research query."""

    query: str
    total_results: int
    tier_groups: dict[int, list[dict]] = field(default_factory=dict)
    ai_summary: str = ""
    search_time_ms: float = 0


def search_articles(
    db: Session,
    query: str,
    *,
    max_results: int = 100,
    tier_filter: int = 0,
    days_back: int = 365,
) -> ResearchResult:
    """Search articles using PostgreSQL full-text search, grouped by source tier.

    Args:
        db: Database session
        query: Search query (natural language)
        max_results: Maximum number of results
        tier_filter: Filter to specific tier (0 = all)
        days_back: Search window in days

    Returns:
        ResearchResult with articles grouped by source tier
    """
    import time

    start = time.time()

    # Build PostgreSQL full-text search query
    # Convert natural language query to tsquery format
    search_terms = query.strip().split()
    ts_query = " & ".join(search_terms)

    # Search with ranking
    since = datetime.utcnow().replace(hour=0, minute=0, second=0)
    from datetime import timedelta

    since = since - timedelta(days=days_back)

    q = (
        db.query(
            Article,
            Feed.source_tier,
            Feed.name.label("feed_name"),
            func.ts_rank(
                func.to_tsvector("simple", func.coalesce(Article.title, "") + " " + func.coalesce(Article.summary, "")),
                func.to_tsquery("simple", ts_query),
            ).label("rank"),
        )
        .join(Feed, Article.feed_id == Feed.id)
        .filter(
            func.to_tsvector("simple", func.coalesce(Article.title, "") + " " + func.coalesce(Article.summary, ""))
            .op("@@")(func.to_tsquery("simple", ts_query)),
        )
        .filter(Article.fetched_at >= since)
    )

    if tier_filter:
        q = q.filter(Feed.source_tier == tier_filter)

    q = q.order_by(desc("rank")).limit(max_results)

    rows = q.all()

    # Group by tier
    tier_groups: dict[int, list[dict]] = {}
    for article, source_tier, feed_name, rank in rows:
        if source_tier not in tier_groups:
            tier_groups[source_tier] = []
        tier_groups[source_tier].append({
            "id": article.id,
            "title": article.title,
            "summary": (article.summary or "")[:200],
            "url": article.url,
            "published_at": article.published_at,
            "fetched_at": article.fetched_at,
            "feed_name": feed_name,
            "source_tier": source_tier,
            "rank": float(rank),
        })

    # Sort tier_groups by tier (1 first)
    sorted_groups = dict(sorted(tier_groups.items()))

    elapsed = (time.time() - start) * 1000

    return ResearchResult(
        query=query,
        total_results=len(rows),
        tier_groups=sorted_groups,
        search_time_ms=round(elapsed, 1),
    )


def generate_ai_summary(result: ResearchResult) -> str:
    """Generate AI summary of research results using Google Gemini.

    Returns summary string or empty string if Gemini is not configured.
    """
    if not GEMINI_API_KEY:
        return ""

    try:
        import google.generativeai as genai

        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")

        # Build context from top results per tier
        context_parts = []
        for tier_id, articles in result.tier_groups.items():
            tier_info = SOURCE_TIERS.get(tier_id, SOURCE_TIERS[4])
            tier_label = f"{tier_info['emoji']} {tier_info['label']}"
            top_articles = articles[:5]
            titles = "\n".join(f"  - {a['title']} ({a['feed_name']})" for a in top_articles)
            context_parts.append(f"{tier_label}:\n{titles}")

        context = "\n\n".join(context_parts)

        prompt = f"""Jesteś analitykiem mediowym. Użytkownik szukał: "{result.query}"

Znalezione artykuły ({result.total_results} wyników) pogrupowane po wiarygodności źródła:

{context}

Napisz krótkie podsumowanie (3-5 zdań) po polsku:
- Co jest głównym tematem?
- Jakie są kluczowe wnioski ze źródeł naukowych/branżowych?
- Jak portale informacyjne przetwarzają tę informację?
Odpowiedz zwięźle, profesjonalnie."""

        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception:
        logger.exception("Gemini AI summary failed")
        return ""
