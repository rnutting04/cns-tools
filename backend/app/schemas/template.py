# app/schemas/template.py
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


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


class LetterJobResponse(BaseModel):
    id: UUID
    template_id: UUID
    association_id: UUID
    status: str
    output_path: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class GenerateResponse(BaseModel):
    job_id: UUID
    download_url: str
    status: str
