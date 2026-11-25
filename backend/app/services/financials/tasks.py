"""Background runs of the accounting tools over combined multi-association
PDFs (e.g. ~180 balance sheets in one file, which needs minutes of OCR)."""

from __future__ import annotations

import io
import logging
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.accounting_job import AccountingJob
from app.models.letter_job import JobStatus
from app.services.storage import storage_service

from .batch import association_name, flagged, run_sections
from .ocr import ocr_available
from .pdf import Page, iter_pages, page_count

logger = logging.getLogger(__name__)

# Seconds between progress writes while pages are being read.
PROGRESS_EVERY = 1.0


@celery_app.task(bind=True, time_limit=3600, soft_time_limit=3540)
def run_accounting_job(self, job_id: str) -> dict[str, Any]:
    db = SessionLocal()
    job: AccountingJob | None = None
    try:
        job = db.query(AccountingJob).filter(AccountingJob.id == UUID(job_id)).first()
        if job is None:
            return {"error": f"AccountingJob {job_id} not found"}
        job.status = JobStatus.processing
        db.commit()

        data = storage_service.download_file(job.input_path)
        job.total_pages = page_count(io.BytesIO(data))
        job.results = []
        db.commit()

        last = time.monotonic()
        text_pages = 0

        def pages_with_progress():
            nonlocal last, text_pages
            for page in iter_pages(io.BytesIO(data), max_ocr_pages=None):
                text_pages += bool(page.words)
                job.pages_done = page.number
                name = association_name(page)
                if name:
                    job.current_association = name[:255]
                if time.monotonic() - last >= PROGRESS_EVERY:
                    db.commit()
                    last = time.monotonic()
                yield page

        for section, result in run_sections(job.tool, pages_with_progress()):
            first, last_page = section.page_range
            job.results = [
                *job.results,
                {
                    "association": section.name,
                    "first_page": first,
                    "last_page": last_page,
                    "flagged": flagged(job.tool, result),
                    "result": result,
                },
            ]
            db.commit()
            last = time.monotonic()

        if text_pages == 0:
            detail = "This PDF has no readable text."
            if not ocr_available():
                detail += " OCR (Tesseract) isn't installed on the worker."
            _fail(db, job, detail)
            return {"error": detail}

        job.status = JobStatus.complete
        job.current_association = None
        job.pages_done = job.total_pages
        job.finished_at = datetime.now(UTC)
        db.commit()
        return {"associations": len(job.results)}
    except SoftTimeLimitExceeded:
        if job is not None:
            _fail(db, job, "Took longer than an hour; try splitting the file.")
        return {"error": "time limit"}
    except Exception as exc:  # noqa: BLE001 — record any failure on the job
        logger.exception("accounting job %s failed", job_id)
        if job is not None:
            db.rollback()
            _fail(db, job, f"Couldn't read this PDF: {type(exc).__name__}")
        return {"error": str(exc)}
    finally:
        # The PDF holds owner/bank data; keep it only as long as the run.
        if job is not None and job.input_path:
            try:
                storage_service.delete_file(job.input_path)
                job.input_path = None
                db.commit()
            except Exception:  # noqa: BLE001
                logger.warning("couldn't delete accounting job input %s", job.input_path)
        db.close()


def _fail(db, job: AccountingJob, detail: str) -> None:
    job.status = JobStatus.failed
    job.error_detail = detail[:500]
    job.current_association = None
    job.finished_at = datetime.now(UTC)
    db.commit()


__all__ = ["Page", "run_accounting_job"]
