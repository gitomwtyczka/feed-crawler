"""
Auto-categorize feeds into departments based on domain/name patterns.

Adds missing departments (ISBNews, Newseria, Agencje, Media PL, Podcasts, etc.)
and assigns feeds to departments using keyword rules.

Usage:
    python -m src.categorize_feeds
"""

from __future__ import annotations

import logging
import re

from .database import Base, SessionLocal, engine
from .models import Department, Feed, FeedDepartment

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# New departments to create
NEW_DEPARTMENTS = [
    {"name": "AGENCJE PRASOWE", "slug": "agencje-prasowe",
     "description": "Agencje informacyjne — ISBnews, PAP, Reuters, AP, AFP"},
    {"name": "NEWSERIA", "slug": "newseria",
     "description": "Serwisy Newseria — biznes, innowacje, lifestyle"},
    {"name": "MEDIA POLSKIE", "slug": "media-polskie",
     "description": "Polskie media newsowe — TVN24, Polsat, RMF, Onet, WP, Interia, Gazeta"},
    {"name": "MEDIA GLOBALNE", "slug": "media-globalne",
     "description": "Globalne media newsowe — BBC, CNN, Reuters, Al Jazeera, The Guardian, NYT"},
    {"name": "PODCASTS & AUDIO", "slug": "podcasts-audio",
     "description": "Podcasty i serwisy audio — Radiolab, Hidden Brain, Discovery, TED"},
    {"name": "FINANSE & RYNKI", "slug": "finanse-rynki",
     "description": "Rynki finansowe, giełda, bankowość — Bankier, Bloomberg, FT, Forsal"},
    {"name": "POLITYKA", "slug": "polityka",
     "description": "Polityka krajowa i zagraniczna — Politico, The Hill, Foreign Affairs"},
    {"name": "TECH & STARTUPY", "slug": "tech-startupy",
     "description": "Technologie, startupy, AI, crypto — TechCrunch, Ars Technica, The Verge, Wired"},
]

# Rules: (pattern_in_url_or_name, department_slug)
# First match wins; patterns are case-insensitive
CATEGORIZE_RULES = [
    # Agencje prasowe
    (r"isbnews|isb\.pl", "agencje-prasowe"),
    (r"pap\.pl|depesza", "agencje-prasowe"),
    (r"reuters\.com", "agencje-prasowe"),
    (r"apnews\.com|ap\.org", "agencje-prasowe"),

    # Newseria
    (r"newseria\.pl", "newseria"),

    # Media polskie
    (r"tvn24|tvn\.pl", "media-polskie"),
    (r"polsat|interia\.pl", "media-polskie"),
    (r"rmf24|rmf\.fm", "media-polskie"),
    (r"onet\.pl", "media-polskie"),
    (r"wp\.pl|wiadomosci\.wp", "media-polskie"),
    (r"gazeta\.pl|wyborcza", "media-polskie"),
    (r"fakt\.pl|se\.pl", "media-polskie"),
    (r"natemat\.pl", "media-polskie"),
    (r"tokfm|radio\.zet|polskieradio", "media-polskie"),
    (r"dziennik\.pl|gazetaprawna", "media-polskie"),
    (r"wprost|newsweek\.pl|polityka\.pl", "media-polskie"),
    (r"rp\.pl|rzeczpospolita", "media-polskie"),
    (r"bankier\.pl", "finanse-rynki"),
    (r"money\.pl|pb\.pl|parkiet", "finanse-rynki"),
    (r"forsal\.pl|wnp\.pl", "finanse-rynki"),
    (r"puls\s*biznesu|biznes\.pl", "finanse-rynki"),

    # Media globalne
    (r"bbc\.co|bbc\.com", "media-globalne"),
    (r"cnn\.com", "media-globalne"),
    (r"theguardian\.com|guardian\.co", "media-globalne"),
    (r"nytimes\.com|nyt\.com", "media-globalne"),
    (r"washingtonpost|wapo\.com", "media-globalne"),
    (r"aljazeera", "media-globalne"),
    (r"dw\.com|france24|euronews", "media-globalne"),
    (r"economist\.com", "media-globalne"),
    (r"ft\.com|financial.times", "media-globalne"),
    (r"bloomberg\.com", "finanse-rynki"),
    (r"cnbc\.com|marketwatch", "finanse-rynki"),
    (r"wsj\.com|wall.street", "finanse-rynki"),

    # Podcasts
    (r"podcast|acast\.com|simplecast|omnycontent|megaphone|anchor\.fm|podbean|libsyn|transistor|spotify.*show", "podcasts-audio"),
    (r"radiolab|hidden.brain|freakonomics|ted\.com.*talks|discovery.*bbc", "podcasts-audio"),

    # Tech
    (r"techcrunch|arstechnica|theverge|wired\.com", "tech-startupy"),
    (r"engadget|gizmodo|mashable|thenextweb", "tech-startupy"),
    (r"hackernews|hacker.news|ycombinator", "tech-startupy"),
    (r"openai\.com|anthropic|deepmind", "tech-startupy"),

    # Polityka
    (r"politico\.(eu|com)", "polityka"),
    (r"thehill\.com|foreignaffairs|foreignpolicy", "polityka"),
    (r"council.*foreign|cfr\.org", "polityka"),

    # Defence (already exists)
    (r"isw\.pub|atlantic.council|csis\.org|sipri|rusi\.org|iiss\.org", "defence-geopolitics"),
    (r"janes\.com|defense|defensa|military", "defence-geopolitics"),

    # Economy (already exists)
    (r"imf\.org|ecb\.europa|oecd|bruegel|piie", "economy-global-trade"),
    (r"worldbank|wto\.org|unctad", "economy-global-trade"),

    # Science (already exists)
    (r"nature\.com|science\.org|nasa\.gov|phys\.org|cern\.ch", "science-high-tech"),
    (r"newscientist|scientificamerican|mit\.edu", "science-high-tech"),

    # Health (already exists)
    (r"who\.int|cdc\.gov|ema\.europa|statnews", "health-biotech"),
    (r"lancet|nejm|bmj\.com|medscape", "health-biotech"),

    # Energy (already exists)
    (r"iea\.org|irena\.org|theconversation", "energy-climate"),
    (r"carbonbrief|cleantech|renewableenergy", "energy-climate"),

    # Cyber (already exists)
    (r"checkpoint|mandiant|crowdstrike|fireeye", "cyber-digital"),
    (r"krebs.on.security|bleepingcomputer|darkreading", "cyber-digital"),

    # Konkurencja biznes (already exists)
    (r"business.insider\.pl|bi\.pl", "konkurencja-biznes"),
    (r"bizcentral|brief\.pl", "konkurencja-biznes"),

    # Konkurencja ogólne (already exists)
    (r"glamour\.pl|vogue\.pl|cosmopolitan\.pl", "konkurencja-ogolne-lifestyle"),
    (r"elle\.pl|noizz\.pl|pudelek", "konkurencja-ogolne-lifestyle"),
]


def categorize():
    """Auto-categorize feeds into departments."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # ── Create new departments ──
        dept_map: dict[str, int] = {}
        for d in db.query(Department).all():
            dept_map[d.slug] = d.id

        for nd in NEW_DEPARTMENTS:
            if nd["slug"] not in dept_map:
                dept = Department(name=nd["name"], slug=nd["slug"], description=nd["description"])
                db.add(dept)
                db.flush()
                dept_map[nd["slug"]] = dept.id
                logger.info("Created department: %s (id=%d)", nd["slug"], dept.id)

        db.commit()

        # ── Categorize feeds ──
        feeds = db.query(Feed).all()
        assigned = 0
        skipped = 0

        for feed in feeds:
            # Check if already has a department
            existing = db.query(FeedDepartment).filter(FeedDepartment.feed_id == feed.id).first()
            if existing:
                skipped += 1
                continue

            # Try to match against rules
            text = f"{feed.name} {feed.url} {feed.rss_url}".lower()
            matched_slug = None
            for pattern, slug in CATEGORIZE_RULES:
                if re.search(pattern, text, re.IGNORECASE):
                    matched_slug = slug
                    break

            if matched_slug and matched_slug in dept_map:
                assoc = FeedDepartment(feed_id=feed.id, department_id=dept_map[matched_slug])
                db.add(assoc)
                assigned += 1
            else:
                # Unmatched — try generic categorization by content
                pass  # Will be categorized manually via admin

        db.commit()
        logger.info("Assigned: %d, Already had dept: %d, Unmatched: %d",
                     assigned, skipped, len(feeds) - assigned - skipped)

        # Stats
        for slug, dept_id in sorted(dept_map.items()):
            count = db.query(FeedDepartment).filter(FeedDepartment.department_id == dept_id).count()
            logger.info("  %s: %d feeds", slug, count)

    finally:
        db.close()


if __name__ == "__main__":
    categorize()
