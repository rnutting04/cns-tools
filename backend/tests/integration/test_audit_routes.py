"""Integration tests for the audit log query/export routes (super_admin only)."""

import pytest

from app.models.user import UserRole
from app.services.audit import log_event

pytestmark = pytest.mark.integration


def _seed_events(db_session, actor):
    log_event(db_session, actor=actor, action="user.created", target_type="user", target_id="1")
    log_event(db_session, actor=actor, action="user.created", target_type="user", target_id="2")
    log_event(db_session, actor=actor, action="auth.login", target_type=None, target_id=None)
    db_session.flush()


class TestListAuditEvents:
    def test_requires_super_admin(self, client, as_user):
        as_user(role=UserRole.admin)
        assert client.get("/api/audit").status_code == 403

    def test_lists_with_pagination_metadata(self, client, db_session, as_user):
        admin = as_user(role=UserRole.super_admin)
        _seed_events(db_session, admin)
        resp = client.get("/api/audit")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert body["page"] == 1
        assert len(body["items"]) == 3

    def test_filter_by_action(self, client, db_session, as_user):
        admin = as_user(role=UserRole.super_admin)
        _seed_events(db_session, admin)
        resp = client.get("/api/audit", params={"actions": ["auth.login"]})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["action"] == "auth.login"


class TestDistinctActions:
    def test_returns_sorted_distinct_actions(self, client, db_session, as_user):
        admin = as_user(role=UserRole.super_admin)
        _seed_events(db_session, admin)
        resp = client.get("/api/audit/actions")
        assert resp.status_code == 200
        assert resp.json() == ["auth.login", "user.created"]


class TestExportCsv:
    def test_exports_csv(self, client, db_session, as_user):
        admin = as_user(role=UserRole.super_admin)
        _seed_events(db_session, admin)
        resp = client.get("/api/audit/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        text = resp.content.decode()
        assert "timestamp,actor_email,action" in text
        assert "user.created" in text
