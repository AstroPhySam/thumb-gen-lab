from collections.abc import Callable
from functools import lru_cache
from .config import Settings, get_settings
from .infra.events import EventBroker
from .infra.job_store import JobStore
from .infra.redis import get_redis
from .infra.storage import MinioStorage
from .services.jobs import JobService
from .services.thumbnails import ThumbnailService
from .services.uploads import UploadService


def get_settings_dep() -> Settings:
    return get_settings()


@lru_cache
def get_job_store() -> JobStore:
    return JobStore(get_redis(), ttl_hours=get_settings().JOB_TTL_HOURS)


@lru_cache
def get_event_broker() -> EventBroker:
    return EventBroker(get_redis())


@lru_cache
def get_storage() -> MinioStorage:
    return MinioStorage()


@lru_cache
def get_job_service() -> JobService:
    return JobService(get_job_store(), get_event_broker())


def enqueue_processing(job_id: str, filename: str) -> None:
    from .tasks import process_thumbnail

    process_thumbnail.delay(job_id, filename)


def get_enqueue() -> Callable[[str, str], None]:
    return enqueue_processing


@lru_cache
def get_upload_service() -> UploadService:
    return UploadService(
        get_storage(),
        get_job_service(),
        get_event_broker(),
        get_enqueue(),
        get_settings(),
    )


@lru_cache
def get_thumbnail_service() -> ThumbnailService:
    return ThumbnailService(get_storage(), get_job_service(), get_settings())
