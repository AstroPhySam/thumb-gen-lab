# Deploy : AWS

The thumbnail service is deployed to AWS (EC2 + Docker Compose + ECR + native S3) with Terraform, Ansible and GitHub Actions. The Terraform root module lives in `infra/aws/`; the app deploy playbook lives in `ansible/deploy.aws.yml`.

## Target architecture

```
Internet ──> Security Group (22/80/443) ──> EC2 t3.micro (Ubuntu 24.04, ap-south-1)
                                              ├─ Caddy container   (80/443, reverse proxy, serves frontend)
                                              ├─ api container     (FastAPI/uvicorn :8000, ECR image)
                                              ├─ worker container  (Celery, ECR image)
                                              └─ redis container   (broker + state, AOF)

                 Amazon S3 -> originals / thumbnails buckets (native S3, no MinIO)
                 AWS ECR   -> thumbgen-api, thumbgen-worker repositories
```

- Compose file: `docker-compose.prod.aws.yml` : images pulled from **ECR**, storage is **native S3**
  via the app's S3-compatible `MinioStorage` adapter (`MINIO_ENDPOINT=s3.<region>.amazonaws.com`).
- No domain → bare HTTP on the instance IP; Caddy `auto_https off`.

## Prerequisites (one-time)

1. **AWS account** : `thumbgen-bootstrap` IAM user with `AdministratorAccess` + access key.
2. **State bucket** : `thumbgen-tfstate-017731864396-ap-south-1-an` (region `ap-south-1`, versioning on).
3. **Two SSH keypairs** : **Admin key** (`aws-server-setup` as `ubuntu`/`admin`) and **Deploy key**
   (`aws-app-deploy` as `deploy`).

## Auth model

| Workflow                             | Credentials                                                              |
| ------------------------------------ | ------------------------------------------------------------------------ |
| `aws-terraform-plan/apply/destroy`   | bootstrap user static keys (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`) |
| `build-push-ecr`                     | **OIDC**, assumes `gh-actions-deploy` role (secret `AWS_ROLE_ARN`)       |
| `aws-server-setup`, `aws-app-deploy` | SSH keys only                                                            |

The first Terraform apply runs on the bootstrap keys and **creates** the OIDC provider + role, the
ECR repos, the S3 buckets, and the app IAM user, so there is no chicken-and-egg.

## GitHub secrets & variables

| Type     | Name                     | Purpose                                                         |
| -------- | ------------------------ | --------------------------------------------------------------- |
| secret   | `AWS_ACCESS_KEY_ID`      | bootstrap user key (terraform workflows)                        |
| secret   | `AWS_SECRET_ACCESS_KEY`  | bootstrap user secret                                           |
| secret   | `SSH_PUBLIC_KEY`         | public admin key → EC2 key pair + `admin` user                  |
| secret   | `SSH_PRIVATE_KEY`        | private admin key (`ubuntu` bootstrap / `admin` SSH)            |
| secret   | `DEPLOY_SSH_PUBLIC_KEY`  | public deploy key → `deploy`'s authorized_keys                  |
| secret   | `DEPLOY_SSH_PRIVATE_KEY` | private deploy key (app deploy SSH)                             |
| secret   | `GH_PAT`                 | fine-grained PAT with **Actions variables/secrets: read/write** |
| variable | `AWS_REGION`             | optional; defaults to `ap-south-1`                              |

### Auto-set by `aws-terraform-apply` (no manual entry)

| Type     | Name                                |
| -------- | ----------------------------------- |
| variable | `AWS_INSTANCE_IP`                   |
| variable | `ECR_REGISTRY`                      |
| variable | `MINIO_REGION`                      |
| variable | `MINIO_BUCKET_ORIGINALS`            |
| variable | `MINIO_BUCKET_THUMBNAILS`           |
| secret   | `MINIO_ACCESS_KEY` (app IAM key)    |
| secret   | `MINIO_SECRET_KEY` (app IAM secret) |
| secret   | `AWS_ROLE_ARN` (OIDC role)          |

## Deployment flow

Run these workflows in order from the Actions tab:

1. **`aws-terraform-plan`** : `terraform fmt/init/validate/plan` (bootstrap keys).
2. **`aws-terraform-apply`** : `terraform apply -auto-approve`, then writes all vars/secrets above via `gh`.
3. **`build-push-ecr`** : OIDC → builds `py-mono` → pushes `thumbgen-api`/`thumbgen-worker` to ECR (tagged `sha` + `latest`).
4. **`aws-server-setup`** with `ssh_user = ubuntu` : hardening + rootless Docker + `awscli` (re-runs use `admin`).
5. **`aws-app-deploy`** : clones the repo to `/opt/thumbgen`, renders the prod `.env` (S3 endpoint/keys, `ECR_REGISTRY`, `DOMAIN`), logs into **ECR** with the app IAM credentials, pulls the images, starts the stack, then health-gates `http://<ip>/healthz`.

### Ansible specifics (`deploy.aws.yml`)

- AWS CLI **v2** is installed from the official installer during server setup (no `awscli` apt package
  on Ubuntu 24.04); `aws ecr get-login-password` feeds `docker login` using the app IAM keys.
- `docker_compose_v2` runs with `build: never`, `pull: always`, `recreate: always`.
- The `env.aws.j2` template renders `MINIO_ENDPOINT/SECURE/REGION`, `MINIO_ACCESS_KEY/SECRET_KEY`,
  `MINIO_BUCKET_*`, `ECR_REGISTRY`, `DOMAIN`, `CORS_ORIGINS`.

### Cost

`t3.micro` is free-tier eligible for 12 months; ECR, S3 and a single snapshot are pennies, typically **$0-11/mo**.

## Verification

```bash
curl -s http://<instance_ip>/healthz
curl -s -F "file=@image.jpg" http://<instance_ip>/api/upload
curl -o thumbs.zip http://<instance_ip>/api/download/<job_id>
aws s3 ls s3://<bucket_prefix>-thumbnails-<account_id>/<job_id>/
```

## Tear down

`aws-terraform-destroy` with the `confirm` input exactly `DESTROY`, first empties the S3 buckets
(objects + all versions), then destroys all AWS resources and clears the auto-set vars/secrets.

> See `infra/README.md` for the backend/auth overview and `docs/deploy-civo.md` for the Civo environment.
