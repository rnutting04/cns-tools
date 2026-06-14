"""Integration tests for the auth routes."""

import pytest

from app.models.audit_event import AuditEvent
from tests import factories

pytestmark = pytest.mark.integration


class TestLogin:
    def test_valid_credentials_returns_token(self, client, db_session):
        user = factories.create_user(db_session, password=factories.DEFAULT_PASSWORD)
        resp = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": factories.DEFAULT_PASSWORD},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]

    def test_wrong_password_returns_401_and_audits_failure(self, client, db_session):
        user = factories.create_user(db_session, password=factories.DEFAULT_PASSWORD)
        resp = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": "wrong-password!!"},
        )
        assert resp.status_code == 401
        failed = db_session.query(AuditEvent).filter_by(action="auth.login_failed").count()
        assert failed == 1

    def test_unknown_email_returns_401(self, client, db_session):
        resp = client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "whatever12345"},
        )
        assert resp.status_code == 401

    def test_inactive_account_returns_403(self, client, db_session):
        user = factories.create_user(
            db_session, password=factories.DEFAULT_PASSWORD, is_active=False
        )
        resp = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": factories.DEFAULT_PASSWORD},
        )
        assert resp.status_code == 403


class TestMe:
    def test_returns_current_user(self, client, as_user):
        as_user(email="me@example.com")
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
        assert resp.json()["email"] == "me@example.com"
