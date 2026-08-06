import json
import asyncio
from collections.abc import AsyncGenerator, Callable
from redis import Redis
from .redis import get_redis


def sse_frame(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class EventBroker:
    def __init__(self, redis: Redis | None = None):
        self._redis = redis or get_redis()

    @staticmethod
    def event_channel(job_id: str) -> str:
        return f"events:{job_id}"

    def publish(self, job_id: str, event: str, payload: dict | None = None) -> None:
        message = json.dumps({"event": event, "payload": payload or {}})
        self._redis.publish(self.event_channel(job_id), message)

    async def subscribe_stream(
        self,
        job_id: str,
        get_status: Callable[[str], dict | None],
    ) -> AsyncGenerator[str, None]:
        pubsub = self._redis.pubsub()
        pubsub.subscribe(self.event_channel(job_id))

        try:
            current = get_status(job_id)
            status = current.get("status") if current else None

            if status == "done":
                yield sse_frame("done", {"download_url": f"/api/download/{job_id}"})
                return

            if status == "failed":
                yield sse_frame("failed", {"error": current.get("error", "unknown")})
                return

            yield sse_frame(status or "queued", {})

            while True:
                message = await asyncio.to_thread(
                    pubsub.get_message,
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )

                if message and message.get("type") == "message":
                    data = json.loads(message["data"])
                    yield sse_frame(data["event"], data["payload"])

                    if data["event"] in ("done", "failed"):
                        return
                else:
                    yield sse_frame("ping", {})
        finally:
            pubsub.unsubscribe(self.event_channel(job_id))
            pubsub.close()
