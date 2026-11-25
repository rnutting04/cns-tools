"""Integration tests for the Excel tools routes."""

import io

import openpyxl
import pytest

from app.models.audit_event import AuditEvent
from app.models.user import UserRole

pytestmark = pytest.mark.integration

URL = "/api/excel/reserve-schedule/check"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _workbook_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "CAR"
    ws.append(
        [
            "Code",
            "Description",
            "Start of Year",
            "Receipts",
            "Adjustment",
            "Percentage",
            "Expenses",
            "Balance",
        ]
    )
    ws.append([7061, "Pool Resurface", 27282.79, 2231.09, 0, 0.04, 40320, -10806.12])
    ws.append([None, "TOTAL", 0, 0, 0, 1, 0, -10806.12])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_requires_auth(client):
    res = client.post(URL, files={"workbook": ("x.xlsx", _workbook_bytes(), XLSX)})
    assert res.status_code == 401


def test_rejects_non_xlsx(client, as_user):
    as_user(role=UserRole.employee)
    res = client.post(URL, files={"workbook": ("x.xlsx", b"not a workbook", XLSX)})
    assert res.status_code == 422


def test_flags_negative_line_and_audits(client, as_user, db_session):
    user = as_user(role=UserRole.employee)
    res = client.post(URL, files={"workbook": ("mass.xlsx", _workbook_bytes(), XLSX)})
    assert res.status_code == 200
    body = res.json()
    assert body["sheet_count"] == 1
    [issue] = body["issues"]
    assert issue["sheet"] == "CAR" and issue["cell"] == "H2"
    assert issue["balance"] == -10806.12

    event = db_session.query(AuditEvent).filter_by(action="excel.reserve_schedule.check").one()
    assert event.actor_user_id == user.id
    assert event.event_metadata["issues"] == 1
