"""
OPML Bulk Importer + Direct Feed Import — mass source acquisition.

Downloads OPML files and imports direct feed URLs into the database
with auto-tier classification.

Usage:
    python -m src.opml_importer          # import all
    python -m src.opml_importer --dry    # preview only
"""

from __future__ import annotations

import logging
import re
import sys
import xml.etree.ElementTree as ET

import httpx

sys.path.insert(0, "/app")

from src.database import SessionLocal
from src.models import Feed
from src.source_tiers import classify_feed

logger = logging.getLogger(__name__)

# ── OPML Sources to import ──

OPML_SOURCES: list[dict] = [
    # awesome-rss-feeds — countries
    {"name": "Poland", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Poland.opml"},
    {"name": "United Kingdom", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/United%20Kingdom.opml"},
    {"name": "United States", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/United%20States.opml"},
    {"name": "Germany", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Germany.opml"},
    {"name": "France", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/France.opml"},
    {"name": "India", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/India.opml"},
    {"name": "Australia", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Australia.opml"},
    {"name": "Canada", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Canada.opml"},
    {"name": "Brazil", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Brazil.opml"},
    {"name": "Spain", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Spain.opml"},
    {"name": "Italy", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Italy.opml"},
    {"name": "Japan", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Japan.opml"},
    {"name": "Russia", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Russia.opml"},
    {"name": "Mexico", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Mexico.opml"},
    {"name": "Ireland", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Ireland.opml"},
    {"name": "South Africa", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/South%20Africa.opml"},
    {"name": "Nigeria", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Nigeria.opml"},
    {"name": "Ukraine", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Ukraine.opml"},
    {"name": "Indonesia", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Indonesia.opml"},
    {"name": "Philippines", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Philippines.opml"},
    {"name": "Pakistan", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Pakistan.opml"},
    {"name": "Bangladesh", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Bangladesh.opml"},
    {"name": "Hong Kong", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Hong%20Kong%20SAR%20China.opml"},
    {"name": "Iran", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/countries/with_category/Iran.opml"},
    # awesome-rss-feeds — recommended (categories)
    {"name": "Tech", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Tech.opml"},
    {"name": "Science", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Science.opml"},
    {"name": "News", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/News.opml"},
    {"name": "Business", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Business%20%26%20Economy.opml"},
    {"name": "Programming", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Programming.opml"},
    {"name": "Sports", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Sports.opml"},
    {"name": "Gaming", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Gaming.opml"},
    {"name": "Movies", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Movies.opml"},
    {"name": "Music", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Music.opml"},
    {"name": "Food", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Food.opml"},
    {"name": "Travel", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Travel.opml"},
    {"name": "Fashion", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Fashion.opml"},
    {"name": "Books", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Books.opml"},
    {"name": "History", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/History.opml"},
    {"name": "Space", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Space.opml"},
    {"name": "Football", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Football.opml"},
    {"name": "Television", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Television.opml"},
    {"name": "Startups", "url": "https://raw.githubusercontent.com/plenaryapp/awesome-rss-feeds/master/recommended/with_category/Startups.opml"},
    # Feeds for Journalists
    {"name": "Journalists", "url": "https://raw.githubusercontent.com/scripting/feedsForJournalists/master/list.opml"},
]

# ── Direct Feed URLs (no OPML needed) ──
# Massive list of known RSS/Atom feeds from top global + Polish sources

DIRECT_FEEDS: list[tuple[str, str]] = [
    # ─── Tier 1: Scientific ───
    ("Nature", "https://www.nature.com/nature.rss"),
    ("Science Magazine", "https://www.science.org/rss/news_current.xml"),
    ("The Lancet", "https://www.thelancet.com/rssfeed/lancet_online.xml"),
    ("PNAS", "https://www.pnas.org/action/showFeed?type=etoc&feed=rss&jc=pnas"),
    ("Cell", "https://www.cell.com/cell/current.rss"),
    ("NEJM", "https://www.nejm.org/action/showFeed?jc=nejm&type=etoc&feed=rss"),
    ("BMJ", "https://www.bmj.com/rss/recent.xml"),
    ("PubMed Trending", "https://pubmed.ncbi.nlm.nih.gov/trending/rss/"),
    ("arXiv CS", "https://rss.arxiv.org/rss/cs"),
    ("arXiv Physics", "https://rss.arxiv.org/rss/physics"),
    ("arXiv Math", "https://rss.arxiv.org/rss/math"),
    ("arXiv Biology", "https://rss.arxiv.org/rss/q-bio"),
    ("arXiv AI", "https://rss.arxiv.org/rss/cs.AI"),
    ("arXiv ML", "https://rss.arxiv.org/rss/cs.LG"),
    ("WHO News", "https://www.who.int/rss-feeds/news-english.xml"),
    ("CDC MMWR", "https://tools.cdc.gov/api/v2/resources/media/403702.rss"),
    ("ScienceDaily", "https://www.sciencedaily.com/rss/all.xml"),
    ("New Scientist", "https://www.newscientist.com/feed/home/"),
    ("Scientific American", "https://rss.sciam.com/ScientificAmerican-Global"),
    ("Phys.org", "https://phys.org/rss-feed/"),
    ("NASA", "https://www.nasa.gov/rss/dyn/breaking_news.rss"),
    ("ESA", "https://www.esa.int/rssfeed/Our_Activities/Space_Science"),
    ("EurekAlert", "https://www.eurekalert.org/rss/technology_engineering.xml"),
    ("CERN", "https://home.cern/api/news/news/feed.rss"),
    ("MIT News", "https://news.mit.edu/rss/feed"),
    ("Stanford News", "https://news.stanford.edu/feed/"),
    ("Harvard Gazette", "https://news.harvard.edu/gazette/feed/"),
    ("Oxford Research", "https://www.ox.ac.uk/news-and-events/rss-feeds/research.xml"),
    ("Cambridge Research", "https://www.cam.ac.uk/research/news/feed"),
    # ─── Tier 2: Industry / Expert ───
    ("McKinsey Insights", "https://www.mckinsey.com/insights/rss"),
    ("Harvard Business Review", "https://feeds.hbr.org/harvardbusiness"),
    ("Brookings", "https://www.brookings.edu/feed/"),
    ("RAND", "https://www.rand.org/content/rand/blog.xml"),
    ("Foreign Affairs", "https://www.foreignaffairs.com/rss.xml"),
    ("Foreign Policy", "https://foreignpolicy.com/feed/"),
    ("Council on Foreign Relations", "https://www.cfr.org/rss/"),
    ("IMF Blog", "https://www.imf.org/en/News/rss?language=eng"),
    ("World Bank", "https://feeds.worldbank.org/topic/poverty"),
    ("ECB", "https://www.ecb.europa.eu/rss/press.html"),
    ("Fed Reserve", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("OECD", "https://www.oecd.org/newsroom/rss/"),
    ("WEF", "https://www.weforum.org/feed/"),
    ("IRENA", "https://www.irena.org/rss"),
    ("IEA", "https://www.iea.org/rss/"),
    ("Chatham House", "https://www.chathamhouse.org/rss"),
    ("Carnegie Endowment", "https://carnegieendowment.org/rss/solr/"),
    ("CSIS", "https://www.csis.org/analysis/feed"),
    ("Atlantic Council", "https://www.atlanticcouncil.org/feed/"),
    ("STAT News", "https://www.statnews.com/feed/"),
    ("MedPage Today", "https://www.medpagetoday.com/rss/headlines.xml"),
    ("Fierce Pharma", "https://www.fiercepharma.com/rss/xml"),
    ("Newseria Biznes", "https://biznes.newseria.pl/feed"),
    ("Newseria Innowacje", "https://innowacje.newseria.pl/feed"),
    ("Newseria Lifestyle", "https://lifestyle.newseria.pl/feed"),
    # ─── Tier 3: Quality News — Global ───
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("BBC UK", "https://feeds.bbci.co.uk/news/uk/rss.xml"),
    ("BBC Tech", "https://feeds.bbci.co.uk/news/technology/rss.xml"),
    ("BBC Science", "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml"),
    ("BBC Business", "https://feeds.bbci.co.uk/news/business/rss.xml"),
    ("BBC Health", "https://feeds.bbci.co.uk/news/health/rss.xml"),
    ("BBC Entertainment", "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml"),
    ("BBC Education", "https://feeds.bbci.co.uk/news/education/rss.xml"),
    ("BBC Sport", "https://feeds.bbci.co.uk/sport/rss.xml"),
    ("Reuters World", "https://www.reutersagency.com/feed/"),
    ("AP News", "https://rsshub.app/apnews/topics/apf-topnews"),
    ("NYT World", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"),
    ("NYT US", "https://rss.nytimes.com/services/xml/rss/nyt/US.xml"),
    ("NYT Business", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml"),
    ("NYT Technology", "https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml"),
    ("NYT Science", "https://rss.nytimes.com/services/xml/rss/nyt/Science.xml"),
    ("NYT Health", "https://rss.nytimes.com/services/xml/rss/nyt/Health.xml"),
    ("NYT Arts", "https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml"),
    ("NYT Opinion", "https://rss.nytimes.com/services/xml/rss/nyt/Opinion.xml"),
    ("Washington Post", "https://feeds.washingtonpost.com/rss/world"),
    ("Guardian World", "https://www.theguardian.com/world/rss"),
    ("Guardian UK", "https://www.theguardian.com/uk-news/rss"),
    ("Guardian Tech", "https://www.theguardian.com/uk/technology/rss"),
    ("Guardian Environment", "https://www.theguardian.com/environment/rss"),
    ("Guardian Business", "https://www.theguardian.com/uk/business/rss"),
    ("Guardian Science", "https://www.theguardian.com/science/rss"),
    ("Guardian Culture", "https://www.theguardian.com/uk/culture/rss"),
    ("Guardian Sport", "https://www.theguardian.com/uk/sport/rss"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("DW News", "https://rss.dw.com/xml/rss-en-all"),
    ("France24 EN", "https://www.france24.com/en/rss"),
    ("Euronews", "https://www.euronews.com/rss"),
    ("CNN World", "https://rss.cnn.com/rss/edition_world.rss"),
    ("CNN Business", "https://rss.cnn.com/rss/money_latest.rss"),
    ("CNN Tech", "https://rss.cnn.com/rss/edition_technology.rss"),
    ("ABC News", "https://abcnews.go.com/abcnews/internationalheadlines"),
    ("NPR News", "https://feeds.npr.org/1001/rss.xml"),
    ("NPR World", "https://feeds.npr.org/1004/rss.xml"),
    ("NPR Science", "https://feeds.npr.org/1007/rss.xml"),
    ("NPR Tech", "https://feeds.npr.org/1019/rss.xml"),
    ("PBS NewsHour", "https://www.pbs.org/newshour/feeds/rss/headlines"),
    ("The Economist", "https://www.economist.com/rss"),
    ("Financial Times", "https://www.ft.com/rss/home"),
    ("Bloomberg", "https://www.bloomberg.com/feed/podcast/etf-iq.xml"),
    ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114"),
    ("Wall Street Journal", "https://feeds.a]wsj.com/rss/RSSWorldNews.xml"),
    ("Forbes", "https://www.forbes.com/innovation/feed/"),
    ("Business Insider", "https://www.businessinsider.com/rss"),
    ("Politico", "https://www.politico.com/rss/politics08.xml"),
    ("Politico EU", "https://www.politico.eu/feed/"),
    ("The Hill", "https://thehill.com/feed/"),
    ("Axios", "https://api.axios.com/feed/"),
    ("Vox", "https://www.vox.com/rss/index.xml"),
    ("The Atlantic", "https://www.theatlantic.com/feed/all/"),
    ("Slate", "https://slate.com/feeds/all.rss"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
    ("Wired", "https://www.wired.com/feed/rss"),
    ("TechCrunch", "https://techcrunch.com/feed/"),
    ("Engadget", "https://www.engadget.com/rss.xml"),
    ("The Register", "https://www.theregister.com/headlines.atom"),
    ("Hacker News", "https://news.ycombinator.com/rss"),
    ("ZDNet", "https://www.zdnet.com/news/rss.xml"),
    ("CNET", "https://www.cnet.com/rss/all/"),
    ("9to5Mac", "https://9to5mac.com/feed/"),
    ("9to5Google", "https://9to5google.com/feed/"),
    ("The Information", "https://www.theinformation.com/feed"),
    ("Protocol", "https://www.protocol.com/feeds/feed.rss"),
    ("Rest of World", "https://restofworld.org/feed/"),
    ("Quartz", "https://qz.com/feed/"),
    # ─── Tier 3: Quality News — Poland ───
    ("PAP", "https://www.pap.pl/rss.xml"),
    ("TVN24", "https://tvn24.pl/najwazniejsze.xml"),
    ("TVN24 Biznes", "https://tvn24.pl/biznes/najwazniejsze.xml"),
    ("Polsat News", "https://www.polsatnews.pl/rss/polska.xml"),
    ("Gazeta Wyborcza", "https://wyborcza.pl/rss/"),
    ("Rzeczpospolita", "https://www.rp.pl/rss_main"),
    ("Bankier.pl", "https://www.bankier.pl/rss/wiadomosci.xml"),
    ("Money.pl", "https://www.money.pl/rss/rss.xml"),
    ("ISBnews", "https://www.isbnews.pl/feed/"),
    ("Puls Biznesu", "https://www.pb.pl/rss/"),
    ("Dziennik.pl", "https://www.dziennik.pl/rss/"),
    ("Forsal", "https://forsal.pl/rss.xml"),
    ("Spider's Web", "https://spidersweb.pl/feed"),
    ("Niebezpiecznik", "https://niebezpiecznik.pl/feed/"),
    ("Antyweb", "https://antyweb.pl/feed"),
    ("Chip.pl", "https://www.chip.pl/feed"),
    ("Komputer Świat", "https://www.komputerswiat.pl/rss/caly-serwis.xml"),
    ("Benchmark", "https://www.benchmark.pl/rss/aktualnosci-i-testy.xml"),
    ("Geekweek", "https://geekweek.interia.pl/feed"),
    ("Polskie Radio", "https://www.polskieradio.pl/rss/"),
    ("Radio ZET", "https://wiadomosci.radiozet.pl/rss.xml"),
    ("TOK FM", "https://www.tokfm.pl/rss/"),
    ("Gazeta Prawna", "https://www.gazetaprawna.pl/rss/"),
    ("Prawo.pl", "https://www.prawo.pl/rss/"),
    ("Medonet", "https://www.medonet.pl/rss.xml"),
    ("Zdrowie WPROST", "https://zdrowie.wprost.pl/feed"),
    ("Polityka Zdrowotna", "https://www.politykazdrowotna.com/feed"),
    ("Sport.pl", "https://sport.pl/rss.xml"),
    ("WP SportoweFakty", "https://sportowefakty.wp.pl/rss"),
    ("Przegląd Sportowy", "https://www.przegladsportowy.pl/rss.xml"),
    ("Meczyki", "https://www.meczyki.pl/rss"),
    ("Łączy Nas Piłka", "https://laczynaspilka.pl/feed"),
    ("Natemat", "https://natemat.pl/rss/najnowsze"),
    ("Noizz", "https://noizz.pl/rss"),
    ("Wprost", "https://www.wprost.pl/rss"),
    ("Newsweek PL", "https://www.newsweek.pl/rss"),
    ("Polityka", "https://www.polityka.pl/rss/"),
    ("Tygodnik Powszechny", "https://www.tygodnikpowszechny.pl/rss"),
    ("Kultura Liberalna", "https://kulturaliberalna.pl/feed/"),
    ("Krytyka Polityczna", "https://krytykapolityczna.pl/feed/"),
    # ─── Tier 3: Quality News — Europe ───
    ("Der Spiegel EN", "https://www.spiegel.de/international/index.rss"),
    ("Die Zeit EN", "https://www.zeit.de/english/index"),
    ("Le Monde EN", "https://www.lemonde.fr/en/rss/une.xml"),
    ("El Pais EN", "https://feeds.elpais.com/mrss-s/pages/ep/site/english.elpais.com/portada"),
    ("La Repubblica", "https://www.repubblica.it/rss/homepage/rss2.0.xml"),
    ("NOS (Netherlands)", "https://feeds.nos.nl/nosnieuwsalgemeen"),
    ("SVT (Sweden)", "https://www.svt.se/nyheter/rss.xml"),
    ("NRK (Norway)", "https://www.nrk.no/toppsaker.rss"),
    ("YLE (Finland)", "https://feeds.yle.fi/uutiset/v1/recent.rss?publisherIds=YLE_UUTISET"),
    ("RTE (Ireland)", "https://www.rte.ie/news/rss/news-headlines.xml"),
    ("SRF (Switzerland)", "https://www.srf.ch/news/bnf/rss/1890"),
    ("ORF (Austria)", "https://rss.orf.at/news.xml"),
    ("Jutarnji (Croatia)", "https://www.jutarnji.hr/feed"),
    ("Dnevnik (Slovenia)", "https://www.dnevnik.si/rss"),
    # ─── Tier 3: Quality News — Asia / Middle East ───
    ("Japan Times", "https://www.japantimes.co.jp/feed/"),
    ("South China Morning Post", "https://www.scmp.com/rss/91/feed"),
    ("Nikkei Asia", "https://asia.nikkei.com/rss"),
    ("The Hindu", "https://www.thehindu.com/feeder/default.rss"),
    ("Times of India", "https://timesofindia.indiatimes.com/rssfeeds/-2128936835.cms"),
    ("Dawn (Pakistan)", "https://www.dawn.com/feeds/home"),
    ("Haaretz", "https://www.haaretz.com/srv/haaretz-latest-headlines"),
    ("Jerusalem Post", "https://www.jpost.com/Rss/RssFeedsHeadlines.aspx"),
    ("Bangkok Post", "https://www.bangkokpost.com/rss/data/topstories.xml"),
    ("Straits Times", "https://www.straitstimes.com/news/world/rss.xml"),
    ("Channel News Asia", "https://www.channelnewsasia.com/rss"),
    # ─── Tier 3: Africa / Americas ───
    ("Mail & Guardian (SA)", "https://mg.co.za/feed/"),
    ("Daily Maverick (SA)", "https://www.dailymaverick.co.za/feed/"),
    ("Nation (Kenya)", "https://nation.africa/rss"),
    ("Punch (Nigeria)", "https://punchng.com/feed/"),
    ("Globe and Mail (Canada)", "https://www.theglobeandmail.com/arc/outboundfeeds/rss/category/world/"),
    ("The Star (Canada)", "https://www.thestar.com/content/thestar/feed.RSSManagerServlet.articles.topstories.rss"),
    ("Sydney Morning Herald", "https://www.smh.com.au/rss/feed.xml"),
    ("NZ Herald", "https://www.nzherald.co.nz/arc/outboundfeeds/rss/curated/78/?outputType=xml"),
    # ─── Tier 4: Portals — Poland ───
    ("WP.pl", "https://wiadomosci.wp.pl/rss.xml"),
    ("Onet", "https://wiadomosci.onet.pl/rss"),
    ("Interia", "https://fakty.interia.pl/rss"),
    ("Gazeta.pl", "https://wiadomosci.gazeta.pl/rss"),
    ("O2.pl", "https://www.o2.pl/rss"),
    ("Pudelek", "https://www.pudelek.pl/rss"),
    ("Pomponik", "https://pomponik.pl/rss"),
    ("SE.pl", "https://www.se.pl/rss/"),
    ("Fakt.pl", "https://www.fakt.pl/rss/"),
    # ─── Tier 5: UGC / Community ───
    ("Reddit World News", "https://www.reddit.com/r/worldnews/.rss"),
    ("Reddit Science", "https://www.reddit.com/r/science/.rss"),
    ("Reddit Technology", "https://www.reddit.com/r/technology/.rss"),
    ("Reddit Programming", "https://www.reddit.com/r/programming/.rss"),
    ("Reddit Poland", "https://www.reddit.com/r/polska/.rss"),
    ("Reddit Europe", "https://www.reddit.com/r/europe/.rss"),
    ("Reddit Space", "https://www.reddit.com/r/space/.rss"),
    ("Reddit AI", "https://www.reddit.com/r/artificial/.rss"),
    ("Reddit MachineLearning", "https://www.reddit.com/r/MachineLearning/.rss"),
    ("Reddit Futurology", "https://www.reddit.com/r/Futurology/.rss"),
    ("Lobsters", "https://lobste.rs/rss"),
    ("Dev.to", "https://dev.to/feed"),
    ("Hashnode", "https://hashnode.com/rss"),
]


def _sanitize_xml(text: str) -> str:
    """Fix common XML issues in OPML files (unescaped & in attributes)."""
    # Replace & not followed by amp; lt; gt; quot; apos; #
    return re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;|#)", "&amp;", text)


def parse_opml(xml_text: str) -> list[dict]:
    """Parse OPML XML and extract feed entries."""
    feeds = []
    try:
        sanitized = _sanitize_xml(xml_text)
        root = ET.fromstring(sanitized)  # noqa: S314
        for outline in root.iter("outline"):
            xml_url = outline.get("xmlUrl") or outline.get("xmlurl")
            if xml_url:
                name = (
                    outline.get("title")
                    or outline.get("text")
                    or xml_url.split("/")[2]
                )
                feeds.append({
                    "name": name.strip(),
                    "url": xml_url.strip(),
                })
    except ET.ParseError:
        logger.exception("Failed to parse OPML")

    return feeds


def import_feeds(dry_run: bool = False) -> dict:
    """Download all OPML sources and import feeds."""
    db = SessionLocal()
    stats = {"total_found": 0, "new": 0, "duplicate": 0, "errors": 0, "sources": 0}

    try:
        existing_urls = set()
        for (url,) in db.query(Feed.rss_url).filter(Feed.rss_url.isnot(None)).all():
            existing_urls.add(url.lower().rstrip("/"))

        client = httpx.Client(timeout=30, follow_redirects=True)

        # 1) OPML sources
        for source in OPML_SOURCES:
            try:
                resp = client.get(source["url"])
                if resp.status_code != 200:
                    logger.warning("OPML %s: HTTP %d", source["name"], resp.status_code)
                    stats["errors"] += 1
                    continue

                feeds = parse_opml(resp.text)
                source_new = 0
                for feed_data in feeds:
                    stats["total_found"] += 1
                    feed_url = feed_data["url"].lower().rstrip("/")
                    if feed_url in existing_urls:
                        stats["duplicate"] += 1
                        continue
                    tier = classify_feed(feed_data["url"], feed_data["name"])
                    if not dry_run:
                        db.add(Feed(
                            name=feed_data["name"][:200],
                            rss_url=feed_data["url"],
                            url=feed_data["url"],
                            feed_type="rss",
                            source_tier=tier,
                            is_active=True,
                        ))
                    existing_urls.add(feed_url)
                    stats["new"] += 1
                    source_new += 1
                stats["sources"] += 1
                print(f"  ✅ OPML {source['name']}: {len(feeds)} found, {source_new} new")
            except Exception:
                logger.exception("Error: %s", source["name"])
                stats["errors"] += 1

        # 2) Direct feeds
        direct_new = 0
        for name, url in DIRECT_FEEDS:
            stats["total_found"] += 1
            if url.lower().rstrip("/") in existing_urls:
                stats["duplicate"] += 1
                continue
            tier = classify_feed(url, name)
            if not dry_run:
                db.add(Feed(
                    name=name[:200],
                    rss_url=url,
                    url=url,
                    feed_type="rss",
                    source_tier=tier,
                    is_active=True,
                ))
            existing_urls.add(url.lower().rstrip("/"))
            stats["new"] += 1
            direct_new += 1
        print(f"  ✅ Direct feeds: {len(DIRECT_FEEDS)} total, {direct_new} new")
        stats["sources"] += 1

        if not dry_run:
            db.commit()
            print("\n💾 Committed to database")

        client.close()
    finally:
        db.close()

    return stats


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    dry_run = "--dry" in sys.argv
    print(f"\n🚀 Mass Source Import — {'DRY RUN' if dry_run else 'LIVE'}")
    print("=" * 50)
    stats = import_feeds(dry_run=dry_run)
    print(f"\n📊 Results:")
    print(f"  Sources: {stats['sources']}")
    print(f"  Found:   {stats['total_found']}")
    print(f"  New:     {stats['new']}")
    print(f"  Dupes:   {stats['duplicate']}")
    print(f"  Errors:  {stats['errors']}")

