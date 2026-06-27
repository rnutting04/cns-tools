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
