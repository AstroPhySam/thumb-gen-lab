import io
import re
import uuid
from pathlib import PurePath
from typing import BinaryIO
from ..config import Settings
from ..infra.events import EventBroker
from ..infra.storage import MinioStorage
from .jobs import JobService

SAFE_NAME_RE = re.compile(r"[^a-zA-Z0-9_.-]+")


def safe_filename(filename: str | None) -> str:
    name = PurePath(filename or "image.jpg").name
    name = SAFE_NAME_RE.sub("_", name).strip("._")
    return name or "image.jpg"


class UploadError(Exception):
    def __init__(self, detail: str, status_code: int = 400):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class UploadService:
    def __init__(
        self,
        storage: MinioStorage,
        job_service: JobService,
        events: EventBroker,
        enqueue: callable,
        settings: Settings,
    ):
        self._storage = storage
        self._job_service = job_service
        self._events = events
        self._enqueue = enqueue
        self._settings = settings

    def upload(
        self, filename: str | None, content_type: str | None, stream: BinaryIO
    ) -> dict:
        content_type = content_type or ""
        if not content_type.startswith("image/"):
            raise UploadError("Only image uploads are allowed", status_code=400)

        safe = safe_filename(filename)
        stream.seek(0, io.SEEK_END)
        size = stream.tell()
        stream.seek(0)

        if size == 0:
            raise UploadError("Empty file", status_code=400)

        max_bytes = self._settings.MAX_UPLOAD_MB * 1024 * 1024
        if size > max_bytes:
            raise UploadError(
                f"File exceeds {self._settings.MAX_UPLOAD_MB}MB limit",
                status_code=413,
            )

        job_id = uuid.uuid4().hex
        self._job_service.create(job_id, safe)

        try:
            self._storage.save_original(job_id, safe, stream, size, content_type)
            self._enqueue(job_id, safe)
        except Exception as exc:
            message = f"Failed to enqueue job: {exc}"
            self._job_service.mark_failed(job_id, message)
            raise UploadError(message, status_code=500) from exc

        return {"job_id": job_id, "status": "queued"}
