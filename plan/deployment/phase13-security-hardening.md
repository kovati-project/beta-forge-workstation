# Phase 13 — Security Hardening

**Services:** Authentik IdP (`:9080`), Authentik Worker, authentik-postgres, authentik-redis  
**Compose file:** `docker/compose.auth.yml`  
**Scripts:** `deploy-phase13.sh`, `validate-phase13.sh`, `security-hardening-audit.sh`  
**Config template:** `configs/authentik/.env.example`

---

## Prerequisites

- [ ] Phase 09 deployed — Storage stack running (Authentik uses its own Postgres, separate from Phase 09 Postgres)
- [ ] Phase 05 deployed — Open WebUI running (primary service being protected)
- [ ] Port check: MinIO S3 API is on host port `9000` — Authentik is mapped to `9080:9000` (container internal still `:9000`; host port is `9080`)

**Phase 01 note:** Caddy reverse proxy / forward auth is deferred (Phase 01 tabled). For now, services are accessible at direct IPs without auth enforcement at the network level. Authentik is deployed and configured so it's ready when Phase 01 is activated.

---

## Step 1 — Generate Secrets

The deploy script auto-generates secrets using `openssl rand`. You can also pre-generate them manually for record-keeping:

```bash
openssl rand -base64 32   # POSTGRES_PASSWORD
openssl rand -base64 32   # REDIS_PASSWORD
openssl rand -base64 60   # AUTHENTIK_SECRET_KEY (needs 60 chars)
```

See `configs/authentik/.env.example` for the `.env` format. The deploy script writes `.env` to the project root (`~/ai-workstation/.env`) and sets permissions to `600`.

**Back up `.env` before it's overwritten.** The deploy script skips generation if `.env` already exists — the Postgres password cannot be changed after the database is initialised without wiping the Authentik database.

---

## Step 2 — Create Authentik Data Directories

```bash
ssh kasemo@10.10.10.2 "sudo mkdir -p /data/authentik/{postgres,redis,media,custom-templates} && \
  sudo chmod -R 755 /data/authentik && \
  sudo chown -R kasemo:kasemo /data/authentik"
```

---

## Step 3 — Create Security Networks

Authentik requires the `ai-inference` network (external) to be created before it starts. The deploy script creates all security networks automatically, but you can run it manually:

```bash
ssh kasemo@10.10.10.2 "for net in ai-inference ai-training ai-storage ai-monitoring ai-agents ai-auth; do
  docker network create --driver bridge \$net 2>/dev/null || echo \"exists: \$net\"
done"
```

---

## Step 4 — Deploy

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/deploy-phase13.sh"
```

The script:
1. Creates all 6 security networks
2. Generates `.env` with random secrets (skips if `.env` exists)
3. Adds `.env` to `.gitignore`
4. Creates `/data/authentik/` directories
5. Starts `compose.auth.yml` (Postgres, Redis, Authentik server, Authentik worker)
6. Polls `http://localhost:9080/-/health/live/` — waits up to 60s
7. Prints instructions for Caddy TLS setup (deferred — skip for now)

Authentik takes 30–90s to initialise its database schema on first start. The polling loop handles this.

---

## Step 5 — Initial Authentik Setup

Open `http://10.10.10.2:9080/if/flow/initial-setup/` in a browser.

1. Enter an email address for the admin account
2. Set a strong admin password
3. Click "Complete setup"

This creates the `akadmin` superuser account. You cannot log into Authentik without completing this step.

---

## Step 6 — Configure Applications in Authentik

In the Authentik admin UI (`http://10.10.10.2:9080/if/admin/`):

**Admin → Applications → Create Application** for each service:

| Application | Slug | Launch URL | Protocol |
| ----------- | ---- | ---------- | -------- |
| Open WebUI | `open-webui` | `http://10.10.10.2:3000` | OAuth2/OIDC |
| Grafana | `grafana` | `http://10.10.10.2:3001` | OAuth2/OIDC |
| n8n | `n8n` | `http://10.10.10.2:5678` | OAuth2/OIDC |
| JupyterLab | `jupyterlab` | `http://10.10.10.2:8888` | OAuth2/OIDC |
| Loadout Manager | `loadout` | `http://10.10.10.2:8800` | Proxy |

For each OAuth2 application, create a provider first:
- **Admin → Providers → Create → OAuth2/OpenID Provider**
- Set Redirect URIs to the service callback URL (e.g. `http://10.10.10.2:3000/auth/callback`)
- Set Signing Key to the auto-generated key

---

## Step 7 — Create User Groups

**Admin → Groups → Create:**

| Group | Purpose |
| ----- | ------- |
| `admins` | Full access to all services, MFA required |
| `users` | Standard access to inference, WebUI, voice |
| `readonly` | Grafana/Langfuse read-only monitoring access |

---

## Step 8 — Enable MFA for Admin Group

**Admin → Groups → admins → Edit → Add Policy: TOTP Authenticator**

After assigning, the next admin login will require TOTP setup. Use any TOTP app (Authy, Google Authenticator, etc.).

---

## Step 9 — Configure Host Firewall (UFW)

```bash
ssh kasemo@10.10.10.2 "sudo ufw default deny incoming && \
  sudo ufw default allow outgoing && \
  sudo ufw allow from 192.168.1.0/24 to any port 22 comment 'SSH management' && \
  sudo ufw allow 3000/tcp comment 'Open WebUI' && \
  sudo ufw allow 3001/tcp comment 'Grafana' && \
  sudo ufw allow 5678/tcp comment 'n8n' && \
  sudo ufw allow 9080/tcp comment 'Authentik' && \
  sudo ufw allow 8800/tcp comment 'Loadout Manager' && \
  echo 'y' | sudo ufw enable"
```

**UFW + Docker note:** Docker bypasses UFW by default via iptables rules. UFW rules above control direct host port access but won't block traffic routed through Docker networks. Full containment requires configuring `/etc/ufw/after.rules` to restrict the Docker bridge. See the Phase 13 brief for the full iptables approach if needed.

Verify:
```bash
ssh kasemo@10.10.10.2 "sudo ufw status verbose"
```

---

## Step 10 — Enable auditd (Optional)

```bash
ssh kasemo@10.10.10.2 "sudo apt install -y auditd && sudo systemctl enable --now auditd"

# Audit privileged commands and Docker daemon interactions
ssh kasemo@10.10.10.2 "sudo auditctl -a always,exit -F arch=b64 -S execve -F uid=0 -k root_commands"
ssh kasemo@10.10.10.2 "sudo auditctl -w /var/run/docker.sock -p rwxa -k docker_socket"
```

---

## Step 11 — Run Security Audit

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/security-hardening-audit.sh"
```

The audit checks: container privilege levels, Docker daemon configuration, SSH hardening, UFW status, secret exposure in compose files.

---

## Step 12 — Validate

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase13.sh"
```

Expected: automated checks pass (Authentik API on `:9080`, secrets in `.env`, networks present, compose files valid, storage directories ready).

---

## Quick Reference

```bash
# Authentik health
ssh kasemo@10.10.10.2 "curl -sf http://localhost:9080/-/health/live/ && echo OK"

# View Authentik logs
ssh kasemo@10.10.10.2 "docker logs -f authentik"

# Restart Authentik (e.g. after .env change)
ssh kasemo@10.10.10.2 "docker compose -f ~/ai-workstation/docker/compose.auth.yml restart authentik authentik-worker"

# Rotate Authentik secret key (requires full stack restart — invalidates all sessions)
ssh kasemo@10.10.10.2 "openssl rand -base64 60 | tr -d '\n' > /tmp/new_key && \
  sed -i \"s/AUTHENTIK_SECRET_KEY=.*/AUTHENTIK_SECRET_KEY=\$(cat /tmp/new_key)/\" ~/ai-workstation/.env && \
  docker compose -f ~/ai-workstation/docker/compose.auth.yml up -d"

# Connect to Authentik's Postgres DB
ssh kasemo@10.10.10.2 "docker exec -it authentik-postgres psql -U authentik -d authentik"

# UFW status
ssh kasemo@10.10.10.2 "sudo ufw status verbose"
```

---

## Troubleshooting

| Symptom | Check |
| ------- | ----- |
| Port conflict on `:9000` | Authentik host port is `9080` (MinIO S3 is on `9000`) — never map Authentik to `9000:9000` |
| Authentik returns 502 Bad Gateway | Worker not running — `docker ps \| grep authentik-worker` |
| `.env` not loaded at startup | `deploy-phase13.sh` uses `export $(cat .env \| xargs)` — must be run from the project root (`~/ai-workstation/`) |
| Database schema migration running | Authentik logs will say "Running migrations" — this is normal on first start; wait for it to complete (up to 2min) |
| Admin account already exists error | Initial setup already completed — log in at `http://10.10.10.2:9080/if/flow/initial-setup/` with existing credentials |
| Caddy forward auth references | Phase 01 is tabled — `configs/caddy/Caddyfile.security` exists for reference but Caddy is not running; deploy-phase13.sh prints Caddy instructions but they are not required for Phase 13 to be complete |
