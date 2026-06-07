#!/usr/bin/env bash
# Deploy Phase 05: Open WebUI + SearXNG
# Run on the workstation as kasemo.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== Phase 05: Open WebUI Deploy ==="
echo ""

# ── Verify compose file exists ────────────────────────────────────────────────
if [[ ! -f "$REPO_ROOT/docker/compose.webui.yml" ]]; then
    echo "ERROR: Expected compose file at $REPO_ROOT/docker/compose.webui.yml"
    exit 1
fi

# ── 1. Prereq checks ──────────────────────────────────────────────────────────
echo "[1/3] Checking prerequisites..."
if ! docker ps --filter name=ollama --filter status=running | grep -q ollama; then
    echo "  ✗ Ollama is not running — start Phase 03 services first"
    exit 1
fi
echo "  ✓ Ollama running"

if ! curl -sf http://localhost:11434/v1/models | grep -q nomic-embed-text; then
    echo "  ⚠  nomic-embed-text not found in Ollama — pulling now..."
    docker exec ollama ollama pull nomic-embed-text
fi
echo "  ✓ nomic-embed-text present (required for RAG)"

# ── 2. Check SearXNG config ───────────────────────────────────────────────────
echo "[2/3] Checking SearXNG config..."
if [[ ! -f "$REPO_ROOT/configs/searxng/settings.yml" ]]; then
    echo "  ✗ configs/searxng/settings.yml not found"
    exit 1
fi
if grep -q "change-this-to-a-random-32-char-string" "$REPO_ROOT/configs/searxng/settings.yml"; then
    echo "  ⚠  SearXNG secret_key is still the placeholder value."
    echo "     Update configs/searxng/settings.yml before proceeding? (y/N)"
    read -r confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || echo "  Continuing with placeholder — update before production use."
fi

# ── 3. Start services ─────────────────────────────────────────────────────────
echo "[3/3] Starting Open WebUI and SearXNG..."
docker compose -f "$REPO_ROOT/docker/compose.webui.yml" up -d
echo "  Waiting for Open WebUI startup (20s)..."
sleep 20

if curl -sf http://localhost:3000/ &>/dev/null; then
    echo "  ✓ Open WebUI running at http://10.10.10.2:3000"
else
    echo "  ✗ Open WebUI not responding — check: docker logs open-webui"
    exit 1
fi

echo ""
echo "=== Deploy complete ==="
echo ""
echo "Next steps (in browser at http://10.10.10.2:3000):"
echo "  1. Register your admin account (first signup = admin)"
echo "  2. Admin → Settings → General: verify WEBUI_SECRET_KEY entropy"
echo "  3. Verify models visible: Admin → Settings → Connections"
echo "  4. Test chat with a small model (mistral:7b recommended for first test)"
echo "  5. Test image generation: type /image a red cat in the chat"
echo "  6. Settings → Documents: verify chunk size 1000, overlap 100"
echo ""
echo "Continue.dev config for client machines:"
echo "  Copy configs/open-webui/continue-config.json to ~/.continue/config.json"
echo "  Install VS Code extension: code --install-extension Continue.continue"
