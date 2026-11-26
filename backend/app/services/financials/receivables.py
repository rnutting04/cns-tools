"""AR and prepaid assessments, across combined files.

The business prints three combined reports, each covering every association:
the balance sheets, the "CSC AR Names" aging report and the "CSC_Prepaid"
report. Each file is split into associations (see ``batch``), the
associations are paired up by name across the files, and for each one:

- Accounts Receivable (GL 1100, Total column) vs the AR report's Count-line
  balance;
- Prepaid Member Assessments (GL 2100, Total column) vs the prepaid report's
  total.

The comparisons are the same rules the financial packet review uses
(``checks._schedule_check``), so pass / fail / review mean the same thing.
The files can be in different orders and needn't cover the same
associations: anything that can't be paired is listed for a person.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .batch import Section, _alnum, _name_key, _numbering, same_association
from .checks import CheckResult, Side, Status, _schedule_check
from .extract import (
    BalanceSheet,
    BSRow,
    PageType,
    ReportTotal,
    classify,
    extract_packet,
    parse_ar_aging,
    parse_prepaid_assessments,
)
from .pdf import Page

# The three uploads, in the order they're read.
ROLES = ("balance_sheet", "ar", "prepaid")
ROLE_NAMES = {
    "balance_sheet": "balance sheet file",
    "ar": "AR file",
    "prepaid": "prepaid file",
}
# What each file's pages should classify as (to catch a file in the wrong slot).
EXPECTED_TYPE = {
    "balance_sheet": PageType.BALANCE_SHEET,
    "ar": PageType.AR_AGING,
    "prepaid": PageType.PREPAID_ASSESSMENTS,
}

UNNAMED = "(name not found)"


@dataclass
class Found:
    """One association's section in one of the files, already read (the
    pages themselves aren't kept: a combined file is hundreds of pages)."""

    role: str
    name: str
    first_page: int
    last_page: int
    balance_sheet: BalanceSheet | None = None
    report: ReportTotal | None = None


def read_section(role: str, section: Section) -> Found:
    first, last = section.page_range
    found = Found(role, section.name, first, last)
    if role == "balance_sheet":
        found.balance_sheet = extract_packet(section.pages).balance_sheet
    elif role == "ar":
        found.report = parse_ar_aging(section.pages)
    else:
        found.report = parse_prepaid_assessments(section.pages)
    return found


def looks_like(role: str, page: Page) -> bool:
    """Is this page the kind of report its file was uploaded as?"""
    return classify(page) is EXPECTED_TYPE[role]


# --------------------------------------------------------------------------
# Pairing and comparing
# --------------------------------------------------------------------------


def pair(names: list[str], pool: list[Found]) -> list[Found | None]:
    """For each name, its section in ``pool`` (each used at most once).
    Exact names are paired first, across the whole list, so a loose match
    can never take a section another association matches exactly."""
    out: list[Found | None] = [None] * len(names)
    used: set[int] = set()
    exact = (lambda a, b: _alnum(a) == _alnum(b), same_association)
    for test in exact:
        for n, name in enumerate(names):
            if out[n] is not None or name == UNNAMED:
                continue
            for i, f in enumerate(pool):
                if i not in used and f.name != UNNAMED and test(name, f.name):
                    used.add(i)
                    out[n] = f
                    break
    # Last resort, among what's left: OCR lost part of one name ("Second"
    # for "Ironwood Second", "Meadows" for "McIntosh Meadows"). Pair only
    # when exactly one name on each side fits.
    left = [n for n, f in enumerate(out) if f is None and names[n] != UNNAMED]
    free = [i for i, f in enumerate(pool) if i not in used and f.name != UNNAMED]
    fits = {n: [i for i in free if _part_of(names[n], pool[i].name)] for n in left}
    for n, cands in fits.items():
        if len(cands) == 1 and sum(cands[0] in c for c in fits.values()) == 1:
            out[n] = pool[cands[0]]
    return out


def _words(name: str) -> set[str]:
    return {w for w in (_name_key(t) for t in name.split()) if w}


def _part_of(a: str, b: str) -> bool:
    """Is one name's every word in the other (same numbering)?"""
    wa, wb = _words(a), _words(b)
    if not wa or not wb or _numbering(a) != _numbering(b):
        return False
    short = min(wa, wb, key=len)
    # One-word leftovers must be a real word, not a stray digit.
    return (wa <= wb or wb <= wa) and sum(len(w) for w in short) >= 5


def _side(s: Side | None) -> dict[str, Any] | None:
    if s is None:
        return None
    b = s.bbox
    return {
        "source": s.source,
        "label": s.label,
        "amount": float(s.amount) if s.amount is not None else None,
        "page": s.page,
        "bbox": [b.x0, b.top, b.x1, b.bottom] if b else None,
        "verified": s.verified,
        "guessed": s.guessed,
    }


def _check_json(c: CheckResult) -> dict[str, Any]:
    return {
        "id": c.id,
        "title": c.title,
        "status": c.status.value,
        "balance_sheet": _side(c.left),
        "report": _side(c.right),
        "difference": float(c.difference) if c.difference is not None else None,
        "notes": c.notes,
    }


_CHECKS = {
    # role: (id, title, GL code, label keys, report name)
    "ar": (
        "ar",
        "Accounts Receivable (1100)",
        "1100",
        ("acctreceivablemembers", "accountsreceivablemembers"),
        "AR report",
    ),
    "prepaid": (
        "prepaid_assessments",
        "Prepaid Member Assessments (2100)",
        "2100",
        ("prepaidmemberassessment",),
        "prepaid report",
    ),
}


def compare(role: str, bs: Found | None, report: Found | None) -> CheckResult:
    id, title, code, keys, report_name = _CHECKS[role]
    if bs is None or bs.balance_sheet is None:
        why = (
            "This association has no balance sheet in the balance sheet file."
            if bs is None
            else "This association's balance sheet couldn't be read "
            "(its Operating / Reserve / Total columns weren't found)."
        )
        right = Side.of(report_name, report.report.total) if report and report.report else None
        return CheckResult(id, title, Status.REVIEW, None, right, notes=[why])
    row: BSRow | None = bs.balance_sheet.find(code, keys)
    if report is None:
        left = Side.of("balance sheet", row.amount() if row else None, row.label if row else title)
        if row is None or (left.amount is not None and left.amount == 0):
            return CheckResult(
                id,
                title,
                Status.NOT_APPLICABLE,
                left if row else None,
                None,
                notes=[f"Nothing on the balance sheet and no {report_name} for this association."],
            )
        return CheckResult(
            id,
            title,
            Status.MISSING,
            left,
            None,
            notes=[f"No {report_name} for this association in the {ROLE_NAMES[role]}."],
        )
    return _schedule_check(None, id, title, row, report.report, report_name)


_OK = (Status.PASS, Status.NOT_APPLICABLE)


def _note_shared_difference(checks: list[CheckResult]) -> None:
    """AR and prepaid off by the very same amount usually means one entry
    is on the balance sheet in both 1100 and 2100 (or reclassed between
    them) — worth saying, since it points the reviewer at one cause."""
    diffs = [c for c in checks if c.difference and c.status is not Status.PASS]
    if len(diffs) == 2 and abs(diffs[0].difference) == abs(diffs[1].difference):
        amount = abs(diffs[0].difference)
        for c in diffs:
            c.notes.append(
                f"AR and prepaid are both off by {amount:,.2f}: likely one amount counted in "
                "both 1100 and 2100, or a reclass between them."
            )


def reconcile(found: dict[str, list[Found]]) -> list[dict[str, Any]]:
    """One result per association: balance sheet associations in file order,
    then any association that only appears in the AR or prepaid file."""
    reports = [r for r in ("ar", "prepaid") if r in found]
    sheets = found.get("balance_sheet", [])
    names = [bs.name for bs in sheets]
    pairs = {r: pair(names, found[r]) for r in reports}
    out: list[dict[str, Any]] = []

    for n, bs in enumerate(sheets):
        paired = {r: pairs[r][n] for r in reports}
        checks = [compare(r, bs, paired[r]) for r in reports]
        _note_shared_difference(checks)
        out.append(
            _result(
                bs.name,
                bs.first_page,
                bs.last_page,
                {"balance_sheet": bs, **paired},
                checks,
            )
        )

    # Report sections no balance sheet claimed, grouped by association.
    leftovers: list[dict[str, Found]] = []
    for r in reports:
        taken = {id(f) for f in pairs[r] if f is not None}
        for f in found[r]:
            if id(f) in taken:
                continue
            group = next(
                (
                    g
                    for g in leftovers
                    if r not in g
                    and f.name != UNNAMED
                    and any(same_association(f.name, o.name) for o in g.values())
                ),
                None,
            )
            if group is None:
                leftovers.append({r: f})
            else:
                group[r] = f
    for g in leftovers:
        any_f = next(iter(g.values()))
        where = " and ".join(ROLE_NAMES[r] for r in g)
        problem = (
            f"Found in the {where} but no balance sheet matched this name. "
            "Compare it by hand (the name may be printed differently, or it's "
            "part of a master association)."
        )
        if any_f.name == UNNAMED:
            problem = (
                f"The association name couldn't be read on these pages of the {where}. "
                "Compare it by hand."
            )
        out.append(
            {
                "association": any_f.name,
                "first_page": any_f.first_page,
                "last_page": any_f.last_page,
                "flagged": True,
                "result": {
                    "problem": problem,
                    "pages": _pages(g),
                    "reports": {
                        r: _side(Side.of(ROLE_NAMES[r], f.report.total if f.report else None))
                        for r, f in g.items()
                    },
                },
            }
        )
    return out


def _pages(found: dict[str, Found | None]) -> dict[str, list[int] | None]:
    return {r: ([f.first_page, f.last_page] if f else None) for r, f in found.items()}


def _result(
    name: str,
    first: int,
    last: int,
    found: dict[str, Found | None],
    checks: list[CheckResult],
) -> dict[str, Any]:
    names = {
        r: f.name
        for r, f in found.items()
        if f is not None and r != "balance_sheet" and _alnum(f.name) != _alnum(name)
    }
    return {
        "association": name,
        "first_page": first,
        "last_page": last,
        "flagged": any(c.status not in _OK for c in checks),
        "result": {
            "pages": _pages(found),
            # Where a report printed the name differently (paired by OCR tolerance).
            "names": names,
            "checks": [_check_json(c) for c in checks],
        },
    }


__all__ = ["ROLES", "Found", "compare", "looks_like", "read_section", "reconcile"]
