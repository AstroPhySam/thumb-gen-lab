# One-time bootstrap

Do these once, before running `terraform init`. Steps 2-3 you can do in the
Civo Dashboard instead of the CLI.

## 1. SSH keypair (local)

```powershell
ssh-keygen -t ed25519 -f "$HOME\.ssh\civo-thumbgen" -C "thumbgen-deploy"
```

The **public** key is referenced by `ssh_public_key_path` in `terraform.tfvars`
(use an **absolute path** — Terraform's `file()` does not expand `~`, e.g.
`C:/Users/<you>/.ssh/civo-thumbgen.pub` or `/home/<you>/.ssh/civo-thumbgen.pub`).
The **private** key stays local and will be used by Ansible / GitHub Actions
(never commit it).

## 2. Terraform state object store (Civo Dashboard)

- Create an **Object Store** bucket named exactly **`infrastates`** in
  region **`MUM1`** (must match `backend "s3"` in `providers.tf`).
- Create an **Object Store credential** for it (e.g. `InfraAsCode`) and note
  the Access Key ID and Secret Key. Civo shows the secret only once.

If you pick a different region or bucket name, update `providers.tf`
(`endpoints.s3`, `region`, `bucket`) to match.

## 3. Credentials — shell env or credentials file (never in repo files)

Option A — per-shell env vars:

```powershell
$env:CIVO_TOKEN             = "<civo api key>"
$env:AWS_ACCESS_KEY_ID      = "<infrastates access key>"
$env:AWS_SECRET_ACCESS_KEY  = "<infrastates secret key>"
```

Option B — persist across shells via `%UserProfile%\.aws\credentials`:

```ini
[default]
aws_access_key_id = <infrastates access key>
aws_secret_access_key = <infrastates secret key>
```

These are the Civo Object Store keys, not AWS. Terraform's `s3` backend is
S3-compatible and talks only to the Civo endpoint configured in `providers.tf`.

## 4. GitHub Actions (optional but recommended)

The workflow `.github/workflows/terraform.yml` runs `plan` / `apply` / `destroy`
via manual dispatch (`workflow_dispatch`). Add these repo **secrets** in
GitHub → Settings → Secrets and variables → Actions:

- `CIVO_TOKEN` — Civo API key
- `AWS_ACCESS_KEY_ID` — Civo Object Store access key (same as step 3)
- `AWS_SECRET_ACCESS_KEY` — Civo Object Store secret key
- `SSH_PUBLIC_KEY` — the **public** key referenced by `ssh_public_key_path`
  (workflow writes it to a temp file; Terraform never sees a path in tfvars)

Run it from the Actions tab: choose `apply` or `destroy`. Destroy requires the
`confirm` input to be exactly `DESTROY`. Non-secret vars (`region`,
`instance_size`, …) use their Terraform defaults in CI.

### Deploy workflow (`.github/workflows/deploy.yml`)

Deploys the app stack to the instance with Ansible (Docker + compose build + up,
then a health check). Triggered manually from the Actions tab. It reads the
instance IP from Terraform state, so run `terraform apply` first.

Additional repo **secrets / variables** for deploy:

- `SSH_PRIVATE_KEY` (secret) — the **private** key matching `ssh_public_key_path`
  (`~/.ssh/civo-thumbgen`). CI uses it to SSH into the instance as `root`.
- `DOMAIN` (variable, optional) — the prod `.env` `DOMAIN` (domain or instance
  IP). **If unset, the workflow falls back to the instance's public IP**, so
  Caddy serves plain HTTP at `http://<ip>/` until you set a real domain.
- `MINIO_ROOT_USER` (variable, optional — defaults to `minioadmin`) and
  `MINIO_ROOT_PASSWORD` (secret, required) — prod MinIO credentials, rendered
  into the server-side `.env` (never in the repo).

Deploy target on the server: `/opt/thumbgen`. The repo's root `.env` (your Civo
creds) is never copied to the server.

## 5. Ready

```powershell
cd infra
Copy-Item terraform.tfvars.example terraform.tfvars   # then edit
terraform init
terraform plan
terraform apply          # capture the instance_public_ip output
terraform output instance_public_ip
```

Tear everything down with `terraform destroy`.

## Domain note

No domain yet? Set the prod `.env` `DOMAIN` to the instance's **public IP** —
Caddy then serves plain HTTP at `http://<ip>/` (no cert attempt for IPs).

When you get a domain: point a DNS `A` record at the instance IP and set
`DOMAIN=<your.domain>` in the prod `.env`. Caddy auto-provisions the
Let's Encrypt cert (firewall already allows 80/443). No code change needed.

## Notes

- Default SSH user for Ubuntu images on Civo is `root`.
- The firewall allows SSH (22), HTTP (80) and HTTPS (443) ingress from
  anywhere; all other inbound traffic is dropped. Redis/MinIO/API ports are not
  exposed.
