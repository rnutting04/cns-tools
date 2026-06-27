from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class JobListItem(BaseModel):
    id: UUID
    job_type: Literal["letter", "budget"]
    title: str
    association_name: str
    status: str
    created_at: datetime
    created_by: UUID
    created_by_name: str


class JobDetail(BaseModel):
    id: UUID
    job_type: Literal["letter", "budget"]
    title: str
    association_name: str
    status: str
    created_at: datetime
    current_step: str | None = None
    download_url: str | None = None
