import io
import tempfile
import zipfile
from PIL import Image, ImageOps
from ..config import Settings
from ..infra.storage import MinioStorage
from .jobs import JobService


class ThumbnailService:
    def __init__(
        self,
        storage: MinioStorage,
        job_service: JobService,
        settings: Settings,
    ):
        self._storage = storage
        self._job_service = job_service
        self._settings = settings

    def process(self, job_id: str, filename: str) -> dict:
        self._job_service.mark_processing(job_id)

        original = self._storage.get_original(job_id, filename)
        with Image.open(io.BytesIO(original)) as img:
            img = ImageOps.exif_transpose(img)
            rgb = img.convert("RGB") if img.mode != "RGB" else img
            for size in self._settings.THUMB_SIZES:
                thumb = rgb.copy()
                thumb.thumbnail((size, size), Image.LANCZOS)
                buffer = io.BytesIO()
                thumb.save(
                    buffer,
                    format="JPEG",
                    quality=self._settings.THUMB_QUALITY,
                    optimize=True,
                )
                self._storage.save_thumbnail(job_id, size, buffer.getvalue())

        result = {
            "status": "done",
            "thumbnail_keys": [f"{size}w.jpg" for size in self._settings.THUMB_SIZES],
            "download_url": f"/api/download/{job_id}",
        }
        self._job_service.mark_done(job_id, result["download_url"])
        return result

    def create_zip(self, job_id: str) -> tuple[io.BufferedIOBase, int]:
        buffer = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for size in self._settings.THUMB_SIZES:
                archive.writestr(
                    f"{size}w.jpg",
                    self._storage.get_thumbnail(job_id, size),
                )

        size = buffer.tell()
        buffer.seek(0)
        return buffer, size
