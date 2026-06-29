#!/bin/bash
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

# vLLM is loaded on-demand by the Loadout Manager — not always running
echo "Checking Phase 03 (vLLM)..."
if ! curl -sf http://localhost:8000/v1/models > /dev/null 2>&1; then
    echo "WARNING: vLLM not active (normal — activate a loadout profile to start it)"
else
    echo "✓ vLLM running on :8000"
fi
echo ""

# Verify Ollama is running
echo "Checking Ollama..."
if ! curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "WARNING: Ollama not running on :11434 — OpenHands will deploy but needs a model endpoint at runtime"
else
    echo "✓ Ollama running on :11434"
fi
echo ""

# Check if code models are available
echo "Checking for code models in Ollama..."
MODELS=$(curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"' | wc -l)
if [ "$MODELS" -lt 3 ]; then
    echo "WARNING: Only $MODELS models found. Pull code models:"
    echo "  docker exec ollama ollama pull qwen2.5-coder:32b"
    echo "  docker exec ollama ollama pull qwen2.5-coder:14b"
    echo "  docker exec ollama ollama pull qwen2.5-coder:7b"
    echo "  docker exec ollama ollama pull deepseek-coder-v2:16b"
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

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Code generation stack ready:"
echo ""
echo "  OpenHands (autonomous agent):      http://10.10.10.2:3003"
echo "  vLLM primary (Qwen 32B):           http://10.10.10.2:8000"
echo "  Ollama (fast models):              http://10.10.10.2:11434"
echo ""
echo "Next steps:"
echo ""
echo "1. Install Continue.dev in your IDE:"
echo "   VS Code:   code --install-extension Continue.continue"
echo "   PyCharm:   Marketplace → search 'Continue'"
echo "   Neovim:    git clone https://github.com/continuedev/continue.git"
echo ""
echo "2. Configure Continue.dev:"
echo "   Copy configs/continue/config.json to:"
echo "   ~/.continue/config.json"
echo ""
echo "3. Pull code models in Ollama:"
echo "   docker exec ollama ollama pull qwen2.5-coder:32b"
echo "   docker exec ollama ollama pull qwen2.5-coder:14b"
echo "   docker exec ollama ollama pull qwen2.5-coder:7b"
echo "   docker exec ollama ollama pull deepseek-coder-v2:16b"
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
echo "7. Test model routing:"
echo "   python3 scripts/code-router.py"
echo ""
echo "8. Run validation:"
echo "   bash scripts/validate-phase11.sh"
