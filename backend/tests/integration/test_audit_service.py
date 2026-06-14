"""Tests for the audit logging service and retention purge (use the test DB)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models.audit_event import AuditEvent
from app.services.audit import log_event
from app.services.audit_retention import purge_old_events
from tests import factories

pytestmark = pytest.mark.integration


class TestLogEvent:
    def test_records_event_with_actor(self, db_session):
        actor = factories.create_user(db_session)
        log_event(
            db_session,
            actor=actor,
            action="user.updated",
            target_type="user",
            target_id=actor.id,
            metadata={"field": "title"},
        )
        db_session.flush()

        event = db_session.query(AuditEvent).filter_by(action="user.updated").one()
        assert event.actor_user_id == actor.id
        assert event.target_type == "user"
        assert event.target_id == str(actor.id)  # coerced to string
        assert event.event_metadata == {"field": "title"}

    def test_system_event_has_null_actor(self, db_session):
        log_event(db_session, actor=None, action="auth.login_failed")
        db_session.flush()

        event = db_session.query(AuditEvent).filter_by(action="auth.login_failed").one()
        assert event.actor_user_id is None
        assert event.event_metadata == {}

    def test_does_not_commit(self, db_session):
        # log_event must leave committing to the caller; the row is pending only.
        log_event(db_session, actor=None, action="test.pending")
        assert any(
            isinstance(obj, AuditEvent) and obj.action == "test.pending" for obj in db_session.new
        )


class TestPurgeOldEvents:
    def _event(self, db_session, *, age_days: int) -> AuditEvent:
        created = datetime.now(tz=UTC) - timedelta(days=age_days)
        event = AuditEvent(action="test.event", event_metadata={}, created_at=created)
        db_session.add(event)
        return event

    def test_deletes_only_events_older_than_retention(self, db_session):
        self._event(db_session, age_days=400)  # should be purged
        self._event(db_session, age_days=400)  # should be purged
        self._event(db_session, age_days=10)  # should survive
        db_session.flush()

        deleted = purge_old_events(db_session, retention_days=365)

        assert deleted == 2
        remaining = db_session.query(AuditEvent).filter_by(action="test.event").count()
        assert remaining == 1

    def test_nothing_to_purge_returns_zero(self, db_session):
        self._event(db_session, age_days=5)
        db_session.flush()
        assert purge_old_events(db_session, retention_days=365) == 0
