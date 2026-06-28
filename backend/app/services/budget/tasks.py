# app/services/budget/tasks.py
"""
Celery task for background budget generation.

The HTTP route (app/routers/budget.py) validates the upload, stores both input
files in MinIO, and creates a pending BudgetJob, then enqueues this task with
just the job id. The task downloads the files, runs the pipeline, and stores
the output xlsx back to MinIO.

Frontend polls GET /budget/jobs/{job_id} for status and a presigned download URL.
"""

from typing import Any
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.budget_job import BudgetJob
from app.models.letter_job import JobStatus
from app.models.user import User
from app.services.budget.exceptions import (
    BudgetPipelineError,
    CrossCheckFailed,
    IngestFailed,
    ValidationFailed,
)
from app.services.budget.service import run_budget_pipeline
from app.services.email.tasks import budget_complete_email
from app.services.storage import storage_service


def _step(db, job: BudgetJob, step: str) -> None:
    job.current_step = step
    db.commit()


def _fail(db, job: BudgetJob, code: str, detail: Any) -> None:
    job.status = JobStatus.failed
    job.current_step = None
    job.error_code = code
    job.error_detail = detail
    db.commit()


@celery_app.task(bind=True, time_limit=600, soft_time_limit=540)
def generate_budget_task(self, job_id: str) -> dict[str, Any]:
    """
    Run the budget pipeline for an already-created BudgetJob.

    Downloads input files from MinIO, runs all pipeline stages, and stores
    the output xlsx back to MinIO. Updates job.status throughout.

    Not retried on failure — budget pipeline errors are almost always permanent
    (bad PDF, extraction failure, validation mismatch), and retrying would
    waste Anthropic API calls.
    """
    db = SessionLocal()
    try:
        job = db.query(BudgetJob).filter(BudgetJob.id == UUID(job_id)).first()
        if not job:
            return {"error": f"BudgetJob {job_id} not found"}

        job.status = JobStatus.processing
        db.commit()

        financial_report_bytes = storage_service.download_file(job.financial_report_path)
        prior_budget_bytes = storage_service.download_file(job.prior_budget_path)

        result = run_budget_pipeline(
            financial_report_bytes=financial_report_bytes,
            financial_report_filename=job.financial_report_filename,
            prior_budget_bytes=prior_budget_bytes,
            prior_budget_filename=job.prior_budget_filename,
            association_name=job.association_name,
            budget_year=job.budget_year,
            on_step=lambda step: _step(db, job, step),
        )

        output_key = (
            f"budget/{job_id}/output/"
            f"{job.association_name.replace(' ', '_')}_{job.budget_year}_budget.xlsx"
        )
        storage_service.upload_file(
            result.xlsx_bytes,
            output_key,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        job.status = JobStatus.complete
        job.current_step = None
        job.output_path = output_key
        job.review_flag_count = len(result.review_flags)
        db.commit()

        creator = db.query(User).filter(User.id == job.created_by).first()
        if creator:
            budget_complete_email(
                creator.email, creator.fname, job.association_name, job.budget_year
            )

        return {"job_id": job_id, "status": "complete"}

    except IngestFailed as exc:
        _fail(db, job, "ingest_failed", {"message": str(exc)})
        return {"job_id": job_id, "status": "failed", "error_code": "ingest_failed"}

    except CrossCheckFailed as exc:
        _fail(db, job, "cross_check_failed", {"mismatches": exc.mismatches})
        return {"job_id": job_id, "status": "failed", "error_code": "cross_check_failed"}

    except ValidationFailed as exc:
        _fail(db, job, "validation_failed", {"errors": exc.errors})
        return {"job_id": job_id, "status": "failed", "error_code": "validation_failed"}

    except BudgetPipelineError as exc:
        _fail(db, job, "pipeline_error", {"message": str(exc)})
        return {"job_id": job_id, "status": "failed", "error_code": "pipeline_error"}

    except SoftTimeLimitExceeded:
        _fail(db, job, "timeout", {"message": "Budget generation exceeded the time limit."})
        return {"job_id": job_id, "status": "failed", "error_code": "timeout"}

    except Exception as exc:
        _fail(db, job, "unexpected_error", {"message": str(exc)})
        return {"job_id": job_id, "status": "failed", "error_code": "unexpected_error"}

    finally:
        db.close()
