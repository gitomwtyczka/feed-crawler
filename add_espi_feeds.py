"""
ESPI/EBI + PAP Institutional Feeds — mandatory stock exchange reports.

ESPI = Elektroniczny System Przekazywania Informacji (mandatory corporate reports)
EBI = Elektroniczny Biuletyn Informacyjny (NewConnect reports)
PAP = Polska Agencja Prasowa (Polish Press Agency)

These are INSTITUTIONAL sources — every listed company in Poland MUST publish
reports through ESPI/EBI. This is law (EU MAR regulation).

[crawler-oracle 01] — institutional financial feeds
"""

import sys
sys.path.insert(0, ".")

import logging
from src.database import SessionLocal
from src.models import Feed

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Institutional Financial Feeds ──
INSTITUTIONAL_FEEDS = [
    # PAP Biznes — official ESPI/EBI distributor
    {"name": "PAP Biznes ESPI", "rss": "https://biznes.pap.pl/pl/espi/rss", "tier": 1, "type": "rss"},
    {"name": "PAP Biznes EBI", "rss": "https://biznes.pap.pl/pl/ebi/rss", "tier": 1, "type": "rss"},
    {"name": "PAP Biznes Notowania", "rss": "https://biznes.pap.pl/pl/notowania/rss", "tier": 1, "type": "rss"},
    {"name": "PAP Biznes News", "rss": "https://biznes.pap.pl/pl/news/rss", "tier": 1, "type": "rss"},

    # GPW — Warsaw Stock Exchange
    {"name": "GPW Komunikaty", "rss": "https://www.gpw.pl/komunikaty?type=rss", "tier": 1, "type": "rss"},
    {"name": "GPW Giełda", "rss": "https://www.gpw.pl/news?type=rss", "tier": 1, "type": "rss"},

    # StockWatch — professional stock analysis
    {"name": "StockWatch.pl", "rss": "https://www.stockwatch.pl/rss/", "tier": 2, "type": "rss"},
    {"name": "StockWatch ESPI", "rss": "https://www.stockwatch.pl/rss/espi/", "tier": 2, "type": "rss"},

    # Stooq — stock data
    {"name": "Stooq Wiadomości", "rss": "https://stooq.pl/rss/", "tier": 2, "type": "rss"},

    # Parkiet — stock market daily
    {"name": "Parkiet.com", "rss": "https://www.parkiet.com/rss.xml", "tier": 1, "type": "rss"},

    # Puls Biznesu
    {"name": "Puls Biznesu", "rss": "https://www.pb.pl/rss/", "tier": 1, "type": "rss"},

    # KNF — financial regulator
    {"name": "GNews PL: KNF regulator", "rss": "https://news.google.com/rss/search?q=KNF+Komisja+Nadzoru+Finansowego&hl=pl&gl=PL&ceid=PL:pl", "tier": 2, "type": "google_news"},

    # GPW via Google News (backup)
    {"name": "GNews PL: GPW giełda", "rss": "https://news.google.com/rss/search?q=GPW+giełda+warszawska&hl=pl&gl=PL&ceid=PL:pl", "tier": 2, "type": "google_news"},

    # Obligacje — bond market
    {"name": "Obligacje.pl", "rss": "https://obligacje.pl/pl/rss/", "tier": 2, "type": "rss"},

    # Analizy.pl — fund analysis
    {"name": "Analizy.pl", "rss": "https://www.analizy.pl/rss", "tier": 2, "type": "rss"},
]


def add_institutional():
    """Add institutional financial feeds to database."""
    db = SessionLocal()
    try:
        existing_names = {f.name for f in db.query(Feed.name).all()}
        existing_urls = {f.rss_url for f in db.query(Feed.rss_url).all()}

        added = 0
        skipped = 0

        for feed_info in INSTITUTIONAL_FEEDS:
            if feed_info["name"] in existing_names or feed_info["rss"] in existing_urls:
                logger.info("  ⏭️  %s — already exists", feed_info["name"])
                skipped += 1
                continue

            feed = Feed(
                name=feed_info["name"],
                url=feed_info["rss"].split("/rss")[0] if "/rss" in feed_info["rss"] else feed_info["rss"],
                rss_url=feed_info["rss"],
                feed_type=feed_info.get("type", "rss"),
                source_tier=feed_info["tier"],
                language="pl",
                fetch_interval=30 if feed_info["tier"] == 1 else 60,
                is_active=True,
            )
            db.add(feed)
            added += 1
            logger.info("  ✅ Added: %s (tier %d)", feed_info["name"], feed_info["tier"])

        db.commit()
        logger.info("\n📊 Results: %d added, %d skipped", added, skipped)
        return {"added": added, "skipped": skipped}

    finally:
        db.close()


if __name__ == "__main__":
    print("\n🏛️ ESPI/EBI + Institutional Financial Feeds")
    print("=" * 50)
    print(f"Feeds to add: {len(INSTITUTIONAL_FEEDS)}")
    print()
    results = add_institutional()
    print(f"\n✅ Done: {results}")
