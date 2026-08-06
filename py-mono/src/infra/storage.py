import io
from typing import BinaryIO
from minio import Minio
from ..config import Settings, get_settings


class MinioStorage:
    def __init__(self, client: Minio | None = None, settings: Settings | None = None):
        self._settings = settings or get_settings()
        self._client = client or Minio(
            self._settings.MINIO_ENDPOINT,
            access_key=self._settings.MINIO_ACCESS_KEY,
            secret_key=self._settings.MINIO_SECRET_KEY,
            secure=self._settings.MINIO_SECURE,
        )

    def ensure_buckets(self) -> None:
        for bucket in (
            self._settings.MINIO_BUCKET_ORIGINALS,
            self._settings.MINIO_BUCKET_THUMBNAILS,
        ):
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket)

    @staticmethod
    def original_key(job_id: str, filename: str) -> str:
        return f"{job_id}/{filename}"

    @staticmethod
    def thumbnail_key(job_id: str, size: int) -> str:
        return f"{job_id}/{size}w.jpg"

    def save_original(
        self,
        job_id: str,
        filename: str,
        data: BinaryIO,
        length: int,
        content_type: str,
    ) -> str:
        key = self.original_key(job_id, filename)
        self._client.put_object(
            self._settings.MINIO_BUCKET_ORIGINALS,
            key,
            data,
            length=length,
            content_type=content_type,
        )
        return key

    def get_original(self, job_id: str, filename: str) -> bytes:
        response = self._client.get_object(
            self._settings.MINIO_BUCKET_ORIGINALS,
            self.original_key(job_id, filename),
        )
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def save_thumbnail(self, job_id: str, size: int, data: bytes) -> str:
        key = self.thumbnail_key(job_id, size)
        self._client.put_object(
            self._settings.MINIO_BUCKET_THUMBNAILS,
            key,
            io.BytesIO(data),
            length=len(data),
            content_type="image/jpeg",
        )
        return key

    def get_thumbnail(self, job_id: str, size: int) -> bytes:
        response = self._client.get_object(
            self._settings.MINIO_BUCKET_THUMBNAILS,
            self.thumbnail_key(job_id, size),
        )
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()
