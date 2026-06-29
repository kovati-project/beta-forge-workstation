#!/usr/bin/env bash
# Deploy Phase 08: Agentic Workflows & MCP
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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
echo "  ✓ n8n files directory ready"

# ── 3. Start agentic services ─────────────────────────────────────────────────
echo "[3/4] Starting agentic services..."
for _c in n8n mcp-filesystem mcp-fetch mcp-browser mcp-code-exec; do
    remove_orphan "$_c" ai-agentic
done
docker compose -f "$REPO_ROOT/docker/compose.agentic.yml" up -d \
  n8n mcp-filesystem mcp-fetch mcp-browser mcp-code-exec
echo "  Waiting for startup (15s)..."
sleep 15

# ── 4. Verify startup ─────────────────────────────────────────────────────────
echo "[4/4] Verifying services..."

READY=0
for svc in n8n mcp-filesystem mcp-fetch mcp-browser mcp-code-exec; do
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
echo "Services deployed (${READY}/5):"
echo "  n8n              → http://10.10.10.2:5678"
echo "  MCP filesystem   → :3100"
echo "  MCP fetch        → :3103"
echo "  MCP browser      → :3101"
echo "  MCP code-exec    → :3102"
echo ""
echo "Next steps:"
echo "  1. Visit http://10.10.10.2:5678 and create owner account"
echo "  2. Configure Ollama integration: Settings → AI → OpenAI base URL: http://10.10.10.2:11434/v1"
echo "  3. Add MCP server connections in n8n credentials"
echo "  4. Build first workflow: Health Monitor (check Loadout Manager every 5 min)"
echo ""
echo "Optional: Deploy Dify"
echo "  docker compose -f docker/compose.agentic.yml up -d dify-api dify-web dify-db dify-redis"
echo "  Access at http://10.10.10.2:3010"
