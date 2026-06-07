#!/usr/bin/env bash
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

# Ollama
check "Ollama container running"         "docker ps --filter name=ollama --filter status=running | grep -q ollama"
check "Ollama API responding"            "curl -sf http://localhost:11434/v1/models"
check "Ollama has at least one model"    "docker exec ollama ollama list 2>/dev/null | grep -qv '^NAME'"
check "nomic-embed-text present"         "docker exec ollama ollama list 2>/dev/null | grep -q nomic-embed-text"

# vLLM pair A
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
    echo -e "${YELLOW}—${NC} vLLM pair A not running (model not downloaded yet — skip until symlink is set)"
fi

# Storage
echo ""
check "/data/models/ollama exists"       "test -d /data/models/ollama"
check "/data/models/vllm exists"         "test -d /data/models/vllm"
check "/data/models/hf-cache exists"     "test -d /data/models/hf-cache"

echo ""
echo "Result: ${PASS} passed, ${FAIL} failed, ${WARN} manual checks"
[[ $FAIL -eq 0 ]] && echo -e "${GREEN}Phase 03 READY${NC}" || echo -e "${RED}Phase 03 NOT READY — fix failures above${NC}"
exit $FAIL
