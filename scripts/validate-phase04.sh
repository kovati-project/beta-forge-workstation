#!/usr/bin/env bash
# Validate Phase 04: Image Inference Stack
# Run on the workstation after deploy-phase04.sh and at least one model download.
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

echo "=== Phase 04 Validation ==="
echo ""

# Core services
check "ComfyUI container running"      "docker ps --filter name=comfyui --filter status=running | grep -q comfyui"
check "ComfyUI API responding"         "curl -sf http://localhost:8188/system_stats"
check "Rembg container running"        "docker ps --filter name=rembg --filter status=running | grep -q rembg"
check "Rembg API responding"           "curl -sf http://localhost:8190/ 2>/dev/null || true"
check "Real-ESRGAN container running"  "docker ps --filter name=realesrgan --filter status=running | grep -q realesrgan"

# Models
echo ""
check "At least one ComfyUI checkpoint exists"  "ls /data/models/comfyui/checkpoints/ 2>/dev/null | grep -q '.'"
check "ComfyUI Manager installed"               "docker exec comfyui test -d /opt/ComfyUI/custom_nodes/ComfyUI-Manager"

# GPU assignment
echo ""
check "ComfyUI assigned to GPU0"  "docker inspect comfyui | grep -q '\"0\"'"

# InvokeAI should NOT be running
echo ""
check "InvokeAI NOT running (correct — profiled)" "! docker ps --filter name=invokeai --filter status=running | grep -q invokeai"

# Manual checks
echo ""
warn "ComfyUI web UI loads at http://10.10.10.2:8188"
warn "Checkpoint visible in ComfyUI model list (refresh browser)"
warn "Test generation completes — queue a simple txt2img and check /data/outputs/comfyui/"
warn "GPU0 VRAM shows 8–12GB during SDXL generation — check: nvidia-smi"

echo ""
echo "Result: ${PASS} passed, ${FAIL} failed, ${WARN} manual checks"
[[ $FAIL -eq 0 ]] && echo -e "${GREEN}Phase 04 READY${NC}" || echo -e "${RED}Phase 04 NOT READY — fix failures above${NC}"
exit $FAIL
