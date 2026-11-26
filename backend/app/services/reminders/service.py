"""Scheduling, rendering and sending reminder emails.

``dispatch_due`` runs every few minutes (Celery beat, see app.celery_app):
it sends every reminder whose ``next_send_at`` has passed and moves it on to
its next occurrence. Safe to run twice at once or to retry: due rows are
locked (``SKIP LOCKED``) and every email is recorded in reminder_deliveries
under a unique (reminder, event date, recipient) key before it's queued.
A reminder that was missed (worker or scheduler down) goes out late, once,
rather than not at all; occurrences that were skipped meanwhile aren't sent.
"""

from __future__ import annotations

import logging
from datetime import date
from html import escape

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.reminder import Reminder, ReminderDelivery
from app.models.user import User
from app.services.email import layout

from .schedule import next_due, utcnow

logger = logging.getLogger(__name__)


def apply_schedule(r: Reminder, after=None, past_event: date | None = None) -> None:
    """Point ``next_event_date`` / ``next_send_at`` at the next email still
    to send (or None: paused, or a one-off that's done)."""
    nxt = (
        next_due(r.start_date, r.repeat, r.lead_days, r.send_time, after or utcnow(), past_event)
        if r.active
        else None
    )
    r.next_event_date, r.next_send_at = nxt if nxt else (None, None)


def _long_date(d: date) -> str:
    return f"{d:%A, %B} {d.day}, {d.year}"


def render(r: Reminder, event: date, creator_name: str) -> tuple[str, str]:
    """(subject, html) for one occurrence."""
    when = _long_date(event)
    if r.lead_days:
        when += f" (in {r.lead_days} day{'s' if r.lead_days != 1 else ''})"
    blocks = [layout.heading(r.title), layout.paragraph(f"<b>When:</b> {escape(when)}")]
    for para in (p.strip() for p in r.message.split("\n\n")):
        if para:
            blocks.append(layout.paragraph(escape(para).replace("\n", "<br />")))
    blocks.append(layout.button("Open C&S Tools", settings.FRONTEND_URL))
    html = layout.render(
        preheader=f"Reminder: {r.title} — {when}",
        title=r.title,
        blocks=blocks,
        footer_note=(
            f"You're receiving this because {escape(creator_name)} added you to the "
            f"reminder “{escape(r.title)}” in C&amp;S Tools. Reply to this email to be removed."
        ),
    )
    return r.title, html


def _creator_name(db: Session, r: Reminder) -> str:
    u = r.creator or db.get(User, r.created_by)
    return f"{u.fname} {u.lname}".strip() if u else "a C&S Tools admin"


def _inactive_emails(db: Session) -> set[str]:
    rows = db.query(func.lower(User.email)).filter(User.is_active.is_(False)).all()
    return {e for (e,) in rows}


def dispatch_due(db: Session, now=None) -> int:
    """Send every due reminder and schedule its next occurrence. Returns the
    number of emails queued."""
    from app.services.email.tasks import send_email_task  # celery import cycle

    now = now or utcnow()
    due = (
        db.query(Reminder)
        .filter(Reminder.active.is_(True), Reminder.next_send_at <= now)
        .with_for_update(skip_locked=True)
        .all()
    )
    if not due:
        return 0
    skip = _inactive_emails(db)
    outbox: list[tuple[str, str, str]] = []
    for r in due:
        event = r.next_event_date
        subject, html = render(r, event, _creator_name(db, r))
        for addr in r.recipients:
            if addr.lower() in skip:
                continue  # deactivated accounts get nothing
            row = db.execute(
                insert(ReminderDelivery)
                .values(reminder_id=r.id, event_date=event, recipient=addr, sent_at=now)
                .on_conflict_do_nothing(constraint="uq_reminder_delivery")
                .returning(ReminderDelivery.id)
            ).first()
            if row:  # not already sent for this occurrence
                outbox.append((addr, subject, html))
        r.last_sent_at = now
        apply_schedule(r, after=now, past_event=event)
        if r.repeat == "none":
            r.active = False
    # Record first, then queue: a crash in between loses an email rather
    # than sending it twice. send_email_task retries delivery itself.
    db.commit()
    for to, subject, html in outbox:
        send_email_task.delay(to, subject, html)
    logger.info("reminders: %d due, %d emails queued", len(due), len(outbox))
    return len(outbox)
