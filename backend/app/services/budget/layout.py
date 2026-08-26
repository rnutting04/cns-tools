# app/services/budget/layout.py
#
# Shared workbook-layout detection for the budget pipeline.
#
# WHY THIS MODULE EXISTS
# ----------------------
# Ingest (stage 1) and render (stage 5) both have to answer the same four
# questions about an association's workbook:
#
#   1. Which worksheet holds the budget?
#   2. Which column holds the row labels?
#   3. Which columns hold prior-year / projected / proposed amounts?
#   4. Which rows are section headers, and what section does each start?
#
# Those answers used to live twice — once in ingest.py, once in render.py —
# with subtly different code. They drifted, and both copies shared the same
# blind spots: sheet chosen by name containing "budget" (so a sheet named
# "2025" was never found), and value columns required the literal word
# "budget" (so "2026 ADOPTED" was never found). Detection now lives here once
# and both stages import it, so a fix lands in both places at the same time.
#
# Everything here is deterministic. When detection is not confident enough,
# `SheetLayout.warnings` explains why, and the caller decides whether to fall
# back to AI layout mapping or ask a human to confirm.

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from app.services.budget.schema import BudgetSection

# ── Value-column vocabulary ──────────────────────────────────────────────────
# Associations label the same three columns half a dozen different ways:
#   "2025 BUDGET" / "2025 PROPOSED BUDGET" / "2025 Budget"   → an adopted budget
#   "2026 ADOPTED" / "2026 Final"                            → also an adopted budget
#   "2025 PROJECTED" / "Projected 2025" / "2025 ANNUAL PROJECTED" → projected
#   "2025 ACTUAL"                                            → actuals, never a budget
# Role detection is keyword-based but does NOT require the word "budget",
# which is what previously made MCP's "2026 ADOPTED" column invisible.
_PROJECTED_KW = ("projected", "projection")
_ACTUAL_KW = ("actual",)
_ADOPTED_KW = ("budget", "adopted", "proposed", "final", "approved")

_YEAR_RE = re.compile(r"\b(20\d{2})\b")


@dataclass
class ValueColumn:
    """One year-stamped numeric column in the budget sheet."""

    col: int
    year: int | None
    role: str  # "adopted" | "projected" | "actual"
    header: str


@dataclass
class SheetLayout:
    """Everything the pipeline needs to know about one association's workbook."""

    sheet_title: str
    header_row: int
    label_col: int
    gl_col: int | None
    prior_col: int | None  # source of prior-year amounts (ingest reads this)
    projected_col: int | None
    proposed_col: int | None  # newest adopted column (render's new-year slot)
    notes_col: int | None
    value_cols: list[ValueColumn] = field(default_factory=list)
    # first row of real budget data; rows above it are the assessment-rate preamble
    data_start_row: int = 0
    # row index → section that starts at that row
    section_rows: dict[int, BudgetSection] = field(default_factory=dict)
    # row index → the sheet's OWN header text for that section. A workbook may
    # keep two sections that normalize to one BudgetSection (MCP splits
    # "BUILDING AND GROUNDS" from "MAINTENANCE", each with its own printed
    # subtotal). Keeping the source label lets each retain its own subtotal row
    # instead of being merged into one.
    section_source_labels: dict[int, str] = field(default_factory=dict)
    # subtotal group ("SECTION::Sheet Heading") → the sheet's own subtotal row.
    # Render writes each group's =SUM into this exact row, so it never has to
    # guess from label text. That guessing was unreliable across associations:
    # "TOTAL BLDG & GROUNDS", "TOTAL UTILITES" (sic) and a bare "TOTAL OPERATING"
    # used for an expense block all defeat name matching.
    subtotal_rows: dict[str, int] = field(default_factory=dict)
    reserve_sheet: str | None = None
    warnings: list[str] = field(default_factory=list)
    signature: str = ""

    @property
    def confident(self) -> bool:
        return not self.warnings


def to_number(value) -> float | None:
    """Coerce a cell value to float, or return None if it isn't numeric.

    Handles real numbers AND text-formatted numbers, since some association
    templates store amounts as strings rather than numbers, e.g. " 998,385 ",
    "$1,000.00", or "(1,200)" for a negative. Without this, every text-stored
    amount reads as non-numeric and its whole row looks like an empty divider,
    which makes the parser find zero line items.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace("$", "").replace(",", "").replace("%", "").strip()
    if s in ("", "-", "–", "—"):
        return None
    try:
        num = float(s)
    except ValueError:
        return None
    return -num if negative else num


# ── Section-header classification ────────────────────────────────────────────
# Ordered; first substring match wins. Deliberately wider than the original
# lists, which only knew about income/revenue/operating/reserve on the income
# side and admin/maint/util/other/general/reserve/capital on the expense side.
# The additions are the exact headers that silently mis-parsed real workbooks:
#   "MEMBER ASSESSMENT"    (MCP)  → operating revenue, was unclassified
#   "BUILDING AND GROUNDS" (MCP)  → maintenance,       was unclassified
#   "REPAIR AND MAINTENANCE" (HAW)→ maintenance
#   "EXPENSES FOR THE HOA" + bare "Operating" (RVL) → a single flat expense block
_INCOME_SECTION_KEYWORDS: list[tuple[str, BudgetSection]] = [
    ("reserve", BudgetSection.REVENUE_RESERVES),
    ("income", BudgetSection.REVENUE_OPERATING),
    ("revenue", BudgetSection.REVENUE_OPERATING),
    ("assessment", BudgetSection.REVENUE_OPERATING),
    ("member", BudgetSection.REVENUE_OPERATING),
    ("dues", BudgetSection.REVENUE_OPERATING),
    ("operating", BudgetSection.REVENUE_OPERATING),
]

_EXPENSE_SECTION_KEYWORDS: list[tuple[str, BudgetSection]] = [
    ("admin", BudgetSection.ADMINISTRATION),
    ("util", BudgetSection.UTILITIES),
    ("maint", BudgetSection.MAINTENANCE),
    ("repair", BudgetSection.MAINTENANCE),
    ("grounds", BudgetSection.MAINTENANCE),
    ("building", BudgetSection.MAINTENANCE),
    ("landscap", BudgetSection.MAINTENANCE),
    ("reserve", BudgetSection.RESERVES),
    ("capital", BudgetSection.RESERVES),
    ("other", BudgetSection.OTHER),
    ("general", BudgetSection.OTHER),
    ("misc", BudgetSection.OTHER),
    # Bare "Operating" as an EXPENSE block (RVL) is a flat, unsectioned list
    # mixing admin/utilities/maintenance under one subtotal. Mapping it to
    # OTHER matches the sheet's own single "TOTAL OPERATING" expense row —
    # OTHER is an operating-expense section in assemble.py's grand totals.
    ("operating", BudgetSection.OTHER),
]

# Headers that mark the income → expense transition even though they are not
# themselves a section (e.g. "EXPENSES", "EXPENSES FOR ASSOCIATION").
_EXPENSE_BOUNDARY_RE = re.compile(r"\bexpense", re.I)

# "Strong" headers open the real budget body. Everything above the first one is
# the assessment-rate preamble: per-unit/per-quarter rate tables that carry
# numbers but are not budget line items. PRD's preamble is 25 rows of rates by
# building type (Sago, Norfork, Alexandra...) that would otherwise be ingested
# as operating-revenue line items. Sheets with no strong header at all (MCP)
# skip preamble trimming entirely and rely on the junk-label filter instead.
_STRONG_HEADER_RE = re.compile(r"\b(income|revenues?|expenses?)\b", re.I)

# Rows that carry numbers but are not budget line items.
_JUNK_LABEL_RE = re.compile(
    r"^\s*(surplus|deficit|surplus[/\-]|check\s*figure|per\s+unit|per\s+quarter|"
    r"per\s+month|assessment\s+for\s+year|#\s*of\s+units|\(a\+b\))",
    re.I,
)


def classify_section(text: str, expense_mode: bool) -> BudgetSection | None:
    t = text.strip().lower()
    table = _EXPENSE_SECTION_KEYWORDS if expense_mode else _INCOME_SECTION_KEYWORDS
    for kw, section in table:
        if kw in t:
            return section
    return None


def is_total_row(label: str) -> bool:
    u = label.strip().upper()
    return u.startswith("TOTAL") or u.startswith("[SUBTOTAL]") or u.endswith("TOTAL")


def is_junk_row(label: str) -> bool:
    return bool(_JUNK_LABEL_RE.match(label.strip()))


# ── Sheet selection ──────────────────────────────────────────────────────────
_SHEET_NAME_PENALTY = ("graph", "chart", "total", "summary", "pivot")
_SHEET_SECTION_PROBE = (
    "income",
    "revenue",
    "expense",
    "administration",
    "maintenance",
    "utilities",
    "reserve",
    "operating",
    "assessment",
)


def score_sheet(ws) -> int:
    """
    Score how likely a worksheet is to be THE budget sheet.

    Name matching alone was the original bug: GOR's budget lives on a sheet
    named "2025", while sheets named "Totals" and "Chart1" sort ahead of it,
    so `worksheets[0]` picked a 6-row summary tab and the parse produced zero
    line items. Scoring uses structure instead, and the dominant signal is a
    year-stamped value column — a real budget sheet always has one, and
    graph/summary tabs never do.
    """
    if ws.max_row < 5 or ws.max_column < 2:
        return -100

    score = 0
    name = (ws.title or "").strip().lower()
    if "budget" in name:
        score += 5
    if any(p in name for p in _SHEET_NAME_PENALTY):
        score -= 5

    # Strongest signal: a year-stamped value column in the first few rows.
    if _scan_value_columns(ws)[0]:
        score += 8

    # Section vocabulary and TOTAL rows, scanned across the whole label area.
    text_cells: list[str] = []
    for row in range(1, min(ws.max_row, 120) + 1):
        for col in range(1, min(ws.max_column, 4) + 1):
            v = ws.cell(row=row, column=col).value
            if isinstance(v, str) and v.strip():
                text_cells.append(v.strip().lower())

    joined = " ".join(text_cells)
    score += 3 * sum(1 for kw in _SHEET_SECTION_PROBE if kw in joined)
    score += 2 * min(sum(1 for t in text_cells if t.startswith("total")), 5)

    # Numeric density.
    numeric = sum(
        1
        for row in range(1, min(ws.max_row, 120) + 1)
        for col in range(1, min(ws.max_column, 12) + 1)
        if to_number(ws.cell(row=row, column=col).value) is not None
    )
    score += min(numeric // 10, 8)
    return score


def pick_budget_sheet(wb):
    """Return the worksheet most likely to hold the budget."""
    best, best_score = None, -10_000
    for ws in wb.worksheets:
        s = score_sheet(ws)
        if s > best_score:
            best, best_score = ws, s
    return best if best is not None else wb.worksheets[0]


def find_reserve_sheet(wb, budget_sheet_title: str) -> str | None:
    """
    Return the name of the reserve-study sheet, if the workbook has one.

    GOR ("Reserve"), MOR ("Reserves") and PRD ("reserve") all ship the full
    reserve study — total life, remaining life, replacement cost, current
    balance — right in the workbook. That is strictly better data than asking
    the AI to recover reserve balances from the PDF.
    """
    for ws in wb.worksheets:
        if ws.title == budget_sheet_title:
            continue
        name = (ws.title or "").strip().lower()
        if "reserve" in name:
            return ws.title
    return None


# ── Column detection ─────────────────────────────────────────────────────────
def _scan_value_columns(ws) -> tuple[list[ValueColumn], int]:
    """
    Find year-stamped value columns and the header row they live on.

    Returns ([], 1) when the sheet has no recognizable header row.
    """
    for check_row in range(1, min(ws.max_row, 8) + 1):
        found: list[ValueColumn] = []
        for col in range(1, ws.max_column + 1):
            raw = ws.cell(row=check_row, column=col).value
            if raw is None:
                continue
            h = str(raw).strip()
            if not h:
                continue
            hl = h.lower()
            m = _YEAR_RE.search(h)

            if any(k in hl for k in _PROJECTED_KW):
                role = "projected"
            elif any(k in hl for k in _ACTUAL_KW):
                role = "actual"
            elif any(k in hl for k in _ADOPTED_KW):
                role = "adopted"
            else:
                continue

            # A year is what separates a column header ("2026 ADOPTED") from a
            # sheet title ("Morton Village ADOPTED Operating Budget") or a
            # section header ("OPERATING BUDGET"). Allow a short bare phrase
            # too, for legacy templates whose header is just "BUDGET".
            if not m and len(h.split()) > 2:
                continue
            found.append(
                ValueColumn(col=col, year=int(m.group(1)) if m else None, role=role, header=h)
            )

        # Require at least two value columns so a stray "Actual" label in the
        # body of the sheet cannot be mistaken for the header row.
        if len(found) >= 2:
            return found, check_row
    return [], 1


def detect_label_col(ws, header_row: int = 1) -> int:
    """
    Return the 1-based column index holding row labels.

    Scans columns 1-4 and returns the leftmost with at least three alphabetic
    cells. Handles templates where column A is blank or holds numeric GL codes
    and the real labels live in column B.
    """
    start = header_row + 1
    for col in range(1, min(ws.max_column, 4) + 1):
        letters = sum(
            1
            for row in range(start, min(ws.max_row, start + 60) + 1)
            if (v := ws.cell(row=row, column=col).value) is not None
            and to_number(v) is None
            and re.search(r"[a-zA-Z]", str(v))
        )
        if letters >= 3:
            return col
    return 1


def _detect_gl_col(ws, label_col: int, header_row: int) -> int | None:
    """A GL-code column sits immediately left of the labels and holds 4-5 digit codes."""
    if label_col <= 1:
        return None
    col = label_col - 1
    hits = 0
    for row in range(header_row + 1, min(ws.max_row, header_row + 80) + 1):
        v = ws.cell(row=row, column=col).value
        if v is None:
            continue
        s = str(v).strip()
        if re.fullmatch(r"\d{4,5}(\.\d+)?[a-z]?", s, re.I):
            hits += 1
    return col if hits >= 3 else None


def _detect_notes_col(ws, value_cols: list[ValueColumn], header_row: int) -> int | None:
    """
    Find a free-text notes/comments column.

    MOR's column K and PRD's "COMMENTS" column carry the analyst's rationale
    ("Increase 5%", "Decreased Audit not req'd"). That is the context that makes
    a proposed number defensible, so it is worth carrying through the pipeline
    rather than discarding.
    """
    # Header-labelled first.
    for col in range(1, ws.max_column + 1):
        raw = ws.cell(row=header_row, column=col).value
        if raw is None:
            continue
        h = str(raw).strip().lower()
        if h in ("comments", "comment", "notes", "note") or h.startswith("note"):
            return col

    # Otherwise: the first column right of the value columns with several
    # multi-word text cells and no numbers.
    if not value_cols:
        return None
    start = max(v.col for v in value_cols) + 1
    for col in range(start, min(ws.max_column, start + 4) + 1):
        prose = 0
        for row in range(header_row + 1, min(ws.max_row, header_row + 80) + 1):
            v = ws.cell(row=row, column=col).value
            if isinstance(v, str) and len(v.split()) >= 2 and to_number(v) is None:
                prose += 1
        if prose >= 3:
            return col
    return None


def detect_columns(
    ws, budget_year: int
) -> tuple[list[ValueColumn], int, int | None, int | None, int | None, int]:
    """
    Resolve value columns into (value_cols, prior, projected, proposed, notes, header_row).

    prior_col is the ADOPTED column stamped budget_year-1 — the slot that the
    previous pipeline run filled and that now holds last year's adopted budget.
    proposed_col is the newest adopted column (render's write target for the
    new year). Columns whose role is "actual" are never eligible as prior_col:
    reading MCP's "2025 ACTUAL" instead of its "2026 ADOPTED" was exactly the
    silent wrong-column bug.
    """
    value_cols, header_row = _scan_value_columns(ws)
    if not value_cols:
        return [], None, None, None, None, header_row

    adopted = [v for v in value_cols if v.role == "adopted"]
    projected = next((v.col for v in value_cols if v.role == "projected"), None)

    prior_col: int | None = None
    exact = [v for v in adopted if v.year == budget_year - 1]
    if exact:
        prior_col = exact[0].col
    elif adopted:
        # No exact year match: the newest adopted column is the best guess.
        dated = [v for v in adopted if v.year is not None]
        prior_col = max(dated, key=lambda v: v.year).col if dated else adopted[-1].col

    proposed_col: int | None = None
    if adopted:
        dated = [v for v in adopted if v.year is not None]
        proposed_col = (
            max(dated, key=lambda v: v.year).col if dated else max(v.col for v in adopted)
        )

    notes = _detect_notes_col(ws, value_cols, header_row)
    return value_cols, prior_col, projected, proposed_col, notes, header_row


# ── Section mapping ──────────────────────────────────────────────────────────
def map_sections(ws, label_col: int, value_cols: list[ValueColumn], header_row: int):
    """
    Walk the sheet and return (section_rows, subtotal_rows, warnings).

    The income → expense boundary is resolved in priority order:
      1. a row matching /expense/            (GOR, MOR, PRD, HAW, RVL)
      2. a TOTAL INCOME / TOTAL REVENUE row  (GOR, MOR, PRD, HAW)
      3. the first header that can ONLY be an expense category (MCP)

    Rule 3 is what fixes MCP: it has no "EXPENSES" divider and no
    "TOTAL INCOME" row, so the old parser stayed in income mode for the entire
    sheet, every expense header failed to classify, and all 35 lines landed in
    REVENUE_RESERVES.
    """
    data_cols = [v.col for v in value_cols] or [
        c for c in range(1, ws.max_column + 1) if c != label_col
    ]

    section_rows: dict[int, BudgetSection] = {}
    section_source_labels: dict[int, str] = {}
    subtotal_rows: dict[str, int] = {}
    warnings: list[str] = []

    # Pass 1 — find where the real budget body starts (see _STRONG_HEADER_RE).
    data_start = header_row + 1
    for row in range(header_row + 1, ws.max_row + 1):
        raw = ws.cell(row=row, column=label_col).value
        if raw is None:
            continue
        label = str(raw).strip()
        if not label or not _STRONG_HEADER_RE.search(label):
            continue
        if any(to_number(ws.cell(row=row, column=c).value) is not None for c in data_cols):
            continue  # a "Total Income" figure row, not a divider
        data_start = row
        break

    expense_mode = False
    current: BudgetSection | None = None
    current_source: str | None = None
    # header row → label, so a section claimed by two headers can be reported
    header_labels: dict[BudgetSection, list[str]] = {}

    for row in range(data_start, ws.max_row + 1):
        raw = ws.cell(row=row, column=label_col).value
        if raw is None:
            continue
        label = str(raw).strip()
        if not label:
            continue

        has_numbers = any(
            to_number(ws.cell(row=row, column=c).value) is not None for c in data_cols
        )

        # Explicit boundary marker.
        if not expense_mode and _EXPENSE_BOUNDARY_RE.search(label) and not has_numbers:
            expense_mode = True
            # "OTHER EXPENSE"/"EXPENSES FOR THE HOA" are both a boundary AND a
            # section header, so fall through to classification below.

        if is_total_row(label):
            if not expense_mode and re.search(r"\b(income|revenue)\b", label, re.I):
                expense_mode = True
            if current is not None:
                group = f"{current.value}::{current_source}" if current_source else current.value
                subtotal_rows.setdefault(group, row)
            continue

        if has_numbers:
            continue  # ordinary line item

        # Header row (no numbers). Try the current mode, then check whether it
        # is an unambiguous expense header that should flip us into expense mode.
        sec = classify_section(label, expense_mode)
        if not expense_mode:
            forced = classify_section(label, True)
            if sec is None and forced in (
                BudgetSection.ADMINISTRATION,
                BudgetSection.MAINTENANCE,
                BudgetSection.UTILITIES,
            ):
                expense_mode = True
                sec = forced

        if sec is not None:
            section_rows[row] = sec
            section_source_labels[row] = label
            header_labels.setdefault(sec, []).append(label)
            current = sec
            current_source = label

    if not section_rows:
        warnings.append("No section headers were recognized on the budget sheet.")
    elif len({s for s in section_rows.values()}) == 1:
        warnings.append(
            f"Every line was classified into a single section "
            f"({next(iter(section_rows.values())).value}) — section headers were "
            f"probably not recognized."
        )

    return section_rows, section_source_labels, subtotal_rows, warnings, data_start


def build_layout(wb, budget_year: int) -> SheetLayout:
    """Detect the full layout of a workbook. Never raises; reports doubt in `warnings`."""
    ws = pick_budget_sheet(wb)
    value_cols, prior, projected, proposed, notes, header_row = detect_columns(ws, budget_year)
    label_col = detect_label_col(ws, header_row)
    gl_col = _detect_gl_col(ws, label_col, header_row)
    section_rows, section_source_labels, subtotal_rows, warnings, data_start = map_sections(
        ws, label_col, value_cols, header_row
    )

    if not value_cols:
        warnings.append(
            "No year-stamped budget columns found — could not tell which column "
            "holds last year's adopted amounts."
        )
    elif prior is None:
        warnings.append(
            f"No adopted budget column for {budget_year - 1} — "
            f"found: {', '.join(v.header for v in value_cols)}."
        )

    lay = SheetLayout(
        sheet_title=ws.title,
        header_row=header_row,
        label_col=label_col,
        gl_col=gl_col,
        prior_col=prior,
        projected_col=projected,
        proposed_col=proposed,
        notes_col=notes,
        value_cols=value_cols,
        data_start_row=data_start,
        section_rows=section_rows,
        section_source_labels=section_source_labels,
        subtotal_rows=subtotal_rows,
        reserve_sheet=find_reserve_sheet(wb, ws.title),
        warnings=warnings,
    )
    lay.signature = fingerprint(ws, lay)
    return lay


def render_columns(
    layout: SheetLayout, budget_year: int
) -> tuple[int, int | None, int, int | None]:
    """
    Resolve render's WRITE destinations: (prior_dest, projected, proposed, notes).

    Ingest and render deliberately target different columns. Each run shifts the
    workbook forward one year:
      - ingest READS the adopted column stamped budget_year-1 (last year's
        adopted budget).
      - render WRITES last year's values into the column stamped budget_year-2
        and re-headers it, then clears the newest adopted column to become the
        blank proposed slot for budget_year.

    Sharing SheetLayout means both stages agree on the sheet, the label column
    and the set of value columns even though they pick different targets — which
    is what stopped them drifting apart.
    """
    adopted = [v for v in layout.value_cols if v.role == "adopted"]
    if not adopted:
        # Unrecognizable headers: fall back to the historical B / D guess.
        return 2, layout.projected_col, 4, layout.notes_col

    dated = [v for v in adopted if v.year is not None]
    proposed = max(dated, key=lambda v: v.year).col if dated else max(v.col for v in adopted)

    dest = [v.col for v in adopted if v.year == budget_year - 2 and v.col != proposed]
    if dest:
        prior_dest = dest[0]
    else:
        others = [v.col for v in adopted if v.col != proposed]
        if others:
            prior_dest = others[0]
        else:
            # Only ONE adopted column (MCP: ACTUAL | PROJECTED | ADOPTED). There
            # is no second budget column to shift into, so last year's figures
            # belong in the historical "actual" slot. Without this, prior_dest
            # collided with proposed and render wrote both into the same column.
            actual = [v.col for v in layout.value_cols if v.role == "actual" and v.col != proposed]
            spare = [
                v.col for v in layout.value_cols if v.col not in (proposed, layout.projected_col)
            ]
            prior_dest = actual[0] if actual else (spare[0] if spare else proposed)

    return prior_dest, layout.projected_col, proposed, layout.notes_col


def self_check(ws, layout: SheetLayout, lines: list[dict]) -> list[str]:
    """
    Verify a parse against the workbook's own arithmetic.

    An HOA operating budget balances: total revenue equals total expenses. The
    sheet also prints its own TOTAL INCOME row. Both are independent of how the
    parser reached its answer, which makes them a genuine check rather than a
    restatement of the parse — the MCP and RVL mis-parses that used to sail
    through would both fail here, because every line landing in one section
    leaves the opposite side at zero.

    Returns a list of problems; empty means the parse can be trusted to run
    unattended.
    """
    problems: list[str] = []
    if not lines:
        return ["No budget line items were found."]

    revenue = sum(
        ln["prior_year"] or 0.0 for ln in lines if ln["section"].value.startswith("REVENUE")
    )
    expense = sum(
        ln["prior_year"] or 0.0 for ln in lines if not ln["section"].value.startswith("REVENUE")
    )

    if revenue == 0:
        problems.append("No revenue lines were found — the income section was not recognized.")
    if expense == 0:
        problems.append("No expense lines were found — expense sections were not recognized.")

    if revenue and expense:
        diff = abs(revenue - expense)
        tol = max(1.0, revenue * 0.005)  # 0.5%, absorbs rounding across ~50 lines
        if diff > tol:
            problems.append(
                f"Budget does not balance: revenue ${revenue:,.2f} vs expenses "
                f"${expense:,.2f} (${diff:,.2f} apart). A line may be in the wrong "
                f"section, or read from the wrong column."
            )

    # Tie back to the sheet's own printed TOTAL INCOME, when it has one.
    for row in range(layout.header_row + 1, ws.max_row + 1):
        raw = ws.cell(row=row, column=layout.label_col).value
        if raw is None:
            continue
        label = str(raw).strip()
        if not re.match(r"^\s*total\s+(income|revenue)", label, re.I):
            continue
        if layout.prior_col is None:
            break
        printed = to_number(ws.cell(row=row, column=layout.prior_col).value)
        if printed is None:
            break
        if abs(printed - revenue) > max(1.0, abs(printed) * 0.005):
            problems.append(
                f"Extracted revenue ${revenue:,.2f} does not match the sheet's own "
                f'"{label}" row of ${printed:,.2f}.'
            )
        break

    return problems


def fingerprint(ws, layout: SheetLayout) -> str:
    """
    Stable structural signature of a sheet layout.

    Two workbooks with the same fingerprint have the same shape, so a layout a
    human has already confirmed can be reused automatically instead of asking
    again. With ~200 associations this is what keeps confirmation from becoming
    200 separate reviews — the associations collapse into a handful of template
    families. The signature deliberately excludes amounts and association names
    so that next year's file for the same template still matches.
    """
    parts = [
        f"labels@{layout.label_col}",
        f"gl@{layout.gl_col}",
        f"hdr@{layout.header_row}",
        "cols="
        + ",".join(f"{v.col}:{v.role}" for v in sorted(layout.value_cols, key=lambda v: v.col)),
        f"notes@{layout.notes_col}",
        "secs=" + ",".join(_section_sequence(layout)),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def _section_sequence(layout: SheetLayout) -> list[str]:
    """
    The ordered section headings, without their row positions.

    Row NUMBERS are deliberately excluded from the fingerprint. Two associations
    on the same template carry different numbers of line items, which shifts
    every section down — fingerprinting positions would give each its own
    signature and turn "one review per template" into one review per
    association. What identifies a template is its column geometry and the
    sequence of section headings; where those sections start does not.
    """
    return [
        layout.section_source_labels.get(row, section.value).strip().upper()
        for row, section in sorted(layout.section_rows.items())
    ]
