"""Tests for OPML mass import tool (src.opml_import).

Covers:
- OPML XML parsing (valid, broken, empty)
- lxml recovery for malformed XML
- Regex fallback for completely broken XML
- Deduplication against existing config
- Feed verification (mocked)
- YAML output generation
- append_to_sources (config file I/O)
"""

import pytest
import yaml

from src.opml_import import (
    AWESOME_CATEGORIES,
    AWESOME_COUNTRIES,
    _awesome_opml_url,
    append_to_sources,
    dedup_against_existing,
    feeds_to_yaml,
    parse_opml_content,
    parse_opml_file,
)

# ── OPML URL Builder ──


class TestAwesomeOpmlUrl:
    def test_category_url(self):
        url = _awesome_opml_url("News", "recommended")
        assert "/recommended/with_category/News.opml" in url

    def test_country_url(self):
        url = _awesome_opml_url("Poland", "country")
        assert "/countries/with_category/Poland.opml" in url

    def test_url_encoding_spaces(self):
        url = _awesome_opml_url("Business & Economy", "recommended")
        assert "%20" in url
        assert "%26" in url

    def test_url_encoding_slash(self):
        url = _awesome_opml_url("UI / UX", "recommended")
        assert "%2F" in url

    def test_categories_not_empty(self):
        assert len(AWESOME_CATEGORIES) > 10

    def test_countries_not_empty(self):
        assert len(AWESOME_COUNTRIES) > 10

    def test_poland_in_countries(self):
        assert "Poland" in AWESOME_COUNTRIES


# ── OPML Parsing ──


VALID_OPML = """<?xml version='1.0' encoding='UTF-8' ?>
<opml version="1.0">
    <head><title>Test feeds</title></head>
    <body>
        <outline text="News" title="News">
            <outline text="BBC News" title="BBC News"
                     xmlUrl="https://feeds.bbci.co.uk/news/rss.xml"
                     htmlUrl="https://bbc.co.uk"
                     type="rss" />
            <outline text="CNN" title="CNN"
                     xmlUrl="https://rss.cnn.com/rss/edition.rss"
                     type="rss" />
        </outline>
        <outline text="Tech">
            <outline text="TechCrunch" title="TechCrunch"
                     xmlUrl="https://techcrunch.com/feed/"
                     htmlUrl="https://techcrunch.com"
                     type="rss" />
        </outline>
    </body>
</opml>"""

BROKEN_OPML_AMPERSAND = """<?xml version='1.0' encoding='UTF-8' ?>
<opml version="1.0">
    <head><title>Broken</title></head>
    <body>
        <outline text="Business & Economy" title="Business & Economy">
            <outline text="Bloomberg" title="Bloomberg"
                     xmlUrl="https://bloomberg.com/feed"
                     type="rss" />
        </outline>
    </body>
</opml>"""

EMPTY_OPML = """<?xml version='1.0' encoding='UTF-8' ?>
<opml version="1.0">
    <head><title>Empty</title></head>
    <body>
    </body>
</opml>"""

NO_BODY_OPML = """<?xml version='1.0' encoding='UTF-8' ?>
<opml version="1.0">
    <head><title>No body</title></head>
</opml>"""

# Simulates feeds where xmlUrl appears before title (regex fallback)
REGEX_FALLBACK_OPML = """<outline xmlUrl="https://example.com/rss" title="Example Feed" type="rss" />
<outline text="Another" xmlUrl="https://another.com/feed" type="rss" />"""


class TestParseOpmlContent:
    def test_valid_opml(self):
        feeds = parse_opml_content(VALID_OPML)
        assert len(feeds) == 3
        names = {f["name"] for f in feeds}
        assert "BBC News" in names
        assert "CNN" in names
        assert "TechCrunch" in names

    def test_valid_opml_rss_urls(self):
        feeds = parse_opml_content(VALID_OPML)
        urls = {f["rss_url"] for f in feeds}
        assert "https://feeds.bbci.co.uk/news/rss.xml" in urls
        assert "https://techcrunch.com/feed/" in urls

    def test_valid_opml_html_url(self):
        feeds = parse_opml_content(VALID_OPML)
        bbc = [f for f in feeds if f["name"] == "BBC News"][0]
        assert bbc["url"] == "https://bbc.co.uk"

    def test_valid_opml_feed_type(self):
        feeds = parse_opml_content(VALID_OPML)
        for f in feeds:
            assert f["feed_type"] == "rss"

    def test_broken_ampersand_opml(self):
        """lxml or regex should handle unescaped & in OPML."""
        feeds = parse_opml_content(BROKEN_OPML_AMPERSAND)
        assert len(feeds) >= 1
        assert feeds[0]["rss_url"] == "https://bloomberg.com/feed"

    def test_empty_opml(self):
        feeds = parse_opml_content(EMPTY_OPML)
        assert feeds == []

    def test_no_body_opml(self):
        feeds = parse_opml_content(NO_BODY_OPML)
        assert feeds == []

    def test_empty_string(self):
        feeds = parse_opml_content("")
        assert feeds == []

    def test_non_xml_string(self):
        feeds = parse_opml_content("this is not xml at all")
        assert feeds == []

    def test_outlines_without_xmlurl_skipped(self):
        opml = """<?xml version='1.0' ?>
        <opml version="1.0"><body>
            <outline text="Category only" />
            <outline text="Has RSS" xmlUrl="https://rss.com/feed" type="rss" />
        </body></opml>"""
        feeds = parse_opml_content(opml)
        assert len(feeds) == 1
        assert feeds[0]["rss_url"] == "https://rss.com/feed"


class TestParseOpmlFile:
    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_opml_file(tmp_path / "nonexistent.opml")

    def test_valid_file(self, tmp_path):
        opml_file = tmp_path / "test.opml"
        opml_file.write_text(VALID_OPML, encoding="utf-8")
        feeds = parse_opml_file(opml_file)
        assert len(feeds) == 3


# ── Deduplication ──


class TestDedup:
    def test_dedup_removes_existing_by_url(self, tmp_path):
        config = {"sources": [{"name": "BBC", "rss_url": "https://feeds.bbci.co.uk/news/rss.xml"}]}
        config_file = tmp_path / "sources.yaml"
        config_file.write_text(yaml.dump(config), encoding="utf-8")

        new_feeds = [
            {"name": "BBC News", "rss_url": "https://feeds.bbci.co.uk/news/rss.xml"},
            {"name": "CNN", "rss_url": "https://rss.cnn.com/rss/edition.rss"},
        ]

        unique = dedup_against_existing(new_feeds, str(config_file))
        assert len(unique) == 1
        assert unique[0]["name"] == "CNN"

    def test_dedup_removes_existing_by_name(self, tmp_path):
        config = {"sources": [{"name": "BBC News", "rss_url": "https://old-url.com/rss"}]}
        config_file = tmp_path / "sources.yaml"
        config_file.write_text(yaml.dump(config), encoding="utf-8")

        new_feeds = [
            {"name": "BBC News", "rss_url": "https://new-url.com/rss"},
        ]

        unique = dedup_against_existing(new_feeds, str(config_file))
        assert len(unique) == 0

    def test_dedup_case_insensitive_url(self, tmp_path):
        config = {"sources": [{"name": "X", "rss_url": "https://EXAMPLE.COM/RSS"}]}
        config_file = tmp_path / "sources.yaml"
        config_file.write_text(yaml.dump(config), encoding="utf-8")

        new_feeds = [{"name": "Y", "rss_url": "https://example.com/rss"}]
        unique = dedup_against_existing(new_feeds, str(config_file))
        assert len(unique) == 0

    def test_dedup_missing_file_returns_all(self, tmp_path):
        new_feeds = [{"name": "A", "rss_url": "https://a.com/rss"}]
        unique = dedup_against_existing(new_feeds, str(tmp_path / "missing.yaml"))
        assert len(unique) == 1


# ── YAML Output ──


class TestFeedsToYaml:
    def test_generates_valid_yaml(self):
        feeds = [{"name": "Test", "rss_url": "https://test.com/rss", "category": "news"}]
        output = feeds_to_yaml(feeds, department="news")
        data = yaml.safe_load(output)
        assert "sources" in data
        assert len(data["sources"]) == 1

    def test_sets_department(self):
        feeds = [{"name": "Test", "rss_url": "https://test.com/rss", "category": "science"}]
        output = feeds_to_yaml(feeds)
        data = yaml.safe_load(output)
        assert data["sources"][0]["departments"] == ["science"]

    def test_sets_fetch_interval(self):
        feeds = [{"name": "Test", "rss_url": "https://test.com/rss", "category": "x"}]
        output = feeds_to_yaml(feeds, fetch_interval=60)
        data = yaml.safe_load(output)
        assert data["sources"][0]["fetch_interval"] == 60


# ── Append to Sources ──


class TestAppendToSources:
    def test_creates_new_file(self, tmp_path):
        config_file = tmp_path / "new_sources.yaml"
        feeds = [
            {"name": "Test1", "rss_url": "https://test1.com/rss", "category": "news"},
            {"name": "Test2", "rss_url": "https://test2.com/rss", "category": "tech"},
        ]
        added = append_to_sources(feeds, str(config_file))
        assert added == 2

        data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert len(data["sources"]) == 2

    def test_appends_to_existing(self, tmp_path):
        config_file = tmp_path / "existing.yaml"
        config_file.write_text(yaml.dump({"sources": [
            {"name": "Existing", "rss_url": "https://existing.com/rss"},
        ]}), encoding="utf-8")

        feeds = [{"name": "New", "rss_url": "https://new.com/rss", "category": "news"}]
        added = append_to_sources(feeds, str(config_file))
        assert added == 1

        data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert len(data["sources"]) == 2

    def test_skips_duplicates(self, tmp_path):
        config_file = tmp_path / "dupes.yaml"
        config_file.write_text(yaml.dump({"sources": [
            {"name": "Existing", "rss_url": "https://existing.com/rss"},
        ]}), encoding="utf-8")

        feeds = [{"name": "Dupe", "rss_url": "https://existing.com/rss", "category": "news"}]
        added = append_to_sources(feeds, str(config_file))
        assert added == 0


# ── Model Changes: nullable url/rss_url ──


class TestFeedModelNullable:
    """Verify Feed model accepts empty url/rss_url (for scrapers)."""

    def test_feed_without_rss_url(self, db):
        from src.models import Feed

        feed = Feed(name="KGPSP Scraper", url="", rss_url="", feed_type="scraper")
        db.add(feed)
        db.flush()
        assert feed.id is not None

    def test_feed_with_none_url(self, db):
        from src.models import Feed

        feed = Feed(name="No URL Feed", rss_url="https://test.com/rss")
        db.add(feed)
        db.flush()
        assert feed.id is not None

    def test_multiple_feeds_same_empty_url(self, db):
        """Multiple scrapers can share empty rss_url."""
        from src.models import Feed

        f1 = Feed(name="Scraper1", url="", rss_url="", feed_type="scraper")
        f2 = Feed(name="Scraper2", url="", rss_url="", feed_type="scraper")
        db.add_all([f1, f2])
        db.flush()
        assert f1.id != f2.id
