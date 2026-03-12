"""
AI Router Client — integrates Feed Crawler with the multi-tier AI Router.

Router: http://95.179.201.157:8000 (Vultr VPS, [VPS-LLM 01])
Tier 1 (Bielik 1.5B, local, $0): classify, extract keywords, sentiment
Tier 2 (Gemini Flash, API, $0): summarize, translate, Q&A

Usage:
    from src.ai_router import classify_article, summarize_article, extract_keywords
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ── Configuration ──

AI_ROUTER_URL = os.environ.get("AI_ROUTER_URL", "http://95.179.201.157:8000")
AI_ROUTER_TIMEOUT = 60  # Bielik on Vultr 2vCPU needs more time


async def _post(endpoint: str, payload: dict) -> dict | None:
    """Send POST to AI Router. Returns response dict or None on failure."""
    try:
        async with httpx.AsyncClient(timeout=AI_ROUTER_TIMEOUT) as client:
            resp = await client.post(f"{AI_ROUTER_URL}{endpoint}", json=payload)
            if resp.status_code == 200:
                return resp.json()
            logger.warning("AI Router %s returned %d: %s",
                          endpoint, resp.status_code, resp.text[:200])
            return None
    except httpx.ConnectError:
        logger.warning("AI Router niedostępny: %s", AI_ROUTER_URL)
        return None
    except Exception as e:
        logger.exception("AI Router error on %s: %s", endpoint, e)
        return None


def _post_sync(endpoint: str, payload: dict) -> dict | None:
    """Synchronous version for use in non-async contexts (scheduler jobs)."""
    try:
        with httpx.Client(timeout=AI_ROUTER_TIMEOUT) as client:
            resp = client.post(f"{AI_ROUTER_URL}{endpoint}", json=payload)
            if resp.status_code == 200:
                return resp.json()
            logger.warning("AI Router %s returned %d: %s",
                          endpoint, resp.status_code, resp.text[:200])
            return None
    except httpx.ConnectError:
        logger.warning("AI Router niedostępny: %s", AI_ROUTER_URL)
        return None
    except Exception as e:
        logger.exception("AI Router error on %s: %s", endpoint, e)
        return None


# ── Article Classification (Bielik, $0) ──


def classify_article(title: str, summary: str = "") -> dict | None:
    """Classify article into category using Bielik (local, $0).
    
    Returns: {"category": "polityka", "confidence": 0.85, "model_used": "bielik", ...}
    """
    text = f"{title}. {summary[:300]}" if summary else title
    result = _post_sync("/classify", {
        "prompt": text,
        "max_tokens": 50,
    })
    if result:
        logger.debug("Classified '%s...' → %s (by %s, %dms)",
                     title[:40], result.get("response", "?"),
                     result.get("model_used", "?"), result.get("time_ms", 0))
    return result


# ── Keyword Extraction (Bielik, $0) ──


def extract_keywords(title: str, content: str = "") -> list[str]:
    """Extract keywords/tags from article using Bielik (local, $0).
    
    Returns: list of keyword strings
    """
    text = f"{title}. {content[:500]}" if content else title
    result = _post_sync("/extract", {
        "prompt": text,
        "max_tokens": 100,
    })
    if result and result.get("response"):
        # Parse response — could be comma-separated or JSON
        raw = result["response"]
        keywords = [kw.strip() for kw in raw.replace("\n", ",").split(",") if kw.strip()]
        return keywords[:10]  # max 10 keywords
    return []


# ── Sentiment Analysis (Bielik, $0) ──


def analyze_sentiment(title: str, content: str = "") -> dict | None:
    """Analyze sentiment of article using Bielik (local, $0).
    
    Returns: {"sentiment": "positive|negative|neutral", "score": 0.8, ...}
    """
    text = f"{title}. {content[:300]}" if content else title
    result = _post_sync("/sentiment", {
        "prompt": text,
        "max_tokens": 50,
    })
    return result


# ── Article Summarization (Gemini Flash, $0) ──


def summarize_article(title: str, content: str) -> str | None:
    """Summarize article content using Gemini Flash (API, $0).
    
    Returns: summary string or None
    """
    if not content or len(content) < 100:
        return None

    result = _post_sync("/summarize", {
        "prompt": f"Podsumuj ten artykuł w 2-3 zdaniach po polsku:\n\nTytuł: {title}\n\nTreść: {content[:3000]}",
        "max_tokens": 300,
    })
    if result and result.get("response"):
        return result["response"].strip()
    return None


# ── Feed Relevance Scoring (Bielik, $0) ──


def score_feed_relevance(feed_name: str, recent_titles: list[str]) -> dict | None:
    """Score how relevant a feed is based on recent article titles.
    
    Returns: {"score": 7, "category": "polityka", "recommendation": "keep"}
    """
    titles_text = "\n".join(f"- {t}" for t in recent_titles[:10])
    result = _post_sync("/ask", {
        "prompt": (
            f"Oceń feed '{feed_name}' na skali 1-10 pod kątem jakości "
            f"i przydatności dla monitoringu mediów w Polsce. "
            f"Ostatnie artykuły:\n{titles_text}\n\n"
            f"Odpowiedz krótko: ocena (1-10), kategoria, rekomendacja (keep/drop)."
        ),
        "max_tokens": 100,
    })
    return result


# ── Batch Processing ──


def process_article_ai(title: str, summary: str = "",
                       content: str = "") -> dict:
    """Full AI processing of a single article: classify + keywords + sentiment.
    
    All via Bielik ($0). Returns combined result dict.
    """
    result = {
        "category": None,
        "keywords": [],
        "sentiment": None,
        "summary_ai": None,
    }

    # 1. Classify (Bielik, ~50ms)
    classify_resp = classify_article(title, summary)
    if classify_resp:
        result["category"] = classify_resp.get("response")
        result["_classify_model"] = classify_resp.get("model_used")
        result["_classify_ms"] = classify_resp.get("time_ms")

    # 2. Extract keywords (Bielik, ~50ms)
    result["keywords"] = extract_keywords(title, content or summary)

    # 3. Sentiment (Bielik, ~50ms)
    sentiment_resp = analyze_sentiment(title, summary)
    if sentiment_resp:
        result["sentiment"] = sentiment_resp.get("response")

    # 4. Summarize if we have content (Gemini, ~2s)
    if content and len(content) > 200:
        result["summary_ai"] = summarize_article(title, content)

    return result


# ── Health Check ──


def check_router_health() -> dict | None:
    """Check AI Router health status."""
    try:
        with httpx.Client(timeout=5) as client:
            resp = client.get(f"{AI_ROUTER_URL}/health")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass
    return None


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    # Quick test
    health = check_router_health()
    if health:
        print(f"✅ AI Router online: {health}")
    else:
        print("❌ AI Router offline")
        sys.exit(1)

    # Test classify
    print("\n📰 Test: classify")
    r = classify_article("Sejm uchwalił ustawę o budżecie na 2027 rok")
    print(f"  → {r}")

    # Test extract
    print("\n🔑 Test: extract keywords")
    kws = extract_keywords("Premier spotkał się z Macronem w Paryżu w sprawie obronności UE")
    print(f"  → {kws}")

    # Test sentiment
    print("\n😊 Test: sentiment")
    s = analyze_sentiment("GPW odnotowała rekordowe spadki, inwestorzy w panice")
    print(f"  → {s}")

    # Test summarize
    print("\n📝 Test: summarize")
    summary = summarize_article(
        "Nowa ustawa o AI w Polsce",
        "Sejm uchwalił ustawę regulującą wykorzystanie sztucznej inteligencji w administracji publicznej. " * 10,
    )
    print(f"  → {summary}")
