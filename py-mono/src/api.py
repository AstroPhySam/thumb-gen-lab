import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from .config import get_settings
from .deps import (
    get_event_broker,
    get_job_service,
    get_storage,
    get_thumbnail_service,
    get_upload_service,
)
from .infra.events import EventBroker
from .services.jobs import JobService
from .services.thumbnails import ThumbnailService
from .services.uploads import UploadError, UploadService


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await asyncio.to_thread(get_storage().ensure_buckets)
    yield


app = FastAPI(title="Thumbnail Generation API", lifespan=lifespan)

cors_origins = get_settings().CORS_ORIGINS
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/")
def read_root():
    return {"status": "ok"}


@app.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    upload_service: UploadService = Depends(get_upload_service),
):
    try:
        return await asyncio.to_thread(
            upload_service.upload,
            file.filename,
            file.content_type,
            file.file,
        )
    except UploadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@app.get("/api/status/{job_id}")
def status(job_id: str, job_service: JobService = Depends(get_job_service)):
    job = job_service.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


@app.get("/api/events/{job_id}")
async def events(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
    broker: EventBroker = Depends(get_event_broker),
):
    job = job_service.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return StreamingResponse(
        broker.subscribe_stream(job_id, job_service.get),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _zip_stream(
    buffer,
    chunk_size: int = 1024 * 1024,
) -> AsyncGenerator[bytes, None]:
    while True:
        chunk = await asyncio.to_thread(buffer.read, chunk_size)
        if not chunk:
            break
        yield chunk
    buffer.close()


@app.get("/api/download/{job_id}")
async def download(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
    thumbnail_service: ThumbnailService = Depends(get_thumbnail_service),
):
    job = job_service.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.get("status") != "done":
        raise HTTPException(status_code=409, detail="Job is not finished")

    buffer, size = await asyncio.to_thread(thumbnail_service.create_zip, job_id)

    return StreamingResponse(
        _zip_stream(buffer),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{job_id}.zip"',
            "Content-Length": str(size),
        },
    )
