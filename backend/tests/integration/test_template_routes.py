"""
Integration tests for the letter-generation route.

Storage (S3/MinIO) is mocked at the method level so no real bucket I/O happens;
the focus is the service's control flow and error translation.
"""

import uuid

import pytest

from app.models.letter_job import JobStatus, LetterJob
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
