#!/usr/bin/env bash
# Undo init-secrets.sh — restore all placeholder values so init can re-run cleanly.
#
# Use this when:
#   - init-secrets.sh failed partway through and left files in a mixed state
#   - You want to re-run init-secrets.sh from scratch
#   - Services are unstable due to a botched secret injection
#
# What it does:
#   1. Stops all running compose stacks
#   2. Restores every patched file back to its original placeholder value
#   3. Removes configs/authentik/.env
#   4. Leaves /data/ volumes untouched (PostgreSQL data, MinIO objects, etc.)

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*" >&2; }

echo ""
warn "This will stop all running services and delete docker/.env."
warn "Run init-secrets.sh again afterwards to generate fresh secrets."
echo ""
read -rp "Continue? [y/N] " CONFIRM
[[ "${CONFIRM,,}" != "y" ]] && { echo "Aborted."; exit 0; }
echo ""

# ── 1. Stop all running compose stacks ───────────────────────────────────────
echo "Stopping services..."
for f in docker/compose.webui.yml \
          docker/compose.agentic.yml \
          docker/compose.codegen.yml \
          docker/compose.voice.yml \
          docker/compose.training.yml \
          docker/compose.inference.yml \
          docker/compose.loadout.yml \
          docker/compose.auth.yml \
          docker/compose.monitoring.yml \
          docker/compose.storage.yml; do
    if [[ -f "$f" ]]; then
        docker compose -f "$f" down 2>/dev/null && log "stopped $f" || true
    fi
done
echo ""

# ── 2. Delete secret files ────────────────────────────────────────────────────
# Compose files use ${VAR} references and never need restoring.
# Only docker/.env, configs/authentik/.env, and the two patched config files
# need to be reset.

echo "Removing docker/.env..."
if [[ -f docker/.env ]]; then
    rm docker/.env
    log "docker/.env removed"
else
    warn "docker/.env not found — nothing to remove"
fi

echo "Removing configs/authentik/.env..."
if [[ -f configs/authentik/.env ]]; then
    rm configs/authentik/.env
    log "configs/authentik/.env removed"
else
    warn "configs/authentik/.env not found — nothing to remove"
fi

echo "Restoring configs/postgres/init.sql placeholders..."
python3 - configs/postgres/init.sql <<'PYEOF'
import re, sys, os
path = sys.argv[1]
if not os.path.exists(path):
    sys.exit(0)
with open(path, 'r') as f:
    content = f.read()
for user, placeholder in [('langfuse','langfuse_pass'), ('n8n','n8n_pass'), ('dify','dify_pass')]:
    pattern = r"(?i)(CREATE USER " + re.escape(user) + r" WITH PASSWORD ')[^']*(')"
    content = re.sub(pattern, r'\g<1>' + placeholder + r'\g<2>', content)
with open(path, 'w') as f:
    f.write(content)
PYEOF
log "configs/postgres/init.sql restored"

echo "Restoring configs/searxng/settings.yml placeholder..."
python3 - configs/searxng/settings.yml <<'PYEOF'
import re, sys, os
path = sys.argv[1]
if not os.path.exists(path):
    sys.exit(0)
with open(path, 'r') as f:
    content = f.read()
content = re.sub(r'(?m)^(\s*secret_key:\s*")([^"]+)(")',
                 r'\g<1>change-this-to-a-random-32-char-string\g<3>', content)
with open(path, 'w') as f:
    f.write(content)
PYEOF
log "configs/searxng/settings.yml restored"

# ── 3. Done ───────────────────────────────────────────────────────────────────
echo ""
echo "Reset complete."
echo ""
echo "Note: /data/ volumes are untouched."
echo "If Postgres or MinIO already initialised with the old secrets,"
echo "you may need to wipe their volumes before re-deploying:"
echo ""
echo "  docker volume rm postgres-data qdrant-data grafana-data prometheus-data"
echo "  sudo rm -rf /data/minio /data/authentik"
echo ""
echo "Next steps:"
echo "  bash scripts/init-secrets.sh"
echo "  bash scripts/deploy-all.sh"
echo ""
