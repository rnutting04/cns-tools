# app/services/letters/tasks.py
"""
Celery task for background letter generation.

The HTTP route (app/routers/templates.py) does the validation/authorization and
creates a pending LetterJob synchronously, then enqueues this task with just the
job id. The worker re-renders from the context already stored on the job, so the
task payload stays small and retries are safe.

The frontend polls GET /letters/{job_id} for status and the download URL.
"""

from typing import Any
from uuid import UUID

from app.celery_app import celery_app
from app.database import SessionLocal
from app.services.letters.exceptions import RenderFailed
from app.services.letters.service import render_letter_job


@celery_app.task(bind=True, max_retries=3, acks_late=True)
def generate_letter_task(self, job_id: str) -> dict[str, Any]:
    """
    Render an already-prepared LetterJob. Creates its own DB session since
    workers don't get one injected the way HTTP routes do.

    Retries transient render/upload failures (e.g. MinIO blips) with
    exponential backoff. ``render_letter_job`` is idempotent, so a retry that
    runs after a partial success is safe.
    """
    db = SessionLocal()
    try:
        result = render_letter_job(db, UUID(job_id))
        return {"job_id": str(result.job_id), "status": result.status}
    except RenderFailed as exc:
        raise self.retry(exc=exc, countdown=2**self.request.retries) from exc
    finally:
        db.close()
