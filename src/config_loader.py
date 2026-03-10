"""
Configuration loader: OPML import + YAML source/department loading.

Supports:
- Importing OPML files → generating sources.yaml
- Loading sources.yaml and departments.yaml
- Validating configuration completeness
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree

import yaml

# ── Data classes for typed config ──


@dataclass
class SourceConfig:
    """Single feed source from configuration."""

    name: str
    url: str
    rss_url: str
    feed_type: str = "rss"
    fetch_interval: int = 30
    departments: list[str] = field(default_factory=list)


@dataclass
class DepartmentConfig:
    """Single department from configuration."""

    name: str
    slug: str
    description: str = ""


# ── OPML Import ──


def slugify(text: str) -> str:
    """Convert category name to URL-safe slug.

    'SCIENCE & HIGH-TECH' → 'science-hightech'
    """
    text = text.lower().strip()
    text = text.replace("&amp;", "").replace("&", "")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def parse_opml(opml_path: str | Path) -> dict[str, list[dict]]:
    """Parse an OPML file into a dict of categories → feed lists.

    Returns:
        {
            "SCIENCE & HIGH-TECH": [
                {"name": "Nature", "text": "Nature - Current Issue",
                 "rss_url": "http://...", "url": "https://..."},
                ...
            ],
            ...
        }
    """
    tree = ElementTree.parse(opml_path)  # noqa: S314
    root = tree.getroot()
    body = root.find("body")
    if body is None:
        msg = f"Invalid OPML: no <body> element in {opml_path}"
        raise ValueError(msg)

    categories: dict[str, list[dict]] = {}

    for category_outline in body.findall("outline"):
        category_name = category_outline.get("title", category_outline.get("text", "Unknown"))
        feeds = []

        for feed_outline in category_outline.findall("outline"):
            feed_data = {
                "name": feed_outline.get("title", feed_outline.get("text", "Unknown")),
                "text": feed_outline.get("text", ""),
                "rss_url": feed_outline.get("xmlUrl", ""),
                "url": feed_outline.get("htmlUrl", ""),
                "feed_type": feed_outline.get("type", "rss"),
            }
            if feed_data["rss_url"]:
                feeds.append(feed_data)

        if feeds:
            categories[category_name] = feeds

    return categories


def opml_to_sources_yaml(opml_path: str | Path, fetch_interval: int = 30) -> str:
    """Convert OPML file to sources.yaml content string."""
    categories = parse_opml(opml_path)
    sources = []

    for category_name, feeds in categories.items():
        dept_slug = slugify(category_name)
        for feed_data in feeds:
            source = {
                "name": feed_data["name"],
                "url": feed_data["url"],
                "rss_url": feed_data["rss_url"],
                "feed_type": feed_data["feed_type"],
                "fetch_interval": fetch_interval,
                "departments": [dept_slug],
            }
            sources.append(source)

    return yaml.dump({"sources": sources}, default_flow_style=False, allow_unicode=True, sort_keys=False)


def opml_to_departments_yaml(opml_path: str | Path) -> str:
    """Convert OPML categories to departments.yaml content string."""
    categories = parse_opml(opml_path)
    departments = []

    for category_name in categories:
        dept = {
            "name": category_name,
            "slug": slugify(category_name),
            "description": f"Auto-imported from OPML: {category_name}",
        }
        departments.append(dept)

    # Add placeholder slots for future departments
    departments.append({
        "name": "HISTORYCZNY",
        "slug": "historyczny",
        "description": "Publikacje historyczne (slot na przyszłość)",
    })
    departments.append({
        "name": "STATYSTYKI (Eurostat/GUS)",
        "slug": "statystyki",
        "description": "Statystyki Eurostat, GUS i inne (slot na przyszłość)",
    })

    return yaml.dump({"departments": departments}, default_flow_style=False, allow_unicode=True, sort_keys=False)


# ── YAML Loading ──


def load_sources(config_path: str | Path = "config/sources.yaml") -> list[SourceConfig]:
    """Load sources from YAML config file."""
    path = Path(config_path)
    if not path.exists():
        msg = f"Sources config not found: {path}"
        raise FileNotFoundError(msg)

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "sources" not in data:
        msg = f"Invalid sources config: missing 'sources' key in {path}"
        raise ValueError(msg)

    sources = []
    for src in data["sources"]:
        sources.append(SourceConfig(
            name=src["name"],
            url=src.get("url", ""),
            rss_url=src["rss_url"],
            feed_type=src.get("feed_type", "rss"),
            fetch_interval=src.get("fetch_interval", 30),
            departments=src.get("departments", []),
        ))

    return sources


def load_departments(config_path: str | Path = "config/departments.yaml") -> list[DepartmentConfig]:
    """Load departments from YAML config file."""
    path = Path(config_path)
    if not path.exists():
        msg = f"Departments config not found: {path}"
        raise FileNotFoundError(msg)

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not data or "departments" not in data:
        msg = f"Invalid departments config: missing 'departments' key in {path}"
        raise ValueError(msg)

    departments = []
    for dept in data["departments"]:
        departments.append(DepartmentConfig(
            name=dept["name"],
            slug=dept["slug"],
            description=dept.get("description", ""),
        ))

    return departments
