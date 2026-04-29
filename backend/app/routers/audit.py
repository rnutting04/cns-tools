# app/routers/audit.py
import csv
import io
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session, contains_eager

from app.database import get_db
from app.dependencies import require_super_admin
from app.models.audit_event import AuditEvent
from app.models.user import User

router = APIRouter(prefix="/audit", tags=["audit"])

PAGE_SIZE = 50


class AuditEventResponse(BaseModel):
    id: UUID
    created_at: datetime
    actor_user_id: UUID | None
    actor_email: str | None
    action: str
    target_type: str | None
    target_id: str | None
    event_metadata: dict
    ip_address: str | None
    user_agent: str | None


class AuditPage(BaseModel):
    items: list[AuditEventResponse]
    total: int
    page: int
    pages: int


def _build_query(
    db: Session,
    date_from: datetime | None,
    date_to: datetime | None,
    actor_email: str | None,
    actions: list[str],
    search: str | None,
):
    q = (
        db.query(AuditEvent)
        .outerjoin(User, AuditEvent.actor_user_id == User.id)
        .options(contains_eager(AuditEvent.actor))
    )
    if date_from:
        q = q.filter(AuditEvent.created_at >= date_from)
    if date_to:
        q = q.filter(AuditEvent.created_at <= date_to)
    if actor_email:
        q = q.filter(User.email.ilike(f"%{actor_email}%"))
    if actions:
        q = q.filter(AuditEvent.action.in_(actions))
    if search:
        pattern = f"%{search}%"
        q = q.filter(
            or_(
                AuditEvent.action.ilike(pattern),
                AuditEvent.target_id.ilike(pattern),
                User.email.ilike(pattern),
            )
        )
    return q


def _serialize(event: AuditEvent) -> AuditEventResponse:
    return AuditEventResponse(
        id=event.id,
        created_at=event.created_at,
        actor_user_id=event.actor_user_id,
        actor_email=event.actor.email if event.actor else None,
        action=event.action,
        target_type=event.target_type,
        target_id=event.target_id,
        event_metadata=event.event_metadata or {},
        ip_address=str(event.ip_address) if event.ip_address else None,
        user_agent=event.user_agent,
    )


@router.get("", response_model=AuditPage)
def list_audit_events(
    page: int = Query(1, ge=1),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    actor_email: str | None = None,
    actions: list[str] = Query(default=[]),
    search: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    q = _build_query(db, date_from, date_to, actor_email, actions, search)
    total = q.count()
    items = (
        q.order_by(AuditEvent.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
        .all()
    )
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    return AuditPage(
        items=[_serialize(e) for e in items],
        total=total,
        page=page,
        pages=pages,
    )


@router.get("/actions", response_model=list[str])
def list_distinct_actions(
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    rows = db.query(AuditEvent.action).distinct().order_by(AuditEvent.action).all()
    return [r[0] for r in rows]


@router.get("/export")
def export_csv(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    actor_email: str | None = None,
    actions: list[str] = Query(default=[]),
    search: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_super_admin),
):
    q = _build_query(db, date_from, date_to, actor_email, actions, search)
    events = q.order_by(AuditEvent.created_at.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["timestamp", "actor_email", "action", "target_type", "target_id", "ip_address", "user_agent", "metadata"]
    )
    for e in events:
        writer.writerow([
            e.created_at.isoformat(),
            e.actor.email if e.actor else "",
            e.action,
            e.target_type or "",
            e.target_id or "",
            str(e.ip_address) if e.ip_address else "",
            e.user_agent or "",
            str(e.event_metadata or {}),
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_export.csv"},
    )
