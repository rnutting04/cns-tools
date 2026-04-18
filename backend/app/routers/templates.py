# app/routes/templates.py
import json
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


@router.post("/templates", response_model=TemplateResponse, status_code=201)
async def create_template(
    file: UploadFile = File(...),
    name: str = Form(...),
    category: str = Form(...),
    fields: str = Form(...),
    renderer_type: str = Form("simple"),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if not file.filename or not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="File must be a .docx")

    try:
        fields_data: list[dict[str, Any]] = json.loads(fields)
        field_defs = [FieldDefinition(**f) for f in fields_data]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid fields JSON")

    template_id = uuid.uuid4()
    key = f"templates/{template_id}/{file.filename}"
    file_bytes = await file.read()

    storage_service.upload_file(
        file_bytes,
        key,
        content_type=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
    )

    template = Template(
        id=template_id,
        name=name,
        category=category,
        docx_path=key,
        fields=[f.model_dump() for f in field_defs],
        renderer_type=renderer_type,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get("/templates", response_model=list[TemplateResponse])
def list_templates(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return db.query(Template).filter(Template.is_active.is_(True)).all()


@router.delete("/templates/{template_id}", status_code=204)
def deactivate_template(
    template_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    template.is_active = False
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