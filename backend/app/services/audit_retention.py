# app/services/audit_retention.py
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.audit_event import AuditEvent


def purge_old_events(db: Session, retention_days: int) -> int:
    """
    Delete audit events older than `retention_days` days.
    Returns the number of rows deleted.
    Commits the deletion itself — call outside of any open transaction.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=retention_days)
    deleted = (
        db.query(AuditEvent)
        .filter(AuditEvent.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted
