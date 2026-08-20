# Image Thumbnail Generation Lab

A full-stack, cloud-native lab: an image-thumbnail service deployed end-to-end on two
independent cloud environments: **Civo** and **AWS** with **Terraform** (IaC), **Ansible**
(config mgmt + app deploy), **Docker Compose**, **GitHub Actions** (CI/CD), and OIDC-based auth.

The app ingests an image, resizes it to three thumbnails (1280/640/320) with a Celery
worker, and streams progress to the browser over **SSE**, then serves the thumbnails as a ZIP.

## Architecture

| Layer       | Technology                                                                      |
| ----------- | ------------------------------------------------------------------------------- |
| App         | **FastAPI** + **Celery** + **Redis** + **Pillow** (`py-mono/`, uv, Python 3.12) |
| Storage     | S3-compatible: **MinIO** (local/Civo) or native AWS S3                          |
| Frontend    | Vanilla HTML/CSS/JS (`frontend/`, no build step)                                |
| IaC         | Terraform root modules in `infra/civo/` and `infra/aws/`                        |
| Config mgmt | Ansible (hardening, rootless Docker, app deploy)                                |
| CI/CD       | GitHub Actions workflows (all `workflow_dispatch`)                              |

```
Internet ──> Caddy (80/443, reverse proxy, serves frontend)
               ├─ api container (FastAPI/uvicorn :8000)
               ├─ worker container (Celery, Pillow)
               ├─ redis container (broker + state, AOF)
               └─ MinIO (Civo) / AWS S3 (native)
```

## Repo layout

```
├── py-mono/                 # the application (uv project, shared API+worker image)
├── frontend/                # zero-build test page (upload / SSE status / ZIP download)
├── infra/
│   ├── civo/                # Terraform root module (Civo provider + object-store backend)
│   └── aws/                 # Terraform root module (AWS provider + S3 backend, OIDC, ECR)
├── ansible/                 # setup + deploy playbooks, hardening, rootless Docker, env templates
├── .github/
│   ├── actions/ansible-run/ # reusable action (SSH + Ansible runner)
│   └── workflows/           # terraform plan/apply/destroy + server-setup + app-deploy (x2 clouds)
├── docker-compose.dev.yml        # local dev (api/worker/minio/redis)
├── docker-compose.prod.civo.yml  # Civo prod (build on server)
├── docker-compose.prod.aws.yml   # AWS prod (ECR images + native S3)
└── docs/                    # arch doc + per-environment deploy runbooks
```

## Quick start (local)

```powershell
docker compose -f docker-compose.dev.yml up -d --build
python frontend/serve.py   # open http://localhost:8080
```

## Deploy runbooks

- [`docs/arch-01-py-mono.md`](docs/arch-01-py-mono.md) : app architecture
- [`docs/deploy-civo.md`](docs/deploy-civo.md) : Civo environment
- [`docs/deploy-aws.md`](docs/deploy-aws.md) : AWS environment
- [`infra/README.md`](infra/README.md) : Terraform modules, backends, auth overview

Both environments are deployed from the Actions tab: `*-terraform-plan` →
`*-terraform-apply` → `*-server-setup` → `*-app-deploy`, and torn down with
`*-terraform-destroy` (`confirm = DESTROY`). See the runbooks for prerequisites,
secrets, and step-by-step flows.
