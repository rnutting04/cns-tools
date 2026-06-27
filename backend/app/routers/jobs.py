import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.budget_job import BudgetJob
from app.models.letter_job import JobStatus, LetterJob
from app.models.user import User, UserRole
from app.schemas.jobs import JobDetail, JobListItem
from app.services.storage import storage_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _letter_to_item(job: LetterJob) -> JobListItem:
    creator = job.creator
    return JobListItem(
        id=job.id,
        job_type="letter",
        title=job.template.name if job.template else "Letter",
        association_name=job.association.legal_name if job.association else "",
        status=job.status.value,
        created_at=job.created_at,
        created_by=job.created_by,
        created_by_name=f"{creator.fname} {creator.lname}" if creator else "",
    )


def _budget_to_item(job: BudgetJob) -> JobListItem:
    creator = job.creator
    return JobListItem(
        id=job.id,
        job_type="budget",
        title=f"{job.association_name} {job.budget_year}",
        association_name=job.association_name,
        status=job.status.value,
        created_at=job.created_at,
        created_by=job.created_by,
        created_by_name=f"{creator.fname} {creator.lname}" if creator else "",
    )


@router.get("", response_model=list[JobListItem])
def list_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[JobListItem]:
    is_super_admin = current_user.role == UserRole.super_admin

    letter_q = db.query(LetterJob).options(
        joinedload(LetterJob.template),
        joinedload(LetterJob.association),
        joinedload(LetterJob.creator),
    )
    budget_q = db.query(BudgetJob).options(joinedload(BudgetJob.creator))

    if not is_super_admin:
        letter_q = letter_q.filter(LetterJob.created_by == current_user.id)
        budget_q = budget_q.filter(BudgetJob.created_by == current_user.id)

    items = [_letter_to_item(j) for j in letter_q.all()]
    items += [_budget_to_item(j) for j in budget_q.all()]
    items.sort(key=lambda j: j.created_at, reverse=True)
    return items


@router.get("/{job_id}", response_model=JobDetail)
def get_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> JobDetail:
    is_super_admin = current_user.role == UserRole.super_admin

    letter = (
        db.query(LetterJob)
        .options(joinedload(LetterJob.template), joinedload(LetterJob.association))
        .filter(LetterJob.id == job_id)
        .first()
    )
    if letter:
        if not is_super_admin and letter.created_by != current_user.id:
            raise HTTPException(status_code=404, detail="Job not found")
        download_url = None
        if letter.status == JobStatus.complete and letter.output_path:
            download_url = storage_service.generate_presigned_url(letter.output_path, expires=3600)
        return JobDetail(
            id=letter.id,
            job_type="letter",
            title=letter.template.name if letter.template else "Letter",
            association_name=letter.association.legal_name if letter.association else "",
            status=letter.status.value,
            created_at=letter.created_at,
            download_url=download_url,
        )

    budget = db.query(BudgetJob).filter(BudgetJob.id == job_id).first()
    if budget:
        if not is_super_admin and budget.created_by != current_user.id:
            raise HTTPException(status_code=404, detail="Job not found")
        download_url = None
        if budget.status == JobStatus.complete and budget.output_path:
            download_url = storage_service.generate_presigned_url(budget.output_path, expires=3600)
        return JobDetail(
            id=budget.id,
            job_type="budget",
            title=f"{budget.association_name} {budget.budget_year}",
            association_name=budget.association_name,
            status=budget.status.value,
            created_at=budget.created_at,
            current_step=budget.current_step,
            download_url=download_url,
        )

    raise HTTPException(status_code=404, detail="Job not found")
