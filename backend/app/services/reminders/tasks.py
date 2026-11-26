"""Sends due reminders. Queued every 5 minutes by Celery beat (see
``beat_schedule`` in app.celery_app); runs on the light worker."""

from __future__ import annotations

from app.celery_app import celery_app
from app.database import SessionLocal

from .service import dispatch_due


@celery_app.task(time_limit=120, soft_time_limit=100)
def send_due_reminders() -> int:
    db = SessionLocal()
    try:
        return dispatch_due(db)
    finally:
        db.close()
