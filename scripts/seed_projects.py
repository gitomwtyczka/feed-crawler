"""
Seed test projects into the database.

Usage:
    python -m scripts.seed_projects
    # or from project root:
    python scripts/seed_projects.py
"""

from __future__ import annotations

import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.database import Base, SessionLocal, engine  # noqa: E402
from src.models import Project, ProjectKeyword  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SEED_PROJECTS = [
    {"name": "Strabag", "slug": "strabag", "keywords": ["Strabag", "STRABAG"]},
    {"name": "Orlen", "slug": "orlen", "keywords": ["Orlen", "PKN Orlen", "ORLEN"]},
    {"name": "PZU", "slug": "pzu", "keywords": ["PZU", "Powszechny Zakład Ubezpieczeń"]},
    {"name": "TVP", "slug": "tvp", "keywords": ["TVP", "Telewizja Polska"]},
]


def seed_projects():
    """Seed test projects into the database."""
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        created = 0
        skipped = 0

        for proj_data in SEED_PROJECTS:
            existing = db.query(Project).filter(Project.slug == proj_data["slug"]).first()
            if existing:
                logger.info("Project exists: %s", proj_data["slug"])
                skipped += 1
                continue

            project = Project(
                name=proj_data["name"],
                slug=proj_data["slug"],
            )
            db.add(project)
            db.flush()

            for kw in proj_data["keywords"]:
                db.add(ProjectKeyword(project_id=project.id, keyword=kw))

            created += 1
            logger.info("Created project: %s (id=%d, keywords=%d)", proj_data["name"], project.id, len(proj_data["keywords"]))

        db.commit()
        logger.info("Projects created: %d, skipped: %d", created, skipped)
        logger.info("SEED COMPLETE")

    finally:
        db.close()


if __name__ == "__main__":
    seed_projects()
