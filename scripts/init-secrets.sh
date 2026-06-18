#!/usr/bin/env bash
# Generate secrets for a fresh deployment.
# Run once on the workstation BEFORE deploy-all.sh.
#
# Writes:  docker/.env          (loaded automatically by all compose files)
#          configs/authentik/.env  (legacy path — Authentik deploy script reads it)
#          configs/postgres/init.sql  (patched once; SQL needs literal values)
#          configs/searxng/settings.yml  (patched once; not a compose env var)
#
# Re-sync safe: compose files always use ${VAR} references; docker/.env is
# excluded from sync so secrets survive rsync updates.

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*" >&2; }

ENV_FILE="docker/.env"

# ── Interactive entropy collection ────────────────────────────────────────────
collect_entropy() {
    local TARGET=48
    local BAR_W=40

    if ! [ -e /dev/tty ]; then
        openssl rand -hex 32
        return
    fi

    local count=0 pool="" i
    local TTY=/dev/tty

    printf '\n' > "$TTY"
    printf '  AI WORKSTATION  -  Secret Key Generation\n' > "$TTY"
    printf '  ------------------------------------------\n' > "$TTY"
    printf '\n' > "$TTY"
    printf '  Type random keys to seed the key generator.\n' > "$TTY"
    printf '  Avoid words, names, or patterns. Just mash keys.\n' > "$TTY"
    printf '\n' > "$TTY"

    local empty_bar=""
    for (( i=0; i<BAR_W; i++ )); do empty_bar+='.'; done
    printf "  [%s]   0%%" "$empty_bar" > "$TTY"

    while [[ $count -lt $TARGET ]]; do
        local ch ts
        ts=$(date +%s%N 2>/dev/null || date +%s)
        IFS= read -r -s -n1 ch < "$TTY" 2>/dev/null || ch=''
        pool="${pool}${ts}${ch}"
        count=$(( count + 1 ))

        local filled=$(( count * BAR_W / TARGET ))
        local empty=$(( BAR_W - filled ))
        local pct=$(( count * 100 / TARGET ))
        local bar=""
        for (( i=0; i<filled; i++ )); do bar+='#'; done
        for (( i=0; i<empty;  i++ )); do bar+='.'; done

        printf "\r  [%s] %3d%%" "$bar" "$pct" > "$TTY"
    done

    printf '\n\n' > "$TTY"

    printf '%s%s' "$pool" "$(openssl rand -hex 32)" | sha256sum | cut -c1-64
}

# ── Guard ─────────────────────────────────────────────────────────────────────
if [[ -f "$ENV_FILE" ]]; then
    warn "docker/.env already exists. Re-generating will break running services."
    read -rp "Regenerate all secrets? [y/N] " CONFIRM
    [[ "${CONFIRM,,}" != "y" ]] && { echo "Aborted."; exit 0; }
fi

# ── Collect entropy ───────────────────────────────────────────────────────────
ENTROPY=$(collect_entropy)

printf '  Generating secrets...\n\n' > /dev/tty 2>/dev/null || true

# ── Generators ───────────────────────────────────────────────────────────────
gen32()  { printf '%s%s' "$ENTROPY" "$(openssl rand -hex 8)"  | sha256sum | cut -c1-32; }
gen64()  { printf '%s%s' "$ENTROPY" "$(openssl rand -hex 16)" | sha256sum | cut -c1-64; }
gen60b() { printf '%s%s' "$ENTROPY" "$(openssl rand -hex 20)" | sha256sum | cut -c1-60; }

WEBUI_SECRET_KEY=$(gen64)
N8N_ENCRYPTION_KEY=$(gen32)
DIFY_SECRET_KEY=$(gen64)
DIFY_DB_PASSWORD=$(gen32)
GF_ADMIN_PASSWORD=$(gen32)
MINIO_ROOT_PASSWORD=$(gen32)
POSTGRES_ADMIN_PASSWORD=$(gen32)
LANGFUSE_DB_PASSWORD=$(gen32)
LANGFUSE_NEXTAUTH_SECRET=$(gen64)
LABEL_STUDIO_PASSWORD=$(gen32)
JUPYTER_TOKEN=$(gen32)
AUTHENTIK_PG_PASSWORD=$(gen32)
AUTHENTIK_REDIS_PASSWORD=$(gen32)
AUTHENTIK_SECRET_KEY=$(gen60b)

# ── Write docker/.env ─────────────────────────────────────────────────────────
cat > "$ENV_FILE" <<EOF
# AI Workstation secrets — generated $(date -u +%Y-%m-%dT%H:%M:%SZ)
# DO NOT COMMIT. Excluded from sync. Back up separately.

WEBUI_SECRET_KEY=${WEBUI_SECRET_KEY}
N8N_ENCRYPTION_KEY=${N8N_ENCRYPTION_KEY}
DIFY_SECRET_KEY=${DIFY_SECRET_KEY}
DIFY_DB_PASSWORD=${DIFY_DB_PASSWORD}
GF_ADMIN_PASSWORD=${GF_ADMIN_PASSWORD}
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}
POSTGRES_ADMIN_PASSWORD=${POSTGRES_ADMIN_PASSWORD}
LANGFUSE_DB_PASSWORD=${LANGFUSE_DB_PASSWORD}
LANGFUSE_NEXTAUTH_SECRET=${LANGFUSE_NEXTAUTH_SECRET}
LABEL_STUDIO_PASSWORD=${LABEL_STUDIO_PASSWORD}
JUPYTER_TOKEN=${JUPYTER_TOKEN}
AUTHENTIK_PG_PASSWORD=${AUTHENTIK_PG_PASSWORD}
AUTHENTIK_REDIS_PASSWORD=${AUTHENTIK_REDIS_PASSWORD}
AUTHENTIK_SECRET_KEY=${AUTHENTIK_SECRET_KEY}
EOF
chmod 600 "$ENV_FILE"
log "docker/.env written (chmod 600)"

# ── Write configs/authentik/.env (deploy-phase13.sh reads this path) ─────────
mkdir -p configs/authentik
cat > configs/authentik/.env <<EOF
POSTGRES_PASSWORD=${AUTHENTIK_PG_PASSWORD}
REDIS_PASSWORD=${AUTHENTIK_REDIS_PASSWORD}
AUTHENTIK_SECRET_KEY=${AUTHENTIK_SECRET_KEY}
EOF
chmod 600 configs/authentik/.env
log "configs/authentik/.env written"

# ── Patch configs/postgres/init.sql (SQL needs literal passwords) ─────────────
patch_sql() {
    local file="$1" user="$2" password="$3"
    python3 - "$file" "$user" "$password" <<'PYEOF'
import re, sys
path, user, password = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path, 'r') as f:
    content = f.read()
pattern = r"(?i)(CREATE USER " + re.escape(user) + r" WITH PASSWORD ')[^']*(')"
new_content = re.sub(pattern, r'\g<1>' + password + r'\g<2>', content)
with open(path, 'w') as f:
    f.write(new_content)
PYEOF
    log "init.sql: $user password"
}

if [[ -f configs/postgres/init.sql ]]; then
    patch_sql configs/postgres/init.sql langfuse "$LANGFUSE_DB_PASSWORD"
    patch_sql configs/postgres/init.sql n8n     "$(gen32)"
    patch_sql configs/postgres/init.sql dify    "$DIFY_DB_PASSWORD"
fi

# ── Patch configs/searxng/settings.yml ───────────────────────────────────────
if [[ -f configs/searxng/settings.yml ]]; then
    python3 - configs/searxng/settings.yml "$(gen32)" <<'PYEOF'
import re, sys
path, secret = sys.argv[1], sys.argv[2]
with open(path, 'r') as f:
    content = f.read()
content = re.sub(r'(?m)^(\s*secret_key:\s*")([^"]+)(")',
                 r'\g<1>' + secret + r'\g<3>', content)
with open(path, 'w') as f:
    f.write(content)
PYEOF
    log "configs/searxng/settings.yml: secret_key"
fi

# ── Patch deploy-phase09.sh / sync-checkpoints.sh (embed MinIO password) ─────
for f in scripts/deploy-phase09.sh scripts/sync-checkpoints.sh; do
    [[ -f "$f" ]] || continue
    python3 - "$f" "$MINIO_ROOT_PASSWORD" <<'PYEOF'
import re, sys
path, pw = sys.argv[1], sys.argv[2]
with open(path, 'r') as f:
    content = f.read()
content = re.sub(r'(mc alias set local http://localhost:9000 admin )[^"\s]+',
                 r'\g<1>' + pw, content)
with open(path, 'w') as f:
    f.write(content)
PYEOF
    log "$f: MinIO password"
done

# ── Gitignore ─────────────────────────────────────────────────────────────────
for entry in "docker/.env" "configs/authentik/.env"; do
    grep -qF "$entry" .gitignore 2>/dev/null || echo "$entry" >> .gitignore
done
log ".gitignore updated"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "  Save these credentials before continuing"
echo "  ------------------------------------------"
printf "  %-30s  %s\n" "Grafana admin password:"   "$GF_ADMIN_PASSWORD"
printf "  %-30s  %s\n" "MinIO root password:"       "$MINIO_ROOT_PASSWORD"
printf "  %-30s  %s\n" "Postgres admin password:"   "$POSTGRES_ADMIN_PASSWORD"
printf "  %-30s  %s\n" "Label Studio password:"     "$LABEL_STUDIO_PASSWORD"
printf "  %-30s  %s\n" "JupyterLab token:"          "$JUPYTER_TOKEN"
printf "  %-30s  %s\n" "Authentik PG password:"     "$AUTHENTIK_PG_PASSWORD"
echo ""
echo "  All secrets also recorded in docker/.env"
echo ""
warn "docker/.env is plaintext on disk — keep it out of git and backups."
echo ""
echo "Next steps:"
echo "  bash scripts/setup-storage.sh"
echo "  bash scripts/deploy-all.sh"
echo ""
