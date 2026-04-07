import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.models.association import Association, UserAssociation
from app.models.letter_job import JobStatus, LetterJob
from app.models.template import Template
from app.models.user import User, UserRole
from app.schemas.template import (
    FieldDefinition,
    GenerateResponse,
    LetterGenerateRequest,
    LetterJobResponse,
    TemplateResponse,
)
from app.services.storage import storage_service
from app.services.renderers import RENDERERS
from datetime import datetime, date, timedelta


router = APIRouter(tags=["templates"])

NOTICE_CANDIDACY_DEADLINE_DAYS = 38
OFFICE_LOCATIONS = {
    "Bradenton": {
        "office_street": "4301 32nd Street West, Suite A20",
        "office_city_state_zip": "Bradenton, Florida 34205",
        "office_phone": "941-758-9454",
    },
    "Sarasota": {
        "office_street": "5589 Marquesas Circle Unit 202",
        "office_city_state_zip": "Sarasota, Florida 34233",
        "office_phone": "941-377-3419",
    },
}

def compute_notice_candidacy_deadline(meeting_date_str: str, days_before: int = NOTICE_CANDIDACY_DEADLINE_DAYS):
    try:
        meeting_date = datetime.strptime(meeting_date_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None

    return meeting_date - timedelta(days=days_before)

def ordinal_number(number: int) -> str:
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def expand_string_variants(field_values: dict[str, object]) -> None:
    for key, value in list(field_values.items()):
        if isinstance(value, str):
            field_values[f"{key}_upper"] = value.upper()
            field_values[f"{key}_lower"] = value.lower()
            field_values[f"{key}_title"] = value.title()


def expand_date_variants(field_values: dict[str, object]) -> None:
    for key, value in list(field_values.items()):
        if not isinstance(value, str):
            continue

        try:
            parsed = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            continue

        field_values[f"{key}_iso"] = parsed.isoformat()
        field_values[f"{key}_short"] = parsed.strftime("%m/%d/%Y")
        field_values[f"{key}_long"] = f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"
        field_values[f"{key}_formal"] = (
            f"{ordinal_number(parsed.day)} day of {parsed.strftime('%B')} {parsed.year}"
        )
        field_values[f"{key}_month_year"] = parsed.strftime("%B %Y")


def get_association_field_key(template: Template) -> str | None:
    fields = template.fields or []
    for field in fields:
        if field.get("type") == "association":
            return field.get("key")
    return None


def get_manager_field_key(template: Template) -> str | None:
    fields = template.fields or []
    for field in fields:
        if field.get("type") == "manager":
            return field.get("key")
    return None


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
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
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
    return db.query(Template).filter(Template.is_active == True).all()


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
    template = db.query(Template).filter(
        Template.id == body.template_id,
        Template.is_active == True,
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    field_values: dict[str, Any] = {**body.field_values}

    association_field_key = get_association_field_key(template)
    if not association_field_key:
        raise HTTPException(
            status_code=400,
            detail="This template is missing an association field.",
        )

    association_id = field_values.get(association_field_key)
    if not association_id:
        raise HTTPException(
            status_code=400,
            detail=f"Association field '{association_field_key}' is required.",
        )

    association = db.query(Association).filter(
        Association.id == association_id,
        Association.is_active == True,
    ).first()
    if not association:
        raise HTTPException(status_code=404, detail="Association not found")

    if current_user.role == UserRole.manager:
        link = db.query(UserAssociation).filter(
            UserAssociation.user_id == current_user.id,
            UserAssociation.association_id == association.id,
        ).first()
        if not link:
            raise HTTPException(status_code=403, detail="Access denied to this association")
    
    manager = None
    manager_field_key = get_manager_field_key(template)
    if manager_field_key:
        manager_id = field_values.get(manager_field_key)
        if not manager_id:
            raise HTTPException(
                status_code=400,
                detail=f"Manager field '{manager_field_key}' is required.",
            )

        manager = db.query(User).filter(
            User.id == manager_id,
            User.is_active == True,
        ).first()
        if not manager:
            raise HTTPException(status_code=404, detail="Manager not found")

    today = date.today()
    office_location = field_values.get("office_location")
    office_data = OFFICE_LOCATIONS.get(office_location, {})
    field_values["office_street"] = office_data.get("office_street", "")
    field_values["office_city_state_zip"] = office_data.get("office_city_state_zip", "")
    field_values["office_phone"] = office_data.get("office_phone", "")
    field_values["today_date"] = today.isoformat()
    field_values["legal_association_name"] = association.legal_name
    field_values["filtered_association_name"] = association.filter_name
    field_values["assn_city"] = association.location_name
    field_values["manager_full_name"] = f"{manager.fname} {manager.lname}" if manager else ""
    field_values["manager_titles"] = (manager.title or "") if manager else ""
    field_values["manager_email"] = (manager.email or "") if manager else ""
    if hasattr(association, "location_name") and association.location_name:
        field_values["association_location_name"] = association.location_name
    meeting_date_raw = field_values.get("date")
    deadline = compute_notice_candidacy_deadline(meeting_date_raw)

    if deadline:
        field_values["notice_deadline"] = deadline.isoformat()
    expand_string_variants(field_values)
    expand_date_variants(field_values)

    job = LetterJob(
        template_id=body.template_id,
        association_id=association.id,
        created_by=current_user.id,
        field_values=field_values,
        status=JobStatus.pending,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        template_bytes = storage_service.download_file(template.docx_path)
        renderer = RENDERERS.get(template.renderer_type, RENDERERS["simple"])

        output_bytes = renderer(template_bytes, field_values)

        output_filename = f"{template.name.replace(' ', '_')}_{job.id}.docx"
        output_key = f"outputs/{job.id}/{output_filename}"
        storage_service.upload_file(
            output_bytes,
            output_key,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

        job.output_path = output_key
        job.status = JobStatus.complete
        db.commit()

        download_url = storage_service.generate_presigned_url(output_key, expires=3600)
        return GenerateResponse(job_id=job.id, download_url=download_url, status="complete")

    except Exception as exc:
        job.status = JobStatus.failed
        db.commit()
        raise HTTPException(status_code=500, detail=f"Letter generation failed: {exc}") from exc


@router.get("/letters/history", response_model=list[LetterJobResponse])
def letter_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(LetterJob)
    if current_user.role == UserRole.manager:
        query = query.filter(LetterJob.created_by == current_user.id)
    return query.order_by(LetterJob.created_at.desc()).all()