# app/schemas/accounting.py
"""Standalone accounting tools: audit-threshold and FDIC exposure."""

from datetime import datetime
from typing import Any

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


class AccountingJobSummary(BaseModel):
    """A background run over a combined multi-association PDF."""

    id: str
    tool: str  # fdic | revenue_threshold | receivables | cd_maturity
    filename: str
    status: str  # pending | processing | complete | failed
    total_pages: int | None
    pages_done: int
    current_association: str | None
    associations_done: int
    flagged_count: int
    error_detail: str | None
    created_at: datetime | None
    finished_at: datetime | None


class AccountingJobResult(BaseModel):
    association: str
    first_page: int
    last_page: int
    flagged: bool
    # Tool-specific: {"problem": str} if the section couldn't be processed;
    # otherwise the FDIC ({limit, institutions, unrecognized}) or revenue
    # threshold ({ytd_actual, annual}) result.
    result: dict[str, Any]


class AccountingJobDetail(AccountingJobSummary):
    results: list[AccountingJobResult]


class FdicReport(BaseModel):
    filename: str
    page_count: int
    ocr_pages: int
    limit: float
    balance_sheet_found: bool
    institutions: list[FdicInstitution]  # largest first
    unrecognized: list[FdicAccount]  # deposit rows whose bank couldn't be named
