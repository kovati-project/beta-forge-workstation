#!/usr/bin/env bash
[ -n "${BASH_VERSION:-}" ] || { echo "ERROR: this script needs bash - run: bash $0" >&2; exit 1; }
# Undo init-secrets.sh — restore all placeholder values so init can re-run cleanly.
#
# Use this when:
#   - init-secrets.sh failed partway through and left files in a mixed state
#   - You want to re-run init-secrets.sh from scratch
#   - Services are unstable due to a botched secret injection
#
# What it does:
#   1. Stops all running compose stacks
#   2. Deletes docker/.env and configs/authentik/.env
#   3. Deletes the rendered configs/postgres/init.sql and configs/searxng/settings.yml
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
# Only docker/.env, configs/authentik/.env, and the two rendered config files
# need to be removed.

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

echo "Removing rendered configs/postgres/init.sql..."
# init-secrets.sh renders it from configs/postgres/init.sql.template on the next run.
rm -f configs/postgres/init.sql configs/postgres/.init.sql.* 2>/dev/null \
    || echo "  (could not remove - check its owner; delete it with sudo)"
log "configs/postgres/init.sql removed (re-render: bash scripts/init-secrets.sh)"

echo "Removing generated configs/searxng/settings.yml..."
rm -f configs/searxng/settings.yml 2>/dev/null \
    || echo "  (could not remove - owned by the container user; delete it with sudo)"
log "configs/searxng/settings.yml removed (re-render: bash scripts/init-secrets.sh --render-searxng)"

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
