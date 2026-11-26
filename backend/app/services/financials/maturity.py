"""CD maturity: when each certificate of deposit on the balance sheet comes due.

The balance sheet doesn't have a maturity column; the date is written into
the account name: "1320 R-CD OZK 2/13/27 13m 3.6% (0650)", "1007 Oper CDAR
Truist 11/27/26 52w 1.0%", occasionally only the month ("1307 R-CD Suncoast
12/26 11m 4.16%"). Each CD is put in a tier by how many days are left,
counted from the day the check runs:

    matured   the date has passed: renewed, redeemed, or the name is stale
    due_30    0-30 days
    due_60    31-60 days
    due_90    61-90 days
    later     more than 90 days
    no_date   a CD whose name has no readable date

Investment / brokerage / money market rows in the CD section have no
maturity and are listed as ``investment`` without being flagged.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from .extract import BalanceSheet, BSRow, Value
from .pdf import BBox, Page

# The associations are in Florida: "today" is Eastern, not the worker's UTC.
LOCAL_TZ = ZoneInfo("America/New_York")

# (upper bound in days, tier), checked in order.
TIERS: tuple[tuple[int, str], ...] = ((30, "due_30"), (60, "due_60"), (90, "due_90"))
FLAGGED_TIERS = frozenset({"matured", "due_30", "due_60", "due_90", "no_date"})

# Words that make a row a CD (labels split on spaces and punctuation, so
# "R-CD" gives "cd" and "RCD" stays "rcd").
_CD_WORDS = {"cd", "cds", "cdar", "cdars", "rcd", "ocd", "certificate", "treasury", "tbill", "bill"}
# Rows in the CD section that aren't CDs and have no maturity date.
_INVESTMENT_WORDS = {
    "investment", "investments", "brokerage", "mm", "money", "market", "sweep", "ics",
}  # fmt: skip

_FULL_DATE = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?![\d/])")
_MONTH_YEAR = re.compile(r"(?<![\d/])(\d{1,2})/(\d{2})(?![\d/])")
_TERM = re.compile(r"(?<![\w.])(\d{1,2})\s?(m|mo|w|wk|wks|yr|y)(?![a-z])", re.IGNORECASE)
_CODE = re.compile(r"^\s*\d{4}(?:\.[A-Z]{1,3})?\s+")
_PERIOD = re.compile(r"period\D*(\d{1,2})/(\d{1,2})/(\d{4})", re.IGNORECASE)


def today() -> date:
    return datetime.now(LOCAL_TZ).date()


@dataclass
class MaturityDate:
    when: date
    text: str  # as written in the account name
    month_only: bool = False


def _year(y: str) -> int:
    return int(y) + 2000 if len(y) == 2 else int(y)


def maturity_of(label: str) -> MaturityDate | None:
    """The maturity date written in an account name, or None. A month and
    year alone ("12/26") counts from the 1st, the earliest it could be."""
    name = _CODE.sub("", label)
    for m in _FULL_DATE.finditer(name):
        month, day, year = int(m.group(1)), int(m.group(2)), _year(m.group(3))
        try:
            return MaturityDate(date(year, month, day), m.group(0))
        except ValueError:
            continue  # an OCR slip like 13/2/27: keep looking
    for m in _MONTH_YEAR.finditer(name):
        month, year = int(m.group(1)), _year(m.group(2))
        if 1 <= month <= 12:
            return MaturityDate(date(year, month, 1), m.group(0), month_only=True)
    return None


def _words(label: str) -> set[str]:
    return {w for w in re.split(r"[^a-z]+", _CODE.sub("", label).lower()) if w}


def tier_for(days: int) -> str:
    if days < 0:
        return "matured"
    for limit, tier in TIERS:
        if days <= limit:
            return tier
    return "later"


def period_end(pages: list[Page]) -> date | None:
    """The balance sheet's own date ("Period 10/31/2026")."""
    for p in pages:
        for ln in p.lines[:6]:
            m = _PERIOD.search(ln.text)
            if m:
                try:
                    return date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
                except ValueError:
                    return None
    return None


@dataclass
class Cd:
    label: str
    amount: Decimal
    value: Value  # page / bbox of the amount
    bbox: BBox  # the whole line: name and amount
    tier: str
    maturity: date | None = None
    days: int | None = None  # from the run date; negative once matured
    term: str | None = None  # "13m", "52w", as written
    notes: list[str] = field(default_factory=list)

    @property
    def flagged(self) -> bool:
        return self.tier in FLAGGED_TIERS


@dataclass
class MaturityResult:
    as_of: date
    period_end: date | None
    cds: list[Cd]  # soonest first, then undated, then investments


def _line_box(row: BSRow, v: Value) -> BBox:
    a, b = row.bbox, v.bbox
    if abs(a.cy - b.cy) > 6:  # the label wasn't read on the amount's line
        return b
    return BBox(min(a.x0, b.x0), min(a.top, b.top), max(a.x1, b.x1), max(a.bottom, b.bottom))


def _is_candidate(row: BSRow) -> bool:
    if not row.values or row.key.startswith("total"):
        return False
    return "cd" in row.section or bool(_words(row.label) & _CD_WORDS)


def _fmt(d: date) -> str:
    return f"{d.month}/{d.day}/{d.year}"


def _days(n: int) -> str:
    return f"{n} day{'' if n == 1 else 's'}"


def _explain(cd: Cd, md: MaturityDate | None, as_of: date, stmt: date | None) -> None:
    if md is None:
        if cd.tier == "investment":
            cd.notes.append("Investment account with no maturity date.")
        else:
            term = f" It shows a {cd.term} term but no end date." if cd.term else ""
            cd.notes.append(
                "No maturity date in the account name, so it can't be tracked." + term
                + " Check the CD statement and add the date to the account name."
            )  # fmt: skip
        return
    if md.month_only:
        cd.notes.append(
            f"The account name only gives the month ({md.text}), so this counts from the 1st."
        )
    days = cd.days or 0
    if cd.tier == "matured":
        if stmt and md.when <= stmt:
            cd.notes.append(
                f"Matured {_fmt(md.when)}, before this balance sheet's date ({_fmt(stmt)}), "
                "but it's still listed under the old date. It may have renewed: confirm "
                "with the bank and update the account name."
            )
        else:
            cd.notes.append(
                f"Matured {_fmt(md.when)} ({_days(-days)} ago). Confirm it was renewed or "
                "moved, and update the account name."
            )
    elif cd.tier != "later":
        cd.notes.append(
            "Matures today." if days == 0 else f"Matures {_fmt(md.when)}, in {_days(days)}."
        )


def cd_maturities(bs: BalanceSheet, pages: list[Page], as_of: date | None = None) -> MaturityResult:
    as_of = as_of or today()
    stmt = period_end(pages)
    cds: list[Cd] = []
    for row in bs.rows:
        if row.key == "totalassets":
            break  # assets only
        if not _is_candidate(row):
            continue
        v = row.amount("total")
        if v is None or v.amount == 0:
            continue  # closed out
        md = maturity_of(row.label)
        words = _words(row.label)
        term = _TERM.search(_CODE.sub("", row.label))
        if md is not None:
            days = (md.when - as_of).days
            tier = tier_for(days)
        else:
            days = None
            # "Rese Truist Investment 4.35%", "Merrill Lynch Brokerage"
            investment = bool(words & _INVESTMENT_WORDS) and not (words & _CD_WORDS)
            tier = "investment" if investment else "no_date"
        cd = Cd(
            label=row.label,
            amount=v.amount,
            value=v,
            bbox=_line_box(row, v),
            tier=tier,
            maturity=md.when if md else None,
            days=days,
            term=term.group(0).replace(" ", "") if term else None,
        )
        _explain(cd, md, as_of, stmt)
        cds.append(cd)
    order = {"no_date": 1, "investment": 2}
    cds.sort(key=lambda c: (order.get(c.tier, 0), c.maturity or date.max))
    return MaturityResult(as_of, stmt, cds)


__all__ = [
    "FLAGGED_TIERS",
    "TIERS",
    "Cd",
    "MaturityResult",
    "cd_maturities",
    "maturity_of",
    "period_end",
    "tier_for",
    "today",
]
