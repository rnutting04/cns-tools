# app/services/budget/stages/render.py
#
# Stage 5 — Render
#
# Edits the previous year's xlsx workbook in place:
#   1. Detects which columns hold prior/projected/proposed/notes values
#   2. Updates column headers to the new budget year
#   3. Overwrites each data row's values from the validated BudgetOutput
#      - All data rows, subtotals, and totals: raw numeric values
#
# Any sheets beyond the Budget tab are left untouched, so any charts or
# formatting the association has added are preserved automatically.

import io
import re
from collections import defaultdict
from copy import copy
from dataclasses import dataclass

import openpyxl
from openpyxl.styles import PatternFill

from app.services.budget.exceptions import RenderFailed
from app.services.budget.schema import BudgetLine, BudgetOutput

BLUE_FILL = PatternFill(start_color="DDEEFF", end_color="DDEEFF", fill_type="solid")
NO_FILL = PatternFill(fill_type=None)

# Words ignored when doing keyword-prefix matching on subtotal rows
_SUBTOTAL_STOPWORDS = {"total", "and", "the", "of", "expense", "expenses"}


@dataclass
class RenderResult:
    xlsx_bytes: bytes
    review_flags: list[str]


def _copy_row_style(ws, src_row: int, dst_row: int) -> None:
    for col in range(1, ws.max_column + 1):
        src = ws.cell(row=src_row, column=col)
        dst = ws.cell(row=dst_row, column=col)
        if src.has_style:
            dst.font = copy(src.font)
            dst.border = copy(src.border)
            dst.fill = copy(src.fill)
            dst.number_format = src.number_format
            dst.protection = copy(src.protection)
            dst.alignment = copy(src.alignment)


def _find_budget_sheet(wb):
    """Return the Budget worksheet, falling back to the first sheet."""
    for name in wb.sheetnames:
        if "budget" in name.lower():
            return wb[name]
    return wb.worksheets[0]


def _detect_label_col(ws) -> int:
    """
    Return the 1-based column index that contains row labels.
    Scans columns 1-4 and returns the leftmost one with at least 3 cells
    containing alphabetic text in the first 40 data rows.
    Handles budgets where column A holds GL codes and labels are in column B.
    """
    for col in range(1, min(ws.max_column + 1, 5)):
        letter_count = sum(
            1
            for row in range(2, min(ws.max_row + 1, 42))
            if (v := ws.cell(row=row, column=col).value) is not None
            and not isinstance(v, int | float)
            and re.search(r"[a-zA-Z]", str(v))
        )
        if letter_count >= 3:
            return col
    return 1


def _detect_column_positions(ws, budget_year: int) -> tuple[int, int | None, int, int | None, int]:
    """
    Locate prior-year budget, projected, proposed-budget, and notes columns.

    Each pipeline run shifts the columns forward by one year:
      - The column currently labeled budget_year-2 receives the new prior-year
        header (budget_year-1 Budget) and values — it is the WRITE DESTINATION.
      - The column currently labeled budget_year-1 (the previously-proposed
        slot now filled with adopted values) is wiped and becomes the new
        proposed slot for budget_year — it is the proposed_col.

    Title cells like "Morton Village ADOPTED Operating Budget" are excluded by
    requiring either a 4-digit year OR a short phrase (<=3 words) for any cell
    to be treated as a budget column header.

    Returns (prior_col, projected_col, proposed_col, notes_col, header_row).
    projected_col is None when no Projected column exists.
    Falls back to columns B / D when headers are unrecognisable.
    """
    header_row = 1
    budget_cols: list[tuple[int, int | None]] = []  # (col_idx, parsed_year | None)
    projected_col: int | None = None
    notes_col: int | None = None

    for check_row in range(1, min(ws.max_row + 1, 6)):
        found_any = False
        for col in range(1, ws.max_column + 1):
            raw = ws.cell(row=check_row, column=col).value
            if raw is None:
                continue
            h = str(raw).strip()
            hl = h.lower()
            m_year = re.search(r"\b(20\d{2})\b", h)

            if "projected" in hl and (m_year or len(h.split()) <= 4):
                projected_col = col
                found_any = True
            elif "note" in hl and len(h.split()) <= 3:
                notes_col = col
                found_any = True
            elif "budget" in hl and m_year:
                # Primary: require a 4-digit year so section headers ("OPERATING
                # BUDGET"), subtitles ("ADOPTED Budget"), and spreadsheet titles
                # ("Morton Village ADOPTED Operating Budget") are never detected.
                budget_cols.append((col, int(m_year.group(1))))
                found_any = True
        if found_any:
            header_row = check_row
            break

    # Fallback: no year-stamped budget column found (rare legacy templates that
    # use bare "BUDGET" or two-word "XXXX BUDGET" headers without a 4-digit year).
    if not budget_cols:
        for check_row in range(1, min(ws.max_row + 1, 6)):
            for col in range(1, ws.max_column + 1):
                raw = ws.cell(row=check_row, column=col).value
                if raw is None:
                    continue
                parts = str(raw).strip().split()
                if parts and parts[-1].upper() == "BUDGET" and len(parts) <= 2:
                    budget_cols.append((col, None))
            if budget_cols:
                break

    if not budget_cols:
        return (2, None, 4, notes_col, header_row)

    # proposed_col = rightmost budget column (becomes the new-year blank slot)
    proposed_col = max(c for c, _ in budget_cols)

    # prior_col = the column to WRITE the new prior-year data into.
    # It currently carries year = budget_year - 2 from the previous pipeline run.
    # Fallback: second-to-last (for first-run templates where that year is absent).
    prior_dest_year = budget_year - 2
    prior_matches = [c for c, y in budget_cols if y == prior_dest_year]
    if prior_matches:
        prior_col = prior_matches[0]
    else:
        non_proposed = [c for c, _ in budget_cols if c != proposed_col]
        prior_col = non_proposed[0] if non_proposed else proposed_col

    return (
        prior_col,
        projected_col,
        proposed_col,
        notes_col,
        header_row,
    )


def _find_row(
    label_to_rows: dict[str, list[int]],
    claimed: set[int],
    label: str,
    is_computed: bool,
) -> int | None:
    """
    Return the first unclaimed xlsx row matching *label*.

    Pass 1 — exact case-insensitive match.
    Pass 2 — keyword-prefix forward match: every significant word in the
              budget label prefix-matches some word in the xlsx row.
              "Total Administration" matches "TOTAL ADMIN."
    Pass 3 — keyword-prefix reverse match: every significant word in the
              xlsx row prefix-matches some word in the budget label.
              Handles xlsx rows that are shorter than the budget label, e.g.
              "TOTAL OPERATING AND" matching "Total Operating and Reserves".
    """
    key = label.strip().lower()

    # Pass 1: exact (case-insensitive)
    for row in label_to_rows.get(key, []):
        if row not in claimed:
            return row

    if not is_computed:
        return None

    sig_words = [w.strip(".,()[]/-+") for w in key.split() if w not in _SUBTOTAL_STOPWORDS]
    sig_words = [w for w in sig_words if len(w) >= 4]
    if not sig_words:
        return None

    # Pass 2: all budget sig-words must find a prefix match in the xlsx row.
    for xlsx_key, rows in label_to_rows.items():
        if "total" not in xlsx_key and "surplus" not in xlsx_key:
            continue
        xlsx_words = [w.strip(".,()[]/-+") for w in xlsx_key.split()]
        xlsx_words = [w for w in xlsx_words if len(w) >= 4]
        if not xlsx_words:
            continue
        if all(
            any(
                sw[: max(4, min(len(sw), len(xw)))] == xw[: max(4, min(len(sw), len(xw)))]
                for xw in xlsx_words
            )
            for sw in sig_words
        ):
            for row in rows:
                if row not in claimed:
                    return row

    # Pass 3: all xlsx sig-words must find a prefix match in the budget sig-words.
    # Catches abbreviated xlsx rows ("TOTAL OPERATING AND") that are a strict
    # subset of the full budget label ("Total Operating and Reserves").
    for xlsx_key, rows in label_to_rows.items():
        if "total" not in xlsx_key and "surplus" not in xlsx_key:
            continue
        xlsx_sig = [w.strip(".,()[]/-+") for w in xlsx_key.split() if w not in _SUBTOTAL_STOPWORDS]
        xlsx_sig = [w for w in xlsx_sig if len(w) >= 4]
        if not xlsx_sig:
            continue
        if all(
            any(
                xs[: max(4, min(len(xs), len(sw)))] == sw[: max(4, min(len(xs), len(sw)))]
                for sw in sig_words
            )
            for xs in xlsx_sig
        ):
            for row in rows:
                if row not in claimed:
                    return row

    return None


def run(budget: BudgetOutput, review_flags: list[str], prev_year_xlsx_bytes: bytes) -> RenderResult:
    """
    Stage 5: edit the previous year's xlsx with new budget values.

    Loads the workbook, locates the Budget sheet, detects column positions
    from the header row, shifts all headers to the new year, and writes
    prior/projected/proposed values for every line in BudgetOutput.

    All rows receive raw numeric values — no Excel formulas are written.
    Projected values are already computed by Stage 2, so live formulas
    are unnecessary and were causing #REF! errors from stale prior-year
    references.

    Raises RenderFailed on any openpyxl error.
    """
    try:
        wb = openpyxl.load_workbook(io.BytesIO(prev_year_xlsx_bytes))
        ws = _find_budget_sheet(wb)

        # Detect which column holds row labels — some budgets have GL codes in
        # column A and text labels in column B; hardcoding column A would cause
        # label_to_rows to be keyed by GL numbers and nothing would ever match.
        label_col = _detect_label_col(ws)

        # Load a second copy with data_only=True so we can read cached formula
        # results from the assessment preamble without destroying the formulas.
        wb_data = openpyxl.load_workbook(io.BytesIO(prev_year_xlsx_bytes), data_only=True)
        ws_data = _find_budget_sheet(wb_data)

        prior_col, projected_col, proposed_col, notes_col, header_row = _detect_column_positions(
            ws, budget.budget_year
        )

        # Shift column headers to the new budget year
        prior_year_int = budget.budget_year - 1
        ws.cell(row=header_row, column=prior_col).value = f"{prior_year_int} Budget"
        if projected_col is not None:
            ws.cell(row=header_row, column=projected_col).value = f"Projected {prior_year_int}"
        ws.cell(row=header_row, column=proposed_col).value = f"{budget.budget_year} BUDGET"

        data_start = header_row + 1

        # Detect the preamble boundary: rows before the first recognized budget
        # section header (INCOME, OPERATING, etc.) are assessment tables that
        # must be handled separately from the main budget line-item loop.
        # Rows containing "assessment" are explicitly excluded so sub-headers
        # like "Quarterly Assessment" don't terminate preamble detection early.
        _SECTION_KW = frozenset(
            {
                "income",
                "revenue",
                "operating",
                "administration",
                "maintenance",
                "expense",
                "expenses",
                "utility",
                "utilities",
            }
        )
        preamble_end = data_start  # default: no preamble
        for _pr in range(data_start, ws.max_row + 1):
            _pv = ws.cell(row=_pr, column=label_col).value
            if _pv is None:
                continue
            _pt = str(_pv).strip().lower()
            if "assessment" in _pt:
                continue
            if any(kw in _pt for kw in _SECTION_KW):
                # Check only budget data columns for numeric values — GL code
                # columns (which contain integers like 6010) would otherwise
                # cause every row to be classified as "has numeric values".
                _has_nums = any(
                    isinstance(ws_data.cell(row=_pr, column=c).value, int | float)
                    for c in [prior_col, projected_col, proposed_col]
                    if c is not None
                )
                if not _has_nums:
                    preamble_end = _pr
                    break

        # Build label → row index from column A (lowercase, stripped).
        # Start from the row after the detected header so header text is never
        # treated as a line-item label.
        # Normalize in-cell newlines so "TOTAL OPERATING AND\nRESERVES" matches
        # the budget line label "Total Operating and Reserves".
        label_to_rows: dict[str, list[int]] = {}
        for row in range(data_start, ws.max_row + 1):
            val = ws.cell(row=row, column=label_col).value
            if val is not None:
                key = str(val).strip().lower().replace("\n", " ")
                label_to_rows.setdefault(key, []).append(row)

        # ── Pre-phase: insert rows for lines not found in the Excel ───────────
        # Lines the AI found in the PDF that weren't in the original workbook
        # (prior_year=None, so the left column will be blank/zero). We insert
        # them before their section's subtotal so the main loop writes them
        # normally. Processing top-to-bottom with a cumulative shift counter
        # avoids stale row references after each insertion.

        _subtotal_label_for_section = {
            line.section.value: line.label
            for line in budget.lines
            if line.is_computed and line.code.startswith("subtotal_")
        }

        # Determine which data lines are missing from the workbook.
        _pre_claimed: set[int] = set()
        _unfound_by_section: dict[str, list[BudgetLine]] = defaultdict(list)
        for _line in budget.lines:
            if _line.is_computed:
                continue
            _r = _find_row(label_to_rows, _pre_claimed, _line.label, False)
            if _r is not None:
                _pre_claimed.add(_r)
            else:
                _unfound_by_section[_line.section.value].append(_line)

        if _unfound_by_section:
            # Locate each section's subtotal row.
            _st_claimed: set[int] = set()
            _subtotal_pos: dict[str, int] = {}
            for _sec, _lbl in _subtotal_label_for_section.items():
                _r = _find_row(label_to_rows, _st_claimed, _lbl, True)
                if _r is not None:
                    _subtotal_pos[_sec] = _r
                    _st_claimed.add(_r)

            # Insert rows top-to-bottom so earlier insertions don't shift later positions.
            _ordered_secs = sorted(
                _unfound_by_section.keys(),
                key=lambda s: _subtotal_pos.get(s, 9999),
            )
            _shift = 0
            for _sec in _ordered_secs:
                _new_lines = _unfound_by_section[_sec]
                _base = _subtotal_pos.get(_sec)
                if _base is None:
                    continue
                _insert_at = _base + _shift

                # Skip blank spacing rows above the subtotal so the new item
                # lands adjacent to the last real data row, not in the gap.
                while _insert_at > data_start + 1:
                    _prev_val = ws.cell(row=_insert_at - 1, column=label_col).value
                    if _prev_val is not None and str(_prev_val).strip():
                        break
                    _insert_at -= 1

                # Find a real line-item row for style: scan backwards past blanks
                # and subtotal rows to get a normal data-row style.
                _style_template = _insert_at - 1
                while _style_template > data_start:
                    _tmpl_val = ws.cell(row=_style_template, column=label_col).value
                    if _tmpl_val is not None and str(_tmpl_val).strip():
                        _tu = str(_tmpl_val).strip().upper()
                        if not _tu.startswith("TOTAL") and not _tu.startswith("[SUBTOTAL]"):
                            break
                    _style_template -= 1

                for _i, _nl in enumerate(_new_lines):
                    ws.insert_rows(_insert_at + _i)
                    _copy_row_style(ws, _style_template, _insert_at + _i)
                    ws.cell(row=_insert_at + _i, column=label_col).value = _nl.label
                _shift += len(_new_lines)

            # Rebuild the label index so the main loop finds inserted rows.
            label_to_rows = {}
            for _r in range(data_start, ws.max_row + 1):
                _v = ws.cell(row=_r, column=label_col).value
                if _v is not None:
                    _k = str(_v).strip().lower().replace("\n", " ")
                    label_to_rows.setdefault(_k, []).append(_r)

        # The pipeline writes to exactly two detected columns:
        #   prior_col     ← prior_year (the adopted budget from last cycle)
        #   projected_col ← projected  (annualised YTD actuals)
        # proposed_col is wiped to blank so stale values from a previous run
        # don't linger, but no computed values are written there — the
        # association fills in the new budget column manually (or via their
        # own Excel formulas that read from prior_col and projected_col).
        #
        # Preamble rows (assessment tables before the first section header) are
        # excluded from the wipe: their proposed_col formulas are preserved, and
        # the prior/projected columns are filled from those formula results below.
        active_cols = [c for c in [prior_col, projected_col] if c is not None]

        for _wipe_col in active_cols:
            for _r in range(preamble_end, ws.max_row + 1):
                ws.cell(row=_r, column=_wipe_col).value = None
        if proposed_col is not None:
            for _r in range(preamble_end, ws.max_row + 1):
                ws.cell(row=_r, column=proposed_col).value = None

        # Assessment preamble: roll the old proposed_col value (computed from
        # the formula via the data-only workbook) into prior_col and projected_col
        # so the two historical columns carry last cycle's assessment amounts.
        # proposed_col is left untouched — its formulas auto-recalculate for the
        # new budget year when Excel opens the file.
        if preamble_end > data_start:
            for _pr in range(data_start, preamble_end):
                _pval = ws_data.cell(row=_pr, column=proposed_col).value
                if not isinstance(_pval, int | float):
                    continue
                ws.cell(row=_pr, column=prior_col).value = _pval
                if projected_col is not None:
                    ws.cell(row=_pr, column=projected_col).value = _pval

        def _raw_vals(line):
            """Map col → value for a line (data rows and computed rows alike)."""
            m: dict[int, object] = {prior_col: line.prior_year}
            if projected_col is not None:
                m[projected_col] = line.projected
            return m

        def _write_cols(row: int, col_formula_or_val: dict[int, object], fill=NO_FILL):
            for col, val in col_formula_or_val.items():
                cell = ws.cell(row=row, column=col)
                cell.value = val
                cell.fill = fill

        # --- tracking state ---
        claimed: set[int] = set()
        section_item_rows: dict[str, list[int]] = defaultdict(list)
        subtotal_excel_row: dict[str, int] = {}  # section_key → excel row of its subtotal

        for line in budget.lines:
            row = _find_row(label_to_rows, claimed, line.label, line.is_computed)
            if row is None:
                continue
            claimed.add(row)

            section_key = line.section.value

            if not line.is_computed:
                # ── Data row: write prior_year and projected ──────────────────
                raw = _raw_vals(line)
                for col in active_cols:
                    cell = ws.cell(row=row, column=col)
                    cell.value = raw.get(col)
                    cell.fill = NO_FILL
                if notes_col is not None:
                    ws.cell(row=row, column=notes_col).value = line.note or ""
                section_item_rows[section_key].append(row)

            elif line.code.startswith("subtotal_"):
                subtotal_excel_row[section_key] = row
                _write_cols(row, _raw_vals(line))

            else:
                # total_income, total_operating_and_reserves, surplus, and any
                # other computed rows — all written as plain numbers, no formulas.
                _write_cols(row, _raw_vals(line))

        # ── Post-pass: flag rows within section ranges that weren't matched ──────
        # These rows retain their existing values (intentional — they may be
        # valid budget items with a slightly different label). Just note them
        # so the reviewer can verify nothing was missed.
        for section_key, item_rows in section_item_rows.items():
            if not item_rows:
                continue
            first_row = min(item_rows)
            last_row = subtotal_excel_row.get(section_key, max(item_rows) + 1)
            for r in range(first_row, last_row):
                if r in claimed:
                    continue
                label_val = ws.cell(row=r, column=label_col).value
                if label_val is None:
                    continue
                label_str = str(label_val).strip()
                if not label_str:
                    continue
                review_flags.append(
                    f'Unmatched row in {section_key}: "{label_str}"'
                    f" (row {r}) — verify this line is accounted for"
                )

        buf = io.BytesIO()
        wb.save(buf)
        xlsx_bytes = buf.getvalue()

    except RenderFailed:
        raise
    except Exception as exc:
        raise RenderFailed(f"XLSX render failed: {exc}") from exc

    return RenderResult(xlsx_bytes=xlsx_bytes, review_flags=review_flags)
