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


@pytest.fixture
def sent_mail(monkeypatch):
    """Capture queued mail instead of handing it to the broker.

    ``welcome_email`` and friends resolve ``send_email_task`` as a module global,
    so replacing the attribute intercepts the ``.delay`` call without needing a
    running Redis or eager Celery.
    """
    captured: list[dict] = []

    class _Capture:
        def delay(self, to, subject, html):
            captured.append({"to": to, "subject": subject, "html": html})

    monkeypatch.setattr("app.services.email.tasks.send_email_task", _Capture())
    return captured


class TestSendWelcome:
    """POST /users/{id}/send-welcome — hand account access to an existing user.

    Mechanically this is a password reset, but the distinction that matters is
    which email goes out: a user who has never signed in should be welcomed, not
    told their password was reset.
    """

    def test_admin_sends_welcome_and_rotates_password(self, client, db_session, as_user, sent_mail):
        as_user(role=UserRole.admin)
        target = factories.create_user(db_session, email="existing@example.com")
        old_hash = target.password_hash

        resp = client.post(f"/api/users/{target.id}/send-welcome")
        assert resp.status_code == 204

        refreshed = db_session.query(User).filter_by(id=target.id).one()
        assert refreshed.password_hash != old_hash
        assert refreshed.password_change_required is True

        assert len(sent_mail) == 1
        assert sent_mail[0]["to"] == "existing@example.com"
        assert "Welcome" in sent_mail[0]["subject"]
        assert "password has been reset" not in sent_mail[0]["subject"]

    def test_welcome_email_carries_the_new_password(self, client, db_session, as_user, sent_mail):
        """The emailed password must be the one that now works for login."""
        from app.utils.auth import verify_password

        as_user(role=UserRole.admin)
        target = factories.create_user(db_session)
        client.post(f"/api/users/{target.id}/send-welcome")

        html = sent_mail[0]["html"]
        refreshed = db_session.query(User).filter_by(id=target.id).one()
        # The password appears in the credentials panel; recover it from the
        # monospaced span rather than trusting a substring search.
        import re

        candidates = re.findall(r">([A-Za-z0-9_-]{12,})<", html)
        assert any(
            verify_password(c, refreshed.password_hash) for c in candidates
        ), "emailed password does not match the stored hash"

    def test_deactivated_user_is_rejected(self, client, db_session, as_user, sent_mail):
        as_user(role=UserRole.admin)
        target = factories.create_user(db_session, is_active=False)
        resp = client.post(f"/api/users/{target.id}/send-welcome")
        assert resp.status_code == 400
        assert sent_mail == []

    def test_unknown_user_returns_404(self, client, as_user, sent_mail):
        from uuid import uuid4

        as_user(role=UserRole.admin)
        resp = client.post(f"/api/users/{uuid4()}/send-welcome")
        assert resp.status_code == 404
        assert sent_mail == []

    def test_employee_cannot_send_welcome(self, client, db_session, as_user, sent_mail):
        target = factories.create_user(db_session)
        as_user(role=UserRole.employee)
        resp = client.post(f"/api/users/{target.id}/send-welcome")
        assert resp.status_code == 403
        assert sent_mail == []

    def test_audit_event_distinguishes_welcome_from_reset(self, client, db_session, as_user):
        from app.models.audit_event import AuditEvent

        as_user(role=UserRole.admin)
        target = factories.create_user(db_session)
        client.post(f"/api/users/{target.id}/send-welcome")

        actions = [e.action for e in db_session.query(AuditEvent).all()]
        assert "user.welcome_sent" in actions
        assert "user.password_reset" not in actions


class TestSendWelcomeBulk:
    """POST /users/send-welcome — the rollout path."""

    def test_sends_to_every_selected_active_user(self, client, db_session, as_user, sent_mail):
        as_user(role=UserRole.admin)
        targets = [factories.create_user(db_session) for _ in range(3)]
        resp = client.post(
            "/api/users/send-welcome",
            json={"user_ids": [str(u.id) for u in targets]},
        )
        assert resp.status_code == 200
        assert resp.json() == {"sent": 3, "skipped": []}
        assert sorted(m["to"] for m in sent_mail) == sorted(u.email for u in targets)

    def test_each_recipient_gets_a_distinct_password(self, client, db_session, as_user, sent_mail):
        """A shared temporary password across a batch would be a real hazard."""
        as_user(role=UserRole.admin)
        targets = [factories.create_user(db_session) for _ in range(3)]
        client.post(
            "/api/users/send-welcome",
            json={"user_ids": [str(u.id) for u in targets]},
        )
        hashes = {db_session.query(User).filter_by(id=u.id).one().password_hash for u in targets}
        assert len(hashes) == 3

    def test_deactivated_user_is_skipped_without_failing_the_batch(
        self, client, db_session, as_user, sent_mail
    ):
        as_user(role=UserRole.admin)
        active = factories.create_user(db_session, email="active@example.com")
        inactive = factories.create_user(db_session, email="inactive@example.com", is_active=False)
        inactive_hash = inactive.password_hash

        resp = client.post(
            "/api/users/send-welcome",
            json={"user_ids": [str(active.id), str(inactive.id)]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["sent"] == 1
        assert body["skipped"] == ["inactive@example.com (deactivated)"]
        assert [m["to"] for m in sent_mail] == ["active@example.com"]
        # A skipped user's password must be left alone.
        refreshed = db_session.query(User).filter_by(id=inactive.id).one()
        assert refreshed.password_hash == inactive_hash

    def test_unknown_id_is_skipped(self, client, db_session, as_user, sent_mail):
        from uuid import uuid4

        as_user(role=UserRole.admin)
        active = factories.create_user(db_session)
        missing = uuid4()
        resp = client.post(
            "/api/users/send-welcome",
            json={"user_ids": [str(active.id), str(missing)]},
        )
        assert resp.status_code == 200
        assert resp.json()["sent"] == 1
        assert resp.json()["skipped"] == [f"{missing} (not found)"]

    def test_empty_selection_is_rejected(self, client, as_user, sent_mail):
        as_user(role=UserRole.admin)
        resp = client.post("/api/users/send-welcome", json={"user_ids": []})
        assert resp.status_code == 422
        assert sent_mail == []

    def test_employee_cannot_bulk_send(self, client, db_session, as_user, sent_mail):
        target = factories.create_user(db_session)
        as_user(role=UserRole.employee)
        resp = client.post("/api/users/send-welcome", json={"user_ids": [str(target.id)]})
        assert resp.status_code == 403
        assert sent_mail == []


class TestDeleteUserWithLayoutProfile:
    """A confirmed layout profile must not pin a user account in place.

    budget_layout_profiles.confirmed_by is ON DELETE SET NULL (migration
    b5e8d2c47f16). Before that it was RESTRICT, so deleting anyone who had ever
    confirmed a workbook layout failed, and the router reported it as "User has
    associated jobs or data" — pointing at the wrong thing entirely.
    """

    def test_permanent_delete_nulls_the_confirmer_and_keeps_the_profile(
        self, client, db_session, as_user
    ):
        from app.models.budget_layout_profile import BudgetLayoutProfile

        as_user(role=UserRole.super_admin)
        target = factories.create_user(db_session, is_active=False)
        profile = factories.create_layout_profile(db_session, confirmed_by=target)
        profile_id = profile.id

        resp = client.delete(f"/api/users/{target.id}/permanent")
        assert resp.status_code == 204, resp.json()

        db_session.expire_all()
        survivor = db_session.query(BudgetLayoutProfile).filter_by(id=profile_id).one()
        # The sign-off happened, so it stays confirmed; only the who is forgotten.
        assert survivor.confirmed_by is None
        assert survivor.confirmed is True
        assert db_session.query(User).filter_by(id=target.id).first() is None

    def test_deactivate_leaves_the_confirmer_intact(self, client, db_session, as_user):
        """Soft-delete is the normal path and must not touch the attribution."""
        from app.models.budget_layout_profile import BudgetLayoutProfile

        as_user(role=UserRole.super_admin)
        target = factories.create_user(db_session)
        profile = factories.create_layout_profile(db_session, confirmed_by=target)
        profile_id = profile.id

        assert client.delete(f"/api/users/{target.id}").status_code == 204

        db_session.expire_all()
        survivor = db_session.query(BudgetLayoutProfile).filter_by(id=profile_id).one()
        assert survivor.confirmed_by == target.id
