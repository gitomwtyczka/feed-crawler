"""
Crawl state management.

Stores global crawl on/off flag in a JSON file.
Admin panel toggles this flag; scheduler checks it before each cycle.

State file: data/crawl_state.json
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).parent.parent / "data" / "crawl_state.json"

_DEFAULT_STATE = {
    "crawl_enabled": False,  # Start disabled — user must explicitly enable
    "crawl_interval_minutes": 10,
}


def _ensure_file() -> None:
    """Create state file with defaults if it doesn't exist."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.exists():
        STATE_FILE.write_text(json.dumps(_DEFAULT_STATE, indent=2), encoding="utf-8")
        logger.info("Created crawl state file: %s", STATE_FILE)


def get_state() -> dict:
    """Read current crawl state."""
    _ensure_file()
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def set_state(**kwargs) -> dict:
    """Update crawl state fields."""
    state = get_state()
    state.update(kwargs)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")
    logger.info("Crawl state updated: %s", state)
    return state


def is_crawl_enabled() -> bool:
    """Check if crawling is enabled."""
    return get_state().get("crawl_enabled", False)


def toggle_crawl() -> bool:
    """Toggle crawl on/off. Returns new state."""
    current = is_crawl_enabled()
    set_state(crawl_enabled=not current)
    return not current
