"""Reminder emails: the admin-only API, the 5-minute dispatcher, retention."""

from datetime import date, datetime, time, timedelta
from unittest.mock import patch

import pytest

from app.celery_app import celery_app
from app.models.audit_event import AuditEvent
from app.models.reminder import Reminder, ReminderDelivery
from app.models.user import UserRole
from app.services.maintenance.retention import purge_reminder_history
from app.services.reminders.schedule import send_at, utcnow
from app.services.reminders.service import apply_schedule, dispatch_due
from tests import factories

pytestmark = pytest.mark.integration

SEND = "app.services.email.tasks.send_email_task"


def _body(**over):
    soon = date.today() + timedelta(days=10)
    body = {
        "title": "Mailing day",
        "message": "Letters go out Thursday.\n\nGet merges in by Tuesday.",
        "recipients": ["Ryan@Example.com", "team@example.com", "ryan@example.com"],
        "start_date": soon.isoformat(),
        "repeat": "monthly",
        "lead_days": 3,
        "send_time": "08:00",
    }
    return {**body, **over}


class TestApi:
    def test_admins_only(self, client, as_user):
        as_user(role=UserRole.manager)
        assert client.get("/api/reminders").status_code == 403
        assert client.post("/api/reminders", json=_body()).status_code == 403

    def test_create_schedules_the_first_email(self, client, as_user, db_session):
        admin = as_user(role=UserRole.admin)
        res = client.post("/api/reminders", json=_body())
        assert res.status_code == 201, res.text
        out = res.json()
        assert out["recipients"] == ["ryan@example.com", "team@example.com"]  # deduped
        assert out["schedule"].startswith("Every month on the")
        assert out["next_event_date"] == _body()["start_date"]
        assert out["next_send_at"].endswith("Z") or "+00:00" in out["next_send_at"]
        assert out["created_by_name"] == f"{admin.fname} {admin.lname}"
        assert db_session.query(AuditEvent).filter_by(action="reminder.created").count() == 1

    def test_one_off_in_the_past_is_refused(self, client, as_user):
        as_user(role=UserRole.admin)
        past = (date.today() - timedelta(days=2)).isoformat()
        res = client.post("/api/reminders", json=_body(repeat="none", start_date=past))
        assert res.status_code == 422
        assert "already passed" in res.json()["detail"]

    def test_bad_email_is_refused(self, client, as_user):
        as_user(role=UserRole.admin)
        res = client.post("/api/reminders", json=_body(recipients=["not-an-email"]))
        assert res.status_code == 422

    def test_edit_pause_resume_delete(self, client, as_user, db_session):
        as_user(role=UserRole.admin)
        rid = client.post("/api/reminders", json=_body()).json()["id"]

        res = client.put(f"/api/reminders/{rid}", json=_body(title="Mailing day (moved)"))
        assert res.json()["title"] == "Mailing day (moved)"

        paused = client.patch(f"/api/reminders/{rid}/active", json={"active": False}).json()
        assert paused["active"] is False and paused["next_send_at"] is None
        resumed = client.patch(f"/api/reminders/{rid}/active", json={"active": True}).json()
        assert resumed["next_send_at"] is not None

        assert client.delete(f"/api/reminders/{rid}").status_code == 204
        assert client.get("/api/reminders").json() == []

    def test_send_test_goes_only_to_you(self, client, as_user):
        admin = as_user(role=UserRole.admin)
        rid = client.post("/api/reminders", json=_body()).json()["id"]
        with patch(SEND) as send:
            res = client.post(f"/api/reminders/{rid}/test")
        assert res.status_code == 202
        to, subject, html = send.delay.call_args.args
        assert to == admin.email and subject == "[Test] Mailing day"
        assert "Get merges in by Tuesday." in html


@pytest.fixture
def due_reminder(db_session):
    admin = factories.create_user(db_session, role=UserRole.admin)

    def make(repeat="monthly", recipients=("a@example.com", "b@example.com"), **over):
        event = date(2026, 12, 25)
        r = Reminder(
            title="Mailing day",
            message="Hi <team>",
            recipients=list(recipients),
            start_date=event,
            repeat=repeat,
            lead_days=3,
            send_time=time(8, 0),
            active=True,
            created_by=admin.id,
            **over,
        )
        r.next_event_date = event
        r.next_send_at = send_at(event, 3, time(8, 0))  # Dec 22 13:00 UTC
        db_session.add(r)
        db_session.commit()
        return r

    return make


NOW = datetime(2026, 12, 22, 13, 2)  # two minutes after it was due


class TestDispatch:
    def test_sends_once_per_recipient_and_moves_to_next_month(self, db_session, due_reminder):
        r = due_reminder()
        with patch(SEND) as send:
            assert dispatch_due(db_session, now=NOW) == 2
        assert sorted(c.args[0] for c in send.delay.call_args_list) == [
            "a@example.com",
            "b@example.com",
        ]
        html = send.delay.call_args.args[2]
        assert "Hi &lt;team&gt;" in html and "Friday, December 25, 2026 (in 3 days)" in html
        db_session.refresh(r)
        assert r.next_event_date == date(2027, 1, 25) and r.last_sent_at == NOW
        assert db_session.query(ReminderDelivery).count() == 2

    def test_nothing_due_sends_nothing(self, db_session, due_reminder):
        due_reminder()
        with patch(SEND) as send:
            assert dispatch_due(db_session, now=NOW - timedelta(hours=1)) == 0
        send.delay.assert_not_called()

    def test_never_sends_the_same_occurrence_twice(self, db_session, due_reminder):
        r = due_reminder()
        with patch(SEND):
            dispatch_due(db_session, now=NOW)
        # Someone edits it back onto the occurrence that already went out.
        r.next_event_date = date(2026, 12, 25)
        r.next_send_at = NOW - timedelta(minutes=1)
        db_session.commit()
        with patch(SEND) as send:
            assert dispatch_due(db_session, now=NOW + timedelta(minutes=5)) == 0
        send.delay.assert_not_called()

    def test_one_off_switches_off_after_sending(self, db_session, due_reminder):
        r = due_reminder(repeat="none")
        with patch(SEND):
            dispatch_due(db_session, now=NOW)
        db_session.refresh(r)
        assert r.active is False and r.next_send_at is None

    def test_deactivated_users_get_nothing(self, db_session, due_reminder):
        gone = factories.create_user(db_session, role=UserRole.employee, is_active=False)
        due_reminder(recipients=["a@example.com", gone.email.upper()])
        with patch(SEND) as send:
            assert dispatch_due(db_session, now=NOW) == 1
        assert send.delay.call_args.args[0] == "a@example.com"

    def test_paused_reminders_are_skipped(self, db_session, due_reminder):
        r = due_reminder()
        r.active = False
        apply_schedule(r, after=NOW)
        db_session.commit()
        with patch(SEND) as send:
            assert dispatch_due(db_session, now=NOW) == 0
        send.delay.assert_not_called()


def test_checked_every_five_minutes_on_the_light_queue():
    entry = celery_app.conf.beat_schedule["send-due-reminders"]
    assert entry["task"] == "app.services.reminders.tasks.send_due_reminders"
    assert entry["schedule"].minute == set(range(0, 60, 5))
    assert celery_app.conf.task_routes["app.services.reminders.tasks.*"] == {"queue": "light"}


def test_retention_trims_the_send_log_but_keeps_every_reminder(db_session, due_reminder):
    one_off = due_reminder(repeat="none")
    monthly = due_reminder()
    with patch(SEND):
        dispatch_due(db_session, now=NOW)
    later = utcnow() + timedelta(days=400)
    with patch("app.services.maintenance.retention._now", return_value=later):
        assert purge_reminder_history(db_session, log_days=365) == 4
    ids = {r.id for r in db_session.query(Reminder).all()}
    assert {one_off.id, monthly.id} <= ids  # like users: only an admin deletes them
