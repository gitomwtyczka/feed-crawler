"""
Source Tier classification rules.

Classifies feeds into 5 tiers based on URL and name patterns:
    Tier 1: 🔬 Scientific     (PubMed, Nature, Science, Lancet, arXiv, CERN, ESA)
    Tier 2: 🎓 Industry/Expert (Think tanks, central banks, cybersec, B2B analysis)
    Tier 3: 📰 Quality News    (Wire services, national broadcasters, major papers)
    Tier 4: 📱 Portal/General  (Regional portals, lifestyle, entertainment, niche)
    Tier 5: 💬 User-Generated  (Blogs, podcasts, forums, recipe/photo sites)
"""

from __future__ import annotations

import re

# ── Tier classification rules (checked in order, first match wins) ──

TIER_RULES: list[tuple[int, list[str]]] = [
    # ════════════════════════════════════════════════
    # Tier 1: Scientific & Institutional Research
    # ════════════════════════════════════════════════
    (1, [
        # Journals & publishers
        r"pubmed", r"ncbi\.nlm", r"nature\.com", r"science\.org",
        r"sciencedirect", r"springer\.com", r"wiley\.com",
        r"thelancet", r"lancet\.com", r"nejm\.org", r"bmj\.com",
        r"arxiv\.org", r"biorxiv", r"medrxiv", r"plos\.org",
        r"cell\.com", r"sciencemag", r"jstor\.org",
        r"frontiersin\.org", r"mdpi\.com", r"hindawi",
        r"researchgate", r"academia\.edu", r"scholar\.google",
        # Space agencies
        r"nasa\.gov", r"esa\.int", r"home\.cern", r"cern\.ch",
        r"jaxa\.jp", r"spacex\.com/updates",
        # Health orgs
        r"who\.int", r"nih\.gov", r"cdc\.gov", r"ema\.europa",
        # Science news aggregators
        r"sciencedaily", r"eurekalert", r"phys\.org", r"newscientist",
        r"livescience", r"scientificamerican",
        # Statistical offices
        r"gus\.gov\.pl", r"eurostat", r"stat\.gov",
        # Universities / research
        r"cambridge\.org/research", r"oxford\.ac\.uk", r"mit\.edu/news",
        r"stanford\.edu/news", r"caltech\.edu",
        r"pan\.pl",  # Polska Akademia Nauk
        # Name-based
        r"\bcern\b", r"\besa\b.*space", r"\bnasa\b",
    ]),
    # ════════════════════════════════════════════════
    # Tier 2: Expert, Industry & Policy Analysis
    # ════════════════════════════════════════════════
    (2, [
        # Think tanks & policy
        r"brookings", r"rand\.org", r"cfr\.org", r"chathamhouse",
        r"foreignaffairs", r"foreignpolicy",
        r"atlantic\s*council", r"atlanticcouncil",
        r"carnegie", r"csis\.org", r"csis\b",
        r"bruegel\.org", r"bruegel\b",
        r"piism", r"ose\.gov\.pl",
        # Central banks & finance institutions
        r"ecb\.europa", r"fed\.gov", r"federalreserve",
        r"bankofengland", r"bank.of.england",
        r"boj\.or\.jp", r"bank.of.japan",
        r"bis\.org", r"imf\.org", r"worldbank",
        r"nbp\.pl",  # National Bank of Poland
        r"knf\.gov\.pl",  # KNF
        # Industry analysis
        r"statnews", r"stat\bnews", r"medpagetoday", r"medscape",
        r"irena\.org", r"iea\.org",
        r"theconversation", r"conversation\.com",
        r"technologyreview", r"mit\.edu",
        r"hbr\.org", r"mckinsey", r"deloitte\.com", r"pwc\.com",
        r"accenture\.com/blog", r"gartner\.com",
        # Tech industry
        r"openai\.com/blog", r"deepmind", r"research\.google",
        r"engineering\.fb", r"devblogs\.microsoft",
        r"aws\.amazon\.com/blog", r"cloud\.google\.com/blog",
        # Energy & specialized B2B
        r"biznesalert", r"cire\.pl",
        r"obserwatorfinansowy", r"cashless\.pl",
        r"newseria", r"biznes\.newseria",
        r"fintech\s*poland", r"comparic",
        # Cybersecurity
        r"checkpoint.*research", r"cyberdefence24", r"cyberbezpiecz",
        r"crowdstrike.*blog", r"mandiant", r"krebs\s*on\s*security",
        # Defense & military
        r"defence24", r"defense\.gov", r"defense\s*one",
        r"janes\.com",
        # Pharma
        r"fierce\s*pharma", r"fiercepharma",
        r"endpoints\.news", r"statnews\.com",
        # Legal
        r"prawo\.pl", r"codozasady",
        # Agriculture expert
        r"agrofakt", r"agronews", r"farmer\.pl", r"agrobiznes",
        # Automotive industry
        r"autocar\b", r"carscoops",
        # Real estate / construction
        r"builderpolska", r"builder\b.*polsk",
        # HR / Jobs
        r"bulldogjob",
        # Seeking Alpha (financial analysis)
        r"seekingalpha",
    ]),
    # ════════════════════════════════════════════════
    # Tier 3: Quality News
    # ════════════════════════════════════════════════
    (3, [
        # Wire services
        r"reuters\.com", r"reutersagency", r"apnews\.com", r"\bap\s*news\b",
        r"agencia\s*efe", r"efe\.com",
        r"adnkronos", r"kyodo\s*news",
        r"pap\.pl", r"isbnews",
        # Major broadcasters
        r"bbc\.com", r"bbc\.co\.uk", r"bbci\.co\.uk",
        r"cnn\.com", r"\bcnn\b.*world", r"\bcnn\b.*tech",
        r"abcnews", r"abc\.net\.au",
        r"cbsnews", r"cbs\s*news", r"face\s*the\s*nation",
        r"fox\s*news", r"foxnews",
        r"nbcnews", r"msnbc",
        r"cbc\.ca", r"\bcbc\b",
        r"npr\.org",
        r"pbs\.org",
        r"aljazeera", r"france24", r"dw\.com", r"euronews",
        r"channel\s*news\s*asia",
        r"nhk\.or\.jp",
        # Major newspapers — international
        r"theguardian", r"guardian\.com",
        r"nytimes\.com", r"washingtonpost",
        r"ft\.com", r"economist\.com",
        r"politico\.eu", r"politico\.com",
        r"bloomberg\.com", r"cnbc\.com", r"marketwatch",
        r"wsj\.com",
        r"faz\.net", r"spiegel\b", r"der\s*spiegel", r"die\s*zeit",
        r"elpais", r"el\s*pais", r"el\s*financiero", r"el\s*diario",
        r"lemonde", r"le\s*monde", r"l['']obs", r"nouvelobs",
        r"corriere", r"repubblica",
        r"bangkokpost", r"dawn\.com", r"\bdawn\b.*pakistan",
        r"scmp\.com", r"south\s*china",
        r"daily\s*maverick", r"crikey",
        r"brisbane\s*times", r"sydney\s*morning",
        r"globe\s*and\s*mail", r"financial\s*post",
        r"japan\s*times", r"nikkei",
        r"haaretz", r"times\s*of\s*israel",
        r"buenos\s*aires\s*times",
        # Major newspapers — Polish
        r"gazetaprawna", r"rp\.pl", r"rzeczpospolita",
        r"bankier\.pl", r"parkiet\.com",
        r"polsatnews", r"tvn24",
        r"rmf24", r"rmf\.fm",
        r"do\s*rzeczy", r"dorzeczy",
        r"wpolityce", r"newsweek\.pl",
        r"dziennik\.pl", r"fakt\.pl",
        r"super\s*express", r"se\.pl",
        # Quality digital news
        r"techcrunch", r"arstechnica", r"theverge\.com",
        r"wired\.com",
        r"propublica", r"axios\.com",
        r"fast\s*company", r"fastcompany",
        r"deadline\.com",
        r"investing\.com",
        r"economic\s*times",
        # Broadcast — other countries
        r"digi24", r"telex\.hu", r"hvg\.hu",
        r"dennik", r"dnevnik",
        r"unian",  # Ukraine
        r"focus\s*online",
        # Regional quality
        r"antyweb", r"benchmark\.pl",
        r"chip\.pl",
        r"echo\s*dnia",
        # Google News aggregation feeds
        r"news\.google\.com", r"\bgnews\b",
    ]),
    # ════════════════════════════════════════════════
    # Tier 5: User-Generated, Blogs, Podcasts
    # ════════════════════════════════════════════════
    (5, [
        # Social / aggregators
        r"reddit\.com",
        r"twitter\.com", r"x\.com",
        r"medium\.com/(?!@)", r"substack\.com",
        r"wordpress\.com", r"blogspot\.com", r"blogger\.com",
        r"tumblr\.com", r"livejournal",
        r"quora\.com", r"stackexchange", r"stackoverflow",
        r"forum\.", r"forums?\.",
        # Dev blogs
        r"css-tricks", r"coding\s*horror", r"code\s*wall", r"codenewbie",
        r"dev\.to\b",
        r"a\s*list\s*apart",
        r"dan\s*abramov", r"overreacted",
        r"david\s*walsh\s*blog",
        # Podcasts
        r"atp\.fm", r"relay\.fm",
        r"clockwise", r"accidental\s*tech",
        r"floss\s*weekly", r"developer\s*tea",
        # Food / recipe blogs
        r"cookbooks?\b", r"101\s*cook",
        r"babish", r"bon\s*app[eé]tit",
        r"chocolate.*zucchini", r"david\s*lebovitz",
        r"smitten\s*kitchen", r"shutterbean",
        r"minimalist\s*baker", r"cookie.*kate",
        r"duct\s*tape\s*marketing",
        # Book / reading blogs
        r"book\s*riot", r"aestas\s*book",
        r"year\s*of\s*reading",
        # Photo / humor
        r"awkward\s*family\s*photo", r"fail\s*blog",
        r"atlas\s*obscura",
        # Personal blogs
        r"benedict\s*evans", r"ben-evans",
        r"avc\.com", r"feld\s*thoughts",
        r"dave\s*winer",
        # Car / bike enthusiast
        r"bike\s*exif", r"bmw\s*blog",
        r"canon\s*rumors",
        # Auto video channels
        r"youtube\.com/feeds",
    ]),
    # Tier 4: Portal/General (everything else)
    # This is the default — handled in classify_feed()
]


def classify_feed(url: str, name: str = "") -> int:
    """Classify a feed into a tier (1-5) based on URL and name patterns.

    Returns tier number (1=Scientific, 2=Industry, 3=QualityNews, 4=Portal, 5=UGC).
    """
    text = f"{url} {name}".lower()

    for tier, patterns in TIER_RULES:
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return tier

    # Default: Tier 4 (Portal)
    return 4
