from redis import Redis
from .redis import get_redis


class JobStore:
    def __init__(self, redis: Redis | None = None, ttl_hours: int = 24):
        self._redis = redis or get_redis()
        self._ttl_seconds = ttl_hours * 3600

    @staticmethod
    def job_key(job_id: str) -> str:
        return f"job:{job_id}"

    def get(self, job_id: str) -> dict | None:
        data = self._redis.hgetall(self.job_key(job_id))
        return data or None

    def set_status(self, job_id: str, status: str, **fields: str) -> None:
        pipe = self._redis.pipeline()
        pipe.hset(self.job_key(job_id), "status", status)

        if fields:
            pipe.hset(self.job_key(job_id), mapping=fields)

        pipe.expire(self.job_key(job_id), self._ttl_seconds)
        pipe.execute()
