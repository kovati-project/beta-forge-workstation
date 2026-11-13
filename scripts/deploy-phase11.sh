#!/bin/bash
[ -n "${BASH_VERSION:-}" ] || { echo "ERROR: this script needs bash - run: bash $0" >&2; exit 1; }
# Phase 11 deployment: Code Generation Stack
# Deploys OpenHands autonomous agent, configures Continue.dev IDE integration, model routing

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/container-helpers.sh
source "$REPO_ROOT/scripts/lib/container-helpers.sh"

echo "=== Phase 11: Code Generation ==="
echo ""

# Verify Phase 06 (Loadout Manager) is running
echo "Checking Phase 06 (Loadout Manager)..."
if ! curl -sf http://localhost:8800/health > /dev/null 2>&1; then
    echo "WARNING: Loadout Manager not running (optional for Phase 11)"
else
    echo "✓ Loadout Manager running"
fi
echo ""

# The coding model (Qwen3.8-27B on vllm-4gpu) serves OpenHands, Continue.dev
# and Copilot Chat; vllm-embed serves Continue's codebase embeddings.
echo "Checking vLLM coding model (vllm-4gpu :8002) and embeddings (vllm-embed :8003)..."
if curl -sf http://localhost:8002/v1/models 2>/dev/null | grep -q '"qwen3.8-27b"'; then
    echo "✓ vllm-4gpu serving qwen3.8-27b"
else
    echo "WARNING: vllm-4gpu is not serving qwen3.8-27b — OpenHands will deploy but needs it at runtime:"
    echo "  docker compose -f docker/compose.inference.yml up -d vllm-4gpu vllm-embed"
fi
if curl -sf http://localhost:8003/v1/models 2>/dev/null | grep -q '"nomic-embed-text"'; then
    echo "✓ vllm-embed serving nomic-embed-text"
else
    echo "WARNING: vllm-embed is not serving nomic-embed-text (Continue codebase search, Open WebUI RAG)"
fi
echo ""

# Verify docker compose file exists
if [ ! -f "docker/compose.codegen.yml" ]; then
    echo "ERROR: docker/compose.codegen.yml not found"
    exit 1
fi

# Create storage directories
echo "Creating storage directories..."
sudo mkdir -p /data/openhands
sudo mkdir -p /data/code-cache
sudo chmod -R 755 /data/openhands /data/code-cache
echo "✓ Directories created"
echo ""

# Start OpenHands service
echo "Starting OpenHands..."
remove_orphan openhands ai-codegen
docker compose -f docker/compose.codegen.yml up -d openhands
echo "✓ OpenHands container started"
echo ""

# Wait for OpenHands to be ready
echo "Waiting for OpenHands to initialize..."
for i in {1..30}; do
    if curl -sf http://localhost:3003 > /dev/null 2>&1; then
        break
    fi
    if [ $i -eq 30 ]; then
        echo "WARNING: OpenHands still initializing (might take a moment)"
    fi
    sleep 1
done

# Verify OpenHands is responding
echo ""
echo "Verifying services..."
if curl -sf http://localhost:3003 > /dev/null 2>&1; then
    echo "✓ OpenHands responding on :3003"
else
    echo "⊘ OpenHands initializing (might need more time)"
fi

# OpenHands keeps its own saved settings in /data/openhands/state, and those
# win over the LLM_* env vars after the first start. Sync model and base URL
# from compose.codegen.yml into them. Posting without llm_api_key keeps the
# stored key.
WANT_MODEL=$(grep -oP 'LLM_MODEL=\K\S+' docker/compose.codegen.yml)
WANT_URL=$(grep -oP 'LLM_BASE_URL=\K\S+' docker/compose.codegen.yml)
if SETTINGS=$(curl -sf http://localhost:3003/api/settings); then
    BODY=$(WANT_MODEL="$WANT_MODEL" WANT_URL="$WANT_URL" python3 -c '
import json, os, sys
s = json.load(sys.stdin)
want = {"llm_model": os.environ["WANT_MODEL"], "llm_base_url": os.environ["WANT_URL"]}
if all(s.get(k) == v for k, v in want.items()):
    sys.exit(0)
s.update(want)
drop = {"llm_api_key_set", "search_api_key_set", "provider_tokens_set", "secrets_store", "email", "email_verified"}
print(json.dumps({k: v for k, v in s.items() if v is not None and k not in drop}))
' <<< "$SETTINGS")
    if [ -n "$BODY" ]; then
        curl -sf -X POST http://localhost:3003/api/settings -H 'Content-Type: application/json' -d "$BODY" > /dev/null \
            && echo "✓ OpenHands saved settings now use $WANT_MODEL via $WANT_URL" \
            || echo "WARNING: could not update OpenHands settings to $WANT_MODEL via $WANT_URL"
    else
        echo "✓ OpenHands saved settings already use $WANT_MODEL via $WANT_URL"
    fi
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Code generation stack ready:"
echo ""
echo "  OpenHands (autonomous agent):      http://10.10.10.2:3003"
echo "  vLLM Qwen3.8-27B (chat/agent/FIM): http://10.10.10.2:8002/v1"
echo "  vLLM nomic-embed-text:             http://10.10.10.2:8003/v1"
echo ""
echo "Next steps:"
echo ""
echo "1. Install Continue.dev in your IDE:"
echo "   VS Code:   code --install-extension Continue.continue"
echo "   PyCharm:   Marketplace → search 'Continue'"
echo "   Neovim:    git clone https://github.com/continuedev/continue.git"
echo ""
echo "2. Configure Continue.dev:"
echo "   Copy configs/continue/config.yaml to:"
echo "   ~/.continue/config.yaml"
echo ""
echo "3. Configure VS Code Copilot Chat (Manage Models -> Custom Endpoint):"
echo "   URL http://10.10.10.2:8002/v1, model qwen3.8-27b, tool calling on,"
echo "   any non-empty API key (vLLM does not check it)"
echo ""
echo "4. Test Continue.dev:"
echo "   Ctrl+L (VS Code): Start a code chat session"
echo "   Select a code block, run /security-review slash command"
echo ""
echo "5. Test tab autocomplete:"
echo "   Type incomplete code, wait for suggestions (should be instant)"
echo ""
echo "6. Test OpenHands:"
echo "   Visit http://10.10.10.2:3003"
echo "   Create workspace and run tasks like:"
echo "   - 'Implement a FastAPI endpoint for X with tests'"
echo "   - 'Fix the failing test in test_module.py'"
echo "   - 'Refactor this function to use async/await'"
echo ""
echo "7. Run validation:"
echo "   bash scripts/validate-phase11.sh"
