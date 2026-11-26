"""Retention: uploads go once they're not needed, jobs and their outputs go
after the retention period, lost accounting runs give up their PDFs, and the
nightly task runs it all."""

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.celery_app import celery_app
from app.models.accounting_job import AccountingJob
from app.models.budget_job import BudgetJob
from app.models.letter_job import JobStatus, LetterJob
from app.models.user import UserRole
from app.services.maintenance.retention import (
    expire_budget_uploads,
    fail_stuck_jobs,
    purge_jobs,
)
from tests import factories

pytestmark = pytest.mark.integration

STORAGE = "app.services.maintenance.retention.storage_service"
NOW = datetime.now(UTC).replace(tzinfo=None)


@pytest.fixture
def user(db_session):
    return factories.create_user(db_session, role=UserRole.admin)


@pytest.fixture
def make_run(db_session, user):
    def make(status, age, input_path=None):
        job = AccountingJob(
            tool="cd_maturity",
            filename="x.pdf",
            status=status,
            results=[{"association": "Bay Club", "result": {"shots": [{"image": "data:..."}]}}],
            input_path=input_path,
            created_by=user.id,
            created_at=NOW - age,
        )
        db_session.add(job)
        db_session.commit()
        return job

    return make


@pytest.fixture
def make_budget(db_session, user):
    def make(status, age, step=None, output=None, uploads=True):
        job = BudgetJob(
            association_name="Bay Club",
            budget_year=2027,
            financial_report_path="budget/b/report.pdf" if uploads else "",
            financial_report_filename="report.pdf",
            prior_budget_path="budget/b/prior.xlsx" if uploads else "",
            prior_budget_filename="prior.xlsx",
            output_path=output,
            status=status,
            current_step=step,
            created_by=user.id,
            created_at=NOW - age,
        )
        db_session.add(job)
        db_session.commit()
        return job

    return make


@pytest.fixture
def make_letter(db_session, user):
    assoc = factories.create_association(db_session)
    template = factories.create_template(db_session)

    def make(status, age, output="letters/l/out.docx"):
        job = LetterJob(
            template_id=template.id,
            association_id=assoc.id,
            created_by=user.id,
            field_values={"owner": "A. Owner"},
            output_path=output,
            status=status,
            created_at=NOW - age,
        )
        db_session.add(job)
        db_session.commit()
        return job

    return make


def _deleted(storage):
    return {c.args[0] for c in storage.delete_file.call_args_list}


def _exists(db_session, model, job):
    return db_session.query(model).filter(model.id == job.id).first() is not None


class TestBudgetUploads:
    def test_finished_budgets_lose_uploads_failed_ones_keep_them_14_days(
        self, db_session, make_budget
    ):
        done = make_budget(JobStatus.complete, timedelta(days=1), output="budget/b/out.xlsx")
        failed_recent = make_budget(JobStatus.failed, timedelta(days=13))
        failed_old = make_budget(JobStatus.failed, timedelta(days=15))
        parked_old = make_budget(
            JobStatus.processing, timedelta(days=20), step="awaiting_layout_review"
        )
        running = make_budget(JobStatus.processing, timedelta(days=30))  # a retry, in flight
        with patch(STORAGE) as storage:
            assert expire_budget_uploads(db_session, upload_days=14) == 3
        for job in (done, failed_old, parked_old):
            db_session.refresh(job)
            assert job.financial_report_path == "" and job.prior_budget_path == ""
        for job in (failed_recent, running):
            db_session.refresh(job)
            assert job.financial_report_path
        assert "budget/b/out.xlsx" not in _deleted(storage)  # the output stays

    def test_retry_after_uploads_expired_says_so(self, client, as_user, db_session):
        user = as_user(role=UserRole.admin)
        job = BudgetJob(
            association_name="Bay Club",
            budget_year=2027,
            financial_report_path="",
            financial_report_filename="report.pdf",
            prior_budget_path="",
            prior_budget_filename="prior.xlsx",
            status=JobStatus.failed,
            created_by=user.id,
        )
        db_session.add(job)
        db_session.commit()
        with patch("app.routers.budget.generate_budget_task") as task:
            res = client.post(f"/api/budget/jobs/{job.id}/retry")
        assert res.status_code == 410
        assert "Start a new budget" in res.json()["detail"]
        task.delay.assert_not_called()


class TestPurge:
    def test_everything_older_than_the_period_goes_with_its_files(
        self, db_session, make_run, make_budget, make_letter
    ):
        old_letter = make_letter(JobStatus.complete, timedelta(days=91))
        new_letter = make_letter(JobStatus.complete, timedelta(days=89))
        old_budget = make_budget(JobStatus.complete, timedelta(days=95), output="budget/b/out.xlsx")
        old_parked = make_budget(
            JobStatus.processing, timedelta(days=95), step="awaiting_layout_review"
        )
        old_run = make_run(JobStatus.failed, timedelta(days=200), json.dumps({"ar": "acc/ar.pdf"}))
        new_run = make_run(JobStatus.complete, timedelta(days=10))
        with patch(STORAGE) as storage:
            out = purge_jobs(db_session, retention_days=90)
        assert out == {"letters": 1, "budgets": 2, "accounting_runs": 1}
        assert {"letters/l/out.docx", "budget/b/out.xlsx", "acc/ar.pdf"} <= _deleted(storage)
        assert {"budget/b/report.pdf", "budget/b/prior.xlsx"} <= _deleted(storage)
        assert not _exists(db_session, LetterJob, old_letter)
        assert not _exists(db_session, BudgetJob, old_budget)
        assert not _exists(db_session, BudgetJob, old_parked)
        assert not _exists(db_session, AccountingJob, old_run)
        assert _exists(db_session, LetterJob, new_letter)
        assert _exists(db_session, AccountingJob, new_run)

    def test_job_is_kept_if_its_files_cant_be_deleted(self, db_session, make_letter):
        job = make_letter(JobStatus.complete, timedelta(days=100))
        with patch(STORAGE) as storage:
            storage.delete_file.side_effect = RuntimeError("storage down")
            assert purge_jobs(db_session, retention_days=90)["letters"] == 0
        assert _exists(db_session, LetterJob, job)  # tried again tomorrow

    def test_running_jobs_are_never_purged(self, db_session, make_run, make_letter):
        run = make_run(JobStatus.processing, timedelta(days=120))
        letter = make_letter(JobStatus.pending, timedelta(days=120), output=None)
        with patch(STORAGE):
            purge_jobs(db_session, retention_days=90)
        assert _exists(db_session, AccountingJob, run)
        assert _exists(db_session, LetterJob, letter)


class TestStuck:
    def test_lost_accounting_runs_fail_and_give_up_their_pdfs(self, db_session, make_run):
        stuck = make_run(JobStatus.processing, timedelta(hours=7), "accounting/s/input.pdf")
        waiting = make_run(JobStatus.pending, timedelta(hours=8), "accounting/w/input.pdf")
        running = make_run(JobStatus.processing, timedelta(minutes=20), "accounting/r/input.pdf")
        with patch(STORAGE) as storage:
            assert fail_stuck_jobs(db_session) == 2
        assert _deleted(storage) == {"accounting/s/input.pdf", "accounting/w/input.pdf"}
        for job in (stuck, waiting):
            db_session.refresh(job)
            assert job.status == JobStatus.failed and job.input_path is None
            assert job.error_detail.startswith("Interrupted")
        db_session.refresh(running)
        assert running.status == JobStatus.processing


def test_housekeeping_is_scheduled_nightly_on_the_light_queue():
    entry = celery_app.conf.beat_schedule["purge-old-data"]
    assert entry["task"] == "app.services.maintenance.tasks.purge_old_data"
    assert entry["schedule"].hour == {3} and entry["schedule"].minute == {15}
    route = celery_app.conf.task_routes["app.services.maintenance.tasks.*"]
    assert route == {"queue": "light"}


def test_task_runs_every_step_even_if_one_fails(db_session):
    from app.services.maintenance import tasks

    with (
        patch.object(tasks, "SessionLocal", return_value=db_session),
        patch.object(db_session, "close"),
        patch.object(tasks, "fail_stuck_jobs", side_effect=RuntimeError("boom")),
        patch.object(tasks, "expire_budget_uploads", return_value=2) as uploads,
        patch.object(tasks, "purge_jobs", return_value={"letters": 1}) as purge,
        patch.object(tasks, "purge_old_events", return_value=7),
    ):
        out = tasks.purge_old_data()
    assert out == {
        "stuck_accounting_runs_failed": "failed",
        "budget_uploads_deleted": 2,
        "jobs_deleted": {"letters": 1},
        "audit_events_deleted": 7,
    }
    assert uploads.call_args.args[1] == 14 and purge.call_args.args[1] == 90
