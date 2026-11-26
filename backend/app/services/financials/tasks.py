"""Background runs of the accounting tools over combined multi-association
PDFs (e.g. ~180 balance sheets in one file, which needs minutes of OCR)."""

from __future__ import annotations

import io
import json
import logging
import os
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.accounting_job import AccountingJob
from app.models.letter_job import JobStatus
from app.services.storage import storage_service

from .batch import association_name, flagged, run_sections, split_sections
from .ocr import ocr_available
from .pdf import Page, iter_pages, page_count
from .receivables import ROLE_NAMES, ROLES, looks_like, read_section, reconcile

logger = logging.getLogger(__name__)

# Seconds between progress writes while pages are being read.
PROGRESS_EVERY = 1.0
# Pages read by Tesseract at once in a job (each runs single-threaded).
OCR_WORKERS = max(1, min(3, os.cpu_count() or 1))

# Tools that compare several combined files instead of reading one.
MULTI_FILE_TOOLS = {"receivables": ROLES}

_EXPECTED_REPORT = {
    "balance_sheet": "a balance sheet",
    "ar": 'a "CSC AR Names" aging report',
    "prepaid": 'a "CSC_Prepaid" report',
}


class JobFailed(Exception):
    """A problem with the uploaded files, shown to the user as is."""


def input_keys(job: AccountingJob) -> dict[str, str]:
    """Storage keys of the job's uploads, by role. Multi-file jobs store a
    JSON object in ``input_path``; single-file jobs store the key itself."""
    p = job.input_path
    if not p:
        return {}
    return json.loads(p) if p.startswith("{") else {"report": p}


class _Progress:
    """Pages read so far across all of a job's files, written to the job
    about once a second."""

    def __init__(self, db, job: AccountingJob) -> None:
        self.db, self.job = db, job
        self.offset = 0
        self.last = time.monotonic()

    def pages(self, data: bytes, label: str = "", stats: dict | None = None) -> Iterator[Page]:
        stats = stats if stats is not None else {}
        stats.setdefault("text", 0)
        n = 0
        for page in iter_pages(io.BytesIO(data), max_ocr_pages=None, ocr_workers=OCR_WORKERS):
            n = page.number
            stats["text"] += bool(page.words)
            self.job.pages_done = self.offset + n
            name = association_name(page)
            if name:
                self.job.current_association = (f"{name} ({label})" if label else name)[:255]
            self.tick()
            yield page
        self.offset += n

    def tick(self, force: bool = False) -> None:
        if force or time.monotonic() - self.last >= PROGRESS_EVERY:
            self.db.commit()
            self.last = time.monotonic()


def _no_text(what: str = "This PDF") -> str:
    detail = f"{what} has no readable text."
    if not ocr_available():
        detail += " OCR (Tesseract) isn't installed on the worker."
    return detail


def _run_single(db, job: AccountingJob, data: bytes) -> None:
    progress = _Progress(db, job)
    stats: dict = {}
    for section, result in run_sections(job.tool, progress.pages(data, stats=stats)):
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
        progress.tick(force=True)
    if stats["text"] == 0:
        raise JobFailed(_no_text())


def _run_receivables(db, job: AccountingJob, files: dict[str, bytes]) -> None:
    """Read every file into per-association figures, then pair and compare.
    Results come at the end: an association can't be compared until all
    three files have been read."""
    progress = _Progress(db, job)
    found = {}
    for role in ROLES:
        if role not in files:
            continue
        stats = {"right_kind": 0}

        def counted(pages: Iterator[Page], stats=stats, role=role) -> Iterator[Page]:
            for p in pages:
                stats["right_kind"] += looks_like(role, p)
                yield p

        pages = counted(progress.pages(files[role], ROLE_NAMES[role], stats))
        found[role] = [read_section(role, s) for s in split_sections(pages)]
        what = f"The {ROLE_NAMES[role]}"
        if stats["text"] == 0:
            raise JobFailed(_no_text(what))
        if stats["right_kind"] == 0:
            raise JobFailed(
                f"{what} doesn't look like {_EXPECTED_REPORT[role]}. "
                "Check the files went in the right boxes."
            )
    job.current_association = None
    job.results = reconcile(found)


@celery_app.task(bind=True, time_limit=3600, soft_time_limit=3540)
def run_accounting_job(self, job_id: str) -> dict[str, Any]:
    db = SessionLocal()
    job: AccountingJob | None = None
    keys: dict[str, str] = {}
    try:
        job = db.query(AccountingJob).filter(AccountingJob.id == UUID(job_id)).first()
        if job is None:
            return {"error": f"AccountingJob {job_id} not found"}
        keys = input_keys(job)
        job.status = JobStatus.processing
        db.commit()

        files = {role: storage_service.download_file(key) for role, key in keys.items()}
        job.total_pages = sum(page_count(io.BytesIO(d)) for d in files.values())
        job.results = []
        db.commit()

        if job.tool in MULTI_FILE_TOOLS:
            _run_receivables(db, job, files)
        else:
            _run_single(db, job, files["report"])

        job.status = JobStatus.complete
        job.current_association = None
        job.pages_done = job.total_pages
        job.finished_at = datetime.now(UTC)
        db.commit()
        return {"associations": len(job.results)}
    except JobFailed as exc:
        _fail(db, job, str(exc))
        return {"error": str(exc)}
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
        # The PDFs hold owner/bank data; keep them only as long as the run.
        if job is not None and keys:
            try:
                for key in keys.values():
                    storage_service.delete_file(key)
                job.input_path = None
                db.commit()
            except Exception:  # noqa: BLE001
                logger.warning("couldn't delete accounting job inputs %s", list(keys.values()))
        db.close()


def _fail(db, job: AccountingJob, detail: str) -> None:
    job.status = JobStatus.failed
    job.error_detail = detail[:500]
    job.current_association = None
    job.finished_at = datetime.now(UTC)
    db.commit()


__all__ = ["Page", "input_keys", "run_accounting_job"]
