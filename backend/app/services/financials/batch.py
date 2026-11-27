"""Combined multi-association reports: split one PDF into per-association
sections and run a tool on each.

The business prints a report for every association into one file (~180
associations): e.g. all balance sheets, or all income & expense reports.
Every page's header names its association ("1500 State Street Condo",
"Anna Maria Island Club", "5400"), so a new section starts where that name
changes, or where the report's own "Page 1 of N" restarts.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .extract import Value, _page_of, _within_one_edit, extract_packet
from .fdic import fdic_exposure
from .maturity import FLAGGED_TIERS, cd_maturities
from .negative import negative_balances
from .pdf import BBox, Page
from .thresholds import RevenueBasis, revenue_tier

_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_MONTHS = (
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
)  # fmt: skip
# Header lines that are never the association name.
_NOT_NAME = (
    "balancesheet",
    "incomeandexpense",
    "incomeexpense",
    "report",
    "period",
    "currentmonth",
    "yeartodate",
    "operatingreserve",
    "actualbudget",
    "page",
    # Titles and column headings of the AR aging ("CSC AR NAMES") and
    # prepaid assessment ("CSC_ Prepaid") reports.
    "cscarnames",
    "cscprepaid",
    "residentcontact",
    "propertyaddress",
    "acctstatus",
)


_MONEY = re.compile(r"\d\.\d{2}\b|\d,\d{2}$")


def _alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def association_name(page: Page) -> str:
    """The association named in the page header, or "" if none is found."""
    # The prepaid report prints the name under its two-line column header.
    for ln in page.lines[:8]:
        text = ln.text.strip()
        key = _alnum(text)
        letters = re.sub(r"[^a-z]", "", key)
        if not key:
            continue
        if any(m in letters for m in _NOT_NAME):
            continue
        # The run date/time line: "Saturday, November 18, 2023 15:18".
        if any(d in letters for d in _WEEKDAYS) or (
            any(m in letters for m in _MONTHS) and re.search(r"\d{4}", text)
        ):
            continue
        # Column headings ("Operating Reserve Total", "Actual Budget Variance",
        # the prepaid report's "Prepaid" over "Amount").
        if letters in (
            "operating",
            "reserve",
            "total",
            "operatingreservetotal",
            "prepaid",
            "amount",
            "prepaidamount",
            "property",
            "address",
        ):
            continue
        # A report row (an owner on a page that doesn't repeat the name),
        # not a name: names never carry a money amount, nor an owner's
        # "Last, First" with a 5-digit account number.
        if _MONEY.search(text) or ("," in text and re.search(r"(?<![\d,.])\d{5}(?![\d,.])", text)):
            continue
        return text
    return ""


# A numbering token: Roman numerals (OCR often reads I as l, | or 1) or digits.
_NUMBERING = re.compile(r"^(?:[ivxl|1!]+|\d+)$")


def _numbering(name: str) -> set[str]:
    out = set()
    for t in name.lower().split():
        if _NUMBERING.match(t):
            out.add(t if t.isdigit() else re.sub(r"[l|1!]", "i", t))
    return out


def _same(a: str, b: str, fuzzy: bool) -> bool:
    """Same association name? Exact unless ``fuzzy`` (OCR'd pages), and even
    then never when the names differ in a number or Roman numeral —
    "Banbury I" and "Banbury II" are different associations."""
    if _alnum(a) == _alnum(b):
        return True
    if not fuzzy or _numbering(a) != _numbering(b):
        return False
    a, b = _alnum(a), _alnum(b)
    return min(len(a), len(b)) >= 6 and _within_one_edit(a, b)


def _name_key(name: str) -> str:
    """Comparable form of a name: letters and digits, with Roman numerals
    normalised for OCR ("Ill" and "|||" are both "iii")."""
    out = []
    for t in re.findall(r"[a-z0-9|!]+", name.lower()):
        out.append(re.sub(r"[l|1!]", "i", t) if _NUMBERING.match(t) and not t.isdigit() else t)
    return re.sub(r"[^a-z0-9]", "", "".join(out))


# Some reports cut long names off ("Carpentras at the Villages of Avi").
_MIN_TRUNCATED = 15


def same_association(a: str, b: str) -> bool:
    """Do two reports name the same association? For pairing sections of
    *different* files, so it also accepts one OCR slip and a name one report
    cut short — but never names that differ in a number or Roman numeral."""
    ka, kb = _name_key(a), _name_key(b)
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    if _numbering(a) != _numbering(b):
        return False
    short, long_ = sorted((ka, kb), key=len)
    if len(short) >= 6 and _within_one_edit(ka, kb):
        return True
    # Cut short, possibly with OCR junk on the cut edge ("Nation<", "N:").
    return len(short) >= _MIN_TRUNCATED and long_.startswith(short[:-2])


@dataclass
class Section:
    name: str
    pages: list[Page] = field(default_factory=list)

    @property
    def page_range(self) -> tuple[int, int]:
        return self.pages[0].number, self.pages[-1].number


def split_sections(pages: Iterable[Page]) -> Iterator[Section]:
    """Group consecutive pages by association, yielding each section as soon
    as the next one starts (so a long OCR run can report as it goes)."""
    # The printed "Page N of M" can't be trusted to *join* pages: the
    # combined balance sheet file numbers a blank page "1 of 2" and the next
    # association's page "2 of 2". A different printed name always wins.
    current: Section | None = None
    for page in pages:
        name = association_name(page)
        page_of = _page_of(page)
        restarts = page_of is not None and page_of[0] == 1
        if current is not None:
            if restarts:
                # The report restarted at "Page 1": that's a new association
                # unless the name matches exactly (then it's the same
                # association's next report, e.g. reserve after operating).
                same = bool(name) and _alnum(name) == _alnum(current.name)
            else:
                # Mid-report page: tolerate OCR damage to the name.
                fuzzy = page.ocr or current.pages[-1].ocr
                same = not name or _same(name, current.name, fuzzy)
            if not same:
                yield current
                current = None
        if current is None:
            current = Section(name or "(name not found)")
        current.pages.append(page)
    if current is not None:
        yield current


# --------------------------------------------------------------------------
# Per-section tool results (JSON-ready dicts, stored on the job)
# --------------------------------------------------------------------------


def _fig(v: Value | None) -> dict[str, Any] | None:
    if v is None:
        return None
    b = v.bbox
    return {
        "label": v.label,
        "amount": float(v.amount),
        "page": v.page,
        "bbox": [b.x0, b.top, b.x1, b.bottom],
        "verified": v.verified,
        "guessed": v.guessed,
    }


def _basis(b: RevenueBasis) -> dict[str, Any]:
    return {
        "operating": _fig(b.operating),
        "reserve": _fig(b.reserve),
        "total": float(b.total) if b.total is not None else None,
        "tier": b.tier.value if b.tier else None,
        "notes": b.notes,
    }


_FUND = re.compile(r"current\s*month\s*(.+?)\s*year\s*to\s*date", re.IGNORECASE)


def _funds(section: Section) -> list[str]:
    """Fund labels from the I&E column headers ("Current Month <fund> Year
    to Date <fund>"), in order, e.g. ["Operating", "Reserve"] or
    ["Lagoons I Oper", "Lagoons I Rese", ...] for a master association."""
    out: list[str] = []
    for p in section.pages:
        for ln in p.lines[:8]:
            m = _FUND.search(ln.text)
            if m and m.group(1).strip() not in out:
                out.append(m.group(1).strip())
                break
    return out


def revenue_section(section: Section) -> dict[str, Any]:
    funds = _funds(section)
    if len(funds) > 2:
        # Master associations report several sub-associations' funds in one
        # section. Which revenues count toward the threshold is a judgment
        # call, so don't guess — flag it.
        return {
            "problem": (
                f"Reports {len(funds)} separate funds ({', '.join(funds)}). "
                "Work out the threshold for this association by hand."
            )
        }
    packet = extract_packet(section.pages)
    if not packet.income_expense:
        return {"problem": "No income & expense report found in this section."}
    r = revenue_tier(packet)
    return {"ytd_actual": _basis(r.ytd_actual), "annual": _basis(r.annual)}


def fdic_section(section: Section) -> dict[str, Any]:
    packet = extract_packet(section.pages)
    if packet.balance_sheet is None:
        return {"problem": "Balance sheet couldn't be read in this section."}
    r = fdic_exposure(packet.balance_sheet)

    def acct(a) -> dict[str, Any]:
        return {
            "label": a.label,
            "amount": float(a.amount),
            "network": a.network,
            "source": _fig(a.value),
        }

    return {
        "limit": float(r.limit),
        "institutions": [
            {
                "name": i.name,
                "total": float(i.total),
                "over_limit": i.over_limit,
                "accounts": [acct(a) for a in i.accounts],
                "notes": i.notes,
            }
            for i in r.institutions
        ],
        "unrecognized": [acct(a) for a in r.unrecognized],
    }


def cd_section(section: Section) -> dict[str, Any]:
    packet = extract_packet(section.pages)
    if packet.balance_sheet is None:
        return {"problem": "Balance sheet couldn't be read in this section."}
    r = cd_maturities(packet.balance_sheet, section.pages)

    def cd(c) -> dict[str, Any]:
        b = c.bbox
        return {
            "label": c.label,
            "amount": float(c.amount),
            "tier": c.tier,
            "maturity": c.maturity.isoformat() if c.maturity else None,
            "days": c.days,
            "term": c.term,
            "notes": c.notes,
            "source": _fig(c.value),
            # Filled with images by the job while it still has the PDF.
            "shots": [
                {
                    "role": "report",
                    "page": c.value.page,
                    "bbox": [b.x0, b.top, b.x1, b.bottom],
                    "caption": f"Balance sheet p.{c.value.page}",
                }
            ]
            if c.flagged
            else [],
        }

    return {
        "as_of": r.as_of.isoformat(),
        "period_end": r.period_end.isoformat() if r.period_end else None,
        "cds": [cd(c) for c in r.cds],
    }


def _shot(page: int, b: BBox, caption: str) -> dict[str, Any]:
    """A screenshot placeholder, filled with an image by the job while it
    still has the PDF."""
    return {
        "role": "report",
        "page": page,
        "bbox": [b.x0, b.top, b.x1, b.bottom],
        "caption": caption,
    }


def negative_bank_section(section: Section) -> dict[str, Any]:
    packet = extract_packet(section.pages)
    if packet.balance_sheet is None:
        return {"problem": "Balance sheet couldn't be read in this section."}
    r = negative_balances(packet.balance_sheet)

    def account(a) -> dict[str, Any]:
        page = a.value.page
        return {
            "label": a.label,
            "amount": float(a.amount),
            "amounts": {c: float(v) for c, v in a.amounts.items()},
            "negative": a.negative,
            "verified": a.verified,
            "notes": a.notes,
            "source": _fig(a.value),
            "shots": [_shot(page, a.bbox, f"Balance sheet p.{page}")] if a.negative else [],
        }

    area = r.bank_area
    return {
        "accounts": [account(a) for a in r.accounts],
        "totals_ok": r.totals_ok,
        "total_checks": r.total_checks,
        "shots": [_shot(area[0], area[1], f"Bank section, p.{area[0]}")] if area else [],
    }


TOOLS: dict[str, Callable[[Section], dict[str, Any]]] = {
    "revenue_threshold": revenue_section,
    "fdic": fdic_section,
    "cd_maturity": cd_section,
    "negative_bank": negative_bank_section,
}


def run_sections(tool: str, pages: Iterable[Page]) -> Iterator[tuple[Section, dict[str, Any]]]:
    """(section, result) for each association, in file order. A section that
    fails to parse yields a problem instead of stopping the whole file."""
    fn = TOOLS[tool]
    for section in split_sections(pages):
        try:
            result = fn(section)
        except Exception as exc:  # noqa: BLE001 — one bad section mustn't sink 180
            result = {"problem": f"Couldn't process this section: {exc}"}
        yield section, result


def flagged(tool: str, result: dict[str, Any]) -> bool:
    """Does this association's result need attention?"""
    if "problem" in result:
        return True
    if tool == "fdic":
        return any(i["over_limit"] for i in result["institutions"]) or bool(result["unrecognized"])
    if tool == "cd_maturity":
        return any(c["tier"] in FLAGGED_TIERS for c in result["cds"])
    if tool == "negative_bank":
        # A failed Total Bank sum may hide an overdraft whose sign was misread.
        return any(a["negative"] for a in result["accounts"]) or result["totals_ok"] is False
    return result["ytd_actual"]["tier"] in (None, "compilation", "review", "audit")


__all__ = ["Decimal", "Section", "association_name", "flagged", "run_sections", "split_sections"]
