#!/usr/bin/env bash
[ -n "${BASH_VERSION:-}" ] || { echo "ERROR: this script needs bash - run: bash $0" >&2; exit 1; }
# Deploy Phase 03: Text Inference Stack
# Run on the workstation as kasemo.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/container-helpers.sh
source "$REPO_ROOT/scripts/lib/container-helpers.sh"

echo "=== Phase 03: Text Inference Deploy ==="
echo ""

# ── Verify compose file exists ────────────────────────────────────────────────
if [[ ! -f "$REPO_ROOT/docker/compose.inference.yml" ]]; then
    echo "ERROR: Expected compose file at $REPO_ROOT/docker/compose.inference.yml"
    exit 1
fi

# ── 1. Storage ────────────────────────────────────────────────────────────────
echo "[1/4] Verifying storage layout..."
for dir in /data/models/vllm /data/models/hf-cache; do
    if [[ ! -d "$dir" ]]; then
        echo "  Running setup-storage.sh..."
        bash "$REPO_ROOT/scripts/setup-storage.sh"
        break
    fi
done
echo "  ✓ Storage directories present"

# ── 2. Default model (Qwen3.8-27B-FP8 on all four GPUs) ───────────────────────
# vllm-4gpu serves /models/large. The loadout manager UI (Models → download,
# then activate slot "4gpu") does the same as the commands below.
MODEL_DIR=/data/models/vllm/qwen3.8-27b-fp8
echo "[2/4] Checking the default model..."
if [[ ! -f "$MODEL_DIR/config.json" ]]; then
    echo "  Downloading Qwen/Qwen3.8-27B-FP8 (~31 GB) to $MODEL_DIR..."
    pip3 install -q huggingface_hub
    huggingface-cli download Qwen/Qwen3.8-27B-FP8 --local-dir "$MODEL_DIR" --exclude '*.gguf'
fi
if [[ "$(readlink /data/models/vllm/large)" != "qwen3.8-27b-fp8" ]]; then
    # relative target: it must resolve inside the container too (/models/large)
    ln -sfn qwen3.8-27b-fp8 /data/models/vllm/large
fi
echo "  ✓ /data/models/vllm/large -> $(readlink /data/models/vllm/large)"

# ── 3. Stop what holds the GPUs ───────────────────────────────────────────────
# vllm-4gpu needs all four GPUs; pair A/B and the retired Ollama container
# would hold VRAM on them.
echo "[3/4] Freeing GPUs..."
for c in ollama vllm-pair-a vllm-pair-b; do
    if docker inspect "$c" &>/dev/null; then
        docker rm -f "$c" > /dev/null && echo "  removed $c"
    fi
done

# ── 4. Default stack ──────────────────────────────────────────────────────────
echo "[4/4] Starting vllm-4gpu (Qwen3.8-27B) and vllm-embed..."
remove_orphan vllm-4gpu ai-inference
remove_orphan vllm-embed ai-inference
docker compose -f "$REPO_ROOT/docker/compose.inference.yml" up -d --remove-orphans vllm-4gpu vllm-embed
echo "  Waiting for model load (first start also compiles CUDA graphs; 3–10 min)..."
if timeout 900 bash -c 'until curl -sf http://localhost:8002/v1/models &>/dev/null; do sleep 10; done'; then
    echo "  ✓ vllm-4gpu ready on :8002"
else
    echo "  ⚠  Not ready after 15 min — check: docker logs -f vllm-4gpu"
fi
if timeout 300 bash -c 'until curl -sf http://localhost:8003/v1/models &>/dev/null; do sleep 5; done'; then
    echo "  ✓ vllm-embed ready on :8003"
else
    echo "  ⚠  vllm-embed not ready — check: docker logs -f vllm-embed"
fi

echo ""
echo "=== Deploy complete ==="
echo ""
echo "Optional models for the pair A/B profiles (each stops the default stack):"
echo ""
echo "  vLLM 32B model (pair A):"
echo "    pip3 install -q huggingface_hub"
echo "    huggingface-cli download Qwen/Qwen2.5-32B-Instruct \\"
echo "      --local-dir /data/models/vllm/qwen2.5-32b --exclude '*.gguf'"
echo "    ln -sfn qwen2.5-32b /data/models/vllm/current"
echo "    curl -X POST http://localhost:8800/activate/inference-pair-a"
