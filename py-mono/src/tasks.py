import logging
from .celery_app import celery_app
from .deps import get_job_service, get_thumbnail_service
from .config import get_settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="src.tasks.process_thumbnail")
def process_thumbnail(self, job_id: str, filename: str) -> dict:
    job_service = get_job_service()
    thumbnail_service = get_thumbnail_service()

    try:
        return thumbnail_service.process(job_id, filename)
    except Exception as exc:
        if self.request.retries < get_settings().MAX_RETRIES:
            logger.warning(
                "Retrying thumbnail job %s (attempt %s): %s",
                job_id,
                self.request.retries + 1,
                exc,
            )
            raise self.retry(exc=exc, countdown=2**self.request.retries)

        logger.exception("Failed to process thumbnail job %s", job_id)
        job_service.mark_failed(job_id, str(exc))
        raise
