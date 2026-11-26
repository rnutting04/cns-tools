# app/models/reminder.py
"""Scheduled reminder emails ("mailing day is Thursday", "audit due Friday").

A reminder names an event (``start_date``, optionally repeating), how many
days ahead to send (``lead_days``) and at what Eastern time (``send_time``).
``next_event_date`` / ``next_send_at`` always hold the next occurrence still
to be sent; the dispatcher (app.services.reminders) sends what's due every few
minutes and moves them on. Nothing is stored in the scheduler itself.
"""

import uuid
from datetime import UTC, datetime, time

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Reminder(Base):
    __tablename__ = "reminders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(200), nullable=False)  # also the email subject
    message = Column(Text, nullable=False, default="")
    recipients = Column(JSON, nullable=False, default=list)  # email addresses

    start_date = Column(Date, nullable=False)  # the event's (first) date
    repeat = Column(String(10), nullable=False, default="none")  # none|weekly|monthly|yearly
    lead_days = Column(Integer, nullable=False, default=0)  # send this many days before
    send_time = Column(Time, nullable=False, default=time(8, 0))  # Eastern

    active = Column(Boolean, nullable=False, default=True)
    # The next occurrence still to send; both None once a one-off has gone
    # out or while paused. next_send_at is naive UTC.
    next_event_date = Column(Date, nullable=True)
    next_send_at = Column(DateTime, nullable=True, index=True)
    last_sent_at = Column(DateTime, nullable=True)

    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    creator = relationship("User")
    deliveries = relationship(
        "ReminderDelivery", back_populates="reminder", cascade="all, delete-orphan"
    )


class ReminderDelivery(Base):
    """One email sent for one occurrence to one person. The unique key is what
    stops a retry or overlapping run from sending the same reminder twice."""

    __tablename__ = "reminder_deliveries"
    __table_args__ = (
        UniqueConstraint("reminder_id", "event_date", "recipient", name="uq_reminder_delivery"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reminder_id = Column(
        UUID(as_uuid=True),
        ForeignKey("reminders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_date = Column(Date, nullable=False)
    recipient = Column(String(320), nullable=False)
    sent_at = Column(DateTime, nullable=False, default=_now, index=True)

    reminder = relationship("Reminder", back_populates="deliveries")
