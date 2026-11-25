"""Check the MASS Reserve Schedule workbook.

One tab per association. Each tab has a header row (Code / Description /
Start of Year / Receipts / Adjustment / Percentage / Expenses / Balance),
one row per reserve component, optional group headings ("SIRS Waivable")
and subtotals ("Total Paint"), a TOTAL row, then a receipts breakdown and
notes below it.

Business rule: the Balance of each line item can never be negative. Totals
and subtotals are not checked, only the individual components.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import BinaryIO

import openpyxl
from openpyxl.utils import get_column_letter

# Balances are float sums in Excel; ignore noise below half a cent.
_EPSILON = Decimal("-0.005")


@dataclass
class LineIssue:
    sheet: str
    group: str  # heading the component sits under, e.g. "SIRS Non-Waivable"; "" if none
    cell: str  # e.g. "H10"
    row: int
    code: str
    description: str
    balance: Decimal | None  # None when the cell isn't a number
    problem: str  # "negative" | "not_a_number"


@dataclass
class SheetResult:
    name: str
    line_items: int = 0
    issues: list[LineIssue] = field(default_factory=list)
    # False: no Balance header found on the tab, so it couldn't be checked.
    checked: bool = False


@dataclass
class WorkbookResult:
    sheets: list[SheetResult]

    @property
    def issues(self) -> list[LineIssue]:
        return [i for s in self.sheets for i in s.issues]


def _text(v: object) -> str:
    return str(v).strip() if v is not None else ""


def _number(v: object) -> Decimal | None:
    """A cell's numeric value. Text like "(1,240.04)" or "-$80" counts too,
    since a balance typed as text is still a balance."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int | float):
        return Decimal(str(v))
    s = _text(v)
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace("$", "").replace(",", "").strip()
    try:
        d = Decimal(s)
    except InvalidOperation:
        return None
    return -d if neg else d


def check_sheet(ws) -> SheetResult:
    res = SheetResult(ws.title)
    balance_col: int | None = None
    code_col = desc_col = None
    group = ""
    for row in ws.iter_rows():
        filled = [c for c in row if _text(c.value)]
        if not filled:
            continue
        lowered = {_text(c.value).lower(): c.column for c in filled if isinstance(c.value, str)}

        if balance_col is None:
            if "balance" in lowered:
                balance_col = lowered["balance"]
                code_col = lowered.get("code")
                # A couple of tabs leave the description column unlabelled;
                # it's the column right after Code.
                desc_col = lowered.get("description") or (code_col + 1 if code_col else None)
                res.checked = True
            continue

        # Totals and subtotals ("TOTAL", "Total Paint", "Total Net Receipts").
        if any(t.startswith("total") for t in lowered):
            continue

        by_col = {c.column: c.value for c in filled}
        raw = by_col.get(balance_col)
        if raw is None:
            # A group heading if it's only text, otherwise a receipts or
            # note row below the table: neither is a component.
            if all(isinstance(v, str) for v in by_col.values()) and len(by_col) == 1:
                group = _text(next(iter(by_col.values())))
            continue

        res.line_items += 1
        amount = _number(raw)
        cell = f"{get_column_letter(balance_col)}{row[0].row}"
        problem = None
        if amount is None:
            problem = "not_a_number"
        elif amount < _EPSILON:
            problem = "negative"
        if problem:
            res.issues.append(
                LineIssue(
                    sheet=ws.title,
                    group=group,
                    cell=cell,
                    row=row[0].row,
                    code=_text(by_col.get(code_col)) if code_col else "",
                    description=_text(by_col.get(desc_col)) if desc_col else "",
                    balance=amount.quantize(Decimal("0.01")) if amount is not None else None,
                    problem=problem,
                )
            )
    return res


def check_workbook(source: str | BinaryIO) -> WorkbookResult:
    # data_only: read the values Excel last calculated, not the formulas.
    wb = openpyxl.load_workbook(source, data_only=True)
    try:
        return WorkbookResult([check_sheet(ws) for ws in wb.worksheets])
    finally:
        wb.close()
