"""When a reminder's emails go out.

An event happens on ``start_date`` and then every week / month / year (or
just once). For each occurrence the email goes ``lead_days`` before it at
``send_time`` Eastern. Monthly events keep their day of the month, falling
back to the month's last day ("the 31st" is Feb 28, then Mar 31).

Times are Eastern for people and naive UTC in the database.
"""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/New_York")
REPEATS = ("none", "weekly", "monthly", "yearly")

# How far ahead to look for the next occurrence (a monthly reminder in 2026
# never needs to look past 2036); stops a bad input looping forever.
_MAX_STEPS = 5000


def utcnow() -> datetime:
    """Now, naive UTC (how the database stores times)."""
    return datetime.now(UTC).replace(tzinfo=None)


def _add_months(start: date, months: int) -> date:
    y, m = divmod(start.month - 1 + months, 12)
    year, month = start.year + y, m + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def occurrence(start: date, repeat: str, k: int) -> date | None:
    """The k-th occurrence (0 = ``start``), or None if there isn't one."""
    if k == 0:
        return start
    if repeat == "weekly":
        return start + timedelta(weeks=k)
    if repeat == "monthly":
        return _add_months(start, k)
    if repeat == "yearly":
        return _add_months(start, 12 * k)
    return None


def send_at(event: date, lead_days: int, send_time: time) -> datetime:
    """When the email for ``event`` goes out, as naive UTC."""
    local = datetime.combine(event - timedelta(days=lead_days), send_time, tzinfo=LOCAL_TZ)
    return local.astimezone(UTC).replace(tzinfo=None)


def next_due(
    start: date,
    repeat: str,
    lead_days: int,
    send_time: time,
    after: datetime,
    past_event: date | None = None,
) -> tuple[date, datetime] | None:
    """The first occurrence whose email is due after ``after`` (naive UTC),
    and later than ``past_event`` if given: (event date, send time). None if
    there are no more (a one-off whose time has passed)."""
    for k in range(_MAX_STEPS):
        event = occurrence(start, repeat, k)
        if event is None:
            return None
        if past_event is not None and event <= past_event:
            continue
        when = send_at(event, lead_days, send_time)
        if when > after:
            return event, when
    return None


def to_local(naive_utc: datetime) -> datetime:
    return naive_utc.replace(tzinfo=UTC).astimezone(LOCAL_TZ)


def describe(start: date, repeat: str, lead_days: int, send_time: time) -> str:
    """Plain-English schedule, e.g. Every month on the 25th · 3 days before · 8:00 AM ET."""
    when = {
        "none": f"Once, {start:%a %b} {start.day}, {start.year}",
        "weekly": f"Every {start:%A}",
        "monthly": f"Every month on the {_ordinal(start.day)}",
        "yearly": f"Every year on {start:%B} {start.day}",
    }[repeat]
    lead = (
        "on the day" if lead_days == 0 else f"{lead_days} day{'s' if lead_days != 1 else ''} before"
    )
    clock = datetime.combine(start, send_time).strftime("%I:%M %p").lstrip("0")
    return f"{when} · {lead} · {clock} ET"


def _ordinal(n: int) -> str:
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
