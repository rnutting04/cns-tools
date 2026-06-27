# app/routers/budget.py
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.database import get_db
from app.dependencies import get_current_user
from app.models.budget_job import BudgetJob
from app.models.letter_job import JobStatus
from app.models.user import User
from app.schemas.budget import BudgetJobAcceptedResponse, BudgetJobStatusResponse
from app.services.budget.tasks import generate_budget_task
from app.services.storage import storage_service

from sqlalchemy.orm import Session

router = APIRouter(prefix="/budget", tags=["budget"])


@router.post("/generate", response_model=BudgetJobAcceptedResponse, status_code=202)
async def generate_budget(
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

    financial_report_bytes = await financial_report.read()
    prior_budget_bytes = await prior_budget.read()

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
    db.commit()

    generate_budget_task.delay(str(job.id))
    return BudgetJobAcceptedResponse(job_id=job.id, status=JobStatus.pending.value)


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
    )
