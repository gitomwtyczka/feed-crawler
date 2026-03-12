"""
Reprint detection — classifies articles as original, reprint, or modified reprint.

Simple approach: difflib SequenceMatcher on titles (fast, no dependencies).
Integrated into AI enrichment job.

[crawler-oracle 01]
"""

from difflib import SequenceMatcher
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .models import Article

REPRINT_THRESHOLD = 0.90  # Very similar = przedruk
MODIFIED_THRESHOLD = 0.70  # Similar = przedruk ze zmianami
LOOKBACK_HOURS = 72  # Compare against last 3 days


def _sim(a: str | None, b: str | None) -> float:
    """Fuzzy string similarity (0.0 - 1.0)."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def classify_article(article: Article, db: Session) -> dict:
    """Classify as original/reprint/modified_reprint.

    Compares title (fast) against recent articles from OTHER feeds.
    Returns: {"type": str, "original_id": int|None, "score": float}
    """
    cutoff = datetime.utcnow() - timedelta(hours=LOOKBACK_HOURS)

    # Get recent articles from OTHER feeds only
    recent = (
        db.query(Article.id, Article.title)
        .filter(
            Article.id != article.id,
            Article.feed_id != article.feed_id,  # Different source = reprint candidate
            Article.fetched_at >= cutoff,
        )
        .order_by(Article.fetched_at.asc())
        .limit(300)
        .all()
    )

    best_score = 0.0
    best_match_id = None

    for other_id, other_title in recent:
        score = _sim(article.title, other_title)

        if score > best_score:
            best_score = score
            best_match_id = other_id

        # Early exit on exact match
        if score >= REPRINT_THRESHOLD:
            break

    if best_score >= REPRINT_THRESHOLD:
        return {"type": "reprint", "original_id": best_match_id, "score": round(best_score, 3)}
    elif best_score >= MODIFIED_THRESHOLD:
        return {"type": "modified_reprint", "original_id": best_match_id, "score": round(best_score, 3)}
    else:
        return {"type": "original", "original_id": None, "score": round(best_score, 3)}
