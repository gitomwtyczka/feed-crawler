"""Tests for article deduplication."""

from src.dedup import (
    compute_hash,
    deduplicate_batch,
    is_duplicate,
    normalize_title,
    normalize_url,
)
from src.models import Article


def test_normalize_url_strips_trailing_slash():
    assert normalize_url("https://example.com/article/") == "https://example.com/article"


def test_normalize_url_strips_fragment():
    assert normalize_url("https://example.com/page#section") == "https://example.com/page"


def test_normalize_url_lowercases_host():
    assert normalize_url("https://EXAMPLE.COM/Path") == "https://example.com/Path"


def test_normalize_url_sorts_query_params():
    result = normalize_url("https://example.com/page?b=2&a=1")
    assert result == "https://example.com/page?a=1&b=2"


def test_normalize_title_strips_and_lowercases():
    assert normalize_title("  Hello   World  ") == "hello world"


def test_normalize_title_collapses_whitespace():
    assert normalize_title("Multiple   Spaces\tand\ttabs") == "multiple spaces and tabs"


def test_compute_hash_deterministic():
    h1 = compute_hash("https://example.com/article", "Test Article")
    h2 = compute_hash("https://example.com/article", "Test Article")
    assert h1 == h2
    assert len(h1) == 64  # SHA256 hex


def test_compute_hash_different_for_different_inputs():
    h1 = compute_hash("https://example.com/a", "Title A")
    h2 = compute_hash("https://example.com/b", "Title B")
    assert h1 != h2


def test_compute_hash_normalized():
    """Same article with different URL formatting should get same hash."""
    h1 = compute_hash("https://example.com/article/", "Test Article")
    h2 = compute_hash("https://example.com/article", "Test Article")
    assert h1 == h2


def test_is_duplicate_false_on_empty_db(db):
    """No articles in DB → not a duplicate."""
    assert is_duplicate(db, "https://example.com/new", "New Article") is False


def test_is_duplicate_true_after_insert(db):
    """After inserting an article, same URL+title should be duplicate."""
    url = "https://example.com/dup-test"
    title = "Duplicate Test Article"
    article_hash = compute_hash(url, title)

    article = Article(
        feed_id=1,
        title=title,
        url=url,
        hash=article_hash,
    )
    db.add(article)
    db.flush()

    assert is_duplicate(db, url, title) is True


def test_deduplicate_batch_separates_new_and_existing(db):
    """Batch dedup should correctly split new vs existing."""
    # Insert one article
    existing_url = "https://example.com/existing"
    existing_title = "Existing Article"
    existing_hash = compute_hash(existing_url, existing_title)
    db.add(Article(feed_id=1, title=existing_title, url=existing_url, hash=existing_hash))
    db.flush()

    # Batch with one existing + one new
    batch = [
        {"url": existing_url, "title": existing_title},
        {"url": "https://example.com/brand-new", "title": "Brand New Article"},
    ]

    new, duplicates = deduplicate_batch(db, batch)
    assert len(new) == 1
    assert len(duplicates) == 1
    assert new[0]["title"] == "Brand New Article"
    assert duplicates[0]["title"] == "Existing Article"
