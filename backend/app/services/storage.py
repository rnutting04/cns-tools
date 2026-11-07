# app/services/storage.py
import threading

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.config import settings


class StorageService:
    """S3-compatible object storage (DigitalOcean Spaces in production).

    Both the client and the bucket check are lazy. They used to run in
    __init__, which — because the module ends with a module-level instance —
    meant that merely importing anything that touched storage opened a network
    connection and issued a head_bucket. That made `import app.main` fail
    whenever object storage was unreachable, and forced the CI job to stand up
    a storage container for a test suite that mocks every storage call anyway.
    Nothing here touches the network until a real read or write happens.
    """

    def __init__(self) -> None:
        self._client_instance = None
        self._bucket_ready = False
        self._lock = threading.Lock()

    @property
    def _bucket(self) -> str:
        # Read through to settings rather than snapshotting at construction,
        # so tests and scripts can override configuration after import.
        return settings.SPACES_BUCKET

    @property
    def _client(self):
        if self._client_instance is None:
            with self._lock:
                if self._client_instance is None:
                    self._client_instance = boto3.client(
                        "s3",
                        endpoint_url=settings.SPACES_ENDPOINT,
                        aws_access_key_id=settings.SPACES_KEY,
                        aws_secret_access_key=settings.SPACES_SECRET,
                        config=Config(signature_version="s3v4"),
                    )
        return self._client_instance

    def _ensure_bucket(self) -> None:
        """Create the bucket if it is missing. Runs at most once per process."""
        if self._bucket_ready:
            return
        with self._lock:
            if self._bucket_ready:
                return
            try:
                self._client.head_bucket(Bucket=self._bucket)
            except ClientError:
                self._client.create_bucket(Bucket=self._bucket)
            self._bucket_ready = True

    def upload_file(
        self, file_bytes: bytes, key: str, content_type: str = "application/octet-stream"
    ) -> str:
        self._ensure_bucket()
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=file_bytes,
            ContentType=content_type,
        )
        return f"{settings.SPACES_ENDPOINT}/{self._bucket}/{key}"

    def download_file(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()

    def generate_presigned_url(self, key: str, expires: int = 3600) -> str:
        # Signing is local arithmetic; deliberately no _ensure_bucket call so
        # building a download URL never costs a round trip.
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires,
        )

    def delete_file(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)


storage_service = StorageService()
