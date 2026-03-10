"""Tests for RSS/Atom feed parsing."""

from src.feed_parser import RawArticle, parse_feed_xml


def test_parse_rss_returns_articles(sample_rss):
    """Standard RSS feed should produce correct articles."""
    articles = parse_feed_xml(sample_rss, feed_name="Test", feed_url="https://example.com/rss")
    assert len(articles) == 3
    assert all(isinstance(a, RawArticle) for a in articles)


def test_parse_rss_article_fields(sample_rss):
    """Parsed article should have correct title, URL, author."""
    articles = parse_feed_xml(sample_rss, feed_name="Test")
    planet = articles[0]
    assert planet.title == "Discovery of New Planet"
    assert planet.url == "https://example.com/articles/new-planet"
    assert planet.summary == "Scientists have discovered a new exoplanet."
    assert planet.author == "Dr. Smith"
    assert planet.published_at is not None
    assert planet.feed_name == "Test"


def test_parse_rss_date_extraction(sample_rss):
    """Publication dates should be parsed correctly."""
    articles = parse_feed_xml(sample_rss)
    # First article: Mon, 10 Mar 2026 12:00:00 GMT
    assert articles[0].published_at.year == 2026
    assert articles[0].published_at.month == 3
    assert articles[0].published_at.day == 10


def test_parse_atom_feed(sample_atom):
    """Atom feed should be parsed correctly."""
    articles = parse_feed_xml(sample_atom, feed_name="Atom Test")
    assert len(articles) == 1
    assert articles[0].title == "Atom Entry One"
    assert articles[0].url == "https://atom-example.com/entry-1"


def test_parse_empty_feed(empty_rss):
    """Empty feed should return empty list, no error."""
    articles = parse_feed_xml(empty_rss)
    assert articles == []


def test_parse_malformed_xml(malformed_xml):
    """Malformed XML should return empty list, not crash."""
    articles = parse_feed_xml(malformed_xml)
    assert isinstance(articles, list)


def test_parse_preserves_feed_metadata(sample_rss):
    """feed_name and feed_url should be preserved on each article."""
    articles = parse_feed_xml(sample_rss, feed_name="MyFeed", feed_url="https://myfeed.com/rss")
    for article in articles:
        assert article.feed_name == "MyFeed"
        assert article.feed_url == "https://myfeed.com/rss"


def test_parse_skips_entries_without_title():
    """Entries without title should be skipped."""
    xml = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item><link>https://example.com/no-title</link></item>
      <item><title>Has Title</title><link>https://example.com/ok</link></item>
    </channel></rss>"""
    articles = parse_feed_xml(xml)
    assert len(articles) == 1
    assert articles[0].title == "Has Title"
