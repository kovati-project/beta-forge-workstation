#!/usr/bin/env bash
# Deploy Phase 06: Loadout Manager
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export REPO_ROOT
# shellcheck source=lib/container-helpers.sh
source "$REPO_ROOT/scripts/lib/container-helpers.sh"
LM_DIR="$REPO_ROOT/loadout-manager"

echo "=== Phase 06: Loadout Manager Deploy ==="
echo ""

# ── 1. Verify files ───────────────────────────────────────────────────────────
echo "[1/4] Verifying loadout manager files..."
for f in profiles.yaml main.py requirements.txt Dockerfile; do
    if [[ ! -f "$LM_DIR/$f" ]]; then
        echo "  ✗ Missing: $LM_DIR/$f"
        exit 1
    fi
done
echo "  ✓ All files present"

# ── 2. Verify compose files ───────────────────────────────────────────────────
echo "[2/4] Verifying docker compose files..."
for cf in compose.inference.yml compose.training.yml compose.studio.yml; do
    if [[ ! -f "$REPO_ROOT/docker/$cf" ]]; then
        echo "  ✗ Missing: $REPO_ROOT/docker/$cf (required by loadout profiles)"
        exit 1
    fi
done
echo "  ✓ All compose files present"

# ── 3. Build and start ────────────────────────────────────────────────────────
echo "[3/4] Building loadout manager image..."
docker build -f "$LM_DIR/Dockerfile" -t loadout-manager:latest "$LM_DIR"
echo "  ✓ Image built"

echo "[4/4] Starting loadout manager..."
remove_orphan loadout-manager ai-loadout-mgr
docker compose -f "$REPO_ROOT/docker/compose.loadout.yml" up -d
echo "  Waiting for startup (5s)..."
sleep 5

if curl -sf http://localhost:8800/health &>/dev/null; then
    echo "  ✓ Loadout Manager running at http://10.10.10.2:8800"
else
    echo "  ✗ Not responding — check: docker logs loadout-manager"
    exit 1
fi

echo ""
echo "=== Deploy complete ==="
echo ""
echo "Available profiles:"
curl -s http://localhost:8800/loadouts | jq -r '.[] | .description' | sed 's/^/  - /'
echo ""
echo "Test activation (example):"
echo "  curl -X POST http://localhost:8800/activate/inference-small"
echo ""
echo "Monitor switching:"
echo "  watch -n 1 'curl -s http://localhost:8800/status | jq'"
