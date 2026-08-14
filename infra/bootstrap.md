# One-time bootstrap

Do these once, before running `terraform init`. Steps 2-3 you can do in the
Civo Dashboard instead of the CLI.

## 1. SSH keypairs (local)

**Admin key** (used by root bootstrap, then the `admin` user):

```powershell
ssh-keygen -t ed25519 -f "$HOME\.ssh\civo-thumbgen" -C "thumbgen-admin"
```

The **public** key is referenced by `ssh_public_key_path` in `terraform.tfvars`
(use an **absolute path** — Terraform's `file()` does not expand `~`, e.g.
`C:/Users/<you>/.ssh/civo-thumbgen.pub` or `/home/<you>/.ssh/civo-thumbgen.pub`).
The **private** key stays local and is stored as the `SSH_PRIVATE_KEY` secret for
the `admin` user (never commit it).

**Deploy key** (used by the `deploy` user for App Deploy only):

```powershell
ssh-keygen -t ed25519 -f "$HOME\.ssh\civo-thumbgen-deploy" -C "thumbgen-deploy"
```

Its **public** half becomes the `DEPLOY_SSH_PUBLIC_KEY` secret (Ansible installs
it into `/home/deploy/.ssh/authorized_keys`); its **private** half becomes the
`DEPLOY_SSH_PRIVATE_KEY` secret that the App Deploy workflow uses. `deploy` has
**no sudo** — it only talks to the rootless Docker socket.

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
- `SSH_PUBLIC_KEY` — the **public** admin key referenced by `ssh_public_key_path`
  (workflows write it to a temp file; Terraform never sees a path in tfvars). It
  is installed into the `admin` user's `authorized_keys` during hardening.
- `DEPLOY_SSH_PUBLIC_KEY` — the **public** half of the deploy keypair, installed
  into `/home/deploy/.ssh/authorized_keys` during hardening.
- `DEPLOY_SSH_PRIVATE_KEY` — the **private** half of the deploy keypair, used by
  the App Deploy workflow to connect as `deploy` (no sudo).
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
- `SSH_PRIVATE_KEY` (secret) — the **private admin** key matching
  `ssh_public_key_path` (`~/.ssh/civo-thumbgen`). The Server Setup workflow uses
  it to connect as `root` (bootstrap) or `admin` (after hardening).
- `SSH_PUBLIC_KEY` (secret) — the matching **public admin** key. Ansible
  installs it into the `admin` user's `authorized_keys` during hardening.
- `DEPLOY_SSH_PRIVATE_KEY` (secret) — the deploy keypair's **private** half. The
  App Deploy workflow uses it to connect as `deploy` (no sudo).
- `DEPLOY_SSH_PUBLIC_KEY` (secret) — the deploy keypair's **public** half,
  installed into `/home/deploy/.ssh/authorized_keys` during hardening.
- `DOMAIN` (variable, optional) — the prod `.env` `DOMAIN` (domain or instance
  IP). **If unset, the workflow falls back to the instance's public IP**, so
  Caddy serves plain HTTP at `http://<ip>/` until you set a real domain.
- `MINIO_ROOT_USER` (variable, optional — defaults to `minioadmin`) and
  `MINIO_ROOT_PASSWORD` (secret, required) — prod MinIO credentials, rendered
  into the server-side `.env` (never in the repo).

The **App Deploy** workflow connects as `deploy` (no sudo, rootless Docker). The
**Server Setup** workflow takes an `ssh_user` **input** (default `root`): see
"First deploy (bootstrap)" below for when to use `admin` / `deploy`.

Deploy target on the server: `/opt/thumbgen`. The repo's root `.env` (your Civo
creds) is never copied to the server.

### Host hardening (applied by the server-setup playbook)

The `server-setup` workflow hardens the host (idempotent):

- Creates two non-root users (both locked passwords):
  - **`admin`** — the privileged identity. Installed with `SSH_PUBLIC_KEY` and
    granted passwordless sudo (`/etc/sudoers.d/admin`). Used by Server Setup.
  - **`deploy`** — the least-privilege identity. Installed with
    `DEPLOY_SSH_PUBLIC_KEY`, owns `/opt/thumbgen`, drives rootless Docker.
    **No sudo** — App Deploy runs fully non-root.
- Writes `/etc/ssh/sshd_config.d/00-thumbgen-hardening.conf`:
  `PermitRootLogin no`, `PasswordAuthentication no`, `KbdInteractiveAuthentication no`,
  `PubkeyAuthentication yes`, `MaxAuthTries 3`, `AllowUsers admin deploy`.
- Installs **fail2ban** with an sshd jail (ban 10m after 5 failures) — SSH stays
  open to `0.0.0.0/0` because GitHub Actions runners use dynamic IPs, so IP
  allowlisting would break CI; fail2ban + key-only auth is the mitigation.

### Rootless Docker (set up by the server-setup playbook)

The Docker engine runs **rootless** for the `deploy` user — no root daemon:

- Rootless `dockerd` runs as `deploy` via a systemd user unit
  (`systemctl --user docker`), kept alive across reboots with
  `loginctl enable-linger deploy`. Socket: `/run/user/<uid>/docker.sock`.
- Rootful `docker.service`/`docker.socket` are stopped and disabled.
- Kernel tuning applied and persisted in `/etc/sysctl.d/99-thumbgen-rootless.conf`:
  `kernel.unprivileged_userns_clone=1` and
  `net.ipv4.ip_unprivileged_port_start=80` (lets rootless Caddy publish 80/443).
- Storage uses `fuse-overlayfs` (`~/.config/docker/daemon.json`); container
  images and volumes live under the `deploy` user's home, so no host-level
  permission boundaries apply. The app containers themselves also run as an
  unprivileged `appuser` (UID 10001) baked into the image.

The deploy playbook talks to the rootless daemon by setting
`DOCKER_HOST=unix:///run/user/<uid>/docker.sock` for all `docker` commands.

### First deploy (bootstrap)

1. Add the deploy-key secrets (`DEPLOY_SSH_PUBLIC_KEY`,
   `DEPLOY_SSH_PRIVATE_KEY`) to the repo.
2. Run the **Server Setup** workflow with `ssh_user` = **`root`**. This creates
   `admin` (with your SSH key) and `deploy` (with the deploy key), provisions
   rootless Docker, installs git, owns `/opt/thumbgen`, and hardens sshd.
3. After that run succeeds, `root` can no longer log in over SSH
   (`PermitRootLogin no`, `AllowUsers admin deploy`).
4. Run **App Deploy** — connects as `deploy` with `DEPLOY_SSH_PRIVATE_KEY`, no
   sudo, and brings the stack up via the rootless Docker socket.
5. For every later **Server Setup** change, use `ssh_user` = **`admin`**
   (the privileged identity). For every later **App Deploy**, just run it.

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

- Ubuntu images on Civo boot with `root`; Server Setup migrates to the
  `admin` (privileged) + `deploy` (non-root) split and disables root SSH.
- Manual SSH after bootstrap: `ssh -i ~/.ssh/civo-thumbgen admin@<ip>` for
  administration, `ssh -i ~/.ssh/civo-thumbgen-deploy deploy@<ip>` for app
  work. `deploy` has no sudo.
- The firewall allows SSH (22), HTTP (80) and HTTPS (443) ingress from
  anywhere; all other inbound traffic is dropped. Redis/MinIO/API ports are not
  exposed. SSH stays on `0.0.0.0/0` because GitHub Actions runners have dynamic
  IPs; fail2ban + key-only auth compensate.
