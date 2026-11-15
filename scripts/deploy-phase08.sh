#!/usr/bin/env bash
[ -n "${BASH_VERSION:-}" ] || { echo "ERROR: this script needs bash - run: bash $0" >&2; exit 1; }
# Deploy Phase 08: Agentic Workflows & MCP
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$REPO_ROOT/scripts/lib/workstation-host.sh"  # WORKSTATION_HOST (#51)
# shellcheck source=lib/container-helpers.sh
source "$REPO_ROOT/scripts/lib/container-helpers.sh"

echo "=== Phase 08: Agentic Workflows & MCP Deploy ==="
echo ""

# ── 1. Verify Phase 06 (Loadout Manager) ──────────────────────────────────────
echo "[1/4] Checking Loadout Manager..."
if ! curl -sf http://localhost:8800/health &>/dev/null; then
    echo "  ✗ Loadout Manager not running — Phase 06 required"
    exit 1
fi
echo "  ✓ Loadout Manager available"

# ── 2. Create n8n files directory ─────────────────────────────────────────────
echo "[2/4] Setting up directories..."
sudo mkdir -p /data/n8n-files
# mcp-filesystem mounts only these (read-only) as its /data sandbox
sudo mkdir -p /data/documents /data/datasets /data/outputs /data/notebooks
echo "  ✓ n8n files and MCP sandbox directories ready"

# ── 3. Start agentic services ─────────────────────────────────────────────────
echo "[3/4] Starting agentic services..."
# mcp-code-exec is behind the "code-exec" compose profile until the sandbox
# fixes from the PR #93 review land; ENABLE_MCP_CODE_EXEC=1 opts in.
SERVICES=(n8n mcp-filesystem mcp-fetch mcp-browser)
PROFILE_ARGS=()
if [ "${ENABLE_MCP_CODE_EXEC:-0}" = 1 ]; then
    SERVICES+=(mcp-code-exec)
    PROFILE_ARGS=(--profile code-exec)
else
    echo "  (mcp-code-exec disabled; set ENABLE_MCP_CODE_EXEC=1 to start it)"
fi
for _c in "${SERVICES[@]}"; do
    remove_orphan "$_c" ai-agentic
done
# --build: the MCP images are built locally from docker/mcp/* (pinned versions)
docker compose -f "$REPO_ROOT/docker/compose.agentic.yml" "${PROFILE_ARGS[@]}" up -d --build \
  "${SERVICES[@]}"
echo "  Waiting for startup (15s)..."
sleep 15

# ── 4. Verify startup ─────────────────────────────────────────────────────────
echo "[4/4] Verifying services..."

READY=0
for svc in "${SERVICES[@]}"; do
    if docker ps --filter name=$svc --filter status=running | grep -q $svc; then
        echo "  ✓ $svc running"
        READY=$(( READY + 1 ))
    else
        echo "  ✗ $svc not running — check: docker logs $svc"
    fi
done

echo ""
echo "=== Deploy complete ==="
echo ""
echo "Services deployed (${READY}/${#SERVICES[@]}):"
echo "  n8n              → http://${WORKSTATION_HOST}:5678"
echo "  MCP filesystem   → :3100/mcp (streamable HTTP)"
echo "  MCP fetch        → :3103/mcp"
echo "  MCP browser      → :3101/mcp"
echo "  MCP code-exec    → :3102/mcp"
echo ""
echo "Next steps:"
echo "  1. Visit http://${WORKSTATION_HOST}:5678 and create owner account"
echo "  2. Configure Ollama integration: Settings → AI → OpenAI base URL: http://ollama:11434/v1"
echo "  3. Add MCP server connections in n8n credentials"
echo "  4. Build first workflow: Health Monitor (check Loadout Manager every 5 min)"
echo ""
echo "Optional: Deploy Dify"
echo "  docker compose -f docker/compose.agentic.yml up -d dify-api dify-web dify-db dify-redis"
echo "  Access at http://${WORKSTATION_HOST}:3010"
