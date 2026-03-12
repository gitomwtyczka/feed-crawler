"""
Google Alerts RSS Integration — adds Google Alerts as RSS feeds to the crawler.

HOW IT WORKS:
1. Go to https://www.google.com/alerts
2. Create alert for keyword (e.g. "Biedronka")
3. In "Show options" → change "Deliver to" from "Email" to "RSS feed"
4. Set "How often" to "As-it-happens" 
5. Set "Region" to "Poland"
6. Set "Language" to "Polish"
7. Click "Create Alert"
8. Right-click the RSS icon → "Copy link address"
9. Add the URL to GOOGLE_ALERTS below

The RSS URL looks like:
https://www.google.com/alerts/feeds/USERID/ALERTID

This script adds all configured alerts as feeds to the database.

[crawler-oracle 01] — Google Alerts integration for FMCG + brand monitoring
"""

import sys
sys.path.insert(0, ".")

import logging
from src.database import SessionLocal
from src.models import Feed

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Google Alerts RSS Feeds ──
# Add your Google Alerts RSS URLs here after creating them at google.com/alerts
# Format: {"name": "Alert: keyword", "rss": "https://www.google.com/alerts/feeds/..."}
#
# RECOMMENDED ALERTS TO CREATE:
#
# ── FMCG / Retail (solving the Biedronka gap) ──
# "Biedronka"         → retail, promotions, news
# "Lidl Polska"       → competitor
# "Żabka"             → convenience stores
# "Dino sklepy"       → Polish retail chain
# "Rossmann Polska"   → drugstores
# "Jeronimo Martins"  → Biedronka parent company
# "Eurocash"          → wholesale
# "Pepco"             → discount retail
#
# ── Major brands without good RSS coverage ──
# "PKP Intercity"     → rail transport
# "LOT Polish Airlines" → aviation
# "mBank"             → banking
# "PKO BP"            → banking
# "Poczta Polska"     → postal services
# "CCC buty"          → retail
# "LPP Reserved"      → fashion
# "CD Projekt"        → gaming
# "InPost"            → logistics
#
# ── Industry keywords ──
# "monitoring mediów"  → competitive intelligence
# "rynek FMCG Polska"  → industry reports
# "e-commerce Polska"  → e-commerce trends
# "energetyka OZE"     → renewable energy
# "cyberbezpieczeństwo Polska" → cybersecurity

GOOGLE_ALERTS = [
    # PASTE YOUR GOOGLE ALERTS RSS URLS HERE
    # Example:
    # {"name": "Alert: Biedronka", "rss": "https://www.google.com/alerts/feeds/12345/67890", "tier": 3},
    # {"name": "Alert: Żabka", "rss": "https://www.google.com/alerts/feeds/12345/11111", "tier": 3},
]

# ── Workaround: Google Alerts via direct RSS URL construction ──
# Google Alerts RSS can also be created via URL params (undocumented):
# https://www.google.com/alerts/feeds?params=...
# But this requires a logged-in session, so manual creation is more reliable.

# ── Alternative: Google News topic RSS feeds for FMCG ──
# These work without login!
GOOGLE_NEWS_FMCG = [
    {"name": "GNews PL: Biedronka", "rss": "https://news.google.com/rss/search?q=Biedronka&hl=pl&gl=PL&ceid=PL:pl", "tier": 3},
    {"name": "GNews PL: Lidl Polska", "rss": "https://news.google.com/rss/search?q=Lidl+Polska&hl=pl&gl=PL&ceid=PL:pl", "tier": 3},
    {"name": "GNews PL: Żabka", "rss": "https://news.google.com/rss/search?q=%C5%BBabka+sklep&hl=pl&gl=PL&ceid=PL:pl", "tier": 3},
    {"name": "GNews PL: Dino sklepy", "rss": "https://news.google.com/rss/search?q=Dino+sklepy&hl=pl&gl=PL&ceid=PL:pl", "tier": 3},
    {"name": "GNews PL: Rossmann", "rss": "https://news.google.com/rss/search?q=Rossmann+Polska&hl=pl&gl=PL&ceid=PL:pl", "tier": 3},
    {"name": "GNews PL: Pepco", "rss": "https://news.google.com/rss/search?q=Pepco+Polska&hl=pl&gl=PL&ceid=PL:pl", "tier": 3},
    {"name": "GNews PL: InPost", "rss": "https://news.google.com/rss/search?q=InPost&hl=pl&gl=PL&ceid=PL:pl", "tier": 3},
    {"name": "GNews PL: CD Projekt", "rss": "https://news.google.com/rss/search?q=CD+Projekt&hl=pl&gl=PL&ceid=PL:pl", "tier": 3},
    {"name": "GNews PL: mBank", "rss": "https://news.google.com/rss/search?q=mBank&hl=pl&gl=PL&ceid=PL:pl", "tier": 3},
    {"name": "GNews PL: PKO BP", "rss": "https://news.google.com/rss/search?q=PKO+BP&hl=pl&gl=PL&ceid=PL:pl", "tier": 3},
    {"name": "GNews PL: PZU", "rss": "https://news.google.com/rss/search?q=PZU+ubezpieczenia&hl=pl&gl=PL&ceid=PL:pl", "tier": 3},
    {"name": "GNews PL: LOT", "rss": "https://news.google.com/rss/search?q=LOT+Polish+Airlines&hl=pl&gl=PL&ceid=PL:pl", "tier": 3},
    {"name": "GNews PL: PKP", "rss": "https://news.google.com/rss/search?q=PKP+Intercity&hl=pl&gl=PL&ceid=PL:pl", "tier": 3},
    {"name": "GNews PL: Poczta Polska", "rss": "https://news.google.com/rss/search?q=Poczta+Polska&hl=pl&gl=PL&ceid=PL:pl", "tier": 3},
    {"name": "GNews PL: LPP", "rss": "https://news.google.com/rss/search?q=LPP+Reserved+Sinsay&hl=pl&gl=PL&ceid=PL:pl", "tier": 3},
    {"name": "GNews PL: Eurocash", "rss": "https://news.google.com/rss/search?q=Eurocash&hl=pl&gl=PL&ceid=PL:pl", "tier": 3},
    {"name": "GNews PL: CCC", "rss": "https://news.google.com/rss/search?q=CCC+buty&hl=pl&gl=PL&ceid=PL:pl", "tier": 3},
    {"name": "GNews PL: Jeronimo Martins", "rss": "https://news.google.com/rss/search?q=Jeronimo+Martins&hl=pl&gl=PL&ceid=PL:pl", "tier": 2},
    # Industry monitoring
    {"name": "GNews PL: FMCG rynek", "rss": "https://news.google.com/rss/search?q=FMCG+rynek+Polska&hl=pl&gl=PL&ceid=PL:pl", "tier": 2},
    {"name": "GNews PL: e-commerce PL", "rss": "https://news.google.com/rss/search?q=e-commerce+Polska+rynek&hl=pl&gl=PL&ceid=PL:pl", "tier": 2},
    {"name": "GNews PL: handel detaliczny", "rss": "https://news.google.com/rss/search?q=handel+detaliczny+Polska&hl=pl&gl=PL&ceid=PL:pl", "tier": 2},
]


def add_alerts():
    """Add Google Alerts + Google News brand feeds to database."""
    db = SessionLocal()
    try:
        existing = {f.name for f in db.query(Feed.name).all()}
        existing_urls = {f.rss_url for f in db.query(Feed.rss_url).all()}

        added = 0
        skipped = 0
        all_feeds = GOOGLE_ALERTS + GOOGLE_NEWS_FMCG

        for alert in all_feeds:
            if alert["name"] in existing or alert["rss"] in existing_urls:
                logger.info("  ⏭️  %s — already exists", alert["name"])
                skipped += 1
                continue

            feed = Feed(
                name=alert["name"],
                url="https://news.google.com",
                rss_url=alert["rss"],
                feed_type="google_alerts" if "alerts" in alert["rss"] else "google_news",
                source_tier=alert.get("tier", 3),
                language="pl",
                fetch_interval=15,  # Check every 15 min for alerts
                is_active=True,
            )
            db.add(feed)
            added += 1
            logger.info("  ✅ Added: %s", alert["name"])

        db.commit()
        logger.info("\n📊 Results: %d added, %d skipped", added, skipped)
        return {"added": added, "skipped": skipped}

    finally:
        db.close()


if __name__ == "__main__":
    print("\n📢 Google Alerts + FMCG Brand Monitoring")
    print("=" * 50)
    print(f"Alerts: {len(GOOGLE_ALERTS)}, GNews Brands: {len(GOOGLE_NEWS_FMCG)}")
    print()
    results = add_alerts()
    print(f"\n✅ Done: {results}")
