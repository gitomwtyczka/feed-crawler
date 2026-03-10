"""Tests for OPML import and YAML config loading."""


import yaml

from src.config_loader import (
    DepartmentConfig,
    SourceConfig,
    load_departments,
    load_sources,
    opml_to_departments_yaml,
    opml_to_sources_yaml,
    parse_opml,
    slugify,
)

# ── Slugify ──


def test_slugify_basic():
    assert slugify("SCIENCE & HIGH-TECH") == "science-high-tech"


def test_slugify_ampersand_entity():
    assert slugify("DEFENCE &amp; GEOPOLITICS") == "defence-geopolitics"


def test_slugify_strips_edges():
    assert slugify("  Hello World  ") == "hello-world"


def test_slugify_multiple_separators():
    assert slugify("CYBER & DIGITAL") == "cyber-digital"


# ── OPML Parsing ──


def test_parse_opml_returns_categories(sample_opml):
    result = parse_opml(sample_opml)
    assert "SCIENCE" in result
    assert "HEALTH" in result


def test_parse_opml_feed_count(sample_opml):
    result = parse_opml(sample_opml)
    assert len(result["SCIENCE"]) == 2  # Nature + NASA
    assert len(result["HEALTH"]) == 1   # WHO


def test_parse_opml_feed_fields(sample_opml):
    result = parse_opml(sample_opml)
    nature = result["SCIENCE"][0]
    assert nature["name"] == "Nature"
    assert nature["rss_url"] == "http://feeds.nature.com/rss"
    assert nature["url"] == "https://nature.com"


def test_parse_opml_invalid_file(tmp_path):
    """Non-existent file should raise."""
    import pytest
    with pytest.raises(FileNotFoundError):
        parse_opml(tmp_path / "nonexistent.opml")


# ── OPML → YAML generation ──


def test_opml_to_sources_yaml(sample_opml):
    yaml_str = opml_to_sources_yaml(sample_opml, fetch_interval=15)
    data = yaml.safe_load(yaml_str)
    assert "sources" in data
    assert len(data["sources"]) == 3  # Nature + NASA + WHO
    # Check department mapping
    nature = data["sources"][0]
    assert nature["departments"] == ["science"]


def test_opml_to_departments_yaml(sample_opml):
    yaml_str = opml_to_departments_yaml(sample_opml)
    data = yaml.safe_load(yaml_str)
    assert "departments" in data
    # 2 from OPML + 2 future slots
    slugs = [d["slug"] for d in data["departments"]]
    assert "science" in slugs
    assert "health" in slugs
    assert "historyczny" in slugs
    assert "statystyki" in slugs


# ── YAML Loading ──


def test_load_sources_from_yaml(tmp_path):
    config = {
        "sources": [
            {
                "name": "Test Feed",
                "url": "https://test.com",
                "rss_url": "https://test.com/rss",
                "feed_type": "rss",
                "fetch_interval": 30,
                "departments": ["science"],
            }
        ]
    }
    yaml_file = tmp_path / "sources.yaml"
    yaml_file.write_text(yaml.dump(config), encoding="utf-8")

    sources = load_sources(str(yaml_file))
    assert len(sources) == 1
    assert isinstance(sources[0], SourceConfig)
    assert sources[0].name == "Test Feed"
    assert sources[0].departments == ["science"]


def test_load_departments_from_yaml(tmp_path):
    config = {
        "departments": [
            {"name": "Science", "slug": "science", "description": "Science dept"},
        ]
    }
    yaml_file = tmp_path / "departments.yaml"
    yaml_file.write_text(yaml.dump(config), encoding="utf-8")

    departments = load_departments(str(yaml_file))
    assert len(departments) == 1
    assert isinstance(departments[0], DepartmentConfig)
    assert departments[0].slug == "science"


def test_load_sources_missing_file():
    """Missing file should raise FileNotFoundError."""
    import pytest
    with pytest.raises(FileNotFoundError):
        load_sources("/nonexistent/path/sources.yaml")


def test_load_sources_invalid_yaml(tmp_path):
    """YAML without 'sources' key should raise ValueError."""
    import pytest
    yaml_file = tmp_path / "bad.yaml"
    yaml_file.write_text("foo: bar", encoding="utf-8")
    with pytest.raises(ValueError):
        load_sources(str(yaml_file))
