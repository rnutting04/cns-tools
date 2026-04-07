# app/schemas/template.py
from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime
from uuid import UUID


class FieldDefinition(BaseModel):
    key: str
    label: str
    type: str  # "text" | "date" | "dropdown"
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
    output_path: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class GenerateResponse(BaseModel):
    job_id: UUID
    download_url: str
    status: str
