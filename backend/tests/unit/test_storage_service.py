"""Unit tests for StorageService's laziness and locking.

Two properties matter here and neither is covered elsewhere, because every
other test mocks the storage methods wholesale:

1. Constructing the service must not touch the network. The CI job relies on
   this — it runs no object-storage container, so an eager client would break
   `import app.main` before a single test executed.
2. The first upload must not deadlock. _ensure_bucket holds the instance lock
   while calling the _client property, which takes the same lock to build the
   client; with a non-reentrant Lock that hangs forever on the first write.

A deadlock hangs rather than fails, which would stall CI instead of reporting,
so the locking test runs the call on a worker thread and fails on timeout.
"""

import threading
from unittest.mock import MagicMock

import pytest

from app.services import storage

pytestmark = pytest.mark.unit


def run_with_timeout(fn, seconds: float = 5.0):
    """Run fn on a worker thread; raise if it hasn't returned in time."""
    result: dict = {}

    def target():
        try:
            result["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - re-raised on the main thread
            result["error"] = exc

    t = threading.Thread(target=target, daemon=True)
    t.start()
    t.join(seconds)
    if t.is_alive():
        raise AssertionError(f"call did not return within {seconds}s - deadlock")
    if "error" in result:
        raise result["error"]
    return result.get("value")


class TestLaziness:
    def test_constructing_the_service_creates_no_client(self, monkeypatch):
        calls = []
        monkeypatch.setattr(storage.boto3, "client", lambda *a, **k: calls.append(1))

        storage.StorageService()

        assert calls == [], "boto3 client was built at construction time"

    def test_constructing_the_service_does_not_check_the_bucket(self, monkeypatch):
        client = MagicMock()
        monkeypatch.setattr(storage.boto3, "client", lambda *a, **k: client)

        storage.StorageService()

        client.head_bucket.assert_not_called()
        client.create_bucket.assert_not_called()

    def test_client_is_built_once_and_reused(self, monkeypatch):
        built = []

        def fake_client(*a, **k):
            built.append(1)
            return MagicMock()

        monkeypatch.setattr(storage.boto3, "client", fake_client)
        svc = storage.StorageService()

        svc.generate_presigned_url("a")
        svc.generate_presigned_url("b")

        assert len(built) == 1

    def test_presigning_does_not_check_the_bucket(self, monkeypatch):
        """Building a download URL is local arithmetic; it must cost no round trip."""
        client = MagicMock()
        monkeypatch.setattr(storage.boto3, "client", lambda *a, **k: client)

        storage.StorageService().generate_presigned_url("some/key")

        client.head_bucket.assert_not_called()


class TestBucketBootstrap:
    def test_first_upload_does_not_deadlock(self, monkeypatch):
        """Regression: _ensure_bucket -> _client re-entered a non-reentrant lock."""
        client = MagicMock()
        monkeypatch.setattr(storage.boto3, "client", lambda *a, **k: client)
        svc = storage.StorageService()

        run_with_timeout(lambda: svc.upload_file(b"data", "k/v.txt"))

        client.put_object.assert_called_once()

    def test_missing_bucket_is_created(self, monkeypatch):
        from botocore.exceptions import ClientError

        client = MagicMock()
        client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadBucket"
        )
        monkeypatch.setattr(storage.boto3, "client", lambda *a, **k: client)
        svc = storage.StorageService()

        run_with_timeout(lambda: svc.upload_file(b"data", "k/v.txt"))

        client.create_bucket.assert_called_once()

    def test_bucket_is_checked_only_once_per_process(self, monkeypatch):
        client = MagicMock()
        monkeypatch.setattr(storage.boto3, "client", lambda *a, **k: client)
        svc = storage.StorageService()

        run_with_timeout(lambda: svc.upload_file(b"a", "one.txt"))
        run_with_timeout(lambda: svc.upload_file(b"b", "two.txt"))
        run_with_timeout(lambda: svc.upload_file(b"c", "three.txt"))

        assert client.head_bucket.call_count == 1
        assert client.put_object.call_count == 3
