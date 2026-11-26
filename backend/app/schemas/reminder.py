# app/schemas/reminder.py
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

Repeat = Literal["none", "weekly", "monthly", "yearly"]

MAX_RECIPIENTS = 50


class ReminderIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(default="", max_length=5000)
    recipients: list[EmailStr] = Field(min_length=1, max_length=MAX_RECIPIENTS)
    start_date: date
    repeat: Repeat = "none"
    lead_days: int = Field(default=0, ge=0, le=90)
    send_time: time = time(8, 0)  # Eastern
    active: bool = True

    @field_validator("title")
    @classmethod
    def _strip_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title can't be blank")
        return v

    @field_validator("recipients")
    @classmethod
    def _dedupe(cls, v: list[str]) -> list[str]:
        seen: dict[str, str] = {}
        for addr in v:
            seen.setdefault(addr.lower(), addr.lower())
        return list(seen.values())


class ReminderActive(BaseModel):
    active: bool


class ReminderOut(BaseModel):
    id: str
    title: str
    message: str
    recipients: list[str]
    start_date: date
    repeat: Repeat
    lead_days: int
    send_time: time
    active: bool
    schedule: str  # "Every month on the 25th · 3 days before · 8:00 AM ET"
    next_event_date: date | None
    next_send_at: datetime | None  # UTC
    last_sent_at: datetime | None  # UTC
    created_by_name: str
    created_at: datetime | None


class ReminderDeliveryOut(BaseModel):
    event_date: date
    recipient: str
    sent_at: datetime  # UTC
