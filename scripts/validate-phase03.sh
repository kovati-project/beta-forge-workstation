#!/usr/bin/env bash
[ -n "${BASH_VERSION:-}" ] || { echo "ERROR: this script needs bash - run: bash $0" >&2; exit 1; }
# Run on the workstation after deploy-phase03.sh and model downloads complete.
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
PASS=0; FAIL=0; WARN=0

check() {
    local desc="$1"; shift
    if eval "$@" &>/dev/null; then
        echo -e "${GREEN}✓${NC} $desc"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} $desc"
        ((FAIL++))
    fi
}

warn() {
    echo -e "${YELLOW}?${NC} $1 — check manually"
    ((WARN++))
}

echo "=== Phase 03 Validation ==="
echo ""

# Default stack: vllm-4gpu (Qwen3.8-27B) + vllm-embed
check "vllm-4gpu container running"      "docker ps --filter name=vllm-4gpu --filter status=running | grep -q vllm-4gpu"
check "vllm-4gpu serving qwen3.8-27b"    "curl -sf http://localhost:8002/v1/models | grep -q '\"qwen3.8-27b\"'"
check "vllm-embed container running"     "docker ps --filter name=vllm-embed --filter status=running | grep -q vllm-embed"
check "vllm-embed serving nomic-embed-text" "curl -sf http://localhost:8003/v1/models | grep -q nomic-embed-text"
check "Ollama container removed"         "! docker inspect ollama >/dev/null 2>&1"

# vLLM pair A (opt-in loadout profile; shares GPUs with the default stack)
echo ""
if docker ps --filter name=vllm-pair-a --filter status=running | grep -q vllm-pair-a; then
    check "vLLM pair A container running"  "true"
    check "vLLM pair A API responding"     "curl -sf http://localhost:8000/v1/models"
    check "vLLM pair A using GPU 0+3"      "docker exec vllm-pair-a env | grep -q 'CUDA_VISIBLE_DEVICES=0,3'"
    warn "First-token latency <2s for 32B — test: curl -s http://localhost:8000/v1/chat/completions -H 'Content-Type: application/json' -d '{\"model\":\"current-model\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":5}'"
    warn "GPU0+GPU3 VRAM consumed — check: nvidia-smi"
    warn "No NCCL errors — check: docker logs vllm-pair-a 2>&1 | grep -i nccl"
    warn "GPU utilization >80% during inference — check: nvidia-smi dmon -s u -d 2"
else
    echo -e "${YELLOW}—${NC} vLLM pair A not running (opt-in profile: inference-pair-a)"
fi

# Storage
echo ""
check "/data/models/vllm exists"         "test -d /data/models/vllm"
check "/data/models/hf-cache exists"     "test -d /data/models/hf-cache"

echo ""
echo "Result: ${PASS} passed, ${FAIL} failed, ${WARN} manual checks"
[[ $FAIL -eq 0 ]] && echo -e "${GREEN}Phase 03 READY${NC}" || echo -e "${RED}Phase 03 NOT READY — fix failures above${NC}"
exit $FAIL
