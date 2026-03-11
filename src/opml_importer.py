"""
OPML Bulk Importer — mass source acquisition.

Downloads OPML files from curated GitHub repositories and imports
feeds into the database with auto-tier classification.

Usage:
    python -m src.opml_importer          # import all
    python -m src.opml_importer --dry    # preview only
"""

from __future__ import annotations

import logging
import sys
import xml.etree.ElementTree as ET

import httpx

sys.path.insert(0, "/app")

from src.database import SessionLocal
from src.models import Feed
from src.source_tiers import classify_feed

logger = logging.getLogger(__name__)

# ── OPML Sources to import ──

OPML_SOURCES: list[dict] = [
    # awesome-rss-feeds — countries
    {"name": "Poland", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Poland.opml"},
    {"name": "United Kingdom", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/United%20Kingdom.opml"},
    {"name": "United States", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/United%20States.opml"},
    {"name": "Germany", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Germany.opml"},
    {"name": "France", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/France.opml"},
    {"name": "India", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/India.opml"},
    {"name": "Australia", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Australia.opml"},
    {"name": "Canada", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Canada.opml"},
    {"name": "Brazil", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Brazil.opml"},
    {"name": "Spain", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Spain.opml"},
    {"name": "Italy", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Italy.opml"},
    {"name": "Japan", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Japan.opml"},
    {"name": "Russia", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Russia.opml"},
    {"name": "Mexico", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Mexico.opml"},
    {"name": "Ireland", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Ireland.opml"},
    {"name": "South Africa", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/South%20Africa.opml"},
    {"name": "Nigeria", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Nigeria.opml"},
    {"name": "Ukraine", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Ukraine.opml"},
    {"name": "Indonesia", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Indonesia.opml"},
    {"name": "Philippines", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Philippines.opml"},
    {"name": "Pakistan", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Pakistan.opml"},
    {"name": "Bangladesh", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Bangladesh.opml"},
    {"name": "Hong Kong", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Hong%20Kong%20SAR%20China.opml"},
    {"name": "Myanmar", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Myanmar%20(Burma).opml"},
    {"name": "Iran", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Iran.opml"},
    # awesome-rss-feeds — recommended (categories)
    {"name": "Tech", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Tech.opml"},
    {"name": "Science", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Science.opml"},
    {"name": "News", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/News.opml"},
    {"name": "Business", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Business%20%26%20Economy.opml"},
    {"name": "Programming", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Programming.opml"},
    {"name": "Sports", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Sports.opml"},
    {"name": "Gaming", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Gaming.opml"},
    {"name": "Movies", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Movies.opml"},
    {"name": "Music", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Music.opml"},
    {"name": "Food", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Food.opml"},
    {"name": "Travel", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Travel.opml"},
    {"name": "Fashion", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Fashion.opml"},
    {"name": "Books", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Books.opml"},
    {"name": "History", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/History.opml"},
    {"name": "Cars", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Cars.opml"},
    {"name": "Space", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Space.opml"},
    {"name": "Photography", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Photography.opml"},
    {"name": "Beauty", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Beauty.opml"},
    {"name": "DIY", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/DIY.opml"},
    {"name": "Tennis", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Tennis.opml"},
    {"name": "Cricket", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Cricket.opml"},
    {"name": "Football", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Football.opml"},
    {"name": "Television", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Television.opml"},
    {"name": "Startups", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Startups.opml"},
    {"name": "WebDev", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Web%20Development.opml"},
    {"name": "UI/UX", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/UI%20%2F%20UX.opml"},
    {"name": "Finance", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Personal%20finance.opml"},
    {"name": "Android", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Android.opml"},
    {"name": "Apple", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Apple.opml"},
    {"name": "Architecture", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Architecture.opml"},
    {"name": "Interior Design", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Interior%20design.opml"},
    {"name": "Funny", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Funny.opml"},
    {"name": "iOSDev", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/iOS%20Development.opml"},
    {"name": "AndroidDev", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Android%20Development.opml"},
    # Feeds for Journalists
    {"name": "Journalists", "url": "https://raw.githubusercontent.com/scripting/feedsForJournalists/master/list.opml"},
]


def parse_opml(xml_text: str) -> list[dict]:
    """Parse OPML XML and extract feed entries.

    Returns list of dicts with keys: name, url, category
    """
    feeds = []
    try:
        root = ET.fromstring(xml_text)  # noqa: S314  # noqa: S314  — trusted GitHub sources only
        for outline in root.iter("outline"):
            xml_url = outline.get("xmlUrl") or outline.get("xmlurl")
            if xml_url:
                name = (
                    outline.get("title")
                    or outline.get("text")
                    or xml_url.split("/")[2]
                )
                category = ""
                # Try to get parent category
                for body in root.iter("body"):
                    for cat_outline in body:
                        if cat_outline.get("xmlUrl") is None:
                            for child in cat_outline.iter("outline"):
                                if child is outline:
                                    category = cat_outline.get("text", "")
                                    break

                feeds.append({
                    "name": name.strip(),
                    "url": xml_url.strip(),
                    "category": category,
                })
    except ET.ParseError:
        logger.exception("Failed to parse OPML")

    return feeds


def import_feeds(dry_run: bool = False) -> dict:
    """Download all OPML sources and import feeds.

    Returns stats dict with counts.
    """
    db = SessionLocal()
    stats = {"total_found": 0, "new": 0, "duplicate": 0, "errors": 0, "sources": 0}

    try:
        # Get existing feed URLs for dedup
        existing_urls = set()
        for (url,) in db.query(Feed.rss_url).filter(Feed.rss_url.isnot(None)).all():
            existing_urls.add(url.lower().rstrip("/"))

        client = httpx.Client(timeout=30, follow_redirects=True)

        for source in OPML_SOURCES:
            try:
                resp = client.get(source["url"])
                if resp.status_code != 200:
                    logger.warning("Failed to fetch %s: HTTP %d", source["name"], resp.status_code)
                    stats["errors"] += 1
                    continue

                feeds = parse_opml(resp.text)
                source_new = 0

                for feed_data in feeds:
                    stats["total_found"] += 1
                    feed_url = feed_data["url"].lower().rstrip("/")

                    if feed_url in existing_urls:
                        stats["duplicate"] += 1
                        continue

                    # Auto-classify tier
                    tier = classify_feed(feed_data["url"], feed_data["name"])

                    if not dry_run:
                        new_feed = Feed(
                            name=feed_data["name"][:200],
                            rss_url=feed_data["url"],
                            url=feed_data["url"],
                            feed_type="rss",
                            source_tier=tier,
                            is_active=True,
                        )
                        db.add(new_feed)

                    existing_urls.add(feed_url)
                    stats["new"] += 1
                    source_new += 1

                stats["sources"] += 1
                print(f"  ✅ {source['name']}: {len(feeds)} feeds, {source_new} new")

            except Exception:
                logger.exception("Error processing %s", source["name"])
                stats["errors"] += 1

        if not dry_run:
            db.commit()
            print("\n💾 Committed to database")

        client.close()

    finally:
        db.close()

    return stats


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)

    dry_run = "--dry" in sys.argv
    mode = "DRY RUN" if dry_run else "LIVE IMPORT"
    print(f"\n🚀 OPML Bulk Import — {mode}")
    print("=" * 50)

    stats = import_feeds(dry_run=dry_run)

    print("\n📊 Results:")
    print(f"  Sources processed: {stats['sources']}")
    print(f"  Total feeds found: {stats['total_found']}")
    print(f"  New feeds added:   {stats['new']}")
    print(f"  Duplicates:        {stats['duplicate']}")
    print(f"  Errors:            {stats['errors']}")
