# app/schemas/financials.py
from pydantic import BaseModel


class FinancialCheckSide(BaseModel):
    source: str  # "balance sheet", "bank reconciliation", ...
    label: str
    amount: float | None
    page: int | None
    # True: the report's own arithmetic confirmed this read.
    # False: that arithmetic failed — likely an OCR misread.
    # None: nothing on the report to confirm it against.
    verified: bool | None
    # The line didn't parse cleanly, so the amount was picked by its position
    # on the page. Shown as a best guess for a human to confirm.
    guessed: bool = False
    image: str | None  # data: URL of the highlighted page region (or where it should be)


class FinancialCheckResult(BaseModel):
    id: str
    title: str
    status: str  # pass | fail | review | missing | not_applicable
    difference: float | None
    tolerance: float
    notes: list[str]
    left: FinancialCheckSide | None
    right: FinancialCheckSide | None


class FinancialCheckReport(BaseModel):
    filename: str
    page_count: int
    reports_found: list[str]
    summary: dict[str, int]
    checks: list[FinancialCheckResult]
