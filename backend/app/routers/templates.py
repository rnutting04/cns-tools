# app/routes/templates.py
import json
import os
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.letter_job import LetterJob
from app.models.template import Template
from app.models.user import User, UserRole
from app.schemas.template import (
    FieldDefinition,
    GenerateResponse,
    LetterGenerateRequest,
    LetterJobResponse,
    TemplateResponse,
)
from app.services.audit import log_event
from app.services.letters import generate_letter
from app.services.letters.exceptions import (
    AccessDenied,
    AssociationNotFound,
    InvalidTemplateConfiguration,
    ManagerNotFound,
    MissingRequiredField,
    RenderFailed,
    TemplateNotFound,
)
from app.services.storage import storage_service

router = APIRouter(tags=["templates"])

DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _validate_docx(file: UploadFile) -> None:
    if not file.filename or not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="File must be a .docx")


def _parse_fields(fields: str) -> list[dict[str, Any]]:
    try:
        fields_data: list[dict[str, Any]] = json.loads(fields)
        field_defs = [FieldDefinition(**f) for f in fields_data]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid fields JSON") from None
    return [f.model_dump() for f in field_defs]


@router.post("/templates", response_model=TemplateResponse, status_code=201)
async def create_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    category: str = Form(...),
    fields: str = Form(...),
    renderer_type: str = Form("simple"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    _validate_docx(file)
    fields_payload = _parse_fields(fields)

    template_id = uuid.uuid4()
    key = f"templates/{template_id}/{file.filename}"
    file_bytes = await file.read()

    storage_service.upload_file(file_bytes, key, content_type=DOCX_CONTENT_TYPE)

    template = Template(
        id=template_id,
        name=name,
        category=category,
        docx_path=key,
        fields=fields_payload,
        renderer_type=renderer_type,
    )
    db.add(template)
    log_event(
        db,
        actor=current_user,
        action="template.created",
        target_type="template",
        target_id=str(template_id),
        metadata={"name": name, "category": category, "renderer_type": renderer_type},
    )
    db.commit()
    db.refresh(template)
    return template


@router.get("/templates", response_model=list[TemplateResponse])
def list_templates(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return db.query(Template).filter(Template.is_active.is_(True)).all()


@router.patch("/templates/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: uuid.UUID,
    name: str | None = Form(None),
    category: str | None = Form(None),
    renderer_type: str | None = Form(None),
    fields: str | None = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    changes: dict[str, Any] = {}
    if name is not None:
        template.name = name
        changes["name"] = name
    if category is not None:
        template.category = category
        changes["category"] = category
    if renderer_type is not None:
        template.renderer_type = renderer_type
        changes["renderer_type"] = renderer_type
    if fields is not None:
        template.fields = _parse_fields(fields)
        changes["fields"] = len(template.fields)

    if file is not None:
        _validate_docx(file)
        old_path = template.docx_path
        new_key = f"templates/{template_id}/{file.filename}"
        file_bytes = await file.read()
        storage_service.upload_file(file_bytes, new_key, content_type=DOCX_CONTENT_TYPE)
        template.docx_path = new_key
        if new_key != old_path:
            storage_service.delete_file(old_path)
        changes["docx_path"] = new_key

    log_event(
        db,
        actor=current_user,
        action="template.updated",
        target_type="template",
        target_id=str(template_id),
        metadata=changes,
    )
    db.commit()
    db.refresh(template)
    return template


@router.post(
    "/templates/{template_id}/duplicate",
    response_model=TemplateResponse,
    status_code=201,
)
async def duplicate_template(
    template_id: uuid.UUID,
    name: str | None = Form(None),
    category: str | None = Form(None),
    renderer_type: str | None = Form(None),
    fields: str | None = Form(None),
    file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    source = db.query(Template).filter(Template.id == template_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Template not found")

    new_id = uuid.uuid4()

    if file is not None:
        _validate_docx(file)
        new_key = f"templates/{new_id}/{file.filename}"
        file_bytes = await file.read()
        storage_service.upload_file(file_bytes, new_key, content_type=DOCX_CONTENT_TYPE)
    else:
        filename = os.path.basename(source.docx_path)
        new_key = f"templates/{new_id}/{filename}"
        data = storage_service.download_file(source.docx_path)
        storage_service.upload_file(data, new_key, content_type=DOCX_CONTENT_TYPE)

    new_name = name if name is not None else f"{source.name} (Copy)"
    new_fields = _parse_fields(fields) if fields is not None else source.fields

    template = Template(
        id=new_id,
        name=new_name,
        category=category if category is not None else source.category,
        docx_path=new_key,
        fields=new_fields,
        renderer_type=(renderer_type if renderer_type is not None else source.renderer_type),
    )
    db.add(template)
    log_event(
        db,
        actor=current_user,
        action="template.duplicated",
        target_type="template",
        target_id=str(new_id),
        metadata={"source_template_id": str(template_id), "name": new_name},
    )
    db.commit()
    db.refresh(template)
    return template


@router.delete("/templates/{template_id}", status_code=204)
def deactivate_template(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    template.is_active = False
    log_event(
        db,
        actor=current_user,
        action="template.deactivated",
        target_type="template",
        target_id=str(template_id),
        metadata={"name": template.name, "category": template.category},
    )
    db.commit()


@router.post("/letters/generate", response_model=GenerateResponse, status_code=201)
def generate_letter_route(
    body: LetterGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = generate_letter(
            db=db,
            current_user=current_user,
            template_id=body.template_id,
            field_values=body.field_values,
        )
    except (TemplateNotFound, AssociationNotFound, ManagerNotFound) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AccessDenied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (InvalidTemplateConfiguration, MissingRequiredField) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RenderFailed as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return GenerateResponse(
        job_id=result.job_id,
        download_url=result.download_url,
        status=result.status,
    )


@router.get("/letters/history", response_model=list[LetterJobResponse])
def letter_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(LetterJob)
    if current_user.role == UserRole.manager:
        query = query.filter(LetterJob.created_by == current_user.id)
    return query.order_by(LetterJob.created_at.desc()).all()
