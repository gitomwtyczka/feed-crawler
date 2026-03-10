"""
Authenticated source fetcher for closed/paywalled sources.

Supports login-based sources like:
- Newseria (info.newseria.pl) — HTML form login (video, transcripts, audio)
- ISBNews (portal.isbnews.pl) — HTTP Basic Auth (news agency dispatches)

Credentials are NEVER stored in code — loaded from .env only.
Each source has a dedicated fetcher class with login + scrape logic.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class AuthCredential:
    """Credential pair loaded from environment."""

    username: str
    password: str
    source_name: str

    @property
    def is_valid(self) -> bool:
        return bool(self.username and self.password)


def load_credential(source_slug: str) -> AuthCredential:
    """Load credentials for a source from environment variables.

    Convention: SOURCE_<SLUG>_USERNAME / SOURCE_<SLUG>_PASSWORD
    Example: SOURCE_NEWSERIA_USERNAME, SOURCE_NEWSERIA_PASSWORD
    """
    prefix = f"SOURCE_{source_slug.upper().replace('-', '_')}"
    username = os.getenv(f"{prefix}_USERNAME", "")
    password = os.getenv(f"{prefix}_PASSWORD", "")

    cred = AuthCredential(username=username, password=password, source_name=source_slug)
    if not cred.is_valid:
        logger.warning(
            "Credentials not configured for source: %s (set %s_USERNAME / %s_PASSWORD in .env)",
            source_slug, prefix, prefix,
        )
    return cred


class BaseAuthFetcher(ABC):
    """Base class for authenticated source fetchers."""

    def __init__(self, credential: AuthCredential):
        self.credential = credential
        self.is_logged_in = False

    @abstractmethod
    async def login(self, client: httpx.AsyncClient) -> bool:
        """Authenticate with the source. Returns True on success."""

    @abstractmethod
    async def fetch_articles(self, client: httpx.AsyncClient) -> list[dict]:
        """Fetch articles after successful login. Returns list of article dicts."""

    async def run(self) -> list[dict]:
        """Full cycle: login → fetch → return articles."""
        if not self.credential.is_valid:
            logger.error("Cannot fetch %s — credentials not configured", self.credential.source_name)
            return []

        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=30,
            headers={"User-Agent": "FeedCrawler/1.0"},
        ) as client:
            if not await self.login(client):
                logger.error("Login failed for %s", self.credential.source_name)
                return []

            self.is_logged_in = True
            articles = await self.fetch_articles(client)
            logger.info("%s: fetched %d articles", self.credential.source_name, len(articles))
            return articles


# ══════════════════════════════════════════════════
#  NEWSERIA — info.newseria.pl
#  Login: HTML form POST
#  Categories: BIZNES, LIFESTYLE, INNOWACJE
#  Media: video + transcriptions + audio
# ══════════════════════════════════════════════════


class NewseriaFetcher(BaseAuthFetcher):
    """Fetcher for info.newseria.pl.

    Login flow (discovered via browser inspection 2026-03-10):
    - Login URL: https://info.newseria.pl/?body=account
    - Form POST with fields:
      - id="emial"  (NOTE: typo in HTML — 'emial' not 'email')
      - id="haslo_uzytkownika" (password)
    - Submit button: class="btn btn-primary", value="ZALOGUJ SIĘ"
    - No CSRF token detected
    """

    BASE_URL = "https://info.newseria.pl"
    LOGIN_URL = f"{BASE_URL}/?body=account"

    async def login(self, client: httpx.AsyncClient) -> bool:
        """Login to Newseria via HTML form POST."""
        try:
            # GET login page (session cookies)
            await client.get(self.LOGIN_URL)

            # POST credentials — real field names from Newseria HTML
            login_data = {
                "emial": self.credential.username,  # NOTE: typo in Newseria HTML!
                "haslo_uzytkownika": self.credential.password,
            }
            response = await client.post(self.LOGIN_URL, data=login_data)

            # Check for successful login (redirect or content change)
            if response.status_code in (200, 302):
                # Verify we're actually logged in by checking response
                if "wyloguj" in response.text.lower() or "logout" in response.text.lower():
                    logger.info("Newseria login successful (user: %s)", self.credential.username)
                    return True
                # 200 but still seeing login form = failed
                if "zaloguj" in response.text.lower() and "emial" in response.text.lower():
                    logger.warning("Newseria login returned 200 but login form still visible — bad credentials?")
                    return False
                # Assume success if redirected
                logger.info("Newseria login returned %d — assuming success", response.status_code)
                return True

            logger.warning("Newseria login failed: HTTP %d", response.status_code)
            return False

        except Exception as e:
            logger.exception("Newseria login error: %s", e)
            return False

    async def fetch_articles(self, client: httpx.AsyncClient) -> list[dict]:
        """Fetch latest articles from all Newseria categories."""
        all_articles = []

        # Newseria categories (from navigation)
        categories = ["biznes", "lifestyle", "innowacje"]

        for category in categories:
            try:
                response = await client.get(f"{self.BASE_URL}/{category}")
                if response.status_code != 200:
                    logger.warning("Newseria /%s returned %d", category, response.status_code)
                    continue

                # Parse articles from HTML
                articles = self._parse_category_page(response.text, category)
                all_articles.extend(articles)
                logger.info("Newseria /%s: %d articles", category, len(articles))

            except Exception as e:
                logger.exception("Newseria /%s fetch error: %s", category, e)

        return all_articles

    def _parse_category_page(self, html: str, category: str) -> list[dict]:
        """Parse article list from Newseria category page.

        TODO: Implement HTML parsing after inspecting authenticated page.
        For now returns empty — needs BeautifulSoup or lxml.
        """
        # Placeholder — real parsing requires inspecting authenticated content
        logger.debug("Newseria /%s page: %d bytes (parsing not yet implemented)", category, len(html))
        return []


# ══════════════════════════════════════════════════
#  ISBNews — portal.isbnews.pl
#  Login: HTTP Basic Auth (no HTML form!)
#  Content: dispatches, calendar, macroeconomic data
#  Frequency: dozens of dispatches per day
# ══════════════════════════════════════════════════


class ISBNewsFetcher(BaseAuthFetcher):
    """Fetcher for portal.isbnews.pl.

    Login flow (discovered via browser inspection 2026-03-10):
    - portal.isbnews.pl uses HTTP Basic Auth (server-level, not HTML form)
    - Browser triggers native credential prompt
    - In httpx: pass credentials via httpx.BasicAuth

    Content structure:
    - Kalendarium ISBnews (corporate calendar)
    - Kalendarium makroekonomiczne (macroeconomic calendar)
    - Depesze (news dispatches) — dozens daily

    Must be monitored aggressively (fetch_interval: 5-10 min).
    """

    BASE_URL = "http://portal.isbnews.pl"

    async def login(self, client: httpx.AsyncClient) -> bool:
        """Verify credentials via HTTP Basic Auth."""
        try:
            auth = httpx.BasicAuth(
                username=self.credential.username,
                password=self.credential.password,
            )
            response = await client.get(self.BASE_URL, auth=auth)

            if response.status_code == 200:
                logger.info("ISBNews login successful (HTTP Basic Auth)")
                # Store auth for subsequent requests
                self._auth = auth
                return True
            if response.status_code == 401:
                logger.warning("ISBNews login failed: 401 Unauthorized — bad credentials")
                return False

            logger.warning("ISBNews returned unexpected status: %d", response.status_code)
            return False

        except Exception as e:
            logger.exception("ISBNews login error: %s", e)
            return False

    async def fetch_articles(self, client: httpx.AsyncClient) -> list[dict]:
        """Fetch today's dispatches from ISBNews portal."""
        all_articles = []
        auth = getattr(self, "_auth", None)

        try:
            # Fetch main portal page (dispatches)
            response = await client.get(self.BASE_URL, auth=auth)

            if response.status_code != 200:
                logger.warning("ISBNews portal returned %d", response.status_code)
                return []

            articles = self._parse_dispatches(response.text)
            all_articles.extend(articles)
            logger.info("ISBNews dispatches: %d articles", len(articles))

        except Exception as e:
            logger.exception("ISBNews fetch error: %s", e)

        return all_articles

    def _parse_dispatches(self, html: str) -> list[dict]:
        """Parse dispatch list from ISBNews portal page.

        TODO: Implement HTML parsing after inspecting authenticated content.
        Dispatches typically have: timestamp, title, category, full text.
        """
        logger.debug("ISBNews portal: %d bytes (parsing not yet implemented)", len(html))
        return []

    async def fetch_historical(self, client: httpx.AsyncClient, date: str) -> list[dict]:
        """Fetch dispatches from a specific date (calendar feature).

        Args:
            client: httpx client
            date: Date string in YYYY-MM-DD format

        Returns:
            List of dispatch articles from that date.
        """
        auth = getattr(self, "_auth", None)
        try:
            # ISBNews calendar URL pattern (to be discovered)
            response = await client.get(f"{self.BASE_URL}/depesze/{date}", auth=auth)
            if response.status_code == 200:
                return self._parse_dispatches(response.text)
            logger.warning("ISBNews calendar %s: HTTP %d", date, response.status_code)
        except Exception as e:
            logger.exception("ISBNews historical fetch error: %s", e)
        return []


# ── Registry of authenticated fetchers ──

AUTH_FETCHER_REGISTRY: dict[str, type[BaseAuthFetcher]] = {
    "newseria": NewseriaFetcher,
    "isbnews": ISBNewsFetcher,
}


async def fetch_authenticated_source(source_slug: str) -> list[dict]:
    """Fetch articles from an authenticated source by slug.

    Args:
        source_slug: Source identifier (e.g. 'newseria', 'isbnews')

    Returns:
        List of article dicts, empty if login fails or source unknown.
    """
    fetcher_class = AUTH_FETCHER_REGISTRY.get(source_slug)
    if not fetcher_class:
        logger.error("Unknown authenticated source: %s", source_slug)
        return []

    credential = load_credential(source_slug)
    fetcher = fetcher_class(credential)
    return await fetcher.run()
