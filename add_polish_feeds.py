"""
Aggressive Polish Feed Discovery — one-shot script to find and add
RSS feeds from the top 100+ Polish news portals.

Run: python add_polish_feeds.py

[crawler-oracle 01] — accelerating PL infosphere coverage
"""

import sys
sys.path.insert(0, ".")

import httpx
import feedparser
import logging
from src.database import SessionLocal
from src.models import Feed

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Top Polish Portals with known RSS feeds ──

POLISH_FEEDS = [
    # ── Główne portale ──
    {"name": "Onet Wiadomości", "rss": "https://wiadomosci.onet.pl/.feedsRSS", "url": "https://onet.pl", "tier": 4},
    {"name": "WP Wiadomości", "rss": "https://wiadomosci.wp.pl/rss.xml", "url": "https://wp.pl", "tier": 4},
    {"name": "Interia Fakty", "rss": "https://fakty.interia.pl/feed", "url": "https://interia.pl", "tier": 4},
    {"name": "Gazeta.pl", "rss": "https://wiadomosci.gazeta.pl/pub/rss/wiadomosci.xml", "url": "https://gazeta.pl", "tier": 3},
    {"name": "TVN24", "rss": "https://tvn24.pl/najnowsze.xml", "url": "https://tvn24.pl", "tier": 3},
    {"name": "Polsat News", "rss": "https://www.polsatnews.pl/rss/polska.xml", "url": "https://polsatnews.pl", "tier": 3},

    # ── Dzienniki ogólnopolskie ──
    {"name": "Rzeczpospolita", "rss": "https://www.rp.pl/rss_main", "url": "https://rp.pl", "tier": 3},
    {"name": "Gazeta Wyborcza", "rss": "https://wyborcza.pl/0,0.html?disableRedirects=true", "url": "https://wyborcza.pl", "tier": 3},
    {"name": "Dziennik.pl", "rss": "https://www.dziennik.pl/rss.xml", "url": "https://dziennik.pl", "tier": 3},
    {"name": "Super Express", "rss": "https://www.se.pl/rss.xml", "url": "https://se.pl", "tier": 4},
    {"name": "Fakt", "rss": "https://www.fakt.pl/rss.xml", "url": "https://fakt.pl", "tier": 4},

    # ── Portale ekonomiczne / biznesowe ──
    {"name": "Money.pl", "rss": "https://www.money.pl/rss/rss.xml", "url": "https://money.pl", "tier": 3},
    {"name": "Bankier.pl", "rss": "https://www.bankier.pl/rss/wiadomosci.xml", "url": "https://bankier.pl", "tier": 3},
    {"name": "Puls Biznesu", "rss": "https://www.pb.pl/rss/najnowsze", "url": "https://pb.pl", "tier": 3},
    {"name": "Business Insider PL", "rss": "https://businessinsider.com.pl/.feedsRSS", "url": "https://businessinsider.com.pl", "tier": 3},
    {"name": "Forbes PL", "rss": "https://www.forbes.pl/rss", "url": "https://forbes.pl", "tier": 3},
    {"name": "Parkiet", "rss": "https://www.parkiet.com/rss_main", "url": "https://parkiet.com", "tier": 3},
    {"name": "ISBnews", "rss": "https://www.isbnews.pl/feed/", "url": "https://isbnews.pl", "tier": 2},
    {"name": "300Gospodarka", "rss": "https://300gospodarka.pl/feed", "url": "https://300gospodarka.pl", "tier": 2},

    # ── Technologia ──
    {"name": "Niebezpiecznik", "rss": "https://niebezpiecznik.pl/feed/", "url": "https://niebezpiecznik.pl", "tier": 2},
    {"name": "Dobreprogramy", "rss": "https://www.dobreprogramy.pl/rss", "url": "https://dobreprogramy.pl", "tier": 4},
    {"name": "Telepolis", "rss": "https://www.telepolis.pl/rss", "url": "https://telepolis.pl", "tier": 4},
    {"name": "Antyweb", "rss": "https://antyweb.pl/feed", "url": "https://antyweb.pl", "tier": 2},
    {"name": "Spider's Web", "rss": "https://spidersweb.pl/feed", "url": "https://spidersweb.pl", "tier": 2},
    {"name": "Benchmark.pl", "rss": "https://www.benchmark.pl/rss/aktualnosci.xml", "url": "https://benchmark.pl", "tier": 4},
    {"name": "Chip.pl", "rss": "https://www.chip.pl/feed", "url": "https://chip.pl", "tier": 4},
    {"name": "Komputer Świat", "rss": "https://www.komputerswiat.pl/rss", "url": "https://komputerswiat.pl", "tier": 4},

    # ── Polityka / Społeczeństwo ──
    {"name": "wPolityce.pl", "rss": "https://wpolityce.pl/rss.xml", "url": "https://wpolityce.pl", "tier": 3},
    {"name": "Niezależna.pl", "rss": "https://niezalezna.pl/rss.xml", "url": "https://niezalezna.pl", "tier": 3},
    {"name": "Do Rzeczy", "rss": "https://dorzeczy.pl/feed/", "url": "https://dorzeczy.pl", "tier": 3},
    {"name": "OKO.press", "rss": "https://oko.press/feed/", "url": "https://oko.press", "tier": 3},
    {"name": "Krytyka Polityczna", "rss": "https://krytykapolityczna.pl/feed/", "url": "https://krytykapolityczna.pl", "tier": 3},
    {"name": "Newsweek PL", "rss": "https://www.newsweek.pl/rss.xml", "url": "https://newsweek.pl", "tier": 3},
    {"name": "Polityka", "rss": "https://www.polityka.pl/rss/", "url": "https://polityka.pl", "tier": 3},
    {"name": "Tygodnik Powszechny", "rss": "https://www.tygodnikpowszechny.pl/rss.xml", "url": "https://tygodnikpowszechny.pl", "tier": 3},

    # ── Regionalne ──
    {"name": "Gazeta Krakowska", "rss": "https://gazetakrakowska.pl/rss", "url": "https://gazetakrakowska.pl", "tier": 4},
    {"name": "Dziennik Zachodni", "rss": "https://dziennikzachodni.pl/rss", "url": "https://dziennikzachodni.pl", "tier": 4},
    {"name": "Głos Wielkopolski", "rss": "https://gloswielkopolski.pl/rss", "url": "https://gloswielkopolski.pl", "tier": 4},
    {"name": "Kurier Lubelski", "rss": "https://kurierlubelski.pl/rss", "url": "https://kurierlubelski.pl", "tier": 4},
    {"name": "Gazeta Lubuska", "rss": "https://gazetalubuska.pl/rss", "url": "https://gazetalubuska.pl", "tier": 4},
    {"name": "Gazeta Pomorska", "rss": "https://pomorska.pl/rss", "url": "https://pomorska.pl", "tier": 4},
    {"name": "Dziennik Łódzki", "rss": "https://dzienniklodzki.pl/rss", "url": "https://dzienniklodzki.pl", "tier": 4},
    {"name": "Dziennik Bałtycki", "rss": "https://dziennikbaltycki.pl/rss", "url": "https://dziennikbaltycki.pl", "tier": 4},
    {"name": "Echo Dnia", "rss": "https://echodnia.eu/rss", "url": "https://echodnia.eu", "tier": 4},
    {"name": "Nowiny24", "rss": "https://nowiny24.pl/rss", "url": "https://nowiny24.pl", "tier": 4},
    {"name": "Nowa Trybuna Opolska", "rss": "https://nto.pl/rss", "url": "https://nto.pl", "tier": 4},
    {"name": "Gazeta Wrocławska", "rss": "https://gazetawroclawska.pl/rss", "url": "https://gazetawroclawska.pl", "tier": 4},
    {"name": "Głos Koszaliński", "rss": "https://gk24.pl/rss", "url": "https://gk24.pl", "tier": 4},
    {"name": "Kurier Poranny", "rss": "https://poranny.pl/rss", "url": "https://poranny.pl", "tier": 4},
    {"name": "Express Bydgoski", "rss": "https://expressbydgoski.pl/rss", "url": "https://expressbydgoski.pl", "tier": 4},
    {"name": "Gazeta Olsztyńska", "rss": "https://gazetaolsztynska.pl/rss.xml", "url": "https://gazetaolsztynska.pl", "tier": 4},

    # ── Branżowe ──
    {"name": "Wirtualne Media", "rss": "https://www.wirtualnemedia.pl/rss/wirtualnemedia_rss.xml", "url": "https://wirtualnemedia.pl", "tier": 2},
    {"name": "Press.pl", "rss": "https://www.press.pl/rss", "url": "https://press.pl", "tier": 2},
    {"name": "Rynek Zdrowia", "rss": "https://www.rynekzdrowia.pl/rss.xml", "url": "https://rynekzdrowia.pl", "tier": 2},
    {"name": "Prawo.pl", "rss": "https://www.prawo.pl/rss.xml", "url": "https://prawo.pl", "tier": 2},
    {"name": "Farmer.pl", "rss": "https://www.farmer.pl/rss.xml", "url": "https://farmer.pl", "tier": 2},
    {"name": "Transport Manager", "rss": "https://www.transport-manager.pl/feed/", "url": "https://transport-manager.pl", "tier": 2},
    {"name": "Defence24", "rss": "https://defence24.pl/rss.xml", "url": "https://defence24.pl", "tier": 2},
    {"name": "CyberDefence24", "rss": "https://cyberdefence24.pl/rss.xml", "url": "https://cyberdefence24.pl", "tier": 2},
    {"name": "Energetyka24", "rss": "https://energetyka24.com/rss.xml", "url": "https://energetyka24.com", "tier": 2},
    {"name": "Rynek Infrastruktury", "rss": "https://www.rynekinfrastruktury.pl/rss.xml", "url": "https://rynekinfrastruktury.pl", "tier": 2},

    # ── Naukowe ──
    {"name": "Nauka w Polsce (PAP)", "rss": "https://naukawpolsce.pl/rss.xml", "url": "https://naukawpolsce.pl", "tier": 1},
    {"name": "Crazy Nauka", "rss": "https://www.crazynauka.pl/feed/", "url": "https://crazynauka.pl", "tier": 1},
    {"name": "Kopalnia Wiedzy", "rss": "https://kopalniawiedzy.pl/rss/1", "url": "https://kopalniawiedzy.pl", "tier": 1},

    # ── Sport ──
    {"name": "Sport.pl", "rss": "https://sport.pl/rss.xml", "url": "https://sport.pl", "tier": 4},
    {"name": "Przegląd Sportowy", "rss": "https://www.przegladsportowy.pl/rss.xml", "url": "https://przegladsportowy.pl", "tier": 4},
    {"name": "Meczyki.pl", "rss": "https://www.meczyki.pl/rss.xml", "url": "https://meczyki.pl", "tier": 4},
    {"name": "WP SportoweFakty", "rss": "https://sportowefakty.wp.pl/rss.xml", "url": "https://sportowefakty.wp.pl", "tier": 4},

    # ── Kultura / Lifestyle ──
    {"name": "Culture.pl", "rss": "https://culture.pl/pl/rss.xml", "url": "https://culture.pl", "tier": 3},
    {"name": "Filmweb News", "rss": "https://www.filmweb.pl/feed/news/latest", "url": "https://filmweb.pl", "tier": 4},

    # ── Agencje prasowe ──
    {"name": "PAP", "rss": "https://www.pap.pl/rss.xml", "url": "https://pap.pl", "tier": 3},
    {"name": "PAP Biznes", "rss": "https://www.pap.pl/rss/biznes.xml", "url": "https://pap.pl", "tier": 2},

    # ── Samorząd / Administracja ──
    {"name": "Samorząd PAP", "rss": "https://samorzad.pap.pl/rss.xml", "url": "https://samorzad.pap.pl", "tier": 3},
    {"name": "Portal Samorządowy", "rss": "https://www.portalsamorzadowy.pl/rss.xml", "url": "https://portalsamorzadowy.pl", "tier": 3},
]


def validate_feed(rss_url: str) -> bool:
    """Quick check if RSS URL returns valid feed."""
    try:
        resp = httpx.get(rss_url, timeout=10, follow_redirects=True,
                        headers={"User-Agent": "FeedCrawler/1.0"})
        if resp.status_code != 200:
            return False
        parsed = feedparser.parse(resp.text)
        return len(parsed.entries) > 0
    except Exception:
        return False


def add_feeds():
    """Add all Polish feeds that don't already exist."""
    db = SessionLocal()
    try:
        existing_urls = {f.rss_url for f in db.query(Feed.rss_url).all()}
        existing_names = {f.name for f in db.query(Feed.name).all()}

        added = 0
        skipped = 0
        failed = 0

        for feed_data in POLISH_FEEDS:
            name = feed_data["name"]
            rss_url = feed_data["rss"]

            if rss_url in existing_urls or name in existing_names:
                logger.info("  ⏭️  %s — already exists", name)
                skipped += 1
                continue

            # Validate feed
            logger.info("  🔍 Checking %s...", name)
            if validate_feed(rss_url):
                feed = Feed(
                    name=name,
                    url=feed_data.get("url", ""),
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
                logger.info("  ❌ Invalid RSS: %s (%s)", name, rss_url)

        db.commit()
        logger.info("\n📊 Results: %d added, %d skipped, %d failed", added, skipped, failed)
        return {"added": added, "skipped": skipped, "failed": failed}

    finally:
        db.close()


if __name__ == "__main__":
    print("\n🇵🇱 Aggressive Polish Feed Discovery")
    print("=" * 50)
    print(f"Checking {len(POLISH_FEEDS)} feeds...\n")
    results = add_feeds()
    print(f"\n✅ Done: {results}")
