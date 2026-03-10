"""
OPML Mass Import Tool — scale from dozens to thousands of feeds.

CLI tool to import feeds from:
1. Local OPML files
2. Remote OPML URLs (GitHub awesome-rss-feeds, etc.)
3. Bulk URL lists (one feed URL per line)

Features:
- Dedup against existing config
- Validate feeds before adding (optional)
- Auto-categorize by source metadata
- Output: appended to sources.yaml or new YAML file

Usage:
    python -m src.opml_import --url https://raw.githubusercontent.com/.../News.opml
    python -m src.opml_import --file feeds.opml
    python -m src.opml_import --url-list urls.txt
    python -m src.opml_import --awesome-feeds          # import all curated collections
    python -m src.opml_import --awesome-feeds --verify  # verify each feed before adding
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from xml.etree import ElementTree

import httpx
import yaml

from .config_loader import load_sources, slugify
from .feed_parser import fetch_single_feed

logger = logging.getLogger(__name__)

# ── awesome-rss-feeds OPML URLs (curated, high-quality) ──

AWESOME_FEEDS_BASE = "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master"

AWESOME_CATEGORIES = [
    "News", "Business & Economy", "Science", "Space",
    "Tech", "Programming", "Web Development",
    "Sports", "Football", "Fashion", "Food",
    "Books", "Cars", "Photography", "Travel",
    "Music", "Movies", "Television", "Gaming",
    "Startups", "UI / UX",
]

AWESOME_COUNTRIES = [
    "Australia", "Bangladesh", "Brazil", "Canada",
    "France", "Germany", "Hong Kong SAR China",
    "India", "Indonesia", "Iran", "Ireland", "Italy",
    "Japan", "Mexico", "Myanmar (Burma)",
    "Nigeria", "Pakistan", "Philippines",
    "Poland", "Russia", "South Africa",
    "Spain", "Ukraine", "United Kingdom", "United States",
]


def _awesome_opml_url(name: str, kind: str = "recommended") -> str:
    """Build OPML URL for an awesome-rss-feeds category/country."""
    encoded = name.replace(" ", "%20").replace("&", "%26").replace("/", "%2F")
    if kind == "country":
        return f"{AWESOME_FEEDS_BASE}/countries/with_category/{encoded}.opml"
    return f"{AWESOME_FEEDS_BASE}/recommended/with_category/{encoded}.opml"


# ── OPML Parsing ──


def parse_opml_content(xml_content: str) -> list[dict]:
    """Parse OPML XML content into list of feed dicts.

    Uses lxml with recover=True for broken XML (common in OPML files).
    Falls back to regex extraction if XML parsing completely fails.

    Returns:
        [{"name": "...", "url": "...", "rss_url": "...", "category": "..."}]
    """
    import re

    feeds = []

    # Try lxml first (lenient, handles broken XML)
    root = None
    try:
        from lxml import etree  # noqa: I001

        parser = etree.XMLParser(recover=True, encoding="utf-8")
        root = etree.fromstring(xml_content.encode("utf-8"), parser)  # noqa: S320
    except ImportError:
        # Fallback to stdlib — fix common issues first
        fixed = re.sub(r'&(?!amp;|lt;|gt;|apos;|quot;|#)', '&amp;', xml_content)
        with contextlib.suppress(ElementTree.ParseError):
            root = ElementTree.fromstring(fixed)  # noqa: S314
    except Exception:
        logger.debug("OPML parse error, will try regex fallback")

    if root is not None:
        body = root.find("body")
        if body is not None:
            for outline in body.iter("outline"):
                xml_url = outline.get("xmlUrl", "")
                if not xml_url:
                    continue
                name = outline.get("title", outline.get("text", "Unknown"))
                html_url = outline.get("htmlUrl", "")
                feed_type = outline.get("type", "rss")
                feeds.append({
                    "name": name,
                    "url": html_url,
                    "rss_url": xml_url,
                    "feed_type": feed_type,
                    "category": "",
                })

    # Regex fallback: extract xmlUrl from broken XML (last resort)
    if not feeds:
        pattern = re.compile(
            r'<outline\s[^>]*?xmlUrl="([^"]+)"[^>]*?(?:title="([^"]*?)"|text="([^"]*?)")',
            re.IGNORECASE,
        )
        for match in pattern.finditer(xml_content):
            xml_url = match.group(1)
            name = match.group(2) or match.group(3) or "Unknown"
            feeds.append({
                "name": name,
                "url": "",
                "rss_url": xml_url,
                "feed_type": "rss",
                "category": "",
            })

        # Also try reversed order (text= before xmlUrl=)
        if not feeds:
            pattern2 = re.compile(
                r'(?:title="([^"]*?)"|text="([^"]*?)")[^>]*?xmlUrl="([^"]+)"',
                re.IGNORECASE,
            )
            for match in pattern2.finditer(xml_content):
                xml_url = match.group(3)
                name = match.group(1) or match.group(2) or "Unknown"
                feeds.append({
                    "name": name,
                    "url": "",
                    "rss_url": xml_url,
                    "feed_type": "rss",
                    "category": "",
                })

        if feeds:
            logger.info("Regex fallback: extracted %d feeds from broken OPML", len(feeds))

    return feeds


def parse_opml_file(path: str | Path) -> list[dict]:
    """Parse OPML file from disk."""
    with open(path, encoding="utf-8") as f:
        return parse_opml_content(f.read())


async def fetch_opml(url: str) -> list[dict]:
    """Fetch and parse remote OPML file."""
    async with httpx.AsyncClient(
        follow_redirects=True,
        headers={"User-Agent": "FeedCrawler/1.0"},
        timeout=15,
    ) as client:
        response = await client.get(url)
        if response.status_code != 200:
            logger.warning("Failed to fetch OPML from %s: HTTP %d", url, response.status_code)
            return []
        return parse_opml_content(response.text)


# ── Feed Verification ──


async def verify_feeds(
    feeds: list[dict],
    concurrency: int = 10,
    timeout: int = 10,
) -> list[dict]:
    """Verify which feeds are actually working.

    Returns only feeds that return valid RSS/Atom content.
    """
    semaphore = asyncio.Semaphore(concurrency)
    verified = []

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=timeout,
    ) as client:
        async def _check(feed: dict) -> dict | None:
            async with semaphore:
                result = await fetch_single_feed(
                    client, feed["rss_url"], feed["name"], timeout=timeout,
                )
                if result.status == "success" and len(result.articles) > 0:
                    feed["_articles_found"] = len(result.articles)
                    return feed
                return None

        tasks = [_check(f) for f in feeds]
        results = await asyncio.gather(*tasks)
        verified = [r for r in results if r is not None]

    return verified


# ── Deduplication ──


def dedup_against_existing(
    new_feeds: list[dict],
    existing_path: str = "config/sources.yaml",
) -> list[dict]:
    """Remove feeds that already exist in sources.yaml."""
    try:
        existing = load_sources(existing_path)
        existing_urls = {s.rss_url.lower().rstrip("/") for s in existing if s.rss_url}
        existing_names = {s.name.lower() for s in existing}
    except (FileNotFoundError, ValueError):
        return new_feeds

    unique = []
    for feed in new_feeds:
        url_norm = feed["rss_url"].lower().rstrip("/")
        name_norm = feed["name"].lower()
        if url_norm not in existing_urls and name_norm not in existing_names:
            unique.append(feed)

    logger.info("Dedup: %d new, %d already exist", len(unique), len(new_feeds) - len(unique))
    return unique


# ── YAML Output ──


def feeds_to_yaml(
    feeds: list[dict],
    department: str = "imported",
    fetch_interval: int = 30,
) -> str:
    """Convert feed list to sources.yaml format string."""
    sources = []
    for feed in feeds:
        source = {
            "name": feed["name"],
            "url": feed.get("url", ""),
            "rss_url": feed["rss_url"],
            "feed_type": feed.get("feed_type", "rss"),
            "fetch_interval": fetch_interval,
            "departments": [slugify(feed.get("category", department))],
        }
        sources.append(source)

    return yaml.dump(
        {"sources": sources},
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )


def append_to_sources(
    feeds: list[dict],
    config_path: str = "config/sources.yaml",
    department: str = "imported",
) -> int:
    """Append new feeds to existing sources.yaml.

    Returns number of feeds added.
    """
    path = Path(config_path)

    if path.exists():
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        data = {"sources": []}

    existing_urls = set()
    for src in data.get("sources", []):
        if src.get("rss_url"):
            existing_urls.add(src["rss_url"].lower().rstrip("/"))

    added = 0
    for feed in feeds:
        url_norm = feed["rss_url"].lower().rstrip("/")
        if url_norm in existing_urls:
            continue

        new_entry = {
            "name": feed["name"],
            "url": feed.get("url", ""),
            "rss_url": feed["rss_url"],
            "feed_type": feed.get("feed_type", "rss"),
            "fetch_interval": 30,
            "departments": [slugify(feed.get("category", department))],
        }
        data["sources"].append(new_entry)
        existing_urls.add(url_norm)
        added += 1

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    return added


# ── Awesome-RSS-Feeds bulk import ──


async def import_awesome_feeds(
    categories: list[str] | None = None,
    countries: list[str] | None = None,
    verify: bool = False,
) -> list[dict]:
    """Import feeds from awesome-rss-feeds GitHub repo.

    Args:
        categories: List of categories to import (None = all)
        countries: List of countries to import (None = all)
        verify: If True, verify each feed before including

    Returns:
        List of unique, verified (if requested) feed dicts.
    """
    all_feeds = []

    cats = categories or AWESOME_CATEGORIES
    ctrs = countries or AWESOME_COUNTRIES

    logger.info("Importing from awesome-rss-feeds: %d categories + %d countries", len(cats), len(ctrs))

    for cat in cats:
        url = _awesome_opml_url(cat, "recommended")
        feeds = await fetch_opml(url)
        for f in feeds:
            f["category"] = cat
        all_feeds.extend(feeds)
        logger.info("  %s: %d feeds", cat, len(feeds))

    for country in ctrs:
        url = _awesome_opml_url(country, "country")
        feeds = await fetch_opml(url)
        for f in feeds:
            f["category"] = f"country-{slugify(country)}"
        all_feeds.extend(feeds)
        logger.info("  %s: %d feeds", country, len(feeds))

    # Dedup within imported
    seen_urls = set()
    unique = []
    for feed in all_feeds:
        url_norm = feed["rss_url"].lower().rstrip("/")
        if url_norm not in seen_urls:
            seen_urls.add(url_norm)
            unique.append(feed)

    logger.info("Total: %d unique feeds (from %d raw)", len(unique), len(all_feeds))

    if verify:
        logger.info("Verifying feeds (this may take a while)...")
        unique = await verify_feeds(unique)
        logger.info("Verified: %d working feeds", len(unique))

    return unique


# ── CLI ──


def main() -> None:
    """CLI entry point for mass OPML import."""
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Mass OPML Feed Importer")
    parser.add_argument("--file", help="Import from local OPML file")
    parser.add_argument("--url", help="Import from remote OPML URL")
    parser.add_argument("--awesome-feeds", action="store_true", help="Import from awesome-rss-feeds")
    parser.add_argument("--verify", action="store_true", help="Verify feeds before adding")
    parser.add_argument("--dry-run", action="store_true", help="Print results without saving")
    parser.add_argument("--output", default="config/sources.yaml", help="Output config file")
    parser.add_argument("--department", default="imported", help="Default department for new feeds")
    parser.add_argument(
        "--categories",
        nargs="*",
        help="Specific categories to import (default: all)",
    )
    parser.add_argument(
        "--countries",
        nargs="*",
        help="Specific countries to import (default: all)",
    )
    args = parser.parse_args()

    feeds = []

    if args.file:
        feeds = parse_opml_file(args.file)
        logger.info("Loaded %d feeds from %s", len(feeds), args.file)

    elif args.url:
        feeds = asyncio.run(fetch_opml(args.url))
        logger.info("Loaded %d feeds from %s", len(feeds), args.url)

    elif args.awesome_feeds:
        feeds = asyncio.run(import_awesome_feeds(
            categories=args.categories,
            countries=args.countries,
            verify=args.verify,
        ))

    else:
        parser.print_help()
        return

    # Dedup against existing
    feeds = dedup_against_existing(feeds, args.output)

    if args.dry_run:
        print(f"\n=== DRY RUN: {len(feeds)} new feeds ===")
        for f in feeds[:20]:
            arts = f.get("_articles_found", "?")
            print(f"  [{f.get('category', '?'):20s}] {f['name'][:40]:40s} ({arts} art)")
        if len(feeds) > 20:
            print(f"  ... and {len(feeds) - 20} more")
        print(f"\nTotal: {len(feeds)} feeds would be added to {args.output}")
    else:
        added = append_to_sources(feeds, args.output, args.department)
        logger.info("Added %d feeds to %s", added, args.output)


if __name__ == "__main__":
    main()
