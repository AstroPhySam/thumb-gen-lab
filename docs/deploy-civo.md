# Deploy : Civo

How the thumbnail service is deployed to a single Civo instance with Terraform, Ansible and GitHub Actions. The Terraform root module lives in `infra/civo/`; the app deploy playbooks live in `ansible/` (`setup.yml`, `deploy.civo.yml`).

## Target architecture

```
GitHub Actions â”€â”€> Civo instance (Ubuntu 24.04, g4s.small)
                      â”œâ”€ Caddy container      (80/443, reverse proxy, serves frontend)
                      â”œâ”€ api container        (FastAPI/uvicorn :8000)
                      â”œâ”€ worker container     (Celery, Pillow)
                      â”œâ”€ minio container      (S3-compatible object storage)
                      â””â”€ redis container      (broker + state, AOF)
```

- Compose files: `docker-compose.dev.yml` (local) and `docker-compose.prod.civo.yml` (server).
- `api` and `worker` share one Docker image built **on the server** via `build: always`.
- DNS/TLS is optional â€” with a domain pointed at the instance, Caddy auto-provisions
  Let's Encrypt certs; with a bare IP it serves plain HTTP (`auto_https off`).

## Prerequisites (one-time)

1. **Civo account** â€” API key from the Civo dashboard â†’ `CIVO_TOKEN`.
2. **Object Store** â€” create the `infrastates` bucket (S3-compatible) and an access/secret key pair for Terraform state.
3. **Two SSH keypairs**:
   - **Admin key** â€” used by `civo-server-setup` (`root` bootstrap / `admin` re-runs).
   - **Deploy key** â€” used by `civo-app-deploy` to connect as the `deploy` user (no sudo).

## GitHub secrets & variables

| Type     | Name                     | Purpose                                                                         |
| -------- | ------------------------ | ------------------------------------------------------------------------------- |
| secret   | `CIVO_TOKEN`             | Civo API key (Terraform workflows)                                              |
| secret   | `AWS_ACCESS_KEY_ID`      | Civo Object Store key (Terraform state)                                         |
| secret   | `AWS_SECRET_ACCESS_KEY`  | Civo Object Store secret                                                        |
| secret   | `SSH_PUBLIC_KEY`         | public admin key â†’ installed into `admin`'s authorized_keys                     |
| secret   | `SSH_PRIVATE_KEY`        | private admin key (root/bootstrap SSH)                                          |
| secret   | `DEPLOY_SSH_PUBLIC_KEY`  | public deploy key â†’ `deploy`'s authorized_keys                                  |
| secret   | `DEPLOY_SSH_PRIVATE_KEY` | private deploy key (app deploy SSH)                                             |
| secret   | `GH_PAT`                 | fine-grained PAT with **Actions variables: read/write** (records `INSTANCE_IP`) |
| variable | `INSTANCE_IP`            | set automatically by `civo-terraform-apply`                                     |

## Deployment flow

Run these workflows in order from the Actions tab:

1. **`civo-terraform-plan`** â€” `terraform fmt/init/validate/plan`.
2. **`civo-terraform-apply`** â€” `terraform apply -auto-approve`, then records the instance IP into the `INSTANCE_IP` repo variable.
3. **`civo-server-setup`** with `ssh_user = root` â€” creates `admin`/`deploy` users, hardens SSH, installs fail2ban, bootstraps rootless Docker. Re-runs use `ssh_user = admin`.
4. **`civo-app-deploy`** â€” clones the repo to `/opt/thumbgen`, renders the prod `.env`, builds + starts the stack via rootless Docker, then health-gates `http://<ip>/healthz`.

### Host hardening (Ansible `tasks/harden.yml`)

- Two non-root users with locked passwords: `admin` (passwordless sudo) and `deploy` (**no sudo**, drives rootless Docker).
- `/etc/ssh/sshd_config.d/00-thumbgen-hardening.conf`: `PermitRootLogin no`, `PasswordAuthentication no`, `MaxAuthTries 3`, `AllowUsers admin deploy`.
- fail2ban sshd jail (ban 10m after 5 failures) â€” SSH stays open to `0.0.0.0/0` because GitHub Actions runners use dynamic IPs.

### Rootless Docker (Ansible `tasks/docker.yml`)

- Rootless `dockerd` runs as `deploy` via a systemd user unit, kept alive with `loginctl enable-linger deploy`. Socket: `/run/user/<uid>/docker.sock`.
- Rootful `docker.service`/`docker.socket` stopped and disabled.
- Kernel tuning persisted in `/etc/sysctl.d/99-thumbgen-rootless.conf` (`kernel.unprivileged_userns_clone=1`, `net.ipv4.ip_unprivileged_port_start=80`).
- Storage driver `fuse-overlayfs`; moby rootless helper scripts pinned to v24.0.7.

## Local development

```powershell
docker compose -f docker-compose.dev.yml up -d --build
python frontend/serve.py   # open http://localhost:8080
```

Stop: `docker compose -f docker-compose.dev.yml down` (keeps data); wipe:
`docker compose -f docker-compose.dev.yml down -v`.

## Verification

```bash
curl -s http://<instance_ip>/healthz                # expect 200
curl -s -F "file=@image.jpg" http://<instance_ip>/api/upload
curl -o thumbs.zip http://<instance_ip>/api/download/<job_id>
```

## Tear down

`civo-terraform-destroy` with the `confirm` input exactly `DESTROY` â€” destroys the instance and clears the `INSTANCE_IP` variable.

> See `infra/README.md` for the backend/auth overview and `docs/deploy-aws.md` for the AWS environment.
