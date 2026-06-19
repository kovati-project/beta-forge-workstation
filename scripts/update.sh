#!/usr/bin/env bash
# update.sh — Pull latest code and apply changes to the running system.
#
# Detects what changed and only rebuilds what's necessary:
#   UI / Python changed  → rebuild Docker image + restart loadout-manager
#   Compose files changed → docker compose up -d for affected stacks
#   Scripts changed       → logged (takes effect on next run)
#
# Usage: bash scripts/update.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
BASE="$REPO_ROOT/docker"
export REPO_ROOT

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

log()  { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1" >&2; }

# ── 1. Pull latest code ───────────────────────────────────────────────────────
echo ""
echo -e "${BLUE}╔══════════════════════════════════════╗${NC}"
echo -e "${BLUE}║       Kovati OS — Update             ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════╝${NC}"
echo ""

log "Fetching latest code..."
cd "$REPO_ROOT"

BEFORE=$(git rev-parse HEAD)
git pull
AFTER=$(git rev-parse HEAD)

if [[ "$BEFORE" == "$AFTER" ]]; then
    log "Already up to date ($(git rev-parse --short HEAD))"
    echo ""
    echo "Nothing to do."
    exit 0
fi

log "Updated: $(git rev-parse --short "$BEFORE")..$(git rev-parse --short "$AFTER")"
echo ""

# ── 2. Detect what changed ────────────────────────────────────────────────────
CHANGED=$(git diff --name-only "$BEFORE" "$AFTER")

UI_CHANGED=false
PYTHON_CHANGED=false
COMPOSE_CHANGED=""   # space-separated list of changed compose file basenames

while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    case "$f" in
        ui/*)                     UI_CHANGED=true ;;
        loadout-manager/*.py|loadout-manager/*.yaml|loadout-manager/*.yml)
                                  PYTHON_CHANGED=true ;;
        docker/compose.*)
            base=$(basename "$f")
            COMPOSE_CHANGED="$COMPOSE_CHANGED $base"
            ;;
    esac
done <<< "$CHANGED"

# ── 3. Pre-flight: ghcr.io login ─────────────────────────────────────────────
if grep -q "^GHCR_TOKEN=" "$REPO_ROOT/docker/.env" 2>/dev/null; then
    GHCR_TOKEN=$(grep "^GHCR_TOKEN=" "$REPO_ROOT/docker/.env" | cut -d= -f2-)
    GHCR_USER=$(grep  "^GHCR_USER="  "$REPO_ROOT/docker/.env" | cut -d= -f2-)
    if [[ -n "$GHCR_TOKEN" && -n "$GHCR_USER" ]]; then
        log "Refreshing ghcr.io login..."
        echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
    fi
fi

# ── 4. Pre-flight: n8n key cleanup ───────────────────────────────────────────
if grep -q "^N8N_ENCRYPTION_KEY=" "$REPO_ROOT/docker/.env" 2>/dev/null; then
    log "Removing stale N8N_ENCRYPTION_KEY from docker/.env..."
    sed -i '/^N8N_ENCRYPTION_KEY=/d' "$REPO_ROOT/docker/.env"
    rm -f /data/n8n/config
fi

# ── 5. Rebuild UI + loadout-manager if source changed ────────────────────────
if $UI_CHANGED || $PYTHON_CHANGED; then
    if $UI_CHANGED && $PYTHON_CHANGED; then
        log "UI and Python changed — rebuilding..."
    elif $UI_CHANGED; then
        log "UI changed — rebuilding..."
    else
        log "Python changed — rebuilding container..."
    fi

    bash "$SCRIPT_DIR/deploy-ui.sh"
elif ! $UI_CHANGED && ! $PYTHON_CHANGED; then
    log "No UI/Python changes"
fi

# ── 6. Apply changed compose stacks ──────────────────────────────────────────
if [[ -n "$COMPOSE_CHANGED" ]]; then
    log "Compose files changed:$COMPOSE_CHANGED"

    for compose_file in $COMPOSE_CHANGED; do
        full="$BASE/$compose_file"
        [[ -f "$full" ]] || continue

        log "Pulling images for $compose_file..."
        docker compose -f "$full" pull --quiet || warn "Image pull failed for $compose_file (continuing)"

        log "Applying $compose_file..."
        case "$compose_file" in
            compose.loadout.yml)
                # Handled by deploy-ui.sh above; skip
                ;;
            compose.training.yml)
                # Force-recreate kohya in case image changed
                docker compose -f "$full" up -d --force-recreate kohya 2>/dev/null || true
                docker compose -f "$full" up -d 2>/dev/null || warn "$compose_file apply failed (training services are optional)"
                ;;
            compose.agentic.yml)
                docker compose -f "$full" up -d --force-recreate n8n 2>/dev/null || warn "$compose_file apply failed"
                ;;
            compose.storage.yml)
                docker compose -f "$full" up -d --force-recreate langfuse 2>/dev/null || warn "$compose_file apply failed"
                docker compose -f "$full" up -d 2>/dev/null || warn "$compose_file apply failed"
                ;;
            *)
                docker compose -f "$full" up -d 2>/dev/null || warn "$compose_file apply failed (continuing)"
                ;;
        esac
    done
else
    log "No compose files changed"
fi

# ── 7. Summary ────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}╔══════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           Update complete            ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════╝${NC}"
echo ""
log "Commit: $(git log --oneline -1)"
echo ""
echo "  UI:   http://10.10.10.2:8800"
echo ""
