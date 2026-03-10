"""
Deduplication engine for articles.

Uses SHA256 hash of normalized URL + title to detect duplicates.
Articles fetched once are tagged with all relevant departments.
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING
from urllib.parse import urlparse, urlunparse

from .models import Article

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def normalize_url(url: str) -> str:
    """Normalize URL for consistent hashing.

    - Strips trailing slashes
    - Removes fragments (#...)
    - Lowercases scheme and host
    - Sorts query parameters
    """
    parsed = urlparse(url.strip())
    # Lowercase scheme and host
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    # Remove trailing slash from path
    path = parsed.path.rstrip("/")
    # Sort query params for consistency
    query = parsed.query
    if query:
        params = sorted(query.split("&"))
        query = "&".join(params)
    # Drop fragment
    return urlunparse((scheme, netloc, path, parsed.params, query, ""))


def normalize_title(title: str) -> str:
    """Normalize title for consistent hashing.

    - Strips whitespace
    - Lowercases
    - Removes extra spaces
    """
    return " ".join(title.lower().strip().split())


def compute_hash(url: str, title: str) -> str:
    """Compute SHA256 dedup hash from normalized URL + title.

    Args:
        url: Article URL.
        title: Article title.

    Returns:
        64-char hex SHA256 hash string.
    """
    norm_url = normalize_url(url)
    norm_title = normalize_title(title)
    combined = f"{norm_url}|{norm_title}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def is_duplicate(db: Session, url: str, title: str) -> bool:
    """Check if an article with the same hash already exists in DB.

    Args:
        db: SQLAlchemy session.
        url: Article URL.
        title: Article title.

    Returns:
        True if duplicate exists.
    """
    article_hash = compute_hash(url, title)
    existing = db.query(Article).filter(Article.hash == article_hash).first()
    return existing is not None


def get_existing_by_hash(db: Session, article_hash: str) -> Article | None:
    """Get existing article by its dedup hash.

    Args:
        db: SQLAlchemy session.
        article_hash: SHA256 hash string.

    Returns:
        Article if found, None otherwise.
    """
    return db.query(Article).filter(Article.hash == article_hash).first()


def deduplicate_batch(
    db: Session,
    articles: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Split a batch of articles into new and duplicate.

    Args:
        db: SQLAlchemy session.
        articles: List of dicts with at least 'url' and 'title' keys.

    Returns:
        Tuple of (new_articles, duplicate_articles).
    """
    new = []
    duplicates = []

    for article in articles:
        article_hash = compute_hash(article["url"], article["title"])
        article["hash"] = article_hash

        if get_existing_by_hash(db, article_hash) is not None:
            duplicates.append(article)
        else:
            new.append(article)

    if duplicates:
        logger.info("Dedup: %d new, %d duplicates skipped", len(new), len(duplicates))

    return new, duplicates
