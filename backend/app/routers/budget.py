# app/routers/budget.py
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.budget_job import BudgetJob
from app.models.budget_layout_profile import BudgetLayoutProfile
from app.models.letter_job import JobStatus
from app.models.user import User
from app.schemas.budget import (
    BudgetJobAcceptedResponse,
    BudgetJobDetailResponse,
    BudgetJobStatusResponse,
    ConfirmLayoutRequest,
    LayoutProfileResponse,
)
from app.services.audit import log_event
from app.services.budget import layout_profiles
from app.services.budget.tasks import AWAITING_LAYOUT_REVIEW, generate_budget_task
from app.services.storage import storage_service

router = APIRouter(prefix="/budget", tags=["budget"])


@router.post("/generate", response_model=BudgetJobAcceptedResponse, status_code=202)
def generate_budget(
    association_name: str = Form(...),
    budget_year: int = Form(...),
    financial_report: UploadFile = File(...),
    prior_budget: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BudgetJobAcceptedResponse:
    """
    Accept two input files, store them in MinIO, and enqueue a background
    budget pipeline run. Returns 202 immediately with a job_id to poll.

    Poll GET /budget/jobs/{job_id} for status and the download URL.
    """
    job_id = uuid.uuid4()

    financial_report_bytes = financial_report.file.read()
    prior_budget_bytes = prior_budget.file.read()

    report_key = f"budget/{job_id}/financial_report/{financial_report.filename}"
    prior_key = f"budget/{job_id}/prior_budget/{prior_budget.filename}"

    storage_service.upload_file(financial_report_bytes, report_key, content_type="application/pdf")
    storage_service.upload_file(prior_budget_bytes, prior_key)

    job = BudgetJob(
        id=job_id,
        association_name=association_name,
        budget_year=budget_year,
        financial_report_path=report_key,
        financial_report_filename=financial_report.filename or "",
        prior_budget_path=prior_key,
        prior_budget_filename=prior_budget.filename or "",
        status=JobStatus.pending,
        created_by=current_user.id,
    )
    db.add(job)
    log_event(
        db,
        actor=current_user,
        action="budget.job.created",
        target_type="budget_job",
        target_id=str(job_id),
        metadata={
            "association_name": association_name,
            "budget_year": budget_year,
            "financial_report_filename": financial_report.filename,
            "prior_budget_filename": prior_budget.filename,
        },
    )
    db.commit()

    generate_budget_task.delay(str(job_id))

    return BudgetJobAcceptedResponse(job_id=job_id, status=JobStatus.pending.value)


@router.post("/jobs/{job_id}/retry", response_model=BudgetJobAcceptedResponse)
def retry_budget_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BudgetJobAcceptedResponse:
    job = db.query(BudgetJob).filter(BudgetJob.id == job_id).first()
    if not job or job.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status == JobStatus.complete:
        raise HTTPException(status_code=409, detail="Job already completed")

    job.status = JobStatus.pending
    job.current_step = None
    job.error_code = None
    job.error_detail = None
    log_event(
        db,
        actor=current_user,
        action="budget.job.retried",
        target_type="budget_job",
        target_id=str(job.id),
        metadata={"association_name": job.association_name, "budget_year": job.budget_year},
    )
    db.commit()

    generate_budget_task.delay(str(job.id))
    return BudgetJobAcceptedResponse(job_id=job.id, status=JobStatus.pending.value)


@router.post("/jobs/{job_id}/confirm-layout", response_model=BudgetJobAcceptedResponse)
def confirm_job_layout(
    job_id: uuid.UUID,
    payload: ConfirmLayoutRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BudgetJobAcceptedResponse:
    """
    Confirm the workbook layout for a parked job and resume it.

    The confirmation is stored against the layout's structural signature, not
    against this job or association — so every other association whose workbook
    has the same shape runs unattended from here on, this year and next.
    """
    job = db.query(BudgetJob).filter(BudgetJob.id == job_id).first()
    if not job or job.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.current_step != AWAITING_LAYOUT_REVIEW:
        raise HTTPException(status_code=409, detail="Job is not awaiting layout review")
    if not job.layout_signature:
        raise HTTPException(status_code=409, detail="Job has no detected layout to confirm")

    corrections = (
        payload.corrections.model_dump(exclude_none=True)
        if payload and payload.corrections
        else None
    )
    profile = layout_profiles.confirm(db, job.layout_signature, current_user.id, corrections)
    if profile is None:
        raise HTTPException(status_code=404, detail="No layout profile found for this job")

    job.status = JobStatus.pending
    job.current_step = None
    job.layout_review = None
    log_event(
        db,
        actor=current_user,
        action="budget.layout.confirmed",
        target_type="budget_layout_profile",
        target_id=str(profile.id),
        metadata={
            "signature": profile.signature,
            "association_name": job.association_name,
            "sheet_title": profile.sheet_title,
            "corrections": corrections or {},
        },
    )
    db.commit()

    generate_budget_task.delay(str(job.id))
    return BudgetJobAcceptedResponse(job_id=job.id, status=JobStatus.pending.value)


@router.get("/layout-profiles", response_model=list[LayoutProfileResponse])
def list_layout_profiles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[LayoutProfileResponse]:
    """All known workbook templates and how many runs each has covered."""
    profiles = (
        db.query(BudgetLayoutProfile)
        .order_by(BudgetLayoutProfile.confirmed.desc(), BudgetLayoutProfile.use_count.desc())
        .all()
    )
    return [
        LayoutProfileResponse(
            id=p.id,
            signature=p.signature,
            sheet_title=p.sheet_title,
            confirmed=p.confirmed,
            use_count=p.use_count or 0,
            example_association=p.example_association,
            example_filename=p.example_filename,
            warnings=p.warnings,
            confirmed_at=p.confirmed_at,
        )
        for p in profiles
    ]


@router.get("/jobs/{job_id}/details", response_model=BudgetJobDetailResponse)
def get_budget_job_details(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BudgetJobDetailResponse:
    from sqlalchemy.orm import joinedload

    job = (
        db.query(BudgetJob)
        .options(joinedload(BudgetJob.creator))
        .filter(BudgetJob.id == job_id)
        .first()
    )
    if not job or job.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    return BudgetJobDetailResponse(
        job_id=job.id,
        association_name=job.association_name,
        budget_year=job.budget_year,
        financial_report_filename=job.financial_report_filename,
        prior_budget_filename=job.prior_budget_filename,
        status=job.status.value,
        current_step=job.current_step,
        review_flag_count=job.review_flag_count,
        error_code=job.error_code,
        error_detail=job.error_detail,
        created_by_name=f"{job.creator.fname} {job.creator.lname}",
        created_at=job.created_at,
    )


@router.get("/jobs/{job_id}", response_model=BudgetJobStatusResponse)
def get_budget_job(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BudgetJobStatusResponse:
    """
    Poll the status of a budget generation job.

    Returns a presigned download URL when status == complete.
    Returns error_code + error_detail when status == failed.
    """
    job = db.query(BudgetJob).filter(BudgetJob.id == job_id).first()
    if not job or job.created_by != current_user.id:
        raise HTTPException(status_code=404, detail="Job not found")

    download_url = None
    if job.status == JobStatus.complete and job.output_path:
        download_url = storage_service.generate_presigned_url(job.output_path, expires=3600)

    return BudgetJobStatusResponse(
        job_id=job.id,
        status=job.status.value,
        current_step=job.current_step,
        review_flag_count=job.review_flag_count,
        download_url=download_url,
        error_code=job.error_code,
        error_detail=job.error_detail,
        layout_review=job.layout_review,
    )
