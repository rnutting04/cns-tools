"""Integration tests for the financial packet check route."""

from pathlib import Path

import pytest

from app.models.audit_event import AuditEvent
from app.models.user import UserRole

pytestmark = pytest.mark.integration

PACKET = Path(__file__).resolve().parents[2] / "test_data" / "MOR September 2026.pdf"


def test_requires_auth(client):
    res = client.post(
        "/api/financials/check",
        files={"financial_report": ("x.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert res.status_code == 401


def test_rejects_non_pdf(client, as_user):
    as_user(role=UserRole.employee)
    res = client.post(
        "/api/financials/check", files={"financial_report": ("x.pdf", b"hello", "application/pdf")}
    )
    assert res.status_code == 422


def test_rejects_corrupt_pdf(client, as_user):
    as_user(role=UserRole.employee)
    res = client.post(
        "/api/financials/check",
        files={"financial_report": ("x.pdf", b"%PDF-1.4 garbage", "application/pdf")},
    )
    assert res.status_code == 422


@pytest.mark.skipif(not PACKET.exists(), reason="sample packet not present")
def test_real_packet_report_and_audit(client, as_user, db_session):
    user = as_user(role=UserRole.employee)
    res = client.post(
        "/api/financials/check",
        files={"financial_report": (PACKET.name, PACKET.read_bytes(), "application/pdf")},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["summary"]["fail"] == 0
    assert body["summary"]["pass"] == 11
    ar = next(c for c in body["checks"] if c["id"] == "ar")
    assert ar["left"]["amount"] == 30508.00
    assert ar["right"]["image"].startswith("data:image/png;base64,")

    event = db_session.query(AuditEvent).filter_by(action="financials.check.run").one()
    assert event.actor_user_id == user.id
    assert event.event_metadata["filename"] == PACKET.name
