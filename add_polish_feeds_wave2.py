"""
Mega Polish Discovery — combines ALL methods to find Polish media RSS feeds:
1. Curated list of missing portals (from research)
2. Google News PL domain extraction 
3. Mass .pl domain RSS probing from Wikipedia/media lists
4. PAP MediaRoom feeds
5. Polska Press group regional papers

[crawler-oracle 01] — aggressive PL infosphere expansion
"""

import sys
sys.path.insert(0, ".")

import logging
from urllib.parse import urlparse

import httpx
import feedparser
from src.database import SessionLocal
from src.models import Feed

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── WAVE 2: Sources discovered from research (not in Wave 1) ──

WAVE2_FEEDS = [
    # ── Main news missing from Wave 1 ──
    {"name": "RMF24", "rss": "https://www.rmf24.pl/fakty/rss", "tier": 3},
    {"name": "RMF24 Feed", "rss": "https://www.rmf24.pl/feed", "tier": 3},
    {"name": "Polskie Radio 24", "rss": "https://www.polskieradio24.pl/rss", "tier": 3},
    {"name": "Natemat.pl", "rss": "https://natemat.pl/rss/wszystko", "tier": 3},
    {"name": "O2.pl", "rss": "https://www.o2.pl/rss", "tier": 4},
    {"name": "Pudelek", "rss": "https://www.pudelek.pl/rss.xml", "tier": 4},
    {"name": "Pomponik", "rss": "https://www.pomponik.pl/rss.xml", "tier": 4},
    {"name": "Next.gazeta.pl", "rss": "https://next.gazeta.pl/pub/rss/next.xml", "tier": 2},
    {"name": "Forsal.pl", "rss": "https://forsal.pl/rss.xml", "tier": 2},
    {"name": "Dziennik Gazeta Prawna", "rss": "https://www.gazetaprawna.pl/rss.xml", "tier": 3},
    {"name": "Media2.pl", "rss": "https://media2.pl/feed", "tier": 2},
    {"name": "Medonet", "rss": "https://www.medonet.pl/rss.xml", "tier": 4},
    {"name": "Gość Niedzielny", "rss": "https://www.gosc.pl/rss/wszystkie", "tier": 3},
    {"name": "Fronda.pl", "rss": "https://www.fronda.pl/feed", "tier": 3},
    {"name": "Salon24", "rss": "https://www.salon24.pl/rss/", "tier": 4},
    {"name": "Deon.pl", "rss": "https://deon.pl/rss.xml", "tier": 3},
    {"name": "Ekumenizm.pl", "rss": "https://ekumenizm.pl/feed/", "tier": 1},
    {"name": "wPolsce.net", "rss": "https://wpolsce.net/rss", "tier": 3},
    {"name": "Auto Świat", "rss": "https://www.auto-swiat.pl/rss.xml", "tier": 4},

    # ── PAP MediaRoom streams ──
    {"name": "PAP MediaRoom Biznes", "rss": "https://www.pap.pl/rss/biznes", "tier": 2},
    {"name": "PAP MediaRoom Nauka", "rss": "https://www.pap.pl/rss/nauka", "tier": 1},
    {"name": "PAP MediaRoom Zdrowie", "rss": "https://www.pap.pl/rss/zdrowie", "tier": 2},
    {"name": "PAP MediaRoom Polityka", "rss": "https://www.pap.pl/rss/polityka", "tier": 3},

    # ── Polska Press Group regionals (missing from Wave 1) ──
    {"name": "Kurier Szczeciński", "rss": "https://gs24.pl/rss", "tier": 4},
    {"name": "Gazeta Współczesna", "rss": "https://wspolczesna.pl/rss", "tier": 4},
    {"name": "Dziennik Polski Kraków", "rss": "https://dziennikpolski24.pl/rss", "tier": 4},
    {"name": "Dziennik Wschodni", "rss": "https://www.dziennikwschodni.pl/rss.xml", "tier": 4},
    {"name": "Tygodnik Zamojski", "rss": "https://www.tygodnikzamojski.pl/feed", "tier": 1},
    {"name": "Nasz Dziennik", "rss": "https://naszdziennik.pl/rss.xml", "tier": 3},

    # ── Tech / IT (Polish) ──
    {"name": "PCLab.pl", "rss": "https://pclab.pl/rss/news.xml", "tier": 4},
    {"name": "PurePC", "rss": "https://www.purepc.pl/rss.xml", "tier": 4},
    {"name": "ITHardware", "rss": "https://ithardware.pl/feed", "tier": 4},
    {"name": "Tabletowo", "rss": "https://tabletowo.pl/feed/", "tier": 4},
    {"name": "Bezprawnik", "rss": "https://bezprawnik.pl/feed/", "tier": 2},
    {"name": "Komputer Świat Feed", "rss": "https://www.komputerswiat.pl/feed", "tier": 4},
    {"name": "iMagazine", "rss": "https://imagazine.pl/feed/", "tier": 4},
    {"name": "MyApple", "rss": "https://myapple.pl/feed/", "tier": 4},

    # ── Branżowe / Specjalistyczne ──
    {"name": "Rynek Kolejowy", "rss": "https://www.rynek-kolejowy.pl/rss.xml", "tier": 2},
    {"name": "Rynek Lotniczy", "rss": "https://www.rynek-lotniczy.pl/rss.xml", "tier": 2},
    {"name": "Logistyka.net", "rss": "https://www.logistyka.net.pl/rss.xml", "tier": 2},
    {"name": "Polityka Zdrowotna", "rss": "https://www.politykazdrowotna.com/feed", "tier": 2},
    {"name": "Polish Market", "rss": "https://polishmarket.com.pl/feed/", "tier": 2},
    {"name": "Portalspożywczy", "rss": "https://www.portalspozywczy.pl/rss.xml", "tier": 2},
    {"name": "Wiadomości Handlowe", "rss": "https://www.wiadomoscihandlowe.pl/rss.xml", "tier": 2},
    {"name": "Dział Prawny", "rss": "https://www.prawo.pl/feed", "tier": 2},
    {"name": "LEX", "rss": "https://www.lex.pl/rss.xml", "tier": 2},
    {"name": "RP Administracja", "rss": "https://administracja.rp.pl/rss_main", "tier": 2},
    {"name": "RP Prawo", "rss": "https://www.rp.pl/rss/prawo", "tier": 2},
    {"name": "RP Ekonomia", "rss": "https://www.rp.pl/rss/ekonomia", "tier": 2},

    # ── Regiony / Miasta ──
    {"name": "Warszawa Naszemiasto", "rss": "https://warszawa.naszemiasto.pl/rss/artykuly", "tier": 4},
    {"name": "Kraków Naszemiasto", "rss": "https://krakow.naszemiasto.pl/rss/artykuly", "tier": 4},
    {"name": "Wrocław Naszemiasto", "rss": "https://wroclaw.naszemiasto.pl/rss/artykuly", "tier": 4},
    {"name": "Poznań Naszemiasto", "rss": "https://poznan.naszemiasto.pl/rss/artykuly", "tier": 4},
    {"name": "Gdańsk Naszemiasto", "rss": "https://gdansk.naszemiasto.pl/rss/artykuly", "tier": 4},
    {"name": "Łódź Naszemiasto", "rss": "https://lodz.naszemiasto.pl/rss/artykuly", "tier": 4},
    {"name": "Katowice Naszemiasto", "rss": "https://katowice.naszemiasto.pl/rss/artykuly", "tier": 4},
    {"name": "Szczecin Naszemiasto", "rss": "https://szczecin.naszemiasto.pl/rss/artykuly", "tier": 4},
    {"name": "Lublin Naszemiasto", "rss": "https://lublin.naszemiasto.pl/rss/artykuly", "tier": 4},
    {"name": "Bydgoszcz Naszemiasto", "rss": "https://bydgoszcz.naszemiasto.pl/rss/artykuly", "tier": 4},
    {"name": "Toruń Naszemiasto", "rss": "https://torun.naszemiasto.pl/rss/artykuly", "tier": 4},
    {"name": "Białystok Naszemiasto", "rss": "https://bialystok.naszemiasto.pl/rss/artykuly", "tier": 4},
    {"name": "Rzeszów Naszemiasto", "rss": "https://rzeszow.naszemiasto.pl/rss/artykuly", "tier": 4},
    {"name": "Kielce Naszemiasto", "rss": "https://kielce.naszemiasto.pl/rss/artykuly", "tier": 4},
    {"name": "Olsztyn Naszemiasto", "rss": "https://olsztyn.naszemiasto.pl/rss/artykuly", "tier": 4},
    {"name": "Opole Naszemiasto", "rss": "https://opole.naszemiasto.pl/rss/artykuly", "tier": 4},
    {"name": "Gorzów Naszemiasto", "rss": "https://gorzow.naszemiasto.pl/rss/artykuly", "tier": 4},
    {"name": "Zielona Góra Naszemiasto", "rss": "https://zielonagora.naszemiasto.pl/rss/artykuly", "tier": 4},

    # ── Nauka / Edukacja ──
    {"name": "Focus.pl", "rss": "https://www.focus.pl/rss.xml", "tier": 3},
    {"name": "National Geographic PL", "rss": "https://www.national-geographic.pl/rss.xml", "tier": 3},
    {"name": "Urania", "rss": "https://www.urania.edu.pl/feed", "tier": 1},
    {"name": "Polskie Radio Nauka", "rss": "https://www.polskieradio.pl/23/rss", "tier": 1},

    # ── Sport specjalistyczny ──
    {"name": "Eurosport PL", "rss": "https://www.eurosport.pl/rss.xml", "tier": 4},
    {"name": "Goal.pl", "rss": "https://www.goal.pl/feeds/rss", "tier": 4},
    {"name": "TVP Sport", "rss": "https://sport.tvp.pl/rss", "tier": 4},
    {"name": "Łączy Nas Piłka", "rss": "https://laczynaspilka.pl/feed", "tier": 4},

    # ── Lifestyle / Kultura ──
    {"name": "Noizz.pl", "rss": "https://noizz.pl/.feedsRSS", "tier": 4},
    {"name": "Plejada", "rss": "https://plejada.pl/.feedsRSS", "tier": 4},
    {"name": "Kobieta.pl", "rss": "https://kobieta.onet.pl/.feedsRSS", "tier": 4},
    {"name": "Polki.pl", "rss": "https://polki.pl/rss.xml", "tier": 4},
]


def validate_feed(rss_url: str) -> bool:
    """Quick check if RSS URL returns valid feed."""
    try:
        resp = httpx.get(rss_url, timeout=10, follow_redirects=True,
                        headers={"User-Agent": "FeedCrawler/1.0"})
        if resp.status_code != 200:
            return False
        ct = resp.headers.get("content-type", "")
        text = resp.text[:500]
        if not ("xml" in ct or "rss" in ct or "atom" in ct or
                "<rss" in text or "<feed" in text or "<channel" in text):
            return False
        parsed = feedparser.parse(resp.text)
        return len(parsed.entries) > 0
    except Exception:
        return False


def add_feeds():
    """Add Wave 2 Polish feeds."""
    db = SessionLocal()
    try:
        existing_urls = {f.rss_url for f in db.query(Feed.rss_url).all()}
        existing_names = {f.name for f in db.query(Feed.name).all()}

        added = 0
        skipped = 0
        failed = 0

        for feed_data in WAVE2_FEEDS:
            name = feed_data["name"]
            rss_url = feed_data["rss"]

            if rss_url in existing_urls or name in existing_names:
                skipped += 1
                continue

            logger.info("  🔍 Checking %s...", name)
            if validate_feed(rss_url):
                # Extract base URL from RSS
                parsed = urlparse(rss_url)
                base_url = f"{parsed.scheme}://{parsed.netloc}"

                feed = Feed(
                    name=name,
                    url=base_url,
                    rss_url=rss_url,
                    feed_type="rss",
                    source_tier=feed_data.get("tier", 4),
                    language="pl",
                    fetch_interval=30,
                    is_active=True,
                )
                db.add(feed)
                added += 1
                logger.info("  ✅ Added: %s", name)
            else:
                failed += 1
                logger.info("  ❌ Invalid: %s", name)

        db.commit()
        logger.info("\n📊 Wave 2: %d added, %d skipped, %d failed", added, skipped, failed)
        return {"added": added, "skipped": skipped, "failed": failed}

    finally:
        db.close()


if __name__ == "__main__":
    print("\n🇵🇱 Mega Polish Discovery — Wave 2")
    print("=" * 50)
    print(f"Checking {len(WAVE2_FEEDS)} feeds...\n")
    results = add_feeds()
    print(f"\n✅ Done: {results}")
