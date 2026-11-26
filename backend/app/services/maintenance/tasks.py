"""Nightly housekeeping, scheduled by Celery beat (``beat_schedule`` in
app.celery_app). Applies the retention policy in maintenance.retention.
Each step runs on its own so one failing doesn't stop the others."""

from __future__ import annotations

import logging
from typing import Any

from app.celery_app import celery_app
from app.config import settings
from app.database import SessionLocal
from app.services.audit_retention import purge_old_events

from .retention import (
    expire_budget_uploads,
    fail_stuck_jobs,
    purge_jobs,
    purge_reminder_history,
)

logger = logging.getLogger(__name__)


@celery_app.task(time_limit=600, soft_time_limit=540)
def purge_old_data() -> dict[str, Any]:
    steps = {
        "stuck_accounting_runs_failed": fail_stuck_jobs,
        "budget_uploads_deleted": lambda db: expire_budget_uploads(
            db, settings.UPLOAD_RETENTION_DAYS
        ),
        "jobs_deleted": lambda db: purge_jobs(db, settings.JOB_RETENTION_DAYS),
        "reminder_sends_deleted": lambda db: purge_reminder_history(
            db, settings.AUDIT_RETENTION_DAYS
        ),
        "audit_events_deleted": lambda db: purge_old_events(db, settings.AUDIT_RETENTION_DAYS),
    }
    out: dict[str, Any] = {}
    for name, step in steps.items():
        db = SessionLocal()
        try:
            out[name] = step(db)
        except Exception:  # noqa: BLE001 — log it, carry on with the rest
            logger.exception("housekeeping step %s failed", name)
            db.rollback()
            out[name] = "failed"
        finally:
            db.close()
    logger.info("housekeeping: %s", out)
    return out
