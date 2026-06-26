# app/schemas/budget.py
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
