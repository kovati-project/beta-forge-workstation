#!/usr/bin/env bash
# Generate secrets for a fresh deployment.
# Run once on the workstation BEFORE deploy-all.sh.
#
# Usage:
#   bash scripts/init-secrets.sh                       full run (generate + render)
#   bash scripts/init-secrets.sh --force               also overwrite an existing
#                                                      configs/postgres/init.sql
#   bash scripts/init-secrets.sh --render-postgres-init
#                                                      only render init.sql from
#                                                      docker/.env (no new secrets)
#
# Writes:  docker/.env          (loaded automatically by all compose files)
#          configs/authentik/.env  (legacy path — Authentik deploy script reads it)
#          configs/postgres/init.sql  (rendered from init.sql.template; gitignored,
#                                      mode 600 — SQL needs literal values)
#          configs/searxng/settings.yml  (patched once; not a compose env var)
#
# configs/postgres/init.sql is NEVER committed. The tracked source of truth is
# configs/postgres/init.sql.template, which holds @..._DB_PASSWORD@ placeholders.
# Rendering is idempotent: an init.sql that already holds real values is left
# alone unless --force is given. NOTE: Postgres only executes init.sql when its
# data directory is first created, so re-rendering does NOT change the passwords
# of an already-initialised volume — see docs/runbooks/rotate-postgres-passwords.md.
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

# ── Arguments ─────────────────────────────────────────────────────────────────
FORCE=0
RENDER_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --force)                FORCE=1 ;;
        --render-postgres-init) RENDER_ONLY=1 ;;
        -h|--help)
            sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0 ;;
        *) err "Unknown argument: $arg (try --help)"; exit 2 ;;
    esac
done

# ── Render configs/postgres/init.sql from its template ───────────────────────
# Uses LANGFUSE_DB_PASSWORD / N8N_DB_PASSWORD / DIFY_DB_PASSWORD from the
# environment (full run) or from docker/.env (--render-postgres-init).
# The same variables feed compose: Langfuse's DATABASE_URL uses
# LANGFUSE_DB_PASSWORD and Dify uses DIFY_DB_PASSWORD, so the SQL and the
# service connection strings cannot drift apart.
# File mode defaults to 600 (at rest). The postgres image reads init.sql as its
# in-container "postgres" user, which cannot open a 600 file owned by the host
# user, so scripts/deploy-phase09.sh relaxes it to 644 only for the first
# initialisation of the data volume and then restores 600. If you start the
# stack some other way on a FRESH volume, render with INIT_SQL_MODE=644.
PG_INIT_TEMPLATE="configs/postgres/init.sql.template"
PG_INIT_OUT="configs/postgres/init.sql"

# True if the file still carries template placeholders or the legacy values
# that scripts/reset-secrets.sh writes (i.e. it holds no real passwords yet).
pg_init_unrendered() {
    grep -qE "@(LANGFUSE|N8N|DIFY)_DB_PASSWORD@|PASSWORD '(langfuse|n8n|dify)_pass'" "$1"
}

# Print the value of KEY from a dotenv-style file without executing it.
read_env_value() {
    local file="$1" key="$2" line
    line=$(grep -E "^${key}=" "$file" | tail -n1) || true
    line="${line#*=}"
    line="${line%$'\r'}"
    line="${line#\"}"; line="${line%\"}"
    printf '%s' "$line"
}

render_postgres_init() {
    local mode="${INIT_SQL_MODE:-600}"

    if [[ ! -f "$PG_INIT_TEMPLATE" ]]; then
        if [[ -f "$PG_INIT_OUT" ]]; then
            warn "$PG_INIT_TEMPLATE missing — leaving existing $PG_INIT_OUT untouched"
            return 0
        fi
        err "$PG_INIT_TEMPLATE not found — cannot render $PG_INIT_OUT"
        return 1
    fi

    # Render-only (deploy-time) mode: never touch a file that already has values.
    if (( RENDER_ONLY )) && (( ! FORCE )) && [[ -f "$PG_INIT_OUT" ]] \
            && ! pg_init_unrendered "$PG_INIT_OUT"; then
        log "$PG_INIT_OUT already rendered — leaving as is"
        return 0
    fi

    if (( RENDER_ONLY )); then
        if [[ ! -f "$ENV_FILE" ]]; then
            err "$ENV_FILE not found — run: bash scripts/init-secrets.sh"
            return 1
        fi
        LANGFUSE_DB_PASSWORD=$(read_env_value "$ENV_FILE" LANGFUSE_DB_PASSWORD)
        DIFY_DB_PASSWORD=$(read_env_value "$ENV_FILE" DIFY_DB_PASSWORD)
        N8N_DB_PASSWORD=$(read_env_value "$ENV_FILE" N8N_DB_PASSWORD)
        if [[ -z "$LANGFUSE_DB_PASSWORD" || -z "$DIFY_DB_PASSWORD" ]]; then
            err "LANGFUSE_DB_PASSWORD / DIFY_DB_PASSWORD missing from $ENV_FILE — run: bash scripts/init-secrets.sh"
            return 1
        fi
        if [[ -z "$N8N_DB_PASSWORD" ]]; then
            # docker/.env generated before N8N_DB_PASSWORD existed. n8n runs on
            # SQLite so nothing consumes this role password; persist a fresh one
            # so it is at least recoverable.
            N8N_DB_PASSWORD=$(openssl rand -hex 16)
            printf 'N8N_DB_PASSWORD=%s\n' "$N8N_DB_PASSWORD" >> "$ENV_FILE"
            warn "N8N_DB_PASSWORD was missing — generated and appended to $ENV_FILE"
        fi
    fi

    # Passwords end up in SQL string literals and in postgresql:// URLs, so only
    # URL-safe characters are accepted (generated values are hex).
    local name value
    for name in LANGFUSE_DB_PASSWORD N8N_DB_PASSWORD DIFY_DB_PASSWORD; do
        value="${!name:-}"
        if [[ ! "$value" =~ ^[A-Za-z0-9._~-]{16,}$ ]]; then
            err "$name must be at least 16 chars of [A-Za-z0-9._~-]"
            return 1
        fi
    done

    local content
    content="$(cat "$PG_INIT_TEMPLATE"; printf x)"
    content="${content%x}"
    for name in LANGFUSE_DB_PASSWORD N8N_DB_PASSWORD DIFY_DB_PASSWORD; do
        if [[ "$content" != *"@${name}@"* ]]; then
            err "$PG_INIT_TEMPLATE has no @${name}@ placeholder"
            return 1
        fi
        value="${!name}"
        content="${content//@${name}@/$value}"
    done
    if [[ "$content" =~ @[A-Z0-9_]+_PASSWORD@ ]]; then
        err "$PG_INIT_TEMPLATE has an unknown placeholder — not rendering"
        return 1
    fi

    local tmp
    tmp=$(umask 077; mktemp "$(dirname "$PG_INIT_OUT")/.init.sql.XXXXXX")
    printf '%s' "$content" > "$tmp"
    chmod "$mode" "$tmp"

    if [[ -f "$PG_INIT_OUT" ]]; then
        if cmp -s "$tmp" "$PG_INIT_OUT"; then
            rm -f "$tmp"
            chmod "$mode" "$PG_INIT_OUT"
            log "$PG_INIT_OUT already up to date"
            return 0
        fi
        if (( ! FORCE )) && ! pg_init_unrendered "$PG_INIT_OUT"; then
            rm -f "$tmp"
            warn "$PG_INIT_OUT exists with different passwords — NOT overwritten."
            warn "  docker/.env and init.sql are now out of sync. Re-run with --force to"
            warn "  re-render, and rotate live roles per docs/runbooks/rotate-postgres-passwords.md"
            return 0
        fi
    fi

    mv -f "$tmp" "$PG_INIT_OUT"
    log "$PG_INIT_OUT rendered from template (mode $mode)"
}

# Render-only mode: no prompts, no secret generation (used by deploy-phase09.sh).
if (( RENDER_ONLY )); then
    render_postgres_init
    exit $?
fi

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
# N8N_ENCRYPTION_KEY is intentionally not set here — n8n generates and persists
# its own key in /data/n8n/config on first start. Injecting an env var causes
# mismatch failures if the var ever changes after first init.
DIFY_SECRET_KEY=$(gen64)
DIFY_DB_PASSWORD=$(gen32)
GF_ADMIN_PASSWORD=$(gen32)
MINIO_ROOT_PASSWORD=$(gen32)
POSTGRES_ADMIN_PASSWORD=$(gen32)
LANGFUSE_DB_PASSWORD=$(gen32)
# n8n itself runs on SQLite (compose.agentic.yml); this is only the password of the
# n8n role in the shared postgres, kept in docker/.env so it is recoverable.
N8N_DB_PASSWORD=$(gen32)
LANGFUSE_NEXTAUTH_SECRET=$(gen64)
LABEL_STUDIO_PASSWORD=$(gen32)
JUPYTER_TOKEN=$(gen32)
AUTHENTIK_PG_PASSWORD=$(gen32)
AUTHENTIK_REDIS_PASSWORD=$(gen32)
AUTHENTIK_SECRET_KEY=$(gen60b)

# ── Collect ghcr.io credentials ──────────────────────────────────────────────
echo ""
echo "  GitHub Container Registry (ghcr.io)"
echo "  ─────────────────────────────────────"
echo "  Required for auth-gated images (e.g. kohya-ss)."
echo "  Create a token at: GitHub → Settings → Developer settings"
echo "  → Personal access tokens (classic) → check 'read:packages'"
echo "  Leave blank to skip (you can add it to docker/.env later)."
echo ""
read -rp "  GitHub username: " GHCR_USER
read -rp "  GitHub PAT (read:packages): " GHCR_TOKEN
echo ""

# ── Write docker/.env ─────────────────────────────────────────────────────────
cat > "$ENV_FILE" <<EOF
# AI Workstation secrets — generated $(date -u +%Y-%m-%dT%H:%M:%SZ)
# DO NOT COMMIT. Excluded from sync. Back up separately.

GHCR_USER=${GHCR_USER}
GHCR_TOKEN=${GHCR_TOKEN}

WEBUI_SECRET_KEY=${WEBUI_SECRET_KEY}
DIFY_SECRET_KEY=${DIFY_SECRET_KEY}
DIFY_DB_PASSWORD=${DIFY_DB_PASSWORD}
GF_ADMIN_PASSWORD=${GF_ADMIN_PASSWORD}
MINIO_ROOT_PASSWORD=${MINIO_ROOT_PASSWORD}
POSTGRES_ADMIN_PASSWORD=${POSTGRES_ADMIN_PASSWORD}
LANGFUSE_DB_PASSWORD=${LANGFUSE_DB_PASSWORD}
N8N_DB_PASSWORD=${N8N_DB_PASSWORD}
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

# ── Render configs/postgres/init.sql (SQL needs literal passwords) ────────────
render_postgres_init || { err "init.sql was not rendered"; exit 1; }

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

# ── Gitignore ─────────────────────────────────────────────────────────────────
for entry in "docker/.env" "configs/authentik/.env" "configs/postgres/init.sql"; do
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
