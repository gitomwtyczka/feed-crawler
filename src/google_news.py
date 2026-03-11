"""
Google News RSS Engine — topic-based feed generation.

Generates Google News RSS feed URLs for any topic in any language.
Each generated feed gives access to ALL sources indexed by Google News
for that topic in that region — effectively 20K+ sources without
needing to know individual RSS feed URLs.

Usage:
    python -m src.google_news          # import topic feeds for all languages
    python -m src.google_news --dry    # preview only
"""

from __future__ import annotations

import logging
import sys
from urllib.parse import quote_plus

sys.path.insert(0, "/app")

from src.database import SessionLocal
from src.models import LANGUAGES, Feed
from src.source_tiers import classify_feed

logger = logging.getLogger(__name__)

# Google News RSS base URL
GNEWS_BASE = "https://news.google.com/rss/search"


def gnews_rss_url(query: str, lang: str = "pl") -> str:
    """Build Google News RSS URL for a query in a given language."""
    cfg = LANGUAGES.get(lang, LANGUAGES["pl"])
    q = quote_plus(query)
    return f"{GNEWS_BASE}?q={q}&hl={cfg['google_hl']}&gl={cfg['google_gl']}&ceid={cfg['google_ceid']}"


def gnews_topic_url(topic_id: str, lang: str = "pl") -> str:
    """Build Google News RSS URL for a topic section."""
    cfg = LANGUAGES.get(lang, LANGUAGES["pl"])
    return f"https://news.google.com/rss/topics/{topic_id}?hl={cfg['google_hl']}&gl={cfg['google_gl']}&ceid={cfg['google_ceid']}"


# ── Topic definitions per language ──
# Google News topic IDs
GNEWS_TOPICS = {
    "WORLD": "CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FuQnNHZ0pRVENnQVAB",
    "NATION": "CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx1YlY4U0FuQnNHZ0pRVENnQVAB",
    "BUSINESS": "CAAqJggKIiBDQkFTRWdvSUwyMHZNRGx6TVdZU0FuQnNHZ0pRVENnQVAB",
    "TECHNOLOGY": "CAAqJggKIiBDQkFTRWdvSUwyMHZNRGRqTVhZU0FuQnNHZ0pRVENnQVAB",
    "SCIENCE": "CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp0Y1RjU0FuQnNHZ0pRVENnQVAB",
    "HEALTH": "CAAqIQgKIhtDQkFTRGdvSUwyMHZNR3QwTlRFU0FuQnNLQUFQAQ",
    "SPORTS": "CAAqJggKIiBDQkFTRWdvSUwyMHZNRFp1ZEdvU0FuQnNHZ0pRVENnQVAB",
    "ENTERTAINMENT": "CAAqJggKIiBDQkFTRWdvSUwyMHZNREpxYW5RU0FuQnNHZ0pRVENnQVAB",
}

# ── Search query feeds — topic keywords per language ──
# These capture niche/specialized topics that Google News sections don't cover

TOPIC_QUERIES: dict[str, list[tuple[str, str]]] = {
    "pl": [
        # Polityka / Samorząd
        ("GNews PL: Polityka", "polityka polska rząd sejm"),
        ("GNews PL: Samorząd", "samorząd gmina powiat burmistrz"),
        ("GNews PL: Wybory", "wybory sondaż kampania"),
        # Gospodarka
        ("GNews PL: Gospodarka", "gospodarka polska PKB inflacja"),
        ("GNews PL: Giełda", "giełda GPW akcje indeks"),
        ("GNews PL: Nieruchomości", "nieruchomości mieszkania ceny"),
        ("GNews PL: Finanse", "finanse kredyty banki NBP"),
        # Medycyna
        ("GNews PL: Medycyna", "medycyna zdrowie leczenie szpital"),
        ("GNews PL: Farmacja", "farmacja leki apteka"),
        ("GNews PL: COVID", "pandemia szczepienia epidemia"),
        # Technologia
        ("GNews PL: Sztuczna inteligencja", "sztuczna inteligencja AI chatbot"),
        ("GNews PL: Cyberbezpieczeństwo", "cyberbezpieczeństwo hakerzy atak"),
        ("GNews PL: Startupy PL", "startup polska technologie"),
        # Prawo
        ("GNews PL: Prawo", "prawo ustawa kodeks sąd"),
        ("GNews PL: RODO GDPR", "RODO ochrona danych osobowych"),
        # Energia / Klimat
        ("GNews PL: Energetyka", "energetyka atom OZE prąd"),
        ("GNews PL: Klimat", "klimat emisje ekologia środowisko"),
        # Rolnictwo
        ("GNews PL: Rolnictwo", "rolnictwo agro dopłaty plony"),
        # Transport
        ("GNews PL: Transport", "transport kolej drogi autostrady"),
        # Edukacja
        ("GNews PL: Edukacja", "edukacja szkoła nauczyciele matura"),
        # Obronność
        ("GNews PL: Wojsko", "wojsko polskie obronność NATO"),
        # Kultura
        ("GNews PL: Kultura", "kultura teatr film muzyka"),
        # Sport szczegółowy
        ("GNews PL: Piłka nożna", "piłka nożna ekstraklasa liga"),
        ("GNews PL: Siatkówka", "siatkówka PlusLiga reprezentacja"),
        ("GNews PL: Żużel", "żużel grand prix speedway"),
        # Regiony
        ("GNews PL: Warszawa", "Warszawa wiadomości"),
        ("GNews PL: Kraków", "Kraków wiadomości"),
        ("GNews PL: Wrocław", "Wrocław wiadomości"),
        ("GNews PL: Gdańsk", "Gdańsk Trójmiasto wiadomości"),
        ("GNews PL: Poznań", "Poznań Wielkopolska wiadomości"),
        ("GNews PL: Łódź", "Łódź wiadomości"),
        ("GNews PL: Katowice", "Katowice Śląsk wiadomości"),
        ("GNews PL: Lublin", "Lublin wiadomości"),
        ("GNews PL: Rzeszów", "Rzeszów Podkarpacie wiadomości"),
        ("GNews PL: Białystok", "Białystok Podlasie wiadomości"),
        ("GNews PL: Szczecin", "Szczecin wiadomości"),
        ("GNews PL: Olsztyn", "Olsztyn Warmia Mazury wiadomości"),
        ("GNews PL: Kielce", "Kielce Świętokrzyskie wiadomości"),
        ("GNews PL: Opole", "Opole wiadomości"),
        ("GNews PL: Bydgoszcz", "Bydgoszcz wiadomości"),
        ("GNews PL: Zielona Góra", "Zielona Góra Lubuskie wiadomości"),
    ],
    "en": [
        ("GNews EN: AI", "artificial intelligence machine learning"),
        ("GNews EN: Climate", "climate change environment sustainability"),
        ("GNews EN: Geopolitics", "geopolitics international relations diplomacy"),
        ("GNews EN: Cybersecurity", "cybersecurity hacking data breach"),
        ("GNews EN: Space", "space exploration NASA SpaceX"),
        ("GNews EN: Fintech", "fintech cryptocurrency blockchain"),
        ("GNews EN: Healthcare", "healthcare medicine pharmaceutical"),
        ("GNews EN: Education", "education university college"),
        ("GNews EN: Real Estate", "real estate housing market"),
        ("GNews EN: Startups", "startups venture capital funding"),
        ("GNews EN: Defense", "defense military NATO"),
        ("GNews EN: Energy", "energy renewable solar nuclear"),
        ("GNews EN: EU Politics", "European Union politics Brussels"),
    ],
    "de": [
        ("GNews DE: Politik", "Politik Bundestag Regierung"),
        ("GNews DE: Wirtschaft", "Wirtschaft Konjunktur Unternehmen"),
        ("GNews DE: Technologie", "Technologie KI Digitalisierung"),
        ("GNews DE: Gesundheit", "Gesundheit Medizin Krankenhaus"),
        ("GNews DE: Energie", "Energie Energiewende Klima"),
        ("GNews DE: Automobil", "Automobil VW BMW Mercedes"),
    ],
    "fr": [
        ("GNews FR: Politique", "politique France gouvernement"),
        ("GNews FR: Économie", "économie entreprises marché"),
        ("GNews FR: Technologie", "technologie IA numérique"),
        ("GNews FR: Santé", "santé médecine hôpital"),
        ("GNews FR: Environnement", "environnement climat écologie"),
    ],
    "es": [
        ("GNews ES: Política", "política España gobierno"),
        ("GNews ES: Economía", "economía mercados empresas"),
        ("GNews ES: Tecnología", "tecnología inteligencia artificial"),
        ("GNews ES: Salud", "salud medicina hospital"),
    ],
    "it": [
        ("GNews IT: Politica", "politica Italia governo"),
        ("GNews IT: Economia", "economia mercati imprese"),
        ("GNews IT: Tecnologia", "tecnologia intelligenza artificiale"),
    ],
    "pt": [
        ("GNews PT: Política", "política Portugal governo"),
        ("GNews PT: Economia", "economia mercados empresas"),
        ("GNews PT: Tecnologia", "tecnologia inteligência artificial"),
    ],
}


def import_google_news_feeds(dry_run: bool = False) -> dict:
    """Import Google News RSS feeds for all topics and languages."""
    db = SessionLocal()
    stats = {"total": 0, "new": 0, "duplicate": 0}

    try:
        existing = set()
        for (url,) in db.query(Feed.rss_url).filter(Feed.rss_url.isnot(None)).all():
            existing.add(url.lower().rstrip("/"))

        # 1) Topic section feeds (per language)
        for lang_code in LANGUAGES:
            for topic_name, topic_id in GNEWS_TOPICS.items():
                url = gnews_topic_url(topic_id, lang_code)
                name = f"GNews {lang_code.upper()}: {topic_name}"
                stats["total"] += 1

                if url.lower().rstrip("/") in existing:
                    stats["duplicate"] += 1
                    continue

                if not dry_run:
                    db.add(Feed(
                        name=name[:200],
                        rss_url=url,
                        url=url,
                        feed_type="rss",
                        source_tier=3,  # Quality News aggregate
                        language=lang_code,
                        is_active=True,
                    ))
                existing.add(url.lower().rstrip("/"))
                stats["new"] += 1

        # 2) Search query feeds
        for lang_code, queries in TOPIC_QUERIES.items():
            for name, query in queries:
                url = gnews_rss_url(query, lang_code)
                stats["total"] += 1

                if url.lower().rstrip("/") in existing:
                    stats["duplicate"] += 1
                    continue

                if not dry_run:
                    db.add(Feed(
                        name=name[:200],
                        rss_url=url,
                        url=url,
                        feed_type="rss",
                        source_tier=3,
                        language=lang_code,
                        is_active=True,
                    ))
                existing.add(url.lower().rstrip("/"))
                stats["new"] += 1

        if not dry_run:
            db.commit()
            print("💾 Committed")
    finally:
        db.close()

    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dry_run = "--dry" in sys.argv
    print(f"\n📰 Google News RSS Import — {'DRY RUN' if dry_run else 'LIVE'}")
    print("=" * 50)
    stats = import_google_news_feeds(dry_run=dry_run)
    print(f"\n📊 Results:")
    print(f"  Total: {stats['total']}")
    print(f"  New:   {stats['new']}")
    print(f"  Dupes: {stats['duplicate']}")
