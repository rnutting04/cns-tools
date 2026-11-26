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
from difflib import SequenceMatcher
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
from .pdf import BBox, Page

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


def _check_json(c: CheckResult, shots: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": c.id,
        "title": c.title,
        "status": c.status.value,
        "balance_sheet": _side(c.left),
        "report": _side(c.right),
        "difference": float(c.difference) if c.difference is not None else None,
        "notes": c.notes,
        "shots": shots,
    }


# --------------------------------------------------------------------------
# Explaining a result: plain-language reasons, and the page regions to show
# ("shots"; the job cuts them out of the PDFs while it still has them).
# --------------------------------------------------------------------------

FILE_NAMES = {"balance_sheet": "Balance sheet", "ar": "AR report", "prepaid": "Prepaid report"}


def _shot(role: str, page: int | None, bbox: BBox | None, caption: str) -> list[dict[str, Any]]:
    if page is None or bbox is None:
        return []
    return [
        {
            "role": role,
            "page": page,
            "bbox": [bbox.x0, bbox.top, bbox.x1, bbox.bottom],
            "caption": f"{FILE_NAMES[role]} p.{page}: {caption}",
        }
    ]


def _code_of(row: BSRow) -> int | None:
    return int(row.code[:4]) if row.code and row.code[:4].isdigit() else None


def _row_name(row: BSRow) -> str:
    return (
        row.label if not row.code or row.label.startswith(row.code) else f"{row.code} {row.label}"
    )


def _neighbours(bs: BalanceSheet, code: str) -> tuple[BSRow | None, BSRow | None]:
    """The balance sheet lines just before and after where ``code`` would be."""
    target = int(code)
    coded = [(c, r) for r in bs.rows if (c := _code_of(r)) is not None]
    before = max((x for x in coded if x[0] < target), default=None, key=lambda x: x[0])
    after = min((x for x in coded if x[0] > target), default=None, key=lambda x: x[0])
    return (before[1] if before else None, after[1] if after else None)


def _money(v: Any) -> str:
    return f"{v:,.2f}"


def explain(role: str, c: CheckResult, bs: Found | None) -> list[dict[str, Any]]:
    """Rewrite the check's notes so they say why, in plain words, and return
    the page regions a reviewer should see. Passing checks need neither."""
    if c.status is Status.PASS:
        return []
    _, _, code, keys, report_name = _CHECKS[role]
    sheet = bs.balance_sheet if bs else None
    row = sheet.find(code, keys) if sheet else None
    left, right = c.left, c.right
    shots: list[dict[str, Any]] = []
    if left is not None and left.bbox is not None:
        label = left.label if left.label.startswith(code) else f"{code} {left.label}"
        shots += _shot("balance_sheet", left.page, left.bbox, label.strip())
    if right is not None:
        shots += _shot(role, right.page, right.bbox, f"{report_name} total")
    # Notes from reading a figure don't say which file they're about.
    for side, where in ((left, "Balance sheet"), (right, FILE_NAMES[role])):
        if side is not None and side.note in c.notes:
            c.notes[c.notes.index(side.note)] = f"{where}: {side.note}"

    if c.status is Status.NOT_APPLICABLE and sheet is not None:
        if row is None:
            before, after = _neighbours(sheet, code)
            if before and after:
                where = f"it goes straight from {_row_name(before)} to {_row_name(after)}"
                # Lines aren't always in code order, so take whichever is higher.
                span = BBox(
                    min(before.bbox.x0, after.bbox.x0),
                    min(before.bbox.top, after.bbox.top),
                    max(before.bbox.x1, after.bbox.x1),
                    max(before.bbox.bottom, after.bbox.bottom),
                )
                shots += _shot("balance_sheet", sheet.page, span, f"where {code} would be")
            else:
                where = "no nearby numbered lines were found either"
            c.notes = [
                f"There's no {code} line on the balance sheet ({where}), and the "
                f"{ROLE_NAMES[role]} has no section for this association, so there's "
                "nothing to compare. If the screenshot does show the line, the scan "
                "misread it: check it by hand."
            ]
        else:
            c.notes = [
                f"{code} is 0.00 on the balance sheet and the {ROLE_NAMES[role]} has no "
                "section for this association: nothing owed, so no report is expected."
            ]
    elif c.status is Status.MISSING and left is not None and left.amount is not None:
        c.notes = [
            f"The balance sheet shows {_money(left.amount)} on {code}, but the "
            f"{ROLE_NAMES[role]} has no section for this association. Either the report "
            "wasn't run for it, or its name is printed differently there."
        ]
    elif c.status is Status.FAIL and c.difference is not None and left and right:
        higher = "higher" if c.difference < 0 else "lower"
        c.notes.insert(
            0,
            f"The balance sheet's {code} is {_money(left.amount)}; the {report_name} "
            f"shows {_money(right.amount)}. The report is {_money(abs(c.difference))} "
            f"{higher}.",
        )
    elif c.status is Status.REVIEW and left and right:
        if left.amount is not None and right.amount is not None:
            agree = "agree" if c.difference == 0 else f"differ by {_money(abs(c.difference))}"
            c.notes.insert(
                0,
                f"The balance sheet's {code} reads {_money(left.amount)} and the "
                f"{report_name} {_money(right.amount)}; they {agree}, but at least one "
                "read is doubtful, so a person should confirm it against the screenshots.",
            )
        if not shots and right.page:
            c.notes.append(f"See {FILE_NAMES[role]} p.{right.page}.")
    return shots


def _closest(name: str, candidates: list[Found]) -> Found | None:
    """The most similar name, if any is close enough to be worth suggesting."""
    key = _alnum(name)
    scored = [
        (SequenceMatcher(None, key, _alnum(f.name)).ratio(), f)
        for f in candidates
        if f.name != UNNAMED
    ]
    best = max(scored, default=None, key=lambda x: x[0])
    return best[1] if best and best[0] >= 0.6 else None


def _pages_text(f: Found) -> str:
    return f"p.{f.first_page}" + (f"–{f.last_page}" if f.last_page != f.first_page else "")


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

    taken_by = {r: {id(f) for f in pairs[r] if f is not None} for r in reports}
    unpaired = {r: [f for f in found[r] if id(f) not in taken_by[r]] for r in reports}

    for n, bs in enumerate(sheets):
        paired = {r: pairs[r][n] for r in reports}
        checks = [compare(r, bs, paired[r]) for r in reports]
        shots = [explain(r, c, bs) for r, c in zip(reports, checks, strict=True)]
        _note_shared_difference(checks)
        for r, c in zip(reports, checks, strict=True):
            if c.status is Status.MISSING and (near := _closest(bs.name, unpaired[r])):
                c.notes.append(
                    f"The {ROLE_NAMES[r]} has an unpaired section named “{near.name}” "
                    f"({_pages_text(near)}). If that's this association, compare it by hand."
                )
        out.append(
            _result(
                bs.name,
                bs.first_page,
                bs.last_page,
                {"balance_sheet": bs, **paired},
                checks,
                shots,
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
        # A balance sheet that's missing this report is the likeliest match.
        lacking = [bs for n, bs in enumerate(sheets) if any(pairs[r][n] is None for r in g)]
        if any_f.name != UNNAMED and (near := _closest(any_f.name, lacking)):
            problem += (
                f" Closest balance sheet without this report: “{near.name}” "
                f"({_pages_text(near)})."
            )
        if any_f.name == UNNAMED:
            problem = (
                f"The association name couldn't be read on these pages of the {where}. "
                "Compare it by hand."
            )
        shots = []
        for r, f in g.items():
            total = f.report.total if f.report else None
            page, bbox = (
                (total.page, total.bbox)
                if total
                else (f.report.searched if f.report and f.report.searched else (None, None))
            )
            shots += _shot(r, page, bbox, f"{_CHECKS[r][4]} total")
        out.append(
            {
                "association": any_f.name,
                "first_page": any_f.first_page,
                "last_page": any_f.last_page,
                "flagged": True,
                "result": {
                    "problem": problem,
                    "shots": shots,
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
    shots: list[list[dict[str, Any]]],
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
            "checks": [_check_json(c, s) for c, s in zip(checks, shots, strict=True)],
        },
    }


def all_shots(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every shot in the results, to have its image filled in."""
    out = []
    for r in results:
        res = r["result"]
        out += res.get("shots", [])
        for c in res.get("checks", []):
            out += c.get("shots", [])
    return out


__all__ = [
    "ROLES",
    "Found",
    "all_shots",
    "compare",
    "explain",
    "looks_like",
    "read_section",
    "reconcile",
]
