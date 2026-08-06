from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    REDIS_URL: str = "redis://localhost:6379/0"

    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_SECURE: bool = False
    MINIO_BUCKET_ORIGINALS: str = "originals"
    MINIO_BUCKET_THUMBNAILS: str = "thumbnails"

    THUMB_SIZES: list[int] = [1280, 640, 320]
    THUMB_QUALITY: int = 85
    MAX_UPLOAD_MB: int = 50
    JOB_TTL_HOURS: int = 24

    MAX_RETRIES: int = 3

    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), ".env"),
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
