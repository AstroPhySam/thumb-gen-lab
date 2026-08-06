from ..infra.events import EventBroker
from ..infra.job_store import JobStore


class JobService:
    def __init__(self, job_store: JobStore, events: EventBroker):
        self._job_store = job_store
        self._events = events

    def create(self, job_id: str, filename: str) -> None:
        self._job_store.set_status(job_id, "queued", filename=filename)
        self._events.publish(job_id, "queued")

    def get(self, job_id: str) -> dict | None:
        return self._job_store.get(job_id)

    def mark_processing(self, job_id: str) -> None:
        self._job_store.set_status(job_id, "processing")
        self._events.publish(job_id, "processing")

    def mark_done(self, job_id: str, download_url: str) -> None:
        self._job_store.set_status(job_id, "done", download_url=download_url)
        self._events.publish(job_id, "done", {"download_url": download_url})

    def mark_failed(self, job_id: str, error: str) -> None:
        self._job_store.set_status(job_id, "failed", error=error)
        self._events.publish(job_id, "failed", {"error": error})
