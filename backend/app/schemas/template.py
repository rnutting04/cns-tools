# app/schemas/template.py
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, field_serializer


class FieldDefinition(BaseModel):
    key: str
    label: str
    type: str  # "text" | "date" | "dropdown" | "association" | "manager" | "time"
    options: list[str] = []
    auto_populate: bool = False


class TemplateCreate(BaseModel):
    name: str
    category: str
    fields: list[FieldDefinition]


class TemplateResponse(BaseModel):
    id: UUID
    name: str
    category: str
    docx_path: str
    fields: list[FieldDefinition]
    renderer_type: str = "simple"
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LetterGenerateRequest(BaseModel):
    template_id: UUID
    field_values: dict[str, Any]


def _serialize_utc(value: datetime) -> str:
    """Emit an unambiguous ISO 8601 string. Stored timestamps are naive UTC, so
    attach UTC tzinfo when missing — this makes the browser parse them as UTC
    instead of local time."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


class LetterJobResponse(BaseModel):
    id: UUID
    template_id: UUID
    template_name: str
    association_id: UUID
    association_name: str
    created_by: UUID
    created_by_name: str
    status: str
    output_path: str | None
    created_at: datetime

    @field_serializer("created_at")
    def _ser_created_at(self, value: datetime) -> str:
        return _serialize_utc(value)

    class Config:
        from_attributes = True


class LetterFieldEntry(BaseModel):
    key: str
    label: str
    value: str


class LetterDerivedEntry(BaseModel):
    label: str
    value: str


class LetterJobDetailResponse(BaseModel):
    id: UUID
    template_name: str
    association_name: str
    created_by_name: str
    status: str
    created_at: datetime
    entries: list[LetterFieldEntry]  # template fields the user filled in
    derived: list[LetterDerivedEntry]  # curated auto-resolved fields

    @field_serializer("created_at")
    def _ser_created_at(self, value: datetime) -> str:
        return _serialize_utc(value)


class GenerateResponse(BaseModel):
    job_id: UUID
    download_url: str
    status: str


class GenerateAcceptedResponse(BaseModel):
    """Returned by POST /letters/generate once the job is queued."""

    job_id: UUID
    status: str  # "pending"


class LetterJobStatusResponse(BaseModel):
    """Returned by GET /letters/{job_id} while polling for completion."""

    job_id: UUID
    status: str  # pending | processing | complete | failed
    download_url: str | None = None
