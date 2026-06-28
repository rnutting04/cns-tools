# app/routes/templates.py
import json
import os
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.letter_job import JobStatus, LetterJob
from app.models.template import Template
from app.models.user import User, UserRole
from app.schemas.template import (
    FieldDefinition,
    GenerateAcceptedResponse,
    LetterDerivedEntry,
    LetterFieldEntry,
    LetterGenerateRequest,
    LetterJobDetailResponse,
    LetterJobResponse,
    LetterJobStatusResponse,
    TemplateResponse,
)
from app.services.audit import log_event
from app.services.letters import prepare_letter_job
from app.services.letters.exceptions import (
    AccessDenied,
    AssociationNotFound,
    InvalidTemplateConfiguration,
    ManagerNotFound,
    MissingRequiredField,
    TemplateNotFound,
)
from app.services.letters.tasks import generate_letter_task
from app.services.storage import storage_service

router = APIRouter(tags=["templates"])

DOCX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Curated auto-resolved fields surfaced in the letter detail view, in display
# order. Keys come from the enriched context stored in LetterJob.field_values
# (see services/letters + utils/field_enrichment); the many string/date variants
# (_upper, _iso, ...) are intentionally excluded as noise.
DERIVED_FIELD_LABELS: list[tuple[str, str]] = [
    ("legal_association_name", "Legal name"),
    ("association_location_name", "Location"),
    ("assn_city", "City"),
    ("manager_full_name", "Manager"),
    ("manager_titles", "Manager title"),
    ("manager_email", "Manager email"),
    ("office_street", "Office street"),
    ("office_city_state_zip", "Office city/state/zip"),
    ("office_phone", "Office phone"),
    ("notice_deadline", "Notice deadline"),
    ("today_date", "Letter date"),
]


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
def create_template(
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
    file_bytes = file.file.read()

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
def update_template(
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
        file_bytes = file.file.read()
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
def duplicate_template(
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
        file_bytes = file.file.read()
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


@router.post("/letters/generate", response_model=GenerateAcceptedResponse, status_code=202)
def generate_letter_route(
    body: LetterGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validation + authorization happen synchronously so bad/unauthorized
    # requests fail fast and never reach the worker queue.
    try:
        job = prepare_letter_job(
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

    # Capture the submission-time state before enqueuing: under Celery's eager
    # (test) mode .delay() runs the task inline and would mutate job.status.
    job_id = job.id
    status = job.status.value

    # Hand off the heavy render/upload to the background worker.
    generate_letter_task.delay(str(job_id))

    return GenerateAcceptedResponse(job_id=job_id, status=status)


@router.get("/letters/history", response_model=list[LetterJobResponse])
def letter_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Each user's personal "Generated Letters" list is scoped to their own jobs.
    # Super-admins get the full cross-user list for auditing.
    query = db.query(LetterJob).options(
        joinedload(LetterJob.template),
        joinedload(LetterJob.association),
        joinedload(LetterJob.creator),
    )
    if current_user.role != UserRole.super_admin:
        query = query.filter(LetterJob.created_by == current_user.id)
    jobs = query.order_by(LetterJob.created_at.desc()).all()

    return [
        LetterJobResponse(
            id=job.id,
            template_id=job.template_id,
            template_name=job.template.name,
            association_id=job.association_id,
            association_name=job.association.legal_name,
            created_by=job.created_by,
            created_by_name=f"{job.creator.fname} {job.creator.lname}",
            status=job.status.value,
            output_path=job.output_path,
            # Download URLs are minted lazily (on demand via GET /letters/{id})
            # so a long history list doesn't generate a presigned URL per row.
            created_at=job.created_at,
        )
        for job in jobs
    ]


@router.get("/letters/{job_id}", response_model=LetterJobStatusResponse)
def get_letter_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = db.query(LetterJob).filter(LetterJob.id == job_id).first()
    if not job or not _can_view_job(job, current_user):
        raise HTTPException(status_code=404, detail="Job not found")

    # Presigned URLs expire, so generate a fresh one on each poll once ready.
    download_url = None
    if job.status == JobStatus.complete and job.output_path:
        download_url = storage_service.generate_presigned_url(job.output_path, expires=3600)

    return LetterJobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        download_url=download_url,
    )


@router.post("/letters/{job_id}/retry", response_model=GenerateAcceptedResponse)
def retry_letter_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    job = db.query(LetterJob).filter(LetterJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == JobStatus.complete:
        raise HTTPException(status_code=409, detail="Job already completed")

    job.status = JobStatus.pending
    db.commit()
    generate_letter_task.delay(str(job.id))
    return GenerateAcceptedResponse(job_id=job.id, status=JobStatus.pending.value)


def _can_view_job(job: LetterJob, user: User) -> bool:
    """A job is visible to its creator or to any super-admin (cross-user
    auditing). Callers return 404 (not 403) so the existence of other users'
    jobs is never leaked."""
    return job.created_by == user.id or user.role == UserRole.super_admin


@router.get("/letters/{job_id}/details", response_model=LetterJobDetailResponse)
def get_letter_job_details(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = (
        db.query(LetterJob)
        .options(
            joinedload(LetterJob.template),
            joinedload(LetterJob.association),
            joinedload(LetterJob.creator),
        )
        .filter(LetterJob.id == job_id)
        .first()
    )
    if not job or not _can_view_job(job, current_user):
        raise HTTPException(status_code=404, detail="Job not found")

    values = job.field_values or {}

    # "Your entries" — the template fields the user actually filled in, in the
    # template's declared order, skipping blanks.
    entries = [
        LetterFieldEntry(key=field["key"], label=field["label"], value=str(values[field["key"]]))
        for field in (job.template.fields or [])
        if values.get(field["key"]) not in (None, "")
    ]

    # "Resolved details" — curated auto-derived fields that are present.
    derived = [
        LetterDerivedEntry(label=label, value=str(values[key]))
        for key, label in DERIVED_FIELD_LABELS
        if values.get(key) not in (None, "")
    ]

    return LetterJobDetailResponse(
        id=job.id,
        template_name=job.template.name,
        association_name=job.association.legal_name,
        created_by_name=f"{job.creator.fname} {job.creator.lname}",
        status=job.status.value,
        created_at=job.created_at,
        entries=entries,
        derived=derived,
    )
