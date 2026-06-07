# GHC Task: Phase 13 — Security Hardening
**Brief ID:** P13-001  
**Source doc:** `/plan/steps/13-security-hardening.md`  
**Write feedback to:** `/plan/ghc-feedback/phase13-security-hardening.md`

---

## Context

Phases 01–12 are complete. The workstation is running the full stack with placeholder credentials and no firewall. Phase 01 (Caddy reverse proxy) remains tabled — Authentik will be deployed and usable for services that support native OIDC (Grafana, n8n, JupyterLab), but the Caddy forward-auth integration that protects all services behind SSO must wait until Phase 01 is implemented. Document this gap clearly.

**Port conflict to fix:** The source doc deploys Authentik on port 9000, which MinIO already occupies (Phase 09). Remap Authentik to `9080` (HTTP) and `9443` (HTTPS).

---

## Scope

Create:
1. **`docker/compose.auth.yml`** — Authentik IdP (server + worker + PostgreSQL + Redis)
2. **`configs/authentik/.env.example`** — template for required Authentik secrets (not the real values)
3. **`scripts/setup-secrets.sh`** — create Docker secrets from generated values; idempotent
4. **`scripts/setup-ufw.sh`** — UFW firewall rules locking down all ports to jumpbox IP
5. **`scripts/setup-auditd.sh`** — auditd rules for Docker socket, model access, and config changes
6. **`scripts/deploy-phase13.sh`** — generate secrets, start Authentik, run UFW and auditd setup
7. **`scripts/validate-phase13.sh`** — security state checks; exits non-zero on failure

**Not in scope:** Caddy forward-auth integration (requires Phase 01), mTLS between services, HashiCorp Vault (optional — Docker secrets is sufficient for now), BMC hardening (manual procedure, documented in notes).

---

## Step 1 — `docker/compose.auth.yml`

Authentik requires four services: `authentik-server`, `authentik-worker`, `authentik-db` (PostgreSQL), and `authentik-redis`.

Use the upstream Authentik compose structure with these changes:
- **Remap ports:** `9080:9000` (HTTP) and `9443:9443` (HTTPS) — avoids conflict with MinIO on `9000`
- **Use named volumes** for `authentik-db` and `authentik-redis` data
- All secrets via environment variables sourced from a `.env` file (not hardcoded)
- Required env vars: `AUTHENTIK_SECRET_KEY`, `AUTHENTIK_POSTGRESQL__PASSWORD`, `PG_PASS` (must match between server and db services)

Example structure:
```yaml
services:
  authentik-db:
    image: postgres:16-alpine
    container_name: authentik-db
    restart: unless-stopped
    environment:
      - POSTGRES_USER=authentik
      - POSTGRES_PASSWORD=${PG_PASS}
      - POSTGRES_DB=authentik
    volumes:
      - authentik-db-data:/var/lib/postgresql/data

  authentik-redis:
    image: redis:7-alpine
    container_name: authentik-redis
    restart: unless-stopped
    volumes:
      - authentik-redis-data:/data

  authentik-server:
    image: ghcr.io/goauthentik/server:latest
    container_name: authentik-server
    restart: unless-stopped
    command: server
    ports:
      - "9080:9000"
      - "9443:9443"
    environment:
      - AUTHENTIK_REDIS__HOST=authentik-redis
      - AUTHENTIK_POSTGRESQL__HOST=authentik-db
      - AUTHENTIK_POSTGRESQL__USER=authentik
      - AUTHENTIK_POSTGRESQL__NAME=authentik
      - AUTHENTIK_POSTGRESQL__PASSWORD=${PG_PASS}
      - AUTHENTIK_SECRET_KEY=${AUTHENTIK_SECRET_KEY}
    depends_on:
      - authentik-db
      - authentik-redis
    volumes:
      - authentik-media:/media
      - authentik-templates:/templates

  authentik-worker:
    image: ghcr.io/goauthentik/server:latest
    container_name: authentik-worker
    restart: unless-stopped
    command: worker
    environment:
      - AUTHENTIK_REDIS__HOST=authentik-redis
      - AUTHENTIK_POSTGRESQL__HOST=authentik-db
      - AUTHENTIK_POSTGRESQL__USER=authentik
      - AUTHENTIK_POSTGRESQL__NAME=authentik
      - AUTHENTIK_POSTGRESQL__PASSWORD=${PG_PASS}
      - AUTHENTIK_SECRET_KEY=${AUTHENTIK_SECRET_KEY}
    depends_on:
      - authentik-db
      - authentik-redis
    volumes:
      - authentik-media:/media
      - /var/run/docker.sock:/var/run/docker.sock

volumes:
  authentik-db-data:
  authentik-redis-data:
  authentik-media:
  authentik-templates:
```

Do not include `version: '3.8'`.

---

## Step 2 — `configs/authentik/.env.example`

```bash
# Copy to configs/authentik/.env and fill in values
# Generate with: openssl rand -base64 36 | tr -d '\n'

PG_PASS=change-this-to-a-random-password
AUTHENTIK_SECRET_KEY=change-this-to-a-60-char-random-key
```

The deploy script generates real values and writes them to `configs/authentik/.env` (gitignored). The `.env.example` is committed; `.env` is not.

---

## Step 3 — `scripts/setup-secrets.sh`

Idempotent script — skips creation if a secret already exists.

```bash
#!/usr/bin/env bash
set -euo pipefail

secret_exists() { docker secret inspect "$1" &>/dev/null; }

create_secret() {
    local name=$1 value=$2
    if secret_exists "$name"; then
        echo "  Secret '$name' already exists, skipping."
    else
        echo "$value" | docker secret create "$name" -
        echo "  Created secret: $name"
    fi
}

echo "=== Creating Docker Secrets ==="

# Prompt for values or generate them
MINIO_PASS=$(openssl rand -hex 24)
WEBUI_KEY=$(openssl rand -hex 32)
N8N_KEY=$(openssl rand -hex 16)

create_secret minio_password       "$MINIO_PASS"
create_secret webui_secret_key     "$WEBUI_KEY"
create_secret n8n_encryption_key   "$N8N_KEY"

echo ""
echo "Secrets created. Update compose files to use *_FILE variants:"
echo "  MINIO_ROOT_PASSWORD_FILE=/run/secrets/minio_password"
echo "  WEBUI_SECRET_KEY_FILE=/run/secrets/webui_secret_key"
echo ""
echo "NOTE: Docker secrets require Swarm mode. For non-Swarm use,"
echo "keep secrets in a restricted .env file (chmod 600)."
```

---

## Step 4 — `scripts/setup-ufw.sh`

Lock all service ports to the jumpbox IP (10.10.10.1). Preserves SSH access.

```bash
#!/usr/bin/env bash
set -euo pipefail

JUMPBOX_IP="10.10.10.1"

echo "=== Configuring UFW Firewall ==="

sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH — allow from management VLAN and jumpbox
sudo ufw allow from "$JUMPBOX_IP" to any port 22
sudo ufw allow from 192.168.1.0/24 to any port 22   # management network

# AI services — jumpbox only
for PORT in 3000 3001 3002 3003 5678 6333 6334 7860 8000 8001 8002 \
            8081 8188 8189 8190 8800 8888 8989 9001 9080 9091 9099 \
            9100 9400 11434; do
    sudo ufw allow from "$JUMPBOX_IP" to any port "$PORT"
done

# TTS/STT
sudo ufw allow from "$JUMPBOX_IP" to any port 5000

sudo ufw --force enable
echo ""
sudo ufw status numbered
```

---

## Step 5 — `scripts/setup-auditd.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "=== Configuring auditd ==="

sudo apt install -y auditd audispd-plugins

# Audit rules
sudo auditctl -w /var/run/docker.sock -p rwa  -k docker_socket
sudo auditctl -w /data/models          -p r   -k model_access
sudo auditctl -w /etc/docker           -p rwa -k docker_config
sudo auditctl -w /home/kasemo/ai-workstation/docker -p rwa -k compose_changes
sudo auditctl -w /home/kasemo/ai-workstation/loadout-manager/profiles.yaml -p rwa -k loadout_changes

# Persist rules across reboots
cat <<'EOF' | sudo tee /etc/audit/rules.d/ai-workstation.rules
-w /var/run/docker.sock -p rwa -k docker_socket
-w /data/models -p r -k model_access
-w /etc/docker -p rwa -k docker_config
-w /home/kasemo/ai-workstation/docker -p rwa -k compose_changes
-w /home/kasemo/ai-workstation/loadout-manager/profiles.yaml -p rwa -k loadout_changes
EOF

sudo systemctl enable --now auditd
sudo service auditd restart

echo "auditd configured. Query with: ausearch -k docker_socket"
```

---

## Step 6 — `scripts/deploy-phase13.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$REPO_ROOT/configs/authentik/.env"

echo "=== Phase 13: Security Hardening ==="

# [1/4] Generate Authentik secrets if not present
if [[ ! -f "$ENV_FILE" ]]; then
    echo "[1/4] Generating Authentik secrets..."
    mkdir -p "$REPO_ROOT/configs/authentik"
    cat > "$ENV_FILE" <<EOF
PG_PASS=$(openssl rand -base64 36 | tr -d '\n')
AUTHENTIK_SECRET_KEY=$(openssl rand -base64 60 | tr -d '\n')
EOF
    chmod 600 "$ENV_FILE"
    echo "  Secrets written to $ENV_FILE (chmod 600, do not commit)"
else
    echo "[1/4] Authentik secrets already present."
fi

# [2/4] Start Authentik
echo "[2/4] Starting Authentik..."
docker compose -f "$REPO_ROOT/docker/compose.auth.yml" \
    --env-file "$ENV_FILE" up -d

# [3/4] UFW
echo "[3/4] Configuring firewall..."
bash "$REPO_ROOT/scripts/setup-ufw.sh"

# [4/4] auditd
echo "[4/4] Configuring auditd..."
bash "$REPO_ROOT/scripts/setup-auditd.sh"

echo ""
echo "=== Phase 13 deployed ==="
echo "Authentik setup: http://10.10.10.2:9080/if/flow/initial-setup/"
echo ""
echo "Next steps (manual):"
echo "  1. Create Authentik admin account at the setup URL above"
echo "  2. Configure OIDC applications for Grafana and n8n"
echo "  3. Enable TOTP MFA for the admin group"
echo "  4. BMC hardening — see plan/steps/13-security-hardening.md Step 5"
echo ""
echo "NOTE: Caddy forward-auth (SSO for all services) requires Phase 01."
echo "      Authentik is deployed and usable for native OIDC integrations now."
```

---

## Step 7 — `scripts/validate-phase13.sh`

Automated checks:

| Check | Command |
|-------|---------|
| Authentik server running | `docker ps --filter name=authentik-server --filter status=running \| grep -q authentik-server` |
| Authentik HTTP responding | `curl -sf http://localhost:9080/` |
| Authentik not on port 9000 | `! curl -sf http://localhost:9000/ \| grep -q authentik` |
| Authentik env file exists | `test -f configs/authentik/.env` |
| Authentik env not world-readable | `! stat -c '%a' configs/authentik/.env \| grep -q '644'` |
| UFW enabled | `sudo ufw status \| grep -q 'Status: active'` |
| UFW default deny incoming | `sudo ufw status verbose \| grep -q 'Default: deny (incoming)'` |
| auditd running | `sudo systemctl is-active auditd \| grep -q active` |
| Docker socket audited | `sudo auditctl -l \| grep -q docker_socket` |
| setup-ufw.sh exists | `test -f scripts/setup-ufw.sh` |
| setup-auditd.sh exists | `test -f scripts/setup-auditd.sh` |
| setup-secrets.sh exists | `test -f scripts/setup-secrets.sh` |

Manual checks (warn only):
- Visit `http://10.10.10.2:9080/if/flow/initial-setup/` and complete admin account creation
- Verify UFW blocks a service port from a non-jumpbox IP
- Run Docker Bench Security and review HIGH findings
- Verify BMC default password has been changed (if applicable)
- Confirm `.env` file is in `.gitignore`

Use the same `check()` / `warn()` pattern as prior validate scripts. Exit with `$FAIL` count.

---

## Constraints

1. **Authentik port conflict** — MinIO occupies `9000`. Authentik must use `9080:9000` (HTTP) and `9443:9443` (HTTPS). The source doc's port assignment `9000:9000` will conflict and prevent either service from starting.

2. **Authentik `.env` file** — store at `configs/authentik/.env`, `chmod 600`, add to `.gitignore`. Do not hardcode secrets in `compose.auth.yml`. The `.env.example` template is committed; the real `.env` is not.

3. **`configs/authentik/.env` in `.gitignore`** — add `configs/authentik/.env` to the repo's `.gitignore` file if one exists, or create `.gitignore` with this entry.

4. **Phase 01 gap** — the source doc describes Caddy forward auth protecting all services. Since Phase 01 is tabled, Authentik forward auth cannot be wired to all services. Document this clearly in the deploy script output and in a comment in `compose.auth.yml`. Authentik can still be used for services that support native OIDC (Grafana, n8n).

5. **UFW and Docker** — Docker bypasses UFW rules by default by modifying iptables directly. The UFW rules in `setup-ufw.sh` will NOT restrict Docker-exposed ports without additional iptables configuration. Add a comment in `setup-ufw.sh` noting this limitation and directing the user to configure `DOCKER_OPTS="--iptables=false"` only if full network isolation is required (this disables Docker networking features).

6. **Docker secrets require Swarm mode** — `docker secret create` only works in Swarm mode. `setup-secrets.sh` should note this and offer the `.env` file approach as the practical alternative for a single-node setup.

---

## Feedback Template

Write to `/plan/ghc-feedback/phase13-security-hardening.md`:

```markdown
# GHC Feedback: Phase 13 — Security Hardening
**Brief:** P13-001 | **Status:** Complete / Partial / Blocked

## Files Created
- [ ] docker/compose.auth.yml
- [ ] configs/authentik/.env.example
- [ ] scripts/setup-secrets.sh
- [ ] scripts/setup-ufw.sh
- [ ] scripts/setup-auditd.sh
- [ ] scripts/deploy-phase13.sh
- [ ] scripts/validate-phase13.sh

## Deviations from Brief
| Item | Plan | Actual | Reason |

## Validation Results
[paste validate-phase13.sh output]

## Notes
```
