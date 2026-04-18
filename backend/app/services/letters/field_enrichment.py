# app/services/letters/field_enrichment.py
"""
Pure functions that enrich user-submitted field values with
derived/computed fields before rendering.

All functions here are pure: they take inputs and return new dicts
rather than mutating in place. This makes them trivial to unit test
and safe to call from any context (HTTP route, worker, batch job).
"""
from datetime import date, datetime, timedelta
from typing import Any

from app.config.letter_config import (
    NOTICE_CANDIDACY_DEADLINE_DAYS,
    get_office,
)
from app.models.association import Association
from app.models.user import User


def _ordinal_number(number: int) -> str:
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def _compute_notice_candidacy_deadline(
    meeting_date_str: str | None,
    days_before: int = NOTICE_CANDIDACY_DEADLINE_DAYS,
) -> date | None:
    if not meeting_date_str:
        return None
    try:
        meeting_date = datetime.strptime(meeting_date_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None
    return meeting_date - timedelta(days=days_before)


def _string_variants(key: str, value: str) -> dict[str, str]:
    return {
        f"{key}_upper": value.upper(),
        f"{key}_lower": value.lower(),
        f"{key}_title": value.title(),
    }


def _date_variants(key: str, value: str) -> dict[str, str]:
    """Return date-format variants for value if it parses as ISO date, else empty dict."""
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return {}

    return {
        f"{key}_iso": parsed.isoformat(),
        f"{key}_short": parsed.strftime("%m/%d/%Y"),
        f"{key}_long": f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}",
        f"{key}_formal": (
            f"{_ordinal_number(parsed.day)} day of "
            f"{parsed.strftime('%B')} {parsed.year}"
        ),
        f"{key}_month_year": parsed.strftime("%B %Y"),
    }


def _expand_variants(field_values: dict[str, Any]) -> dict[str, Any]:
    """Generate all string + date variants for the given values."""
    variants: dict[str, Any] = {}
    for key, value in field_values.items():
        if not isinstance(value, str):
            continue
        variants.update(_string_variants(key, value))
        variants.update(_date_variants(key, value))
    return variants


def build_field_context(
    user_input: dict[str, Any],
    association: Association,
    manager: User | None,
) -> dict[str, Any]:
    """
    Build the complete field value dict for rendering a letter.

    Precedence (later keys win):
      1. User-submitted values
      2. Office lookup (from office_location)
      3. Derived fields (association, manager, today's date, deadline)
      4. Variants (string/date format expansions)

    Returns a new dict — does NOT mutate user_input.
    """
    context: dict[str, Any] = dict(user_input)

    # Office lookup
    office = get_office(context.get("office_location"))
    context["office_street"] = office["office_street"]
    context["office_city_state_zip"] = office["office_city_state_zip"]
    context["office_phone"] = office["office_phone"]

    # Association-derived fields
    context["legal_association_name"] = association.legal_name
    context["filtered_association_name"] = association.filter_name
    context["assn_city"] = association.location_name
    if association.location_name:
        context["association_location_name"] = association.location_name

    # Manager-derived fields (blank if no manager)
    if manager:
        context["manager_full_name"] = f"{manager.fname} {manager.lname}"
        context["manager_titles"] = manager.title or ""
        context["manager_email"] = manager.email or ""
    else:
        context["manager_full_name"] = ""
        context["manager_titles"] = ""
        context["manager_email"] = ""

    # Today's date
    context["today_date"] = date.today().isoformat()

    # Notice of candidacy deadline — only set if meeting date is present and parses
    deadline = _compute_notice_candidacy_deadline(context.get("date"))
    if deadline:
        context["notice_deadline"] = deadline.isoformat()

    # Variants go last so they include everything above
    context.update(_expand_variants(context))

    return context