# app/services/letters/tasks.py
"""
Worker-friendly wrapper around generate_letter().

This is the entry point for async execution (Dramatiq, Celery, RQ, etc.).
It handles its own database session lifecycle since workers don't get
one injected the way HTTP routes do.

When you're ready to move generation to a worker, the HTTP route will:
  1. Create a LetterJob in `pending` status
  2. Enqueue generate_letter_task(job_id)
  3. Return the job_id immediately

The frontend polls /letters/{job_id} or subscribes via websocket for status.
"""
from typing import Any
from uuid import UUID

from app.database import SessionLocal  # adjust if your session factory lives elsewhere
from app.models.user import User
from app.services.letters.service import generate_letter


def generate_letter_task(
    user_id: UUID,
    template_id: UUID,
    field_values: dict[str, Any],
) -> dict[str, Any]:
    """
    Synchronous function suitable for wrapping with @dramatiq.actor
    or @celery.task. Creates its own DB session.

    Returns a serializable dict so task result backends can store it.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")

        result = generate_letter(
            db=db,
            current_user=user,
            template_id=template_id,
            field_values=field_values,
        )
        return {
            "job_id": str(result.job_id),
            "download_url": result.download_url,
            "status": result.status,
        }
    finally:
        db.close()


# --- When you wire up Dramatiq, uncomment this ---------------------------
# import dramatiq
#
# @dramatiq.actor(max_retries=3, time_limit=60_000)
# def generate_letter_actor(user_id: str, template_id: str, field_values: dict):
#     return generate_letter_task(
#         user_id=UUID(user_id),
#         template_id=UUID(template_id),
#         field_values=field_values,
#     )