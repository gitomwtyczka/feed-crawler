"""
Seed database from config/sources.yaml and config/departments.yaml.

Usage:
    python -m src.seed_db
"""

from __future__ import annotations

import logging

from .config_loader import load_departments, load_sources
from .database import Base, SessionLocal, engine
from .models import Department, Feed, FeedDepartment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def seed():
    """Seed the database with departments and feeds from YAML config."""
    # Create tables
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # ── Departments ──
        dept_configs = load_departments()
        dept_map: dict[str, int] = {}

        for dc in dept_configs:
            existing = db.query(Department).filter(Department.slug == dc.slug).first()
            if existing:
                dept_map[dc.slug] = existing.id
                logger.info("Department exists: %s", dc.slug)
            else:
                dept = Department(name=dc.name, slug=dc.slug, description=dc.description)
                db.add(dept)
                db.flush()
                dept_map[dc.slug] = dept.id
                logger.info("Created department: %s (id=%d)", dc.slug, dept.id)

        db.commit()
        logger.info("Total departments: %d", len(dept_map))

        # ── Feeds ──
        src_configs = load_sources()
        created = 0
        skipped = 0

        for sc in src_configs:
            # Check if feed already exists (by rss_url)
            existing = db.query(Feed).filter(Feed.rss_url == sc.rss_url).first()
            if existing:
                skipped += 1
                continue

            feed = Feed(
                name=sc.name,
                url=sc.url,
                rss_url=sc.rss_url,
                feed_type=sc.feed_type,
                fetch_interval=sc.fetch_interval,
                is_active=True,
            )
            db.add(feed)
            db.flush()

            # Link to departments
            for dept_slug in sc.departments:
                dept_id = dept_map.get(dept_slug)
                if dept_id:
                    assoc = FeedDepartment(feed_id=feed.id, department_id=dept_id)
                    db.add(assoc)

            created += 1

        db.commit()
        logger.info("Feeds created: %d, skipped (existing): %d", created, skipped)
        logger.info("SEED COMPLETE")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
