"""
Source Tier classification rules.

Classifies feeds into 5 tiers based on URL and name patterns:
    Tier 1: 🔬 Scientific     (PubMed, Nature, Science, Lancet, arXiv)
    Tier 2: 🎓 Industry/Expert (STAT News, BIS, IRENA, think tanks)
    Tier 3: 📰 Quality News    (Reuters, BBC, Guardian, PAP, ISBNews)
    Tier 4: 📱 Portal/General  (WP, Onet, TVN24, general portals)
    Tier 5: 💬 User-Generated  (Reddit, blogs, forums)
"""

from __future__ import annotations

import re

# ── Tier classification rules (checked in order, first match wins) ──

TIER_RULES: list[tuple[int, list[str]]] = [
    # Tier 1: Scientific
    (1, [
        r"pubmed", r"ncbi\.nlm", r"nature\.com", r"science\.org",
        r"sciencedirect", r"springer\.com", r"wiley\.com",
        r"thelancet", r"lancet\.com", r"nejm\.org", r"bmj\.com",
        r"arxiv\.org", r"biorxiv", r"medrxiv", r"plos\.org",
        r"cell\.com", r"sciencemag", r"jstor\.org",
        r"researchgate", r"academia\.edu", r"scholar\.google",
        r"frontiersin\.org", r"mdpi\.com", r"hindawi",
        r"who\.int", r"nih\.gov", r"cdc\.gov", r"ema\.europa",
        r"sciencedaily",
    ]),
    # Tier 2: Industry / Expert
    (2, [
        r"statnews", r"stat\.com", r"medpagetoday", r"medscape",
        r"bis\.org", r"imf\.org", r"worldbank", r"irena\.org",
        r"iea\.org", r"ecb\.europa", r"fed\.gov",
        r"brookings", r"rand\.org", r"cfr\.org", r"chathamhouse",
        r"foreignaffairs", r"foreignpolicy",
        r"theconversation", r"conversation\.com",
        r"technologyreview", r"mit\.edu",
        r"hbr\.org", r"mckinsey", r"deloitte\.com",
        r"eurostat", r"gus\.gov\.pl",
        r"openai\.com/blog", r"deepmind", r"research\.google",
        r"engineering\.fb", r"devblogs\.microsoft",
        r"newseria", r"biznes\.newseria",
        r"obserwatorfinansowy",
    ]),
    # Tier 3: Quality News
    (3, [
        r"reuters\.com", r"reutersagency", r"apnews\.com",
        r"bbc\.com", r"bbc\.co\.uk", r"bbci\.co\.uk",
        r"theguardian", r"guardian\.com",
        r"nytimes\.com", r"washingtonpost",
        r"ft\.com", r"economist\.com",
        r"politico\.eu", r"politico\.com",
        r"aljazeera", r"france24", r"dw\.com", r"euronews",
        r"pap\.pl", r"isbnews",
        r"gazetaprawna", r"rp\.pl", r"rzeczpospolita",
        r"bankier\.pl", r"parkiet\.com",
        r"bloomberg\.com", r"cnbc\.com", r"marketwatch",
        r"wsj\.com",
        r"techcrunch", r"arstechnica", r"theverge\.com",
        r"wired\.com",
        r"propublica", r"axios\.com",
        r"polsatnews", r"tvn24",
        r"rmf24", r"rmf\.fm",
    ]),
    # Tier 5: User-Generated (check BEFORE tier 4 catch-all)
    (5, [
        r"reddit\.com", r"reddit\.science",
        r"twitter\.com", r"x\.com",
        r"medium\.com/(?!@)", r"substack\.com",
        r"wordpress\.com", r"blogspot\.com", r"blogger\.com",
        r"tumblr\.com", r"livejournal",
        r"quora\.com", r"stackexchange", r"stackoverflow",
        r"forum\.", r"forums?\.",
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
