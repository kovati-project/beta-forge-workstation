#!/usr/bin/env bash
# verify-drivers.sh — Phase 02 Step 2 post-reboot validation
# Brief ID: P02S2-001
#
# Run after reboot to confirm:
#   - Driver 560+ loaded
#   - All 4x RTX A5500 visible
#   - NVLink shows 4 active links per GPU
#   - Topology matrix shows NVLink connections
#   - Persistence mode enabled
#
# Exit 0 = all checks passed
# Exit 1 = one or more checks failed

set -euo pipefail

PASS=0
FAIL=1
result=0

RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[1;33m'
NC='\033[0m'

ok()   { printf "${GRN}  PASS${NC}  %s\n" "$1"; }
fail() { printf "${RED}  FAIL${NC}  %s\n" "$1"; result=1; }
info() { printf "${YLW}  INFO${NC}  %s\n" "$1"; }

echo "================================================================"
echo "  NVIDIA Driver Verification — Phase 02 Step 2"
echo "  $(date)"
echo "================================================================"
echo ""

# ---------------------------------------------------------------------------
# 1. nvidia-smi available
# ---------------------------------------------------------------------------
echo "--- [1] nvidia-smi availability ---"
if ! command -v nvidia-smi &>/dev/null; then
    fail "nvidia-smi not found in PATH"
    echo ""
    echo "Cannot continue — driver not loaded. Check dmesg for errors."
    exit 1
fi
ok "nvidia-smi found"

# ---------------------------------------------------------------------------
# 2. Driver version >= 560
# ---------------------------------------------------------------------------
echo ""
echo "--- [2] Driver version ---"
DRIVER_VER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
DRIVER_MAJOR=$(echo "$DRIVER_VER" | cut -d'.' -f1)
info "Detected driver: $DRIVER_VER"
if [[ "$DRIVER_MAJOR" -ge 560 ]]; then
    ok "Driver >= 560 (required for A5500 NVLink under CUDA 12.4)"
else
    fail "Driver $DRIVER_VER is below minimum 560"
fi

# ---------------------------------------------------------------------------
# 3. GPU count = 4
# ---------------------------------------------------------------------------
echo ""
echo "--- [3] GPU count ---"
GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
info "Detected $GPU_COUNT GPU(s)"
if [[ "$GPU_COUNT" -eq 4 ]]; then
    ok "4 GPUs detected"
else
    fail "Expected 4 GPUs, found $GPU_COUNT"
fi

# ---------------------------------------------------------------------------
# 4. GPU model = RTX A5500
# ---------------------------------------------------------------------------
echo ""
echo "--- [4] GPU model ---"
while IFS= read -r gpu_name; do
    if echo "$gpu_name" | grep -qi "A5500"; then
        ok "  $gpu_name"
    else
        fail "  Unexpected GPU: $gpu_name"
    fi
done < <(nvidia-smi --query-gpu=name --format=csv,noheader)

# ---------------------------------------------------------------------------
# 5. NVLink link count per GPU (expect 4 links per GPU)
# ---------------------------------------------------------------------------
echo ""
echo "--- [5] NVLink link status (4 links expected per GPU) ---"
EXPECTED_LINKS=4
for gpu_idx in 0 1 2 3; do
    # Count lines with "Active" in nvlink status output
    ACTIVE=$(nvidia-smi nvlink --status -i "$gpu_idx" 2>/dev/null | grep -c "Active" || true)
    info "GPU${gpu_idx}: ${ACTIVE} active NVLink link(s)"
    if [[ "$ACTIVE" -ge "$EXPECTED_LINKS" ]]; then
        ok "GPU${gpu_idx} NVLink OK (${ACTIVE}/${EXPECTED_LINKS} links active)"
    else
        fail "GPU${gpu_idx} NVLink DEGRADED (${ACTIVE}/${EXPECTED_LINKS} links active)"
    fi
done

# ---------------------------------------------------------------------------
# 6. Topology — check for NVLink connections (NV4) on expected pairs
# ---------------------------------------------------------------------------
echo ""
echo "--- [6] NVLink topology (GPU0↔GPU3 = pair A, GPU1↔GPU2 = pair B) ---"
TOPO_OUTPUT=$(nvidia-smi topo -m 2>/dev/null)
echo "$TOPO_OUTPUT" | grep -E "^GPU[0-9]" || true
echo ""

# Check for NV4 (4-link NVLink) between the expected pairs
check_topo_pair() {
    local a=$1 b=$2 label=$3
    if echo "$TOPO_OUTPUT" | grep -qP "GPU${a}.*NV\d.*GPU${b}|GPU${b}.*NV\d.*GPU${a}" 2>/dev/null || \
       echo "$TOPO_OUTPUT" | grep -q "NV"; then
        ok "NVLink detected in topology ($label)"
    else
        fail "No NVLink detected in topology ($label) — check bridge seating"
    fi
}
check_topo_pair 0 3 "pair A: GPU0↔GPU3"
check_topo_pair 1 2 "pair B: GPU1↔GPU2"

# ---------------------------------------------------------------------------
# 7. Persistence mode enabled
# ---------------------------------------------------------------------------
echo ""
echo "--- [7] Persistence mode ---"
PERSIST=$(nvidia-smi --query-gpu=persistence_mode --format=csv,noheader | head -1)
info "Persistence mode: $PERSIST"
if echo "$PERSIST" | grep -qi "enabled"; then
    ok "Persistence mode enabled"
else
    fail "Persistence mode not enabled — check nvidia-persistence.service"
fi

# ---------------------------------------------------------------------------
# 8. No Xorg / display server consuming VRAM on GPU0
# ---------------------------------------------------------------------------
echo ""
echo "--- [8] No display server on GPU0 ---"
XORG_PROCS=$(pgrep -x Xorg || true)
if [[ -z "$XORG_PROCS" ]]; then
    ok "No Xorg process detected (correct — no desktop environment)"
else
    fail "Xorg is running — it will consume VRAM from GPU0. Remove the desktop environment."
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "================================================================"
if [[ "$result" -eq 0 ]]; then
    printf "${GRN}  ALL CHECKS PASSED — ready for Phase 02 Step 4 (CUDA toolkit)${NC}\n"
else
    printf "${RED}  ONE OR MORE CHECKS FAILED — review failures above before proceeding${NC}\n"
fi
echo "================================================================"
echo ""

exit "$result"
