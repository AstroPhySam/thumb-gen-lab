from redis import Redis
from ..config import get_settings

_redis: Redis | None = None


def get_redis() -> Redis:
    global _redis

    if _redis is None:
        _redis = Redis.from_url(get_settings().REDIS_URL, decode_responses=True)

    return _redis
