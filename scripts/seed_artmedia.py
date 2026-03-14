"""
Seed ARTMedia client + WPiA UW project from IMM Excel data.

Usage:
    python scripts/seed_artmedia.py
"""
from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.auth import hash_password  # noqa: E402
from src.database import Base, SessionLocal, engine  # noqa: E402
from src.models import ClientAccount, Project, ProjectKeyword  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Keywords extracted from IMM Excel (column: frazy)
# Deduplicated and cleaned — core monitoring terms
WPIA_KEYWORDS = [
    "wydział prawa i administracji",
    "wydział prawa i administracji uw",
    "wydział prawa i administracji uniwersytetu warszawskiego",
    "wydział prawa",
    "wpia",
    "wpia uw",
    "wpia_uw",
    "prawo i administracja uw",
    "uniwersytet warszawski prawo",
    "studia prawnicze",
    "prawo uw",
]


def seed():
    """Seed ARTMedia client and WPiA UW project."""
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # ── Client ──
        existing = db.query(ClientAccount).filter(
            ClientAccount.username == "artmedia"
        ).first()
        if existing:
            logger.info("Client 'artmedia' already exists (id=%d), skipping", existing.id)
            client_id = existing.id
        else:
            client = ClientAccount(
                username="artmedia",
                password_hash=hash_password("ArtMedia2026!"),
                company_name="Art Media Agencja PR",
                email="monitoring@artmedia.pl",
                tier="pro",
                is_active=True,
            )
            db.add(client)
            db.flush()
            client_id = client.id
            logger.info("Created client: artmedia (id=%d, tier=pro)", client_id)

        # ── Project: WPiA UW ──
        slug = "wpia-uw"
        project = db.query(Project).filter(Project.slug == slug).first()
        if project:
            logger.info("Project '%s' already exists (id=%d), skipping", slug, project.id)
        else:
            project = Project(
                name="Wydział Prawa i Administracji UW",
                slug=slug,
                description="Monitoring medialny Wydziału Prawa i Administracji Uniwersytetu Warszawskiego",
                client_id=client_id,
                is_active=True,
            )
            db.add(project)
            db.flush()
            logger.info("Created project: %s (id=%d)", project.name, project.id)

            # Add keywords
            for kw in WPIA_KEYWORDS:
                db.add(ProjectKeyword(
                    project_id=project.id,
                    keyword=kw,
                    match_type="contains",
                ))
            logger.info("Added %d keywords to project %s", len(WPIA_KEYWORDS), slug)

        db.commit()
        logger.info("SEED COMPLETE — artmedia client + wpia-uw project")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
