#!/usr/bin/env bash
# Test harness for the NVLink checks ([5] link count, [6] topology) in
# configs/drivers/verify-drivers.sh, against a stub nvidia-smi. The topology
# matrix is the one captured on the host (docs/validation/TASK-014-*); the
# `nvlink --status` lines follow the driver's "Link N: <speed> GB/s" /
# "Link N: <inactive>" format, which is NOT confirmed against the real host.
#
# Usage: bash scripts/tests/test-verify-drivers.sh   (exit 0 = all passed)

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="$(cd "$HERE/../.." && pwd)/configs/drivers/verify-drivers.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

PASSES=0
FAILS=0
check() {
    local desc=$1
    shift
    if "$@"; then PASSES=$((PASSES + 1)); echo "  ok   $desc"
    else FAILS=$((FAILS + 1)); echo "  FAIL $desc"; fi
}

STUB="$WORK/bin"
mkdir -p "$STUB"
# Knobs: STUB_TOPO=healthy|no-nvlink|fail, STUB_DOWN_LINKS=<n> links down on GPU1
cat > "$STUB/nvidia-smi" <<'EOF'
#!/usr/bin/env bash
case "$*" in
  "--query-gpu=driver_version --format=csv,noheader")
    for i in 0 1 2 3; do echo "570.86.15"; done ;;
  "--query-gpu=name --format=csv,noheader")
    for i in 0 1 2 3; do echo "NVIDIA RTX A5500"; done ;;
  "--query-gpu=persistence_mode --format=csv,noheader")
    for i in 0 1 2 3; do echo "Enabled"; done ;;
  "nvlink --status -i "*)
    gpu=${!#}
    echo "GPU $gpu: NVIDIA RTX A5500 (UUID: GPU-0000000$gpu)"
    down=0
    [ "$gpu" = 1 ] && down=${STUB_DOWN_LINKS:-0}
    for l in 0 1 2 3; do
      if [ "$l" -lt "$down" ]; then echo "	 Link $l: <inactive>"
      else echo "	 Link $l: 14.062 GB/s"; fi
    done ;;
  "topo -m")
    case "${STUB_TOPO:-healthy}" in
      fail) echo "Failed to initialize NVML" >&2; exit 9 ;;
      healthy) a=NV4 ;;
      no-nvlink) a=PHB ;;
    esac
    printf '\tGPU0\tGPU1\tGPU2\tGPU3\tCPU Affinity\tNUMA Affinity\tGPU NUMA ID\n'
    printf 'GPU0\t X \tPHB\tNODE\t%s\t0-31\t0\t\tN/A\n' "$a"
    printf 'GPU1\tPHB\t X \t%s\tNODE\t0-31\t0\t\tN/A\n' "$a"
    printf 'GPU2\tNODE\t%s\t X \tPHB\t0-31\t0\t\tN/A\n' "$a"
    printf 'GPU3\t%s\tNODE\tPHB\t X \t0-31\t0\t\tN/A\n' "$a"
    printf '\nLegend:\n\n  X    = Self\n  PHB  = Connection traversing PCIe as well as a PCIe Host Bridge\n'
    printf '  NODE = Connection traversing PCIe as well as the interconnect between PCIe Host Bridges within a NUMA node\n'
    printf '  NV#  = Connection traversing a bonded set of # NVLinks\n' ;;
  *) echo "stub nvidia-smi: unhandled: $*" >&2; exit 99 ;;
esac
EOF
# No Xorg on the test machine (check [8])
printf '#!/usr/bin/env bash\nexit 1\n' > "$STUB/pgrep"
chmod +x "$STUB"/*

run() { OUT=$(PATH="$STUB:$PATH" bash "$SCRIPT" 2>&1); RC=$?; }

echo "verify-drivers.sh: healthy host"
run
check "exits 0" [ "$RC" -eq 0 ]
check "counts 4/4 links on every GPU" [ "$(grep -c 'NVLink OK (4/4' <<<"$OUT")" -eq 4 ]
check "pair A is NV4" grep -q "NVLink in topology (pair A: GPU0↔GPU3: NV4)" <<<"$OUT"
check "pair B is NV4" grep -q "NVLink in topology (pair B: GPU1↔GPU2: NV4)" <<<"$OUT"

echo "verify-drivers.sh: no NVLink in topology (legend still lists NV#)"
STUB_TOPO=no-nvlink run
check "exits 1" [ "$RC" -eq 1 ]
check "fails pair A" grep -q "No NVLink in topology (pair A" <<<"$OUT"
check "fails pair B" grep -q "No NVLink in topology (pair B" <<<"$OUT"

echo "verify-drivers.sh: two links down on GPU1"
STUB_DOWN_LINKS=2 run
check "exits 1" [ "$RC" -eq 1 ]
check "reports GPU1 degraded 2/4" grep -q "GPU1 NVLink DEGRADED (2/4" <<<"$OUT"
check "other GPUs still OK" [ "$(grep -c 'NVLink OK (4/4' <<<"$OUT")" -eq 3 ]

echo "verify-drivers.sh: topo -m fails"
STUB_TOPO=fail run
check "exits 1 (does not die silently)" [ "$RC" -eq 1 ]
check "reports the topo failure" grep -q "topo -m failed: Failed to initialize NVML" <<<"$OUT"
check "still prints the summary" grep -q "ONE OR MORE CHECKS FAILED" <<<"$OUT"

echo ""
echo "verify-drivers.sh tests: $PASSES passed, $FAILS failed"
[ "$FAILS" -eq 0 ]
