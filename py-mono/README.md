# py-mono

The application: a **Python monolith** that ingests images, generates three thumbnail
sizes with a Celery worker, and delivers them to the user as a ZIP through an SSE-backed
live status flow.

FastAPI + Celery + Redis + MinIO (S3-compatible) + Pillow, managed as a `uv` project
(Python 3.12).

```
POST /api/upload  -> FastAPI (save original to MinIO, enqueue task)  -> Redis queue
                                                                          |
                  Celery worker: download original -> Pillow resize (1280/640/320)
                     -> upload thumbnails to MinIO -> publish status via Redis pubsub
                                                                          |
GET /api/events/{id}  -> SSE stream  (queued / processing / done / failed)
GET /api/download/{id}-> on-the-fly ZIP of the 3 thumbnails
```

See [`docs/arch-01-py-mono.md`](../docs/arch-01-py-mono.md) for the full architecture
(layering, API endpoints, SSE event model, storage layout, job state, reliability config).

## Layout

```
py-mono/
│   ├── Dockerfile           # python:3.12-slim + uv, same image for API & worker
│   ├── pyproject.toml       # fastapi, celery, redis, minio, pillow, pydantic-settings
│   ├── uv.lock
│   └── src/
│       ├── api.py               # THIN FastAPI routes (upload / status / SSE / download / health)
│       ├── deps.py              # composition root: builds real services & adapters (DI)
│       ├── celery_app.py        # Celery instance + conf ONLY
│       ├── tasks.py             # thin Celery adapter (retry logic) -> ThumbnailService
│       ├── config.py            # pydantic-settings configuration
│       ├── services/            # business logic (no redis/minio/celery imports)
│       │   ├── jobs.py          # JobService: state transitions + get
│       │   ├── uploads.py       # UploadService: validate/sanitize/save/enqueue
│       │   └── thumbnails.py    # ThumbnailService: process() + create_zip()
│       └── infra/               # concrete adapters
│           ├── redis.py         # Redis client factory
│           ├── job_store.py     # JobStore: job hash + TTL
│           ├── events.py        # EventBroker: publish + SSE stream generator
│           └── storage.py       # MinioStorage: buckets, originals, thumbnails
```

## Run locally

From the repo root (the dev compose file builds `./py-mono` and defaults everything):

```powershell
docker compose -f docker-compose.dev.yml up -d --build
python frontend/serve.py   # open http://localhost:8080
```

- API: http://localhost:8000 (`GET /` → `{"status": "ok"}`)
- MinIO console: http://localhost:9001 (minioadmin/minioadmin)
- Redis: localhost:6379

Stop: `docker compose -f docker-compose.dev.yml down` (keeps data); wipe:
`docker compose -f docker-compose.dev.yml down -v`.

## Deploy

The same image runs in production via Docker Compose — on Civo (MinIO inside the stack)
or AWS (native S3 + ECR). See the runbooks:

- [`docs/deploy-civo.md`](../docs/deploy-civo.md)
- [`docs/deploy-aws.md`](../docs/deploy-aws.md)