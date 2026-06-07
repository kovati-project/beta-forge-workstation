#!/usr/bin/env bash
# Deploy Phase 03: Text Inference Stack
# Run on the workstation as kasemo.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== Phase 03: Text Inference Deploy ==="
echo ""

# ── Verify compose file exists ────────────────────────────────────────────────
if [[ ! -f "$REPO_ROOT/docker/compose.inference.yml" ]]; then
    echo "ERROR: Expected compose file at $REPO_ROOT/docker/compose.inference.yml"
    exit 1
fi

# ── 1. Storage ────────────────────────────────────────────────────────────────
echo "[1/4] Verifying storage layout..."
for dir in /data/models/ollama /data/models/vllm /data/models/hf-cache; do
    if [[ ! -d "$dir" ]]; then
        echo "  Running setup-storage.sh..."
        bash "$REPO_ROOT/scripts/setup-storage.sh"
        break
    fi
done
echo "  ✓ Storage directories present"

# ── 2. Ollama ─────────────────────────────────────────────────────────────────
echo "[2/4] Starting Ollama..."
docker compose -f "$REPO_ROOT/docker/compose.inference.yml" up -d ollama
sleep 5
if docker exec ollama ollama list &>/dev/null; then
    echo "  ✓ Ollama running"
else
    echo "  ✗ Ollama not responding — check: docker logs ollama"
    exit 1
fi

# ── 3. Model symlink check ────────────────────────────────────────────────────
echo "[3/4] Checking vLLM model symlink..."
if [[ ! -e /data/models/vllm/current ]]; then
    echo "  ⚠  /data/models/vllm/current symlink not set."
    echo "     Download a model first, then:"
    echo "     ln -sf /data/models/vllm/<model-dir> /data/models/vllm/current"
    echo "  Skipping vLLM start."
else
    echo "  ✓ Symlink: $(readlink /data/models/vllm/current)"
    echo "[4/4] Starting vLLM pair A..."
    docker compose -f "$REPO_ROOT/docker/compose.inference.yml" up -d vllm-pair-a
    echo "  Waiting for model load (this takes 1–3 min for 32B)..."
    if timeout 300 bash -c 'until curl -sf http://localhost:8000/v1/models &>/dev/null; do sleep 5; done'; then
        echo "  ✓ vLLM pair A ready"
    else
        echo "  ⚠  Model load exceeded 5 min"
        echo "     This is normal for 32B+ — monitor with: docker logs -f vllm-pair-a"
    fi
fi

echo ""
echo "=== Deploy complete ==="
echo ""
echo "Manual model downloads (run after this script):"
echo ""
echo "  Ollama models:"
echo "    docker exec ollama ollama pull mistral:7b"
echo "    docker exec ollama ollama pull qwen2.5-coder:14b"
echo "    docker exec ollama ollama pull nomic-embed-text"
echo ""
echo "  vLLM 32B model (pair A):"
echo "    pip3 install -q huggingface_hub"
echo "    huggingface-cli download Qwen/Qwen2.5-32B-Instruct \\"
echo "      --local-dir /data/models/vllm/qwen2.5-32b --exclude '*.gguf'"
echo "    ln -sf /data/models/vllm/qwen2.5-32b /data/models/vllm/current"
echo "    docker compose -f docker/compose.inference.yml up -d vllm-pair-a"
echo ""
echo "  vLLM 70B model (4-GPU, requires Meta HF license):"
echo "    If you do not have HF token with Llama-3.3 access, run:"
echo "      huggingface-cli login"
echo "    Then:"
echo "    huggingface-cli download meta-llama/Llama-3.3-70B-Instruct \\"
echo "      --local-dir /data/models/vllm/llama3.3-70b --exclude '*.gguf'"
echo "    ln -sf /data/models/vllm/llama3.3-70b /data/models/vllm/large"
