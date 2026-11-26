"""Integration tests for the accounting tools' background-job routes."""

import json
from unittest.mock import patch

import pytest

from app.models.accounting_job import AccountingJob
from app.models.audit_event import AuditEvent
from app.models.letter_job import JobStatus
from app.models.user import UserRole
from tests import factories

pytestmark = pytest.mark.integration

PDF = ("Bal Sheet.pdf", b"%PDF-1.4 combined", "application/pdf")


def _start(client, tool="fdic", file=PDF):
    with (
        patch("app.routers.accounting.storage_service") as storage,
        patch("app.routers.accounting.run_accounting_job") as task,
    ):
        res = client.post("/api/accounting/jobs", data={"tool": tool}, files={"report": file})
    return res, storage, task


def test_requires_auth(client):
    res, _, task = _start(client)
    assert res.status_code == 401
    task.delay.assert_not_called()


def test_start_job_stores_pdf_and_queues_task(client, as_user, db_session):
    user = as_user(role=UserRole.employee)
    res, storage, task = _start(client)
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "pending" and body["filename"] == "Bal Sheet.pdf"

    job = db_session.query(AccountingJob).filter_by(id=body["id"]).one()
    assert job.created_by == user.id and job.tool == "fdic"
    storage.upload_file.assert_called_once()
    assert storage.upload_file.call_args.args[1] == job.input_path
    task.delay.assert_called_once_with(body["id"])
    assert db_session.query(AuditEvent).filter_by(action="accounting.fdic.job").count() == 1


@pytest.mark.parametrize(
    "tool, file, status",
    [
        ("unknown", PDF, 422),
        ("fdic", ("x.pdf", b"not a pdf", "application/pdf"), 422),
    ],
)
def test_start_job_rejects_bad_input(client, as_user, tool, file, status):
    as_user(role=UserRole.employee)
    res, _, task = _start(client, tool, file)
    assert res.status_code == status
    task.delay.assert_not_called()


def _start_receivables(client, files):
    with (
        patch("app.routers.accounting.storage_service") as storage,
        patch("app.routers.accounting.run_accounting_job") as task,
    ):
        res = client.post("/api/accounting/jobs", data={"tool": "receivables"}, files=files)
    return res, storage, task


def test_receivables_job_stores_each_file(client, as_user, db_session):
    as_user(role=UserRole.employee)
    res, storage, task = _start_receivables(
        client,
        {
            "balance_sheet": ("Bal Sheet.pdf", b"%PDF-1.4 bs", "application/pdf"),
            "ar": ("AR.pdf", b"%PDF-1.4 ar", "application/pdf"),
            "prepaid": ("Prepaid.pdf", b"%PDF-1.4 pp", "application/pdf"),
        },
    )
    assert res.status_code == 202
    body = res.json()
    assert body["filename"] == "Bal Sheet.pdf + AR.pdf + Prepaid.pdf"
    job = db_session.query(AccountingJob).filter_by(id=body["id"]).one()
    keys = json.loads(job.input_path)
    assert set(keys) == {"balance_sheet", "ar", "prepaid"}
    uploaded = {c.args[1]: c.args[0] for c in storage.upload_file.call_args_list}
    assert uploaded[keys["ar"]] == b"%PDF-1.4 ar"
    task.delay.assert_called_once_with(body["id"])


@pytest.mark.parametrize(
    "roles",
    [("ar", "prepaid"), ("balance_sheet",)],
    ids=["no balance sheet", "nothing to compare"],
)
def test_receivables_job_needs_balance_sheet_and_a_report(client, as_user, roles):
    as_user(role=UserRole.employee)
    res, storage, task = _start_receivables(
        client, {r: (f"{r}.pdf", b"%PDF-1.4", "application/pdf") for r in roles}
    )
    assert res.status_code == 422
    storage.upload_file.assert_not_called()
    task.delay.assert_not_called()


def test_progress_and_incremental_results(client, as_user, db_session):
    user = as_user(role=UserRole.employee)
    results = [
        {
            "association": n,
            "first_page": i,
            "last_page": i,
            "flagged": i == 2,
            "result": {"problem": "x"},
        }
        for i, n in enumerate(["Amber Glen", "Bay Club", "Carlyle"], start=1)
    ]
    job = AccountingJob(
        tool="fdic",
        filename="Bal Sheet.pdf",
        status=JobStatus.processing,
        total_pages=187,
        pages_done=3,
        current_association="Carlyle",
        results=results,
        created_by=user.id,
    )
    db_session.add(job)
    db_session.commit()

    res = client.get(f"/api/accounting/jobs/{job.id}", params={"since": 1})
    assert res.status_code == 200
    body = res.json()
    assert body["associations_done"] == 3 and body["flagged_count"] == 1
    assert body["current_association"] == "Carlyle"
    assert [r["association"] for r in body["results"]] == ["Bay Club", "Carlyle"]

    listed = client.get("/api/accounting/jobs", params={"tool": "fdic"}).json()
    assert [j["id"] for j in listed] == [str(job.id)]


def test_other_users_job_is_not_visible(client, as_user, db_session):
    other = factories.create_user(db_session, role=UserRole.employee)
    job = AccountingJob(
        tool="fdic", filename="x.pdf", status=JobStatus.complete, results=[], created_by=other.id
    )
    db_session.add(job)
    db_session.commit()
    as_user(role=UserRole.employee)
    assert client.get(f"/api/accounting/jobs/{job.id}").status_code == 404
    assert client.get("/api/accounting/jobs/not-a-uuid").status_code == 404


def test_pending_run_shows_its_place_in_the_queue(client, as_user, db_session):
    from datetime import UTC, datetime, timedelta

    from app.models.budget_job import BudgetJob

    user = as_user(role=UserRole.employee)
    other = factories.create_user(db_session, role=UserRole.employee)
    now = datetime.now(UTC).replace(tzinfo=None)

    def run(status, minutes_ago, owner=other):
        job = AccountingJob(
            tool="cd_maturity",
            filename="x.pdf",
            status=status,
            results=[],
            created_by=owner.id,
            created_at=now - timedelta(minutes=minutes_ago),
        )
        db_session.add(job)
        return job

    run(JobStatus.processing, 30)  # running now
    run(JobStatus.pending, 10)  # ahead
    run(JobStatus.pending, 300)  # lost hours ago: not counted
    db_session.add(
        BudgetJob(
            association_name="Bay Club",
            budget_year=2027,
            financial_report_path="k",
            financial_report_filename="f.pdf",
            prior_budget_path="k",
            prior_budget_filename="p.xlsx",
            status=JobStatus.pending,
            created_by=other.id,
            created_at=now - timedelta(minutes=5),
        )
    )  # ahead: budgets share the long-jobs worker
    mine = run(JobStatus.pending, 1, owner=user)
    run(JobStatus.pending, 0)  # behind
    done = run(JobStatus.complete, 20, owner=user)
    db_session.commit()

    body = client.get(f"/api/accounting/jobs/{mine.id}").json()
    assert (body["queue_ahead"], body["queue_running"]) == (2, 1)
    listed = {j["id"]: j for j in client.get("/api/accounting/jobs").json()}
    assert listed[str(mine.id)]["queue_ahead"] == 2
    assert listed[str(done.id)]["queue_ahead"] is None
