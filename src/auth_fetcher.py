"""
Authenticated source fetcher for closed/paywalled sources.

Supports login-based sources like:
- Newseria (info.newseria.pl) — video, transcripts, audio
- ISBNews (portal.isbnews.pl) — news agency dispatches

Credentials are NEVER stored in code — loaded from .env only.
Each source has a dedicated fetcher class with login + scrape logic.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

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
        logger.warning("Credentials not configured for source: %s (set %s_USERNAME and %s_PASSWORD in .env)", source_slug, prefix, prefix)
    return cred


class BaseAuthFetcher(ABC):
    """Base class for authenticated source fetchers."""

    def __init__(self, credential: AuthCredential):
        self.credential = credential
        self.session_cookies: dict = {}
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


class NewseriaFetcher(BaseAuthFetcher):
    """Fetcher for info.newseria.pl — video, transcripts, audio materials.

    Newseria is a multimedia news agency providing content in:
    - Politics, Economy, Lifestyle
    - Video + transcriptions + audio formats

    Login: form-based authentication at info.newseria.pl
    """

    BASE_URL = "https://info.newseria.pl"
    LOGIN_URL = f"{BASE_URL}/login"  # Placeholder — needs real endpoint discovery

    async def login(self, client: httpx.AsyncClient) -> bool:
        """Login to Newseria via form POST."""
        try:
            # Step 1: GET login page (for CSRF token if needed)
            login_page = await client.get(self.LOGIN_URL)
            if login_page.status_code != 200:
                logger.warning("Newseria login page returned %d", login_page.status_code)

            # Step 2: POST credentials
            # NOTE: Actual form fields need to be discovered by inspecting the login page
            # This is a template — will be refined after testing with real site
            login_data = {
                "username": self.credential.username,
                "password": self.credential.password,
            }
            response = await client.post(self.LOGIN_URL, data=login_data)

            if response.status_code in (200, 302):
                logger.info("Newseria login successful")
                return True

            logger.warning("Newseria login failed: HTTP %d", response.status_code)
            return False

        except Exception as e:
            logger.exception("Newseria login error: %s", e)
            return False

    async def fetch_articles(self, client: httpx.AsyncClient) -> list[dict]:
        """Fetch latest articles from Newseria after login.

        NOTE: Actual scraping logic needs to be implemented after
        inspecting the authenticated page structure.
        """
        try:
            # Fetch main content page
            response = await client.get(f"{self.BASE_URL}/news")

            if response.status_code != 200:
                logger.warning("Newseria content page returned %d", response.status_code)
                return []

            # TODO: Parse HTML response to extract articles
            # This requires inspecting the actual Newseria page structure
            # Typical fields: title, url, summary, category, media_type (video/audio/text)
            logger.info("Newseria page fetched (%d bytes) — parsing not yet implemented", len(response.text))
            return []

        except Exception as e:
            logger.exception("Newseria fetch error: %s", e)
            return []


class ISBNewsFetcher(BaseAuthFetcher):
    """Fetcher for portal.isbnews.pl — Polish news agency dispatches.

    ISBNews provides dozens of dispatches daily covering:
    - Business, economy, finance
    - Real-time breaking news

    Features:
    - Calendar-based navigation (can go back in time)
    - High-frequency updates (monitor throughout the day)
    - Needs aggressive fetch_interval (5-10 min)
    """

    BASE_URL = "http://portal.isbnews.pl"
    LOGIN_URL = f"{BASE_URL}"  # Placeholder — needs real endpoint discovery

    async def login(self, client: httpx.AsyncClient) -> bool:
        """Login to ISBNews via form POST."""
        try:
            login_page = await client.get(self.LOGIN_URL)

            # NOTE: Actual form fields need to be discovered
            login_data = {
                "username": self.credential.username,
                "password": self.credential.password,
            }
            response = await client.post(self.LOGIN_URL, data=login_data)

            if response.status_code in (200, 302):
                logger.info("ISBNews login successful")
                return True

            logger.warning("ISBNews login failed: HTTP %d", response.status_code)
            return False

        except Exception as e:
            logger.exception("ISBNews login error: %s", e)
            return False

    async def fetch_articles(self, client: httpx.AsyncClient) -> list[dict]:
        """Fetch latest dispatches from ISBNews after login.

        NOTE: Actual scraping logic needs to be implemented after
        inspecting the authenticated page structure. ISBNews has
        a calendar feature — we can fetch today's dispatches and
        optionally backfill from previous days.
        """
        try:
            # Fetch today's dispatches
            today = datetime.utcnow().strftime("%Y-%m-%d")
            response = await client.get(f"{self.BASE_URL}/depesze/{today}")

            if response.status_code != 200:
                logger.warning("ISBNews dispatches page returned %d", response.status_code)
                return []

            # TODO: Parse HTML response to extract dispatches
            # ISBNews dispatches are typically: title, time, category, full text
            logger.info("ISBNews page fetched (%d bytes) — parsing not yet implemented", len(response.text))
            return []

        except Exception as e:
            logger.exception("ISBNews fetch error: %s", e)
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
