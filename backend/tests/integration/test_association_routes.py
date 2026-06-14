"""Integration tests for association + manager-assignment routes."""

import pytest

from app.models.user import UserRole
from tests import factories

pytestmark = pytest.mark.integration


class TestCreateAndList:
    def test_admin_can_create(self, client, as_user):
        as_user(role=UserRole.admin)
        resp = client.post(
            "/api/associations",
            json={
                "legal_name": "Oak Grove HOA, Inc.",
                "filter_name": "Oak Grove",
                "location_name": "Sarasota",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["filter_name"] == "Oak Grove"

    def test_manager_sees_only_assigned_associations(self, client, db_session, as_user):
        manager = as_user(role=UserRole.manager)
        assigned = factories.create_association(db_session, filter_name="Assigned")
        factories.create_association(db_session, filter_name="Other")
        factories.assign_manager(db_session, manager, assigned)

        resp = client.get("/api/associations")
        assert resp.status_code == 200
        names = {a["filter_name"] for a in resp.json()}
        assert names == {"Assigned"}


class TestAssignManager:
    def test_assign_then_duplicate_conflicts(self, client, db_session, as_user):
        as_user(role=UserRole.admin)
        assoc = factories.create_association(db_session)
        mgr = factories.create_user(db_session, role=UserRole.manager)

        first = client.post(f"/api/associations/{assoc.id}/managers", json={"user_id": str(mgr.id)})
        assert first.status_code == 201

        dupe = client.post(f"/api/associations/{assoc.id}/managers", json={"user_id": str(mgr.id)})
        assert dupe.status_code == 409

    def test_cannot_assign_employee_role(self, client, db_session, as_user):
        as_user(role=UserRole.admin)
        assoc = factories.create_association(db_session)
        employee = factories.create_user(db_session, role=UserRole.employee)
        resp = client.post(
            f"/api/associations/{assoc.id}/managers", json={"user_id": str(employee.id)}
        )
        assert resp.status_code == 400

    def test_cannot_assign_inactive_user(self, client, db_session, as_user):
        as_user(role=UserRole.admin)
        assoc = factories.create_association(db_session)
        inactive = factories.create_user(db_session, role=UserRole.manager, is_active=False)
        resp = client.post(
            f"/api/associations/{assoc.id}/managers", json={"user_id": str(inactive.id)}
        )
        assert resp.status_code == 400

    def test_remove_manager(self, client, db_session, as_user):
        as_user(role=UserRole.admin)
        assoc = factories.create_association(db_session)
        mgr = factories.create_user(db_session, role=UserRole.manager)
        factories.assign_manager(db_session, mgr, assoc)

        resp = client.delete(f"/api/associations/{assoc.id}/managers/{mgr.id}")
        assert resp.status_code == 204
