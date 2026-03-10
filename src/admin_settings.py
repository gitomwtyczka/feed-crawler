"""
Admin settings — persistent key-value config stored in data/settings.json.

Stores: ISBNews credentials, Discord webhook, SaaS webhook, etc.
All values are editable via /admin/settings form.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

SETTINGS_PATH = Path(os.getenv("DATA_DIR", "data")) / "settings.json"

# Default settings (empty)
DEFAULTS: dict[str, str] = {
    "isbnews_username": "",
    "isbnews_password": "",
    "discord_crawler_webhook_url": "",
    "saas_webhook_url": "",
    "saas_webhook_api_key": "",
}


def _load() -> dict[str, str]:
    """Load settings from JSON file."""
    try:
        if SETTINGS_PATH.exists():
            with open(SETTINGS_PATH) as f:
                return {**DEFAULTS, **json.load(f)}
    except Exception as e:
        logger.error("Failed to load settings: %s", e)
    return dict(DEFAULTS)


def _save(settings: dict[str, str]) -> None:
    """Save settings to JSON file."""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)


def get_settings() -> dict[str, str]:
    """Get all settings."""
    return _load()


def get_setting(key: str, default: str = "") -> str:
    """Get a single setting value."""
    settings = _load()
    return settings.get(key, default)


def update_settings(updates: dict[str, str]) -> dict[str, str]:
    """Update settings with new values (merge, not replace)."""
    settings = _load()
    # Only update non-empty values (don't overwrite password with empty string)
    for k, v in updates.items():
        if v or k not in settings or not settings[k]:
            settings[k] = v
    _save(settings)
    return settings
