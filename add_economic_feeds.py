"""Dodaj źródła ekonomiczne do sources.yaml.

Kategorie:
- Banki centralne (ECB, Fed, NBP, BOE, BOJ, SNB)
- Organizacje międzynarodowe (Bank Światowy, IMF, BIS, OECD, WTO)
- Agencje ratingowe (Moody's, S&P, Fitch - public feeds)
- Dane ekonomiczne (Eurostat, GUS, FRED blog)
- Prasa finansowa (FT, WSJ, Economist - open RSS)
"""
import yaml
from pathlib import Path

ECONOMIC_FEEDS = [
    # ── Banki Centralne ──
    {"name": "ECB Press Releases", "rss_url": "https://www.ecb.europa.eu/rss/press.html", "url": "https://www.ecb.europa.eu", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "ECB Publications", "rss_url": "https://www.ecb.europa.eu/rss/pub.html", "url": "https://www.ecb.europa.eu", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "ECB Working Papers", "rss_url": "https://www.ecb.europa.eu/rss/wppub.html", "url": "https://www.ecb.europa.eu", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "ECB Statistics", "rss_url": "https://www.ecb.europa.eu/rss/stats.html", "url": "https://www.ecb.europa.eu", "feed_type": "rss", "departments": ["ekonomia", "statystyki"]},
    {"name": "ECB Blog", "rss_url": "https://www.ecb.europa.eu/rss/blog.html", "url": "https://www.ecb.europa.eu", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "Federal Reserve Press Releases", "rss_url": "https://www.federalreserve.gov/feeds/press_all.xml", "url": "https://www.federalreserve.gov", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "Federal Reserve Speeches", "rss_url": "https://www.federalreserve.gov/feeds/speeches.xml", "url": "https://www.federalreserve.gov", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "Fed St. Louis - On The Economy", "rss_url": "https://www.stlouisfed.org/on-the-economy/rss", "url": "https://www.stlouisfed.org", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "Fed NY Liberty Street Economics", "rss_url": "https://libertystreeteconomics.newyorkfed.org/feed/", "url": "https://libertystreeteconomics.newyorkfed.org", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "Bank of England News", "rss_url": "https://www.bankofengland.co.uk/rss/news", "url": "https://www.bankofengland.co.uk", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "Bank of England Publications", "rss_url": "https://www.bankofengland.co.uk/rss/publications", "url": "https://www.bankofengland.co.uk", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "Bank of Japan Releases", "rss_url": "https://www.boj.or.jp/en/rss/whatsnew.xml", "url": "https://www.boj.or.jp", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "Swiss National Bank News", "rss_url": "https://www.snb.ch/en/mmr/reference/rss_en/source/rss_en.en.xml", "url": "https://www.snb.ch", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "Reserve Bank of Australia", "rss_url": "https://www.rba.gov.au/rss/rss-cb-media-releases.xml", "url": "https://www.rba.gov.au", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "NBP Kursy Walut", "rss_url": "https://rss.nbp.pl/kursy/TabelaA.xml", "url": "https://www.nbp.pl", "feed_type": "rss", "departments": ["ekonomia", "statystyki"]},

    # ── Organizacje Międzynarodowe ──
    {"name": "World Bank Blog", "rss_url": "https://blogs.worldbank.org/feed", "url": "https://www.worldbank.org", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "World Bank Data Blog", "rss_url": "https://blogs.worldbank.org/opendata/feed", "url": "https://www.worldbank.org", "feed_type": "rss", "departments": ["ekonomia", "statystyki"]},
    {"name": "IMF Blog", "rss_url": "https://www.imf.org/en/Blogs/rss", "url": "https://www.imf.org", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "IMF News", "rss_url": "https://www.imf.org/en/News/rss.xml", "url": "https://www.imf.org", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "BIS Press Releases", "rss_url": "https://www.bis.org/doclist/press.rss", "url": "https://www.bis.org", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "BIS Working Papers", "rss_url": "https://www.bis.org/doclist/wppub.rss", "url": "https://www.bis.org", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "OECD News", "rss_url": "https://www.oecd.org/newsroom/news.xml", "url": "https://www.oecd.org", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "OECD Economy", "rss_url": "https://www.oecd.org/economy/rss/index.xml", "url": "https://www.oecd.org", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "WTO News", "rss_url": "https://www.wto.org/english/news_e/news_rss_e.xml", "url": "https://www.wto.org", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "UN News Economic Development", "rss_url": "https://news.un.org/feed/subscribe/en/news/topic/economic-development/feed/rss.xml", "url": "https://news.un.org", "feed_type": "rss", "departments": ["ekonomia"]},

    # ── Agencje Ratingowe i Doradztwo ──
    {"name": "Moody's Research", "rss_url": "https://www.moodys.com/feed/rss/Moodys_Research", "url": "https://www.moodys.com", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "S&P Global Market Intelligence", "rss_url": "https://www.spglobal.com/marketintelligence/en/rss-feed/topic/economy", "url": "https://www.spglobal.com", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "Fitch Ratings", "rss_url": "https://www.fitchratings.com/rss/research/sovereigns", "url": "https://www.fitchratings.com", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "McKinsey Insights", "rss_url": "https://www.mckinsey.com/insights/rss", "url": "https://www.mckinsey.com", "feed_type": "rss", "departments": ["ekonomia"]},

    # ── Dane Statystyczne ──
    {"name": "Eurostat News", "rss_url": "https://ec.europa.eu/eurostat/api/dissemination/rss/news", "url": "https://ec.europa.eu/eurostat", "feed_type": "rss", "departments": ["statystyki", "ekonomia"]},
    {"name": "GUS Komunikaty", "rss_url": "https://stat.gov.pl/rss/", "url": "https://stat.gov.pl", "feed_type": "rss", "departments": ["statystyki"]},

    # ── Prasa Finansowa / Ekonomiczna ──
    {"name": "Financial Times World", "rss_url": "https://www.ft.com/world?format=rss", "url": "https://www.ft.com", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "The Economist", "rss_url": "https://www.economist.com/finance-and-economics/rss.xml", "url": "https://www.economist.com", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "MarketWatch", "rss_url": "http://feeds.marketwatch.com/marketwatch/topstories/", "url": "https://www.marketwatch.com", "feed_type": "rss", "departments": ["ekonomia", "konkurencja-biznes"]},
    {"name": "Investopedia News", "rss_url": "https://www.investopedia.com/feedbuilder/feed/getfeed/?feedName=rss_headline", "url": "https://www.investopedia.com", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "Bankier.pl", "rss_url": "https://www.bankier.pl/rss/wiadomosci.xml", "url": "https://www.bankier.pl", "feed_type": "rss", "departments": ["ekonomia", "konkurencja-biznes"]},
    {"name": "Money.pl", "rss_url": "https://www.money.pl/rss/rss.xml", "url": "https://www.money.pl", "feed_type": "rss", "departments": ["ekonomia", "konkurencja-biznes"]},
    {"name": "Obserwator Finansowy (NBP)", "rss_url": "https://www.obserwatorfinansowy.pl/feed/", "url": "https://www.obserwatorfinansowy.pl", "feed_type": "rss", "departments": ["ekonomia"]},
    {"name": "Parkiet", "rss_url": "https://www.parkiet.com/rss.xml", "url": "https://www.parkiet.com", "feed_type": "rss", "departments": ["ekonomia", "konkurencja-biznes"]},
    {"name": "Puls Biznesu", "rss_url": "https://www.pb.pl/rss/all.xml", "url": "https://www.pb.pl", "feed_type": "rss", "departments": ["ekonomia", "konkurencja-biznes"]},
    {"name": "Złoty Blog NBP", "rss_url": "https://www.nbp.pl/publikacje/rss/rss_nowosci.xml", "url": "https://www.nbp.pl", "feed_type": "rss", "departments": ["ekonomia"]},
]


def main():
    config_path = Path("config/sources.yaml")
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    existing_urls = {s.get("rss_url", "").lower().rstrip("/") for s in config["sources"]}
    existing_names = {s.get("name", "").lower() for s in config["sources"]}

    added = 0
    skipped = 0
    for feed in ECONOMIC_FEEDS:
        key = feed["rss_url"].lower().rstrip("/")
        if key in existing_urls or feed["name"].lower() in existing_names:
            print(f"  SKIP (exists): {feed['name']}")
            skipped += 1
            continue
        config["sources"].append({
            "name": feed["name"],
            "url": feed.get("url", ""),
            "rss_url": feed["rss_url"],
            "feed_type": feed["feed_type"],
            "fetch_interval": 60,
            "departments": feed.get("departments", ["ekonomia"]),
        })
        existing_urls.add(key)
        existing_names.add(feed["name"].lower())
        added += 1
        print(f"  ADD: {feed['name']}")

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"\nDodano: {added}, Pominięto: {skipped}")
    print(f"Łącznie feedów: {len(config['sources'])}")


if __name__ == "__main__":
    main()
