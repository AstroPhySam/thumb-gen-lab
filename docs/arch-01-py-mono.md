# Arch 1 : Python Monolith

A **Python monolith** that ingests images, generates three thumbnail sizes with a Celery worker, and delivers them to the user as a ZIP downloaded through an SSE-backed live status flow.

```
POST /api/upload  -> FastAPI (save original to MinIO, enqueue task)  -> Redis queue
                                                                          |
                  Celery worker: download original -> Pillow resize (1280/640/320)
                     -> upload thumbnails to MinIO -> publish status via Redis pubsub
                                                                          |
GET /api/events/{id}  -> SSE stream  (queued / processing / done / failed)
GET /api/download/{id}-> on-the-fly ZIP of the 3 thumbnails
```

---

## Repository layout (application code)

```
py-mono/                 # the Python monolith (uv project, Python 3.12)
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
frontend/                # vanilla HTML/CSS/JS test page (separate, no build step)
    ├── index.html
    ├── config.js
    ├── serve.py             # for simple development server to test locally
    ├── css/style.css
    └── js/app.js
```

`frontend/` is intentionally kept **outside** `py-mono` so the project can adopt other
architecture patterns (e.g. dedicated `api-python/`, `worker-rust/`, `notify-rust/`) later.

**Layering:** routes (`api.py`) only parse HTTP and delegate to `services/` (pure business
logic) which talk to `infra/` adapters (Redis, MinIO, Celery). Everything is
constructor-injected via the `deps.py` composition root, so services can be unit-tested
with fakes (no Redis/MinIO/Celery imports inside `services/`).

---

## Components

| Component          | Technology               | Role                                                  |
| ------------------ | ------------------------ | ----------------------------------------------------- |
| **API**            | FastAPI (async, uvicorn) | Ingestion layer: upload, status, SSE, ZIP download    |
| **Worker**         | Celery (prefork)         | CPU-bound image processing (Pillow)                   |
| **Broker / state** | Redis                    | Task queue, result backend, job hashes, pubsub events |
| **Storage**        | MinIO / S3-compatible    | `originals` and `thumbnails` object buckets           |
| **Frontend**       | Vanilla HTML/CSS/JS      | Test page consuming upload + SSE + download           |

---

## API endpoints

| Method | Path                     | Purpose          | Notes                                                                                                                      |
| ------ | ------------------------ | ---------------- | -------------------------------------------------------------------------------------------------------------------------- |
| `GET`  | `/`                      | Health check     | `{"status": "ok"}`                                                                                                         |
| `POST` | `/api/upload`            | Upload an image  | Multipart `file`; validates image MIME + ≤50MB; filename sanitized; streams to MinIO; returns `{job_id, status: "queued"}` |
| `GET`  | `/api/status/{job_id}`   | Poll job status  | Returns Redis job hash: `{status, filename, download_url?, error?}`                                                        |
| `GET`  | `/api/events/{job_id}`   | SSE event stream | `text/event-stream`; relays job events, pings keepalive                                                                    |
| `GET`  | `/api/download/{job_id}` | Download ZIP     | Streamed ZIP (spooled to disk); only when `done`; else `409`; `404` if unknown job                                         |

Error codes: `400` (not an image / empty), `413` (over size cap), `404` (unknown job),
`409` (download before completion).

---

## SSE event model

Server-sent events are published on a Redis pubsub channel `events:{job_id}` and relayed
over `GET /api/events/{job_id}`. Each message is `{event, payload}`; the stream sends
`event: <name>` + `data: <json>` frames and closes after `done` or `failed`.

| Event        | Payload                                    | Meaning                  |
| ------------ | ------------------------------------------ | ------------------------ |
| `queued`     | `{}`                                       | Task enqueued            |
| `processing` | `{}`                                       | Worker started resizing  |
| `done`       | `{download_url: "/api/download/{job_id}"}` | Thumbnails ready         |
| `failed`     | `{error: "..."}`                           | Processing error         |
| `ping`       | `{}`                                       | Keepalive heartbeat (1s) |

On connect, the endpoint replays the current job state first, so a client connecting after
completion still receives the terminal `done`/`failed` event.

---

## Storage layout

```
originals/{job_id}/{filename}        # uploaded source image
thumbnails/{job_id}/{size}w.jpg      # 3 thumbnails: 1280w, 640w, 320w
```

- Thumbnails preserve aspect ratio (`Pillow.thumbnail`, LANCZOS), downscale only, and are
  saved as JPEG quality 85. EXIF orientation is applied (`ImageOps.exif_transpose`) so
  phone photos aren't rotated.
- Uploaded filenames are sanitized to a safe basename before use as object keys.
- Buckets are auto-created at API startup (`ensure_buckets`).
- The ZIP is built **on the fly** at download time from the 3 thumbnail objects — no ZIP is
  ever persisted. Upload and download both stream (spooled) to bound memory use.
- Storage is S3-compatible: the `MinioStorage` adapter works against MinIO or any S3 API
  (e.g. AWS S3), switching only via `MINIO_ENDPOINT`/`MINIO_REGION` config.

---

## Job state (Redis)

- **Hash** `job:{job_id}` — `status`, `filename`, optional `download_url` / `error`. Expired
  after `JOB_TTL_HOURS` (default 24h) so Redis doesn't grow unboundedly.
- **Channel** `events:{job_id}` — pubsub events consumed by the SSE endpoint.
- Celery uses Redis as both **broker** and **result backend**.

---

## Runtime config & reliability

- The API and worker share one Docker image and differ only by command, so both processes
  see identical configuration from the same env map (`REDIS_URL`, MinIO endpoint/keys,
  `THUMB_SIZES`, `THUMB_QUALITY`, `MAX_UPLOAD_MB`, `JOB_TTL_HOURS`, `MAX_RETRIES`,
  `CORS_ORIGINS`), sourced from a gitignored root `.env`.
- **Celery reliability config:** `task_acks_late`, `task_reject_on_worker_lost` and
  `worker_prefetch_multiplier=1` (no duplicate/poisoned work on worker loss), `result_expires`
  (1h). The worker retries transient failures with exponential backoff — up to `MAX_RETRIES`
  (env-configurable, default 3) — before marking a job `failed`.

---

## Frontend

A zero-build vanilla page served by any static server:

- Drag & drop / file picker with original preview.
- `POST /api/upload` via `fetch`.
- `EventSource` on `/api/events/{job_id}` updates the status badge
  (queued → processing → done/failed) live.
- On `done`, a **Download ZIP** button appears and fetches the ZIP blob.

API base URL is env-driven: `js/app.js` reads `window.API_BASE_URL` (see `config.js`).
In production `config.js` ships with `""` (same-origin behind a reverse proxy); in local dev
the `serve.py` dev server injects it from `API_BASE_URL` (default `http://localhost:8000`).

---

## Possible next steps

- Load Testing
- Cache the built ZIP in MinIO and serve via presigned URL (skip per-request zipping).
- Split into `api-python` / `worker-rust` / `notify-rust` per the `PLAN.txt` roadmap.
