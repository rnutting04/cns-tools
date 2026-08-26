# app/services/budget/reserves.py
#
# Parse the reserve study that ships inside the association's own workbook.
#
# GOR ("Reserve"), MOR ("Reserves") and PRD ("reserve") all carry the full
# reserve schedule — component, total life, remaining life, replacement cost,
# current balance, required deposit — which is exactly the ReserveItem shape.
# The pipeline previously ignored it and asked the AI to recover reserve
# balances from the PDF instead, which is strictly worse: the numbers are
# already here, exact, and free to read.
#
# Header layouts differ (headers stack across two rows, and start on row 1, 2
# or 6 depending on the association), so columns are matched semantically
# rather than by position.

import re

from app.services.budget.layout import SheetLayout, to_number

# How many rows a header block can span. All three known templates stack the
# header across exactly two rows ("Total" / "Life"), but allow a little slack.
_HEADER_SPAN = 2

# A "balance" column holds money currently in the fund. These qualifiers mean
# the column is a SHORTFALL instead — the money still needed — and must never
# be read as the current balance:
#   "Balance Needed" (GOR), "Net Additional Reserve Fund Requirements" (MOR),
#   "Add. Reserve Required" (PRD)
_SHORTFALL_WORDS = ("needed", "required", "additional", "add.", "requirement")


def _column_headers(ws, header_row: int, max_col: int, span: int = _HEADER_SPAN) -> dict[int, str]:
    """Flatten a stacked header block into one lowercase string per column."""
    headers: dict[int, str] = {}
    for col in range(1, max_col + 1):
        parts: list[str] = []
        for row in range(header_row, header_row + span):
            v = ws.cell(row=row, column=col).value
            if v is None:
                continue
            s = str(v).strip()
            # A bare year under a header ("2026") is a qualifier, not a label.
            if s and not re.fullmatch(r"20\d{2}", s):
                parts.append(s)
        headers[col] = " ".join(parts).strip().lower()
    return headers


def _resolve_columns(headers: dict[int, str]) -> dict[str, int] | None:
    """
    Map flattened header text to reserve-table roles.

    Returns None when the block doesn't look like a reserve table, which lets
    the caller try the next candidate header position.
    """
    cols: dict[str, int] = {}
    for col, h in headers.items():
        if not h:
            continue
        is_shortfall = any(w in h for w in _SHORTFALL_WORDS)

        if "remain" in h and "remaining_life" not in cols:
            cols["remaining_life"] = col
        elif "life" in h and "total_life" not in cols:
            cols["total_life"] = col

        if "cost" in h and "cost" not in cols:
            cols["cost"] = col

        # Take the RIGHTMOST qualifying balance: PRD prints both an opening
        # ("Balance Dec 31 2023") and a closing ("Est. Balance Dec 31, 2024")
        # balance, and the closing one is the current figure.
        if "balance" in h and not is_shortfall:
            cols["balance"] = col

        if "funding" in h or "deposit" in h:
            cols["deposit"] = col

    if "remaining_life" not in cols or "cost" not in cols:
        return None
    return cols


def _find_header_block(ws, max_col: int) -> tuple[int, int, dict[str, int]] | None:
    """
    Locate the reserve table's header block as (start_row, span, columns).

    Headers stack across rows, and the block starts on row 1 (GOR, MOR) or row 6
    (PRD). Worse, the words split across rows: GOR's row 1 holds "Total"/"Remain"
    and row 2 holds "Life"/"Life", so neither row alone identifies the table.
    Rather than guess the start, try each candidate and keep the first whose
    flattened headers actually resolve into a reserve table.
    """
    for start in range(1, min(ws.max_row, 20) + 1):
        for span in (2, 3):
            headers = _column_headers(ws, start, max_col, span)
            resolved = _resolve_columns(headers)
            if resolved is not None:
                return start, span, resolved
    return None


def parse_reserve_schedule(wb, layout: SheetLayout) -> list[dict]:
    """
    Return the reserve schedule from the workbook's reserve sheet.

    Each entry: {label, total_life_years, remaining_life_years,
                 replacement_cost, current_balance, required_deposit}

    Returns [] when the workbook has no reserve sheet or the table cannot be
    recognized — the caller then falls back to AI-extracted reserve balances.
    """
    if not layout.reserve_sheet or layout.reserve_sheet not in wb.sheetnames:
        return []

    ws = wb[layout.reserve_sheet]
    max_col = min(ws.max_column, 14)
    block = _find_header_block(ws, max_col)
    if block is None:
        return []

    header_row, span, cols = block
    total_life_col = cols.get("total_life")
    remaining_col = cols["remaining_life"]
    cost_col = cols["cost"]
    balance_col = cols.get("balance")
    deposit_col = cols.get("deposit")

    entries: list[dict] = []
    for row in range(header_row + span, ws.max_row + 1):
        label_raw = ws.cell(row=row, column=1).value
        if label_raw is None:
            continue
        label = str(label_raw).strip()
        if not label:
            continue

        remaining = to_number(ws.cell(row=row, column=remaining_col).value)
        total_life = (
            to_number(ws.cell(row=row, column=total_life_col).value) if total_life_col else None
        )
        cost = to_number(ws.cell(row=row, column=cost_col).value)

        # The grand-total row ("Total Reserves", "Total All Reserves") leaves the
        # life columns blank. Requiring a remaining life drops it while keeping
        # genuine components that happen to start with "Total" (MOR's "Total
        # Paving", "Total Pool").
        if remaining is None or cost is None:
            continue

        entries.append(
            {
                "label": label,
                "total_life_years": int(total_life) if total_life is not None else int(remaining),
                "remaining_life_years": int(remaining),
                "replacement_cost": float(cost),
                "current_balance": (
                    to_number(ws.cell(row=row, column=balance_col).value) or 0.0
                    if balance_col
                    else 0.0
                ),
                "required_deposit": (
                    to_number(ws.cell(row=row, column=deposit_col).value) if deposit_col else None
                ),
            }
        )

    return entries
