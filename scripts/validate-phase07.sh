#!/usr/bin/env bash
# Validate Phase 07: Training Pipeline
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
    echo -e "${YELLOW}?${NC} $1 — manual verification needed"
    ((WARN++))
}

echo "=== Phase 07 Validation ==="
echo ""

# Directories
check "Dataset directories exist" "[[ -d /data/datasets/images && -d /data/datasets/text ]]"
check "Checkpoint directories exist" "[[ -d /data/checkpoints/kohya && -d /data/checkpoints/axolotl ]]"
check "Notebooks directory exists" "[[ -d /data/notebooks ]]"

# Services
echo ""
check "Label Studio container running" "docker ps --filter name=label-studio --filter status=running | grep -q label-studio"
check "Label Studio HTTP responding" "curl -sf http://localhost:8081/"
check "JupyterLab container running" "docker ps --filter name=jupyterlab --filter status=running | grep -q jupyterlab"
check "JupyterLab HTTP responding" "curl -sf http://localhost:8888/"

# Compose validation
echo ""
check "compose.training.yml is valid" "docker compose -f docker/compose.training.yml config > /dev/null"
check "Kohya service defined" "docker compose -f docker/compose.training.yml config | grep -q 'kohya'"
check "Axolotl service defined" "docker compose -f docker/compose.training.yml config | grep -q 'axolotl'"
check "Label Studio volume mounted" "docker inspect label-studio | grep -q 'label-studio-data'"

# Configs
echo ""
check "Kohya config template exists" "[[ -f configs/kohya/sdxl_lora.toml ]]"
check "Axolotl config template exists" "[[ -f configs/axolotl/qlora_4gpu.yml ]]"
check "Dataset converter script exists" "[[ -f scripts/convert_labelstudio_to_alpaca.py ]]"

# GPU assignment verification
echo ""
warn "Kohya has GPU 1,2 assigned — verify: docker inspect kohya | grep NVIDIA_VISIBLE"
warn "Axolotl has GPU 0,1,2,3 assigned — verify: docker inspect axolotl | grep NVIDIA_VISIBLE"
warn "JupyterLab has GPU 0 assigned — verify: docker inspect jupyterlab | grep NVIDIA_VISIBLE"

# Manual checks
echo ""
warn "Label Studio login works with admin@local.dev / changeme"
warn "Can access uploaded dataset files from Label Studio UI"
warn "JupyterLab token accessible in docker logs jupyterlab"
warn "PyTorch and CUDA available in JupyterLab container"
warn "Kohya and Unsloth images can be pulled (on-demand)"
warn "Axolotl image can be pulled (on-demand)"

echo ""
echo "Result: ${PASS} passed, ${FAIL} failed, ${WARN} manual checks"
[[ $FAIL -eq 0 ]] && echo -e "${GREEN}Phase 07 READY${NC}" || echo -e "${RED}Phase 07 NOT READY — fix failures above${NC}"
exit $FAIL
