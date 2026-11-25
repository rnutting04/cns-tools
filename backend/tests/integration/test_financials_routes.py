"""Integration tests for the financial packet check route."""

import json
from pathlib import Path

import pytest

from app.models.audit_event import AuditEvent
from app.models.user import UserRole

pytestmark = pytest.mark.integration

PACKET = Path(__file__).resolve().parents[2] / "test_data" / "context" / "CAR October 2026.pdf"


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
    assert body["summary"]["pass"] == 16
    ar = next(c for c in body["checks"] if c["id"] == "ar")
    assert ar["left"]["amount"] == 13039.44
    assert ar["right"]["image"].startswith("data:image/png;base64,")

    event = db_session.query(AuditEvent).filter_by(action="financials.check.run").one()
    assert event.actor_user_id == user.id
    assert event.event_metadata["filename"] == PACKET.name


@pytest.mark.skipif(not PACKET.exists(), reason="sample packet not present")
def test_report_without_images_then_evidence(client, as_user):
    as_user(role=UserRole.employee)
    pdf = (PACKET.name, PACKET.read_bytes(), "application/pdf")
    res = client.post(
        "/api/financials/check", files={"financial_report": pdf}, data={"images": "false"}
    )
    assert res.status_code == 200
    ar = next(c for c in res.json()["checks"] if c["id"] == "ar")
    assert ar["right"]["image"] is None
    region = {"page": ar["right"]["page"], "bbox": ar["right"]["bbox"]}

    res = client.post(
        "/api/financials/evidence",
        files={"financial_report": pdf},
        data={"regions": json.dumps([region, {"page": 999, "bbox": [0, 0, 1, 1]}])},
    )
    assert res.status_code == 200
    first, missing_page = res.json()["images"]
    assert first.startswith("data:image/png;base64,")
    assert missing_page is None


def test_evidence_rejects_bad_regions(client, as_user):
    as_user(role=UserRole.employee)
    res = client.post(
        "/api/financials/evidence",
        files={"financial_report": ("x.pdf", b"%PDF-1.4", "application/pdf")},
        data={"regions": '[{"page": 0, "bbox": [1, 2]}]'},
    )
    assert res.status_code == 422
