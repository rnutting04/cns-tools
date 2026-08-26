# app/schemas/budget.py
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class BudgetJobAcceptedResponse(BaseModel):
    job_id: UUID
    status: str


class BudgetJobStatusResponse(BaseModel):
    job_id: UUID
    status: str
    current_step: str | None = None
    review_flag_count: int | None = None
    download_url: str | None = None
    error_code: str | None = None
    error_detail: Any | None = None
    # Present only while current_step == "awaiting_layout_review": the detected
    # workbook structure and a preview of the parse, for the reviewer to confirm.
    layout_review: Any | None = None


class LayoutCorrections(BaseModel):
    """Reviewer overrides. Any field left None keeps what detection chose."""

    sheet_title: str | None = None
    label_col: int | None = None
    prior_col: int | None = None
    projected_col: int | None = None
    proposed_col: int | None = None
    notes_col: int | None = None
    reserve_sheet: str | None = None


class ConfirmLayoutRequest(BaseModel):
    corrections: LayoutCorrections | None = None


class LayoutProfileResponse(BaseModel):
    id: UUID
    signature: str
    sheet_title: str
    confirmed: bool
    use_count: int
    example_association: str | None = None
    example_filename: str | None = None
    warnings: Any | None = None
    confirmed_at: datetime | None = None


class BudgetJobDetailResponse(BaseModel):
    job_id: UUID
    association_name: str
    budget_year: int
    financial_report_filename: str
    prior_budget_filename: str
    status: str
    current_step: str | None = None
    review_flag_count: int | None = None
    error_code: str | None = None
    error_detail: Any | None = None
    created_by_name: str
    created_at: datetime
