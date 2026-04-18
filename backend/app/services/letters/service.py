# app/services/letters/service.py
"""
Letter generation service.

This is the core business logic for generating letters. It's deliberately
framework-free: no FastAPI imports, no HTTPException. The service is
called from the HTTP route (app/routes/templates.py) but can just as
easily be called from a worker, management command, or test.

Responsibilities:
  - Validate the template and user has access to the association
  - Resolve the association and (optional) manager
  - Build the full field context via field_enrichment.build_field_context
  - Create and track a LetterJob row
  - Dispatch to the appropriate renderer
  - Upload the output and return a presigned download URL
"""
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.association import Association, UserAssociation
from app.models.letter_job import JobStatus, LetterJob
from app.models.template import Template
from app.models.user import User, UserRole
from app.services.letters.exceptions import (
    AccessDenied,
    AssociationNotFound,
    InvalidTemplateConfiguration,
    ManagerNotFound,
    MissingRequiredField,
    RenderFailed,
    TemplateNotFound,
)
from app.services.letters.field_enrichment import build_field_context
from app.services.renderers import RENDERERS
from app.services.storage import storage_service


# --- Result type ---------------------------------------------------------
@dataclass
class LetterGenerationResult:
    job_id: UUID
    download_url: str
    status: str


# --- Template field helpers ---------------------------------------------
def _get_field_key_by_type(template: Template, field_type: str) -> str | None:
    for field in template.fields or []:
        if field.get("type") == field_type:
            return field.get("key")
    return None


# --- Lookup helpers -----------------------------------------------------
def _load_template(db: Session, template_id: UUID) -> Template:
    template = (
        db.query(Template)
        .filter(Template.id == template_id, Template.is_active.is_(True))
        .first()
    )
    if not template:
        raise TemplateNotFound(f"Template {template_id} not found")
    return template


def _load_association(db: Session, association_id: UUID) -> Association:
    association = (
        db.query(Association)
        .filter(Association.id == association_id, Association.is_active.is_(True))
        .first()
    )
    if not association:
        raise AssociationNotFound(f"Association {association_id} not found")
    return association


def _load_manager(db: Session, manager_id: UUID) -> User:
    manager = (
        db.query(User)
        .filter(User.id == manager_id, User.is_active.is_(True))
        .first()
    )
    if not manager:
        raise ManagerNotFound(f"Manager {manager_id} not found")
    return manager


def _assert_user_can_access_association(
    db: Session, user: User, association: Association
) -> None:
    if user.role != UserRole.manager:
        return
    link = (
        db.query(UserAssociation)
        .filter(
            UserAssociation.user_id == user.id,
            UserAssociation.association_id == association.id,
        )
        .first()
    )
    if not link:
        raise AccessDenied("Access denied to this association")


# --- Public API ---------------------------------------------------------
def generate_letter(
    db: Session,
    current_user: User,
    template_id: UUID,
    field_values: dict[str, Any],
    url_expires_seconds: int = 3600,
) -> LetterGenerationResult:
    """
    Generate a letter and return a download URL.

    Raises domain exceptions from app.services.letters.exceptions on error.
    The HTTP route translates those to appropriate status codes.
    """
    # 1. Load template
    template = _load_template(db, template_id)

    # 2. Resolve association (required for all templates)
    association_key = _get_field_key_by_type(template, "association")
    if not association_key:
        raise InvalidTemplateConfiguration(
            "Template is missing an association field."
        )

    association_id = field_values.get(association_key)
    if not association_id:
        raise MissingRequiredField(
            f"Association field '{association_key}' is required."
        )
    association = _load_association(db, association_id)

    # 3. Authorization
    _assert_user_can_access_association(db, current_user, association)

    # 4. Resolve optional manager
    manager: User | None = None
    manager_key = _get_field_key_by_type(template, "manager")
    if manager_key:
        manager_id = field_values.get(manager_key)
        if not manager_id:
            raise MissingRequiredField(
                f"Manager field '{manager_key}' is required."
            )
        manager = _load_manager(db, manager_id)

    # 5. Build full field context (pure function)
    context = build_field_context(
        user_input=field_values,
        association=association,
        manager=manager,
    )

    # 6. Create job row
    job = LetterJob(
        template_id=template_id,
        association_id=association.id,
        created_by=current_user.id,
        field_values=context,
        status=JobStatus.pending,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # 7. Render + upload
    try:
        template_bytes = storage_service.download_file(template.docx_path)
        renderer = RENDERERS.get(template.renderer_type, RENDERERS["simple"])
        output_bytes = renderer(template_bytes, context)

        output_filename = f"{template.name.replace(' ', '_')}_{job.id}.docx"
        output_key = f"outputs/{job.id}/{output_filename}"
        storage_service.upload_file(
            output_bytes,
            output_key,
            content_type=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
        )

        job.output_path = output_key
        job.status = JobStatus.complete
        db.commit()

        download_url = storage_service.generate_presigned_url(
            output_key, expires=url_expires_seconds
        )
        return LetterGenerationResult(
            job_id=job.id,
            download_url=download_url,
            status="complete",
        )

    except Exception as exc:
        job.status = JobStatus.failed
        db.commit()
        raise RenderFailed(f"Letter generation failed: {exc}") from exc