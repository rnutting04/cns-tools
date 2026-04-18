# app/config/letter_config.py
"""
Configuration loader for the letter generation module.

Human-editable content (offices, legal vote language) lives in YAML files
in this directory. Developer-facing business rule constants live here in
Python because they're tied to code paths.

All YAML files are loaded once per process and cached. Restart the server
to pick up changes.
"""
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

import yaml


CONFIG_DIR = Path(__file__).parent


# --- Business rule constants ---------------------------------------------
# Number of days before a meeting date that a notice-of-candidacy deadline falls.
NOTICE_CANDIDACY_DEADLINE_DAYS = 38


# --- Type definitions ----------------------------------------------------
class OfficeData(TypedDict):
    office_street: str
    office_city_state_zip: str
    office_phone: str


class VoteTemplate(TypedDict):
    text: str
    requires_warning: bool


# --- Office lookup -------------------------------------------------------
@lru_cache(maxsize=1)
def _load_offices() -> dict[str, OfficeData]:
    """Load offices.yaml once and cache it."""
    path = CONFIG_DIR / "offices.yaml"
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def get_office(location: str | None) -> OfficeData:
    """
    Look up an office by its location key (e.g. "Bradenton").
    Returns empty strings for all fields if the key is unknown or None.
    """
    empty = OfficeData(
        office_street="",
        office_city_state_zip="",
        office_phone="",
    )
    if not location:
        return empty
    office = _load_offices().get(location)
    return OfficeData(**office) if office else empty


def list_office_names() -> list[str]:
    """Return all configured office location names. Useful for form dropdowns."""
    return list(_load_offices().keys())


# --- Proxy vote templates ------------------------------------------------
@lru_cache(maxsize=1)
def _load_proxy_votes() -> dict:
    """Load proxy_votes.yaml once and cache it."""
    path = CONFIG_DIR / "proxy_votes.yaml"
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def get_proxy_warning_text() -> str:
    """Return the bold warning text shown at the bottom of applicable proxies."""
    data = _load_proxy_votes()
    return (data.get("proxy_warning_text") or "").strip()


def render_proxy_vote(vote: dict) -> tuple[str, bool]:
    """
    Look up a vote template by vote["type"] and fill in its placeholders
    from the vote dict.

    Returns (rendered_text, requires_warning).
    Returns ("", False) if the vote type is unknown.

    Missing placeholders in the vote dict render as empty strings —
    matches the previous behavior of vote.get('fiscal_year', '').
    """
    vote_type = vote.get("type")
    if not vote_type:
        return "", False

    votes = _load_proxy_votes().get("votes") or {}
    template = votes.get(vote_type)
    if not template:
        return "", False

    text_template = (template.get("text") or "").strip()
    requires_warning = bool(template.get("requires_warning", False))

    # defaultdict(str) means missing keys in the vote dict become ""
    # rather than raising KeyError during .format_map()
    safe_vote = defaultdict(str, {k: v for k, v in vote.items() if v is not None})
    try:
        rendered = text_template.format_map(safe_vote)
    except (KeyError, IndexError, ValueError):
        # If format_map fails for any reason (malformed template, weird input),
        # fall back to empty string rather than crashing the whole letter
        return "", False

    return rendered, requires_warning