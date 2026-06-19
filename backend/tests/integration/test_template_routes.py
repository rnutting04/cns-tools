"""
Integration tests for the letter-generation route.

Storage (S3/MinIO) is mocked at the method level so no real bucket I/O happens;
the focus is the service's control flow and error translation.
"""

import json
import uuid

import pytest

from app.models.audit_event import AuditEvent
from app.models.letter_job import JobStatus, LetterJob
from app.models.template import Template
from app.models.user import UserRole
from app.services.storage import storage_service
from tests import factories
from tests.docx_utils import make_docx

pytestmark = pytest.mark.integration


@pytest.fixture
def fake_storage(monkeypatch):
    """Stub storage so download returns a template and upload/presign are no-ops."""
    template_bytes = make_docx(["Dear {{filtered_association_name}},"])
    monkeypatch.setattr(storage_service, "download_file", lambda key: template_bytes)
    monkeypatch.setattr(storage_service, "upload_file", lambda *a, **k: "http://storage/object")
    monkeypatch.setattr(
        storage_service,
        "generate_presigned_url",
        lambda key, expires=3600: "http://storage/download-url",
    )


def _docx_upload(name: str = "new.docx"):
    """Multipart ``files=`` payload carrying a real (in-memory) .docx."""
    return {
        "file": (
            name,
            make_docx(["Hello {{name}}"]),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }


ASSOCIATION_FIELD = {"key": "association_id", "label": "Association", "type": "association"}


class TestGenerateLetter:
    def test_accepts_and_processes_in_background(
        self, client, db_session, as_user, fake_storage, celery_eager
    ):
        as_user(role=UserRole.admin)
        template = factories.create_template(db_session, fields=[ASSOCIATION_FIELD])
        assoc = factories.create_association(db_session, filter_name="Maple Court")

        resp = client.post(
            "/api/letters/generate",
            json={
                "template_id": str(template.id),
                "field_values": {"association_id": str(assoc.id)},
            },
        )
        # The request is accepted immediately with a pending job; no URL yet.
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "pending"
        assert "download_url" not in body

        # The eager worker ran inline against the same session and finished it.
        job = db_session.query(LetterJob).filter_by(id=body["job_id"]).one()
        assert job.status == JobStatus.complete
        assert job.output_path is not None

    def test_unknown_template_returns_404_without_creating_job(
        self, client, db_session, as_user, fake_storage
    ):
        as_user(role=UserRole.admin)
        resp = client.post(
            "/api/letters/generate",
            json={"template_id": str(uuid.uuid4()), "field_values": {}},
        )
        assert resp.status_code == 404
        assert db_session.query(LetterJob).count() == 0

    def test_template_without_association_field_returns_400(
        self, client, db_session, as_user, fake_storage
    ):
        as_user(role=UserRole.admin)
        template = factories.create_template(db_session, fields=[])
        resp = client.post(
            "/api/letters/generate",
            json={"template_id": str(template.id), "field_values": {}},
        )
        assert resp.status_code == 400
        assert db_session.query(LetterJob).count() == 0

    def test_missing_association_value_returns_400(self, client, db_session, as_user, fake_storage):
        as_user(role=UserRole.admin)
        template = factories.create_template(db_session, fields=[ASSOCIATION_FIELD])
        resp = client.post(
            "/api/letters/generate",
            json={"template_id": str(template.id), "field_values": {}},
        )
        assert resp.status_code == 400
        assert db_session.query(LetterJob).count() == 0

    def test_manager_without_access_returns_403(self, client, db_session, as_user, fake_storage):
        as_user(role=UserRole.manager)  # not assigned to the association
        template = factories.create_template(db_session, fields=[ASSOCIATION_FIELD])
        assoc = factories.create_association(db_session)
        resp = client.post(
            "/api/letters/generate",
            json={
                "template_id": str(template.id),
                "field_values": {"association_id": str(assoc.id)},
            },
        )
        assert resp.status_code == 403
        assert db_session.query(LetterJob).count() == 0


def _make_job(db_session, *, created_by, status=JobStatus.pending, output_path=None):
    template = factories.create_template(db_session, fields=[ASSOCIATION_FIELD])
    assoc = factories.create_association(db_session)
    job = LetterJob(
        template_id=template.id,
        association_id=assoc.id,
        created_by=created_by,
        field_values={},
        status=status,
        output_path=output_path,
    )
    db_session.add(job)
    db_session.flush()
    return job


class TestGetLetterJob:
    def test_pending_job_has_no_url(self, client, db_session, as_user, fake_storage):
        user = as_user(role=UserRole.admin)
        job = _make_job(db_session, created_by=user.id, status=JobStatus.pending)

        resp = client.get(f"/api/letters/{job.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "pending"
        assert body["download_url"] is None

    def test_complete_job_returns_fresh_url(self, client, db_session, as_user, fake_storage):
        user = as_user(role=UserRole.admin)
        job = _make_job(
            db_session,
            created_by=user.id,
            status=JobStatus.complete,
            output_path="outputs/x/file.docx",
        )

        resp = client.get(f"/api/letters/{job.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "complete"
        assert body["download_url"] == "http://storage/download-url"

    def test_unknown_job_returns_404(self, client, as_user, fake_storage):
        as_user(role=UserRole.admin)
        resp = client.get(f"/api/letters/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_manager_cannot_read_others_job(self, client, db_session, as_user, fake_storage):
        owner = factories.create_user(db_session, role=UserRole.manager)
        job = _make_job(db_session, created_by=owner.id, status=JobStatus.pending)
        as_user(role=UserRole.manager)  # a different manager

        resp = client.get(f"/api/letters/{job.id}")
        assert resp.status_code == 404

    def test_admin_cannot_read_others_job(self, client, db_session, as_user, fake_storage):
        owner = factories.create_user(db_session, role=UserRole.manager)
        job = _make_job(db_session, created_by=owner.id, status=JobStatus.pending)
        as_user(role=UserRole.admin)  # a non-super admin

        resp = client.get(f"/api/letters/{job.id}")
        assert resp.status_code == 404

    def test_super_admin_can_read_others_job(self, client, db_session, as_user, fake_storage):
        owner = factories.create_user(db_session, role=UserRole.manager)
        job = _make_job(db_session, created_by=owner.id, status=JobStatus.pending)
        as_user(role=UserRole.super_admin)

        resp = client.get(f"/api/letters/{job.id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"


class TestLetterHistory:
    def test_lists_own_jobs_with_names(self, client, db_session, as_user, fake_storage):
        user = as_user(role=UserRole.admin)
        job = _make_job(db_session, created_by=user.id, status=JobStatus.pending)

        resp = client.get("/api/letters/history")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        row = body[0]
        assert row["id"] == str(job.id)
        assert row["template_name"]
        assert row["association_name"]

    def test_history_omits_download_url(self, client, db_session, as_user, fake_storage):
        # URLs are minted lazily (via GET /letters/{id}) so the list endpoint
        # doesn't generate a presigned URL per row.
        user = as_user(role=UserRole.admin)
        _make_job(
            db_session,
            created_by=user.id,
            status=JobStatus.complete,
            output_path="outputs/x/file.docx",
        )

        resp = client.get("/api/letters/history")
        assert resp.status_code == 200
        assert "download_url" not in resp.json()[0]

    def test_scoped_to_current_user_for_all_roles(self, client, db_session, as_user, fake_storage):
        # An admin only sees their own jobs, not other users' jobs.
        other = factories.create_user(db_session, role=UserRole.admin)
        _make_job(db_session, created_by=other.id, status=JobStatus.pending)
        user = as_user(role=UserRole.admin)
        mine = _make_job(db_session, created_by=user.id, status=JobStatus.pending)

        resp = client.get("/api/letters/history")
        assert resp.status_code == 200
        body = resp.json()
        assert [row["id"] for row in body] == [str(mine.id)]

    def test_super_admin_sees_all_jobs_with_creator(
        self, client, db_session, as_user, fake_storage
    ):
        owner = factories.create_user(db_session, role=UserRole.manager, fname="Jane", lname="Doe")
        theirs = _make_job(db_session, created_by=owner.id, status=JobStatus.pending)
        user = as_user(role=UserRole.super_admin)
        mine = _make_job(db_session, created_by=user.id, status=JobStatus.pending)

        resp = client.get("/api/letters/history")
        assert resp.status_code == 200
        body = resp.json()
        assert {row["id"] for row in body} == {str(theirs.id), str(mine.id)}
        theirs_row = next(r for r in body if r["id"] == str(theirs.id))
        assert theirs_row["created_by"] == str(owner.id)
        assert theirs_row["created_by_name"] == "Jane Doe"

    def test_created_at_is_utc_aware(self, client, db_session, as_user, fake_storage):
        user = as_user(role=UserRole.admin)
        _make_job(db_session, created_by=user.id, status=JobStatus.pending)

        resp = client.get("/api/letters/history")
        created_at = resp.json()[0]["created_at"]
        # Unambiguous timezone marker so the browser parses it as UTC, not local.
        assert created_at.endswith("+00:00") or created_at.endswith("Z")


def _make_detailed_job(db_session, *, created_by, field_values, fields):
    template = factories.create_template(db_session, fields=fields)
    assoc = factories.create_association(db_session)
    job = LetterJob(
        template_id=template.id,
        association_id=assoc.id,
        created_by=created_by,
        field_values=field_values,
        status=JobStatus.complete,
        output_path="outputs/x/file.docx",
    )
    db_session.add(job)
    db_session.flush()
    return job


class TestLetterJobDetails:
    FIELDS = [
        ASSOCIATION_FIELD,
        {"key": "meeting_date", "label": "Meeting date", "type": "date"},
    ]
    VALUES = {
        "association_id": "assoc-123",
        "meeting_date": "2026-07-15",
        "legal_association_name": "Maplewood HOA, Inc.",  # curated derived field
        "manager_full_name": "Jane Smith",  # curated derived field
        "meeting_date_upper": "2026-07-15",  # noisy variant — must be excluded
    }

    def test_owner_sees_entries_and_derived(self, client, db_session, as_user, fake_storage):
        user = as_user(role=UserRole.admin)
        job = _make_detailed_job(
            db_session, created_by=user.id, field_values=self.VALUES, fields=self.FIELDS
        )

        resp = client.get(f"/api/letters/{job.id}/details")
        assert resp.status_code == 200
        body = resp.json()

        entry_labels = {e["label"]: e["value"] for e in body["entries"]}
        assert entry_labels == {"Association": "assoc-123", "Meeting date": "2026-07-15"}

        derived_labels = {d["label"]: d["value"] for d in body["derived"]}
        assert derived_labels["Legal name"] == "Maplewood HOA, Inc."
        assert derived_labels["Manager"] == "Jane Smith"
        # Noisy variants are not surfaced.
        assert not any("upper" in d["label"].lower() for d in body["derived"])

    def test_other_user_gets_404(self, client, db_session, as_user, fake_storage):
        owner = factories.create_user(db_session, role=UserRole.manager)
        job = _make_detailed_job(
            db_session, created_by=owner.id, field_values=self.VALUES, fields=self.FIELDS
        )
        as_user(role=UserRole.admin)  # non-super admin

        resp = client.get(f"/api/letters/{job.id}/details")
        assert resp.status_code == 404

    def test_super_admin_can_view_details(self, client, db_session, as_user, fake_storage):
        owner = factories.create_user(db_session, role=UserRole.manager)
        job = _make_detailed_job(
            db_session, created_by=owner.id, field_values=self.VALUES, fields=self.FIELDS
        )
        as_user(role=UserRole.super_admin)

        resp = client.get(f"/api/letters/{job.id}/details")
        assert resp.status_code == 200


class TestRenderFailure:
    def test_render_failure_marks_job_failed(self, client, db_session, as_user, monkeypatch):
        user = as_user(role=UserRole.admin)
        job = _make_job(db_session, created_by=user.id, status=JobStatus.pending)

        def boom(key):
            raise RuntimeError("storage down")

        monkeypatch.setattr(storage_service, "download_file", boom)

        from app.services.letters.exceptions import RenderFailed
        from app.services.letters.service import render_letter_job

        with pytest.raises(RenderFailed):
            render_letter_job(db_session, job.id)

        db_session.expire_all()
        reloaded = db_session.query(LetterJob).filter_by(id=job.id).one()
        assert reloaded.status == JobStatus.failed

        # And the polling endpoint reports the failure with no URL.
        resp = client.get(f"/api/letters/{job.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "failed"
        assert body["download_url"] is None


class TestUpdateTemplate:
    def test_updates_metadata(self, client, db_session, as_user, fake_storage):
        as_user(role=UserRole.admin)
        template = factories.create_template(db_session, name="Old", category="Notices")

        resp = client.patch(
            f"/api/templates/{template.id}",
            data={"name": "New Name", "category": "Letters", "renderer_type": "proxy"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "New Name"
        assert body["category"] == "Letters"
        assert body["renderer_type"] == "proxy"

        db_session.expire_all()
        reloaded = db_session.query(Template).filter_by(id=template.id).one()
        assert reloaded.name == "New Name"

    def test_updates_fields(self, client, db_session, as_user, fake_storage):
        as_user(role=UserRole.admin)
        template = factories.create_template(db_session, fields=[])

        resp = client.patch(
            f"/api/templates/{template.id}",
            data={"fields": json.dumps([ASSOCIATION_FIELD])},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["fields"]) == 1
        assert body["fields"][0]["key"] == "association_id"

    def test_replaces_docx_and_cleans_up_old_file(
        self, client, db_session, as_user, fake_storage, monkeypatch
    ):
        as_user(role=UserRole.admin)
        template = factories.create_template(db_session, docx_path="templates/old/old.docx")

        deleted: list[str] = []
        monkeypatch.setattr(storage_service, "delete_file", lambda key: deleted.append(key))

        resp = client.patch(
            f"/api/templates/{template.id}",
            files=_docx_upload("replacement.docx"),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["docx_path"] == f"templates/{template.id}/replacement.docx"
        assert deleted == ["templates/old/old.docx"]

    def test_unknown_template_returns_404(self, client, as_user, fake_storage):
        as_user(role=UserRole.admin)
        resp = client.patch(f"/api/templates/{uuid.uuid4()}", data={"name": "x"})
        assert resp.status_code == 404

    def test_non_admin_returns_403(self, client, db_session, as_user, fake_storage):
        as_user(role=UserRole.manager)
        template = factories.create_template(db_session)
        resp = client.patch(f"/api/templates/{template.id}", data={"name": "x"})
        assert resp.status_code == 403

    def test_invalid_fields_json_returns_400(self, client, db_session, as_user, fake_storage):
        as_user(role=UserRole.admin)
        template = factories.create_template(db_session)
        resp = client.patch(f"/api/templates/{template.id}", data={"fields": "not json"})
        assert resp.status_code == 400

    def test_non_docx_file_returns_400(self, client, db_session, as_user, fake_storage):
        as_user(role=UserRole.admin)
        template = factories.create_template(db_session)
        resp = client.patch(
            f"/api/templates/{template.id}",
            files={"file": ("note.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400


class TestDuplicateTemplate:
    def test_happy_path_copies_source(self, client, db_session, as_user, fake_storage):
        as_user(role=UserRole.admin)
        source = factories.create_template(
            db_session, name="Annual Notice", fields=[ASSOCIATION_FIELD]
        )

        resp = client.post(f"/api/templates/{source.id}/duplicate")
        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] != str(source.id)
        assert body["name"] == "Annual Notice (Copy)"
        assert len(body["fields"]) == 1

        # Source is untouched.
        db_session.expire_all()
        assert db_session.query(Template).filter_by(id=source.id).one().name == "Annual Notice"

        # Audit event references the source.
        event = db_session.query(AuditEvent).filter_by(action="template.duplicated").one()
        assert event.event_metadata["source_template_id"] == str(source.id)

    def test_applies_overrides(self, client, db_session, as_user, fake_storage):
        as_user(role=UserRole.admin)
        source = factories.create_template(db_session, name="Base", category="Notices")

        resp = client.post(
            f"/api/templates/{source.id}/duplicate",
            data={
                "name": "Custom Copy",
                "category": "Letters",
                "fields": json.dumps([ASSOCIATION_FIELD]),
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Custom Copy"
        assert body["category"] == "Letters"
        assert len(body["fields"]) == 1

    def test_copies_source_docx_when_no_file(
        self, client, db_session, as_user, fake_storage, monkeypatch
    ):
        as_user(role=UserRole.admin)
        source = factories.create_template(db_session, docx_path="templates/src/src.docx")

        uploads: list[str] = []
        monkeypatch.setattr(
            storage_service, "upload_file", lambda data, key, **k: uploads.append(key) or key
        )

        resp = client.post(f"/api/templates/{source.id}/duplicate")
        assert resp.status_code == 201
        new_id = resp.json()["id"]
        assert uploads == [f"templates/{new_id}/src.docx"]

    def test_uses_uploaded_file_when_provided(self, client, db_session, as_user, fake_storage):
        as_user(role=UserRole.admin)
        source = factories.create_template(db_session)

        resp = client.post(
            f"/api/templates/{source.id}/duplicate",
            files=_docx_upload("fresh.docx"),
        )
        assert resp.status_code == 201
        new_id = resp.json()["id"]
        assert resp.json()["docx_path"] == f"templates/{new_id}/fresh.docx"

    def test_unknown_source_returns_404(self, client, as_user, fake_storage):
        as_user(role=UserRole.admin)
        resp = client.post(f"/api/templates/{uuid.uuid4()}/duplicate")
        assert resp.status_code == 404

    def test_non_admin_returns_403(self, client, db_session, as_user, fake_storage):
        as_user(role=UserRole.manager)
        source = factories.create_template(db_session)
        resp = client.post(f"/api/templates/{source.id}/duplicate")
        assert resp.status_code == 403
