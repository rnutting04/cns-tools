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
    def test_happy_path(self, client, db_session, as_user, fake_storage):
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
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "complete"
        assert body["download_url"] == "http://storage/download-url"

        job = db_session.query(LetterJob).filter_by(id=body["job_id"]).one()
        assert job.status == JobStatus.complete
        assert job.output_path is not None

    def test_unknown_template_returns_404(self, client, as_user, fake_storage):
        as_user(role=UserRole.admin)
        resp = client.post(
            "/api/letters/generate",
            json={"template_id": str(uuid.uuid4()), "field_values": {}},
        )
        assert resp.status_code == 404

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

    def test_missing_association_value_returns_400(self, client, db_session, as_user, fake_storage):
        as_user(role=UserRole.admin)
        template = factories.create_template(db_session, fields=[ASSOCIATION_FIELD])
        resp = client.post(
            "/api/letters/generate",
            json={"template_id": str(template.id), "field_values": {}},
        )
        assert resp.status_code == 400

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
