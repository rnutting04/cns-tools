"""Integration tests for user management + password change routes."""

import pytest

from app.models.user import User, UserRole
from tests import factories

pytestmark = pytest.mark.integration


def _new_user_payload(**overrides):
    payload = {
        "fname": "New",
        "lname": "Person",
        "email": "new.person@example.com",
        "title": "Manager",
        "role": "manager",
        "password": "InitialPassw0rd!",
    }
    payload.update(overrides)
    return payload


class TestCreateUser:
    def test_admin_can_create_user(self, client, as_user):
        as_user(role=UserRole.admin)
        resp = client.post("/api/users", json=_new_user_payload())
        assert resp.status_code == 201
        assert resp.json()["email"] == "new.person@example.com"

    def test_duplicate_email_returns_409(self, client, db_session, as_user):
        as_user(role=UserRole.admin)
        factories.create_user(db_session, email="taken@example.com")
        resp = client.post("/api/users", json=_new_user_payload(email="taken@example.com"))
        assert resp.status_code == 409

    def test_employee_cannot_create_user(self, client, as_user):
        as_user(role=UserRole.employee)
        resp = client.post("/api/users", json=_new_user_payload())
        assert resp.status_code == 403

    def test_invalid_email_is_rejected(self, client, as_user):
        as_user(role=UserRole.admin)
        resp = client.post("/api/users", json=_new_user_payload(email="not-an-email"))
        assert resp.status_code == 422


class TestRoleChange:
    def test_super_admin_can_change_role(self, client, db_session, as_user):
        as_user(role=UserRole.super_admin)
        target = factories.create_user(db_session, role=UserRole.employee)
        resp = client.patch(f"/api/users/{target.id}/role", json={"role": "admin"})
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_admin_cannot_change_role(self, client, db_session, as_user):
        as_user(role=UserRole.admin)
        target = factories.create_user(db_session, role=UserRole.employee)
        resp = client.patch(f"/api/users/{target.id}/role", json={"role": "admin"})
        assert resp.status_code == 403


class TestChangePassword:
    URL = "/api/users/me/change-password"

    def test_successful_change_clears_required_flag(self, client, db_session, as_user):
        user = as_user(password=factories.DEFAULT_PASSWORD, password_change_required=True)
        resp = client.post(
            self.URL,
            json={
                "current_password": factories.DEFAULT_PASSWORD,
                "new_password": "BrandNewSecret9!",
            },
        )
        assert resp.status_code == 204
        db_session.refresh(user)
        assert user.password_change_required is False

    def test_wrong_current_password_returns_400(self, client, as_user):
        as_user(password=factories.DEFAULT_PASSWORD)
        resp = client.post(
            self.URL,
            json={"current_password": "not-it-123456", "new_password": "BrandNewSecret9!"},
        )
        assert resp.status_code == 400

    def test_too_short_new_password_returns_400(self, client, as_user):
        as_user(password=factories.DEFAULT_PASSWORD)
        resp = client.post(
            self.URL,
            json={"current_password": factories.DEFAULT_PASSWORD, "new_password": "short"},
        )
        assert resp.status_code == 400

    def test_reusing_current_password_returns_400(self, client, as_user):
        as_user(password=factories.DEFAULT_PASSWORD)
        resp = client.post(
            self.URL,
            json={
                "current_password": factories.DEFAULT_PASSWORD,
                "new_password": factories.DEFAULT_PASSWORD,
            },
        )
        assert resp.status_code == 400


class TestDeactivateUser:
    def test_super_admin_soft_deletes(self, client, db_session, as_user):
        as_user(role=UserRole.super_admin)
        target = factories.create_user(db_session)
        resp = client.delete(f"/api/users/{target.id}")
        assert resp.status_code == 204
        refreshed = db_session.query(User).filter_by(id=target.id).one()
        assert refreshed.is_active is False
