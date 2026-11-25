# app/schemas/accounting.py
"""Standalone accounting tools: audit-threshold and FDIC exposure."""

from pydantic import BaseModel


class SourceFigure(BaseModel):
    """A figure read from the PDF, with where it came from."""

    label: str
    amount: float
    page: int
    bbox: list[float]  # [x0, top, x1, bottom] in PDF points — for /financials/evidence
    verified: bool | None  # True: confirmed by the report's own arithmetic
    guessed: bool  # read by column position because the line was damaged


class RevenueBasisOut(BaseModel):
    operating: SourceFigure | None
    reserve: SourceFigure | None
    total: float | None
    # "none" (< $150k) | "compilation" | "review" | "audit"; None if unreadable
    tier: str | None
    notes: list[str]


class RevenueThresholdReport(BaseModel):
    filename: str
    page_count: int
    ocr_pages: int  # pages read with OCR (the PDF had no text layer)
    ytd_actual: RevenueBasisOut
    annual: RevenueBasisOut


class FdicAccount(BaseModel):
    label: str
    amount: float
    network: bool  # ICS / CDARS reciprocal deposit
    source: SourceFigure


class FdicInstitution(BaseModel):
    name: str
    total: float
    over_limit: bool
    accounts: list[FdicAccount]
    notes: list[str]


class FdicReport(BaseModel):
    filename: str
    page_count: int
    ocr_pages: int
    limit: float
    balance_sheet_found: bool
    institutions: list[FdicInstitution]  # largest first
    unrecognized: list[FdicAccount]  # deposit rows whose bank couldn't be named
