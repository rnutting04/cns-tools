# app/services/audit.py
from typing import Any
from sqlalchemy.orm import Session
from app.models.audit_event import AuditEvent
from app.models.user import User


def log_event(
    db: Session,
    actor: User | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    """
    Record an audit event. Call from service layer after a successful action.
    
    IMPORTANT: Never pass passwords, tokens, or other secrets in metadata.
    """
    event = AuditEvent(
        actor_user_id=actor.id if actor else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id else None,
        event_metadata=metadata or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(event)
    # Note: no db.commit() here. Audit event commits with the parent transaction.