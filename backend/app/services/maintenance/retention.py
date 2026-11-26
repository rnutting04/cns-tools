"""Data retention for everything the jobs store. One policy for all of them:

1. Uploaded source files are kept only while the job needs them.
   - Accounting runs delete their PDFs when the run ends (financials.tasks).
   - Budgets delete theirs on completion (budget.tasks). A failed budget, or
     one parked for layout review, keeps them for ``UPLOAD_RETENTION_DAYS``
     so it can be retried or confirmed; after that they're deleted and the
     budget has to be started again.
2. Job records and what they produced (letters and their .docx, budgets and
   their .xlsx, accounting results and screenshots) are deleted
   ``JOB_RETENTION_DAYS`` after the job was started.
3. Accounting runs lost to a worker restart (still unfinished long after the
   one-hour limit) are failed and their PDFs deleted, so nothing is stranded.
   Budgets aren't checked this way: a retry keeps the original start time,
   so age can't tell a stuck budget from a retried one. Rule 1 covers them.

The audit log has its own period (``AUDIT_RETENTION_DAYS``, audit_retention).
Runs nightly from Celery beat: see maintenance.tasks.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, not_, or_
from sqlalchemy.orm import Session

from app.models.accounting_job import AccountingJob
from app.models.budget_job import BudgetJob
from app.models.letter_job import JobStatus, LetterJob
from app.services.financials.tasks import input_keys
from app.services.storage import storage_service

logger = logging.getLogger(__name__)

# Accounting runs are killed after an hour; anything still unfinished after
# this long has lost its worker.
STUCK_AFTER = timedelta(hours=6)

# Must match budget.tasks.AWAITING_LAYOUT_REVIEW (not imported: that module
# pulls in the whole budget pipeline).
_AWAITING_LAYOUT_REVIEW = "awaiting_layout_review"
_UNFINISHED = (JobStatus.pending, JobStatus.processing)


def _now() -> datetime:
    # created_at is stored as naive UTC.
    return datetime.now(UTC).replace(tzinfo=None)


def _delete_files(keys: Iterable[str | None]) -> bool:
    """Delete storage objects; False if any couldn't be deleted (the nightly
    run tries again)."""
    ok = True
    for key in keys:
        if not key:
            continue
        try:
            storage_service.delete_file(key)
        except Exception:  # noqa: BLE001 — retried tomorrow
            logger.warning("couldn't delete stored file %s", key, exc_info=True)
            ok = False
    return ok


# --------------------------------------------------------------------------
# Uploads
# --------------------------------------------------------------------------


def drop_budget_uploads(job: BudgetJob) -> bool:
    """Delete a budget's uploaded report and prior budget. The paths are
    blanked so the budget reads as "uploads expired" (see budget router)."""
    if not _delete_files([job.financial_report_path, job.prior_budget_path]):
        return False
    job.financial_report_path = ""
    job.prior_budget_path = ""
    return True


def budget_uploads_expired(job: BudgetJob) -> bool:
    return not job.financial_report_path or not job.prior_budget_path


def expire_budget_uploads(db: Session, upload_days: int) -> int:
    """Delete budget uploads that are no longer needed: every finished
    budget's (normally gone already), and failed or parked budgets' after
    ``upload_days``. A budget being worked on right now is left alone.
    Returns how many budgets had their uploads deleted."""
    cutoff = _now() - timedelta(days=upload_days)
    running = and_(
        BudgetJob.status.in_(_UNFINISHED),
        or_(BudgetJob.current_step.is_(None), BudgetJob.current_step != _AWAITING_LAYOUT_REVIEW),
    )
    jobs = (
        db.query(BudgetJob)
        .filter(BudgetJob.financial_report_path != "")
        .filter(not_(running))
        .filter(or_(BudgetJob.status == JobStatus.complete, BudgetJob.created_at < cutoff))
        .all()
    )
    done = sum(drop_budget_uploads(j) for j in jobs)
    db.commit()
    return done


def fail_stuck_jobs(db: Session, stuck_after: timedelta = STUCK_AFTER) -> int:
    """Fail accounting runs unfinished for ``stuck_after`` and delete their
    uploads. Returns how many were failed."""
    cutoff = _now() - stuck_after
    jobs = (
        db.query(AccountingJob)
        .filter(AccountingJob.status.in_(_UNFINISHED), AccountingJob.created_at < cutoff)
        .all()
    )
    for job in jobs:
        if _delete_files(input_keys(job).values()):
            job.input_path = None
        job.status = JobStatus.failed
        job.error_detail = "Interrupted: the background worker stopped. Start the run again."
        job.current_association = None
        job.finished_at = datetime.now(UTC)
    db.commit()
    return len(jobs)


# --------------------------------------------------------------------------
# Job records and outputs
# --------------------------------------------------------------------------


def purge_jobs(db: Session, retention_days: int) -> dict[str, int]:
    """Delete letters, budgets and accounting runs started more than
    ``retention_days`` ago, with every file they still hold. A job whose
    files can't be deleted is kept for the next night. Jobs running right
    now are never deleted (none run anywhere near this long)."""
    cutoff = _now() - timedelta(days=retention_days)
    out = {"letters": 0, "budgets": 0, "accounting_runs": 0}

    letters = (
        db.query(LetterJob)
        .filter(LetterJob.created_at < cutoff, LetterJob.status.notin_(_UNFINISHED))
        .all()
    )
    for letter in letters:
        if _delete_files([letter.output_path]):
            db.delete(letter)
            out["letters"] += 1

    budgets = (
        db.query(BudgetJob)
        .filter(BudgetJob.created_at < cutoff)
        .filter(
            or_(
                BudgetJob.status.notin_(_UNFINISHED),
                BudgetJob.current_step == _AWAITING_LAYOUT_REVIEW,
            )
        )
        .all()
    )
    for budget in budgets:
        files = [budget.output_path, budget.financial_report_path, budget.prior_budget_path]
        if _delete_files(files):
            db.delete(budget)
            out["budgets"] += 1

    runs = (
        db.query(AccountingJob)
        .filter(AccountingJob.created_at < cutoff, AccountingJob.status.notin_(_UNFINISHED))
        .all()
    )
    for run in runs:
        if _delete_files(input_keys(run).values()):
            db.delete(run)
            out["accounting_runs"] += 1

    db.commit()
    return out
