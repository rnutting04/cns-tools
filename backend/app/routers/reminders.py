# app/routers/reminders.py
"""Scheduled reminder emails. Admin-only while it's being tried out; every
admin sees and can edit every reminder."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_admin
from app.models.reminder import Reminder, ReminderDelivery
from app.models.user import User
from app.schemas.reminder import (
    ReminderActive,
    ReminderDeliveryOut,
    ReminderIn,
    ReminderOut,
)
from app.services.audit import log_event
from app.services.reminders.schedule import describe
from app.services.reminders.service import apply_schedule, render

router = APIRouter(prefix="/reminders", tags=["reminders"], dependencies=[Depends(require_admin)])


def _utc(dt: datetime | None) -> datetime | None:
    return dt.replace(tzinfo=UTC) if dt is not None else None


def _out(r: Reminder) -> ReminderOut:
    creator = r.creator
    return ReminderOut(
        id=str(r.id),
        title=r.title,
        message=r.message,
        recipients=list(r.recipients or []),
        start_date=r.start_date,
        repeat=r.repeat,
        lead_days=r.lead_days,
        send_time=r.send_time,
        active=r.active,
        schedule=describe(r.start_date, r.repeat, r.lead_days, r.send_time),
        next_event_date=r.next_event_date,
        next_send_at=_utc(r.next_send_at),
        last_sent_at=_utc(r.last_sent_at),
        created_by_name=f"{creator.fname} {creator.lname}".strip() if creator else "",
        created_at=_utc(r.created_at),
    )


def _get(db: Session, reminder_id: uuid.UUID) -> Reminder:
    r = db.get(Reminder, reminder_id)
    if r is None:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return r


def _schedule_or_422(r: Reminder) -> None:
    apply_schedule(r)
    if r.active and r.next_send_at is None:
        when = describe(r.start_date, r.repeat, r.lead_days, r.send_time)
        raise HTTPException(
            status_code=422,
            detail=f"That time has already passed ({when}). Pick a later date or time.",
        )


def _fill(r: Reminder, data: ReminderIn) -> None:
    for k, v in data.model_dump().items():
        setattr(r, k, v)


@router.get("", response_model=list[ReminderOut])
def list_reminders(db: Session = Depends(get_db)) -> list[ReminderOut]:
    """Active reminders by next send time, then paused / finished ones."""
    rows = db.query(Reminder).all()
    rows.sort(key=lambda r: (r.next_send_at is None, r.next_send_at or datetime.max, r.title))
    return [_out(r) for r in rows]


@router.post("", response_model=ReminderOut, status_code=201)
def create_reminder(
    data: ReminderIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ReminderOut:
    r = Reminder(created_by=current_user.id)
    _fill(r, data)
    _schedule_or_422(r)
    db.add(r)
    db.flush()
    log_event(
        db,
        actor=current_user,
        action="reminder.created",
        target_type="reminder",
        target_id=str(r.id),
        metadata={"title": r.title, "recipients": len(r.recipients), "repeat": r.repeat},
    )
    db.commit()
    db.refresh(r)
    return _out(r)


@router.put("/{reminder_id}", response_model=ReminderOut)
def update_reminder(
    reminder_id: uuid.UUID,
    data: ReminderIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ReminderOut:
    """Replace a reminder's settings. Its next email is worked out again; an
    occurrence that was already emailed isn't emailed twice."""
    r = _get(db, reminder_id)
    _fill(r, data)
    _schedule_or_422(r)
    log_event(
        db,
        actor=current_user,
        action="reminder.updated",
        target_type="reminder",
        target_id=str(r.id),
        metadata={"title": r.title},
    )
    db.commit()
    db.refresh(r)
    return _out(r)


@router.patch("/{reminder_id}/active", response_model=ReminderOut)
def set_active(
    reminder_id: uuid.UUID,
    data: ReminderActive,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> ReminderOut:
    """Pause or resume. Resuming picks up at the next occurrence still ahead."""
    r = _get(db, reminder_id)
    r.active = data.active
    _schedule_or_422(r)
    log_event(
        db,
        actor=current_user,
        action="reminder.resumed" if r.active else "reminder.paused",
        target_type="reminder",
        target_id=str(r.id),
        metadata={"title": r.title},
    )
    db.commit()
    db.refresh(r)
    return _out(r)


@router.delete("/{reminder_id}", status_code=204)
def delete_reminder(
    reminder_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> Response:
    r = _get(db, reminder_id)
    log_event(
        db,
        actor=current_user,
        action="reminder.deleted",
        target_type="reminder",
        target_id=str(r.id),
        metadata={"title": r.title},
    )
    db.delete(r)
    db.commit()
    return Response(status_code=204)


@router.post("/{reminder_id}/test", status_code=202)
def send_test(
    reminder_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
) -> dict:
    """Email the next occurrence to yourself only, now. Not counted as sent."""
    from app.services.email.tasks import send_email_task

    r = _get(db, reminder_id)
    event = r.next_event_date or r.start_date
    name = f"{current_user.fname} {current_user.lname}".strip()
    subject, html = render(r, event, name)
    send_email_task.delay(current_user.email, f"[Test] {subject}", html)
    log_event(
        db,
        actor=current_user,
        action="reminder.test_sent",
        target_type="reminder",
        target_id=str(r.id),
        metadata={"title": r.title},
    )
    db.commit()
    return {"sent_to": current_user.email}


@router.get("/{reminder_id}/deliveries", response_model=list[ReminderDeliveryOut])
def list_deliveries(
    reminder_id: uuid.UUID, db: Session = Depends(get_db)
) -> list[ReminderDeliveryOut]:
    """The 50 most recent emails this reminder sent."""
    _get(db, reminder_id)
    rows = (
        db.query(ReminderDelivery)
        .filter(ReminderDelivery.reminder_id == reminder_id)
        .order_by(ReminderDelivery.sent_at.desc())
        .limit(50)
        .all()
    )
    return [
        ReminderDeliveryOut(event_date=d.event_date, recipient=d.recipient, sent_at=_utc(d.sent_at))
        for d in rows
    ]
