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

There are four single-purpose workflows under `.github/workflows/`, all triggered
manually from the Actions tab:

- **Terraform Plan** — `terraform fmt/init/validate/plan`.
- **Terraform Apply** — `terraform apply`, then records the instance IP into the
  `INSTANCE_IP` repo variable (needs `GH_PAT`, below).
- **Terraform Destroy** — `terraform destroy`, then clears `INSTANCE_IP`.
  Requires the `confirm` input to be exactly `DESTROY`.
- **Deploy** — runs Ansible against the IP stored in `INSTANCE_IP`.

Add these repo **secrets** in GitHub → Settings → Secrets and variables →
Actions:

- `CIVO_TOKEN` — Civo API key (Terraform workflows only)
- `AWS_ACCESS_KEY_ID` — Civo Object Store access key, same as step 3
- `AWS_SECRET_ACCESS_KEY` — Civo Object Store secret key
- `SSH_PUBLIC_KEY` — the **public** key referenced by `ssh_public_key_path`
  (workflows write it to a temp file; Terraform never sees a path in tfvars)
- `GH_PAT` — a **fine-grained personal access token** with
  **Repository → Actions variables: Read and write** (Metadata read is implied).
  `GITHUB_TOKEN` cannot write Actions variables (403), so Terraform Apply/Destroy
  use this PAT to record/clear the `INSTANCE_IP` repo variable that Deploy reads.

Non-secret vars (`region`, `instance_size`, …) use their Terraform defaults in CI.

Run order: **Terraform Apply** first (creates `INSTANCE_IP`), then **Deploy**.

### Deploy workflow (`.github/workflows/deploy.yml`)

Deploys the app stack to the instance with Ansible (Docker + compose build + up,
then a health check). It reads the instance IP from the `INSTANCE_IP` repo
variable, so run **Terraform Apply** first. It needs no Terraform tooling and no
cloud credentials.

Additional repo **secrets / variables** for deploy:

- `INSTANCE_IP` (variable, set by Terraform Apply) — the instance public IP.
- `SSH_PRIVATE_KEY` (secret) — the **private** key matching `ssh_public_key_path`
  (`~/.ssh/civo-thumbgen`). CI uses it to SSH into the instance. Works for both
  the `root` bootstrap run and the `deploy` user afterwards (same keypair).
- `SSH_PUBLIC_KEY` (secret) — the matching **public** key. Ansible installs it
  into the dedicated `deploy` user's `authorized_keys` during host hardening.
- `DOMAIN` (variable, optional) — the prod `.env` `DOMAIN` (domain or instance
  IP). **If unset, the workflow falls back to the instance's public IP**, so
  Caddy serves plain HTTP at `http://<ip>/` until you set a real domain.
- `MINIO_ROOT_USER` (variable, optional — defaults to `minioadmin`) and
  `MINIO_ROOT_PASSWORD` (secret, required) — prod MinIO credentials, rendered
  into the server-side `.env` (never in the repo).

The workflow takes an `ssh_user` **input** (default `root`): see
"First deploy (bootstrap)" below for when to flip it to `deploy`.

Deploy target on the server: `/opt/thumbgen`. The repo's root `.env` (your Civo
creds) is never copied to the server.

### Host hardening (applied by the deploy playbook)

On every deploy, after the stack comes up, the playbook hardens the host
(idempotent):

- Creates a dedicated non-root user **`deploy`** (locked password, member of
  the `docker` group) and grants it passwordless sudo (needed for Ansible
  `become`). Sudo + docker-group membership is root-equivalent — this keeps
  day-to-day SSH off `root` without introducing a second failure mode.
- Installs `SSH_PUBLIC_KEY` into `/home/deploy/.ssh/authorized_keys`.
- Writes `/etc/ssh/sshd_config.d/00-thumbgen-hardening.conf`:
  `PermitRootLogin no`, `PasswordAuthentication no`, `KbdInteractiveAuthentication no`,
  `PubkeyAuthentication yes`, `MaxAuthTries 3`, `AllowUsers deploy`.
- Installs **fail2ban** with an sshd jail (ban 10m after 5 failures) — SSH stays
  open to `0.0.0.0/0` because GitHub Actions runners use dynamic IPs, so IP
  allowlisting would break CI; fail2ban + key-only auth is the mitigation.

### First deploy (bootstrap) — one-time migration to `deploy`

1. Run the **Deploy** workflow with `ssh_user` = **`root`**. This deploys the
   stack, creates the `deploy` user, installs your SSH key, and hardens sshd.
2. After that run succeeds, `root` can no longer log in over SSH
   (`PermitRootLogin no`, `AllowUsers deploy`).
3. For **every later deploy**, run the workflow with `ssh_user` = **`deploy`**.
   `deploy` (same keypair, via sudo) keeps Ansible working.

If a deploy ever fails to connect as `deploy`, use the Civo dashboard console
(or re-run with `ssh_user` = `root` before the sshd drop-in exists) to recover.

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

- Ubuntu images on Civo boot with `root`; the deploy playbook migrates to a
  dedicated `deploy` user and disables root SSH after the first run.
- Manual SSH after the first deploy: `ssh -i ~/.ssh/civo-thumbgen deploy@<ip>`.
- The firewall allows SSH (22), HTTP (80) and HTTPS (443) ingress from
  anywhere; all other inbound traffic is dropped. Redis/MinIO/API ports are not
  exposed. SSH stays on `0.0.0.0/0` because GitHub Actions runners have dynamic
  IPs; fail2ban + key-only auth compensate.
