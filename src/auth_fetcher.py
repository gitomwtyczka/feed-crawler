"""
Authenticated source fetcher for closed/paywalled sources.

Supports:
- Newseria (info.newseria.pl) — RSS is public; login only for media downloads
- ISBNews (portal.isbnews.pl) — HTTP Basic Auth, AJAX API for dispatches

Credentials are NEVER stored in code — loaded from .env only.
"""

from __future__ import annotations

import json
import logging
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


# ── Credentials ──


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
            "Credentials for %s not configured (set %s_USERNAME / %s_PASSWORD in .env)",
            source_slug, prefix, prefix,
        )
    return cred


# ── Base fetcher ──


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
        """Fetch articles after successful login."""

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
#  RSS public feeds → handled by feed_parser (no login needed)
#  Login ONLY for on-demand media downloads (video/audio/transcripts)
# ══════════════════════════════════════════════════


class NewseriaMediaDownloader:
    """On-demand media downloader for Newseria articles.

    NOT a regular fetcher — called manually when user requests media.
    RSS feeds (biznes/lifestyle/innowacje.newseria.pl/rss.php) are public.

    Login flow (browser inspection 2026-03-10):
    - URL: https://info.newseria.pl/?body=account
    - Fields: "emial" (typo!), "haslo_uzytkownika"
    - No CSRF token

    Media download pattern:
    https://{subdomain}.newseria.pl/pobierz_plik.php?id={article_id}&f={field}&red={url}

    Fields:
    - plik_tv_selfile: Video (Full HD)
    - plik_mp4_selfile: Video (MP4)
    - plik_audio_selfile: Audio
    - plik_tekstowy_file: Transcript (PDF/TXT)
    - glowne_foto: Main image
    """

    LOGIN_URL = "https://info.newseria.pl/?body=account"

    # Media field names for download API
    MEDIA_FIELDS = {
        "video_hd": "plik_tv_selfile",
        "video_mp4": "plik_mp4_selfile",
        "audio": "plik_audio_selfile",
        "transcript": "plik_tekstowy_file",
        "image": "glowne_foto",
    }

    def __init__(self, credential: AuthCredential):
        self.credential = credential

    async def login(self, client: httpx.AsyncClient) -> bool:
        """Login to Newseria for media access."""
        try:
            await client.get(self.LOGIN_URL)
            response = await client.post(self.LOGIN_URL, data={
                "emial": self.credential.username,
                "haslo_uzytkownika": self.credential.password,
            })
            if "wyloguj" in response.text.lower():
                logger.info("Newseria login successful")
                return True
            logger.warning("Newseria login failed")
            return False
        except Exception as e:
            logger.exception("Newseria login error: %s", e)
            return False

    async def download_media(
        self, article_url: str, media_type: str = "transcript",
    ) -> bytes | None:
        """Download media file for a Newseria article.

        Args:
            article_url: Full article URL (e.g. https://biznes.newseria.pl/news/xxx,p123)
            media_type: One of: video_hd, video_mp4, audio, transcript, image

        Returns:
            File bytes or None on failure.
        """
        if not self.credential.is_valid:
            logger.error("Newseria credentials not configured")
            return None

        field = self.MEDIA_FIELDS.get(media_type)
        if not field:
            logger.error("Unknown media type: %s", media_type)
            return None

        # Extract article ID and subdomain from URL
        match = re.search(r"https?://(\w+)\.newseria\.pl/news/.*,p(\d+)", article_url)
        if not match:
            logger.error("Cannot parse Newseria article URL: %s", article_url)
            return None

        subdomain = match.group(1)
        article_id = match.group(2)
        download_url = (
            f"https://{subdomain}.newseria.pl/pobierz_plik.php"
            f"?id={article_id}&f={field}&red={article_url}"
        )

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=60,
            headers={"User-Agent": "FeedCrawler/1.0"},
        ) as client:
            if not await self.login(client):
                return None

            response = await client.get(download_url)
            if response.status_code == 200 and len(response.content) > 100:
                logger.info("Downloaded %s (%d bytes) for article %s",
                            media_type, len(response.content), article_id)
                return response.content

            logger.warning("Media download failed: HTTP %d (%d bytes)",
                           response.status_code, len(response.content))
            return None


# ══════════════════════════════════════════════════
#  ISBNews — portal.isbnews.pl
#  HTTP Basic Auth → AJAX API (portal_ajax)
#  Dispatches: dozens daily, aggressive monitoring
# ══════════════════════════════════════════════════


class ISBNewsFetcher(BaseAuthFetcher):
    """Fetcher for portal.isbnews.pl.

    Architecture (discovered 2026-03-10):
    - HTTP Basic Auth (server-level)
    - SPA with jQuery, split-pane layout
    - All data via AJAX POST to portal_ajax
    - Charset: iso-8859-2

    AJAX API:
    - DISPLAY_LIST: get dispatches for a date
      POST params: action=DISPLAY_LIST, art_date=YYYY-MM-DD (empty=today)
      Response: JSON {STATUS, RESPONSE (HTML), SQL}
      HTML contains: <td class='link-art' data-id='NNN'>Title</td>

    - DISPLAY_ARTICLE: get full article text
      POST params: action=DISPLAY_ARTICLE, id=NNN
      Response: JSON {STATUS, RESPONSE (HTML with full text)}
    """

    BASE_URL = "http://portal.isbnews.pl"
    AJAX_URL = f"{BASE_URL}/portal_ajax"

    async def login(self, client: httpx.AsyncClient) -> bool:
        """Verify credentials via HTTP Basic Auth."""
        try:
            self._auth = httpx.BasicAuth(
                username=self.credential.username,
                password=self.credential.password,
            )
            response = await client.get(self.BASE_URL, auth=self._auth)

            if response.status_code == 200:
                logger.info("ISBNews login successful (HTTP Basic Auth)")
                return True
            if response.status_code == 401:
                logger.warning("ISBNews: 401 Unauthorized")
                return False

            logger.warning("ISBNews: unexpected HTTP %d", response.status_code)
            return False

        except Exception as e:
            logger.exception("ISBNews login error: %s", e)
            return False

    async def fetch_articles(self, client: httpx.AsyncClient) -> list[dict]:
        """Fetch today's dispatches via AJAX API."""
        return await self._fetch_date(client, "")

    async def fetch_date(self, target_date: str) -> list[dict]:
        """Fetch dispatches for a specific date (public API).

        Args:
            target_date: Date string YYYY-MM-DD, or "" for today
        """
        if not self.credential.is_valid:
            logger.error("ISBNews credentials not configured")
            return []

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30,
            headers={"User-Agent": "FeedCrawler/1.0"},
        ) as client:
            if not await self.login(client):
                return []
            return await self._fetch_date(client, target_date)

    async def _fetch_date(self, client: httpx.AsyncClient, target_date: str) -> list[dict]:
        """Internal: fetch dispatches for a date via AJAX."""
        auth = getattr(self, "_auth", None)

        try:
            response = await client.post(
                self.AJAX_URL,
                data={
                    "action": "DISPLAY_LIST",
                    "art_date": target_date,
                    "czego": "", "gdzie": "", "range": "",
                    "tag": "", "dict_id": "", "dict_phrase": "",
                },
                auth=auth,
            )

            if response.status_code != 200:
                logger.warning("ISBNews AJAX returned HTTP %d", response.status_code)
                return []

            data = json.loads(response.content.decode("iso-8859-2"))
            if data.get("STATUS") != "OK":
                logger.warning("ISBNews AJAX status: %s", data.get("STATUS"))
                return []

            html = data.get("RESPONSE", "")
            dispatches = self._parse_dispatch_list(html)

            date_label = target_date or "today"
            logger.info("ISBNews %s: %d dispatches", date_label, len(dispatches))

            # Fetch full text for each dispatch
            articles = []
            for dispatch in dispatches:
                article = await self._fetch_article_detail(client, dispatch, auth)
                if article:
                    articles.append(article)

            return articles

        except Exception as e:
            logger.exception("ISBNews fetch error: %s", e)
            return []

    def _parse_dispatch_list(self, html: str) -> list[dict]:
        """Parse dispatch list from AJAX HTML response.

        HTML structure:
        <table class='lista-art' id='lista_art'>
          <tr>
            <td class='data-art'>HH:MM</td>
            <td class='data-art2'>:SS</td>
            <td class='link-art' data-id='428857'>Title</td>
            <td class='art-type'>TYPE</td>
          </tr>
        """
        soup = BeautifulSoup(html, "lxml")
        dispatches = []

        for td in soup.find_all("td", class_="link-art"):
            article_id = td.get("data-id", "")
            title = td.get_text(strip=True)
            if not article_id or not title:
                continue

            # Get time from sibling cells
            row = td.find_parent("tr")
            time_parts = []
            if row:
                for time_td in row.find_all("td", class_=re.compile(r"data-art")):
                    time_parts.append(time_td.get_text(strip=True))
            time_str = "".join(time_parts)

            dispatches.append({
                "id": article_id,
                "title": title,
                "time": time_str,
                "url": f"{self.BASE_URL}/#article/{article_id}",
            })

        return dispatches

    async def _fetch_article_detail(
        self, client: httpx.AsyncClient, dispatch: dict, auth: httpx.BasicAuth | None,
    ) -> dict | None:
        """Fetch full article text for a dispatch."""
        try:
            response = await client.post(
                self.AJAX_URL,
                data={"action": "DISPLAY_ARTICLE", "id": dispatch["id"]},
                auth=auth,
            )

            if response.status_code != 200:
                return None

            data = json.loads(response.content.decode("iso-8859-2"))
            if data.get("STATUS") != "OK":
                return None

            art_html = data.get("RESPONSE", "")
            soup = BeautifulSoup(art_html, "lxml")
            full_text = soup.get_text(separator="\n", strip=True)

            return {
                "id": dispatch["id"],
                "title": dispatch["title"],
                "time": dispatch["time"],
                "url": dispatch["url"],
                "content": full_text,
                "source": "isbnews",
            }

        except Exception as e:
            logger.debug("ISBNews article %s fetch error: %s", dispatch["id"], e)
            return None


# ── Registry ──

AUTH_FETCHER_REGISTRY: dict[str, type[BaseAuthFetcher]] = {
    "isbnews": ISBNewsFetcher,
}


async def fetch_authenticated_source(source_slug: str) -> list[dict]:
    """Fetch articles from an authenticated source.

    Args:
        source_slug: 'isbnews' (Newseria uses public RSS, no auth needed for articles)

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


async def download_newseria_media(
    article_url: str, media_type: str = "transcript",
) -> bytes | None:
    """Download media from a Newseria article (on-demand).

    Args:
        article_url: e.g. https://biznes.newseria.pl/news/xxx,p123
        media_type: video_hd, video_mp4, audio, transcript, image
    """
    credential = load_credential("newseria")
    downloader = NewseriaMediaDownloader(credential)
    return await downloader.download_media(article_url, media_type)
