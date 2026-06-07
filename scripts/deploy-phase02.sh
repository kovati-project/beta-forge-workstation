#!/usr/bin/env bash
# Deploy Phase 02: Host OS & Driver Baseline
# Run on the WORKSTATION (adapress) as kasemo.
# Requires physical/BMC console or SSH from jumpbox.
#
# This script handles everything up to and including the first reboot.
# After the reboot, re-run with: bash scripts/deploy-phase02.sh --post-reboot
#
# Steps:
#   1. Base OS hardening + packages (including nodejs, npm)
#   2. Blacklist nouveau + NVIDIA driver install  → REBOOT
#   3. [post-reboot] Persistence mode + systemd unit
#   4. [post-reboot] CUDA toolkit
#   5. [post-reboot] Docker + NVIDIA Container Toolkit
#   6. [post-reboot] NCCL config + Docker daemon.json
#   7. [post-reboot] NVLink validation script
#   8. [post-reboot] Storage layout

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POST_REBOOT=false

for arg in "$@"; do
  case "$arg" in
    --post-reboot) POST_REBOOT=true ;;
    --help|-h)
      echo "Usage: $0 [--post-reboot]"
      echo "  Run without flags first. Reboot when prompted. Then re-run with --post-reboot."
      exit 0
      ;;
  esac
done

# ── Helpers ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
step()  { echo ""; echo -e "${GREEN}[Phase 02]${NC} $*"; }
ok()    { echo -e "  ${GREEN}✓${NC} $*"; }
warn()  { echo -e "  ${YELLOW}⚠${NC} $*"; }
fail()  { echo -e "  ${RED}✗${NC} $*" >&2; exit 1; }

echo "╔══════════════════════════════════════════════════╗"
echo "║        Phase 02 — Host OS & Driver Baseline      ║"
if $POST_REBOOT; then
echo "║                [post-reboot steps]                ║"
fi
echo "╚══════════════════════════════════════════════════╝"
echo ""

# ── Must run as non-root with sudo access ─────────────────────────────────────
[[ $EUID -ne 0 ]] || fail "Run as kasemo (not root). Script uses sudo internally."
sudo -n true 2>/dev/null || fail "Passwordless sudo required. Add to /etc/sudoers.d/ first."

# ═══════════════════════════════════════════════════════════════════════════════
# PRE-REBOOT STEPS (1 & 2)
# ═══════════════════════════════════════════════════════════════════════════════
if ! $POST_REBOOT; then

# ── Step 1: Base OS packages ──────────────────────────────────────────────────
step "Step 1/8 — Base OS hardening & packages"

sudo apt-get update -q
sudo apt-get full-upgrade -y -q
sudo apt-get install -y -q \
  build-essential git curl wget htop nvtop \
  net-tools iperf3 pciutils lshw \
  python3 python3-pip python3-venv \
  nodejs npm \
  tmux vim jq unzip \
  unattended-upgrades

ok "Base packages installed"

# Verify Node versions meet deploy-ui.sh requirement (>= 18)
NODE_VER=$(node --version | sed 's/v//' | cut -d. -f1)
NPM_VER=$(npm --version | cut -d. -f1)
ok "node v$(node --version | tr -d v)  npm v$(npm --version)"
[[ $NODE_VER -ge 18 ]] || warn "Node < 18 — deploy-ui.sh requires >= 18. Consider NodeSource PPA."

# Set hostname
if [[ "$(hostname)" != "adapress" ]]; then
  sudo hostnamectl set-hostname adapress
  ok "Hostname set to adapress"
else
  ok "Hostname already adapress"
fi

# Disable unnecessary services
sudo systemctl disable --now snapd 2>/dev/null && ok "snapd disabled" || warn "snapd not present (skipping)"
sudo systemctl disable --now apport 2>/dev/null && ok "apport disabled" || warn "apport not present (skipping)"

# Configure automatic security updates
sudo dpkg-reconfigure -plow unattended-upgrades < /dev/null
ok "Unattended security upgrades configured"

# ── Step 2: NVIDIA driver ──────────────────────────────────────────────────────
step "Step 2/8 — NVIDIA driver install (requires reboot after)"

# Blacklist nouveau
sudo tee /etc/modprobe.d/blacklist-nouveau.conf > /dev/null <<'EOF'
blacklist nouveau
options nouveau modeset=0
EOF
sudo update-initramfs -u -q
ok "Nouveau blacklisted"

# NVIDIA CUDA repo keyring
KEYRING_DEB="cuda-keyring_1.1-1_all.deb"
if [[ ! -f "/tmp/$KEYRING_DEB" ]]; then
  wget -q -O "/tmp/$KEYRING_DEB" \
    "https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2604/x86_64/$KEYRING_DEB"
fi
sudo dpkg -i "/tmp/$KEYRING_DEB"
sudo apt-get update -q
ok "NVIDIA CUDA repo added"

# Install driver
sudo apt-get install -y -q nvidia-driver-560 nvidia-utils-560
ok "nvidia-driver-560 installed"

echo ""
echo "  ╔─────────────────────────────────────────────╗"
echo "  │  REBOOT REQUIRED — driver will not load     │"
echo "  │  until nouveau is fully unloaded.           │"
echo "  │                                             │"
echo "  │  sudo reboot                                │"
echo "  │                                             │"
echo "  │  After reboot, re-run:                      │"
echo "  │  bash scripts/deploy-phase02.sh --post-reboot│"
echo "  ╚─────────────────────────────────────────────╝"
echo ""
exit 0

fi  # end pre-reboot block

# ═══════════════════════════════════════════════════════════════════════════════
# POST-REBOOT STEPS (3–8)
# ═══════════════════════════════════════════════════════════════════════════════

# ── Step 3: Verify driver + persistence mode ───────────────────────────────────
step "Step 3/8 — Verify driver & enable persistence mode"

command -v nvidia-smi >/dev/null 2>&1 || fail "nvidia-smi not found — driver not loaded. Check dmesg."
GPU_COUNT=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
DRIVER_VER=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
ok "nvidia-smi: $GPU_COUNT GPUs, driver $DRIVER_VER"
[[ $GPU_COUNT -eq 4 ]] || warn "Expected 4 GPUs, found $GPU_COUNT"

# NVLink check
for i in 0 1 2 3; do
  LINKS=$(nvidia-smi nvlink --status -i $i 2>/dev/null | grep -c "Active" || true)
  ok "GPU$i NVLink: $LINKS active links"
done

# Enable persistence mode
sudo nvidia-smi -pm 1
ok "Persistence mode enabled"

# Systemd unit for persistence across reboots
sudo tee /etc/systemd/system/nvidia-persistence.service > /dev/null <<'EOF'
[Unit]
Description=NVIDIA Persistence Mode
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/nvidia-smi -pm 1
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl enable --now nvidia-persistence.service
ok "nvidia-persistence.service enabled"

# ── Step 4: CUDA toolkit ───────────────────────────────────────────────────────
step "Step 4/8 — CUDA toolkit"

sudo apt-get install -y -q cuda-toolkit-12-4
ok "cuda-toolkit-12-4 installed"

# PATH additions (idempotent)
BASHRC="$HOME/.bashrc"
grep -qF 'export PATH=/usr/local/cuda/bin' "$BASHRC" || \
  echo 'export PATH=/usr/local/cuda/bin:$PATH' >> "$BASHRC"
grep -qF 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64' "$BASHRC" || \
  echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:${LD_LIBRARY_PATH:-}' >> "$BASHRC"
export PATH=/usr/local/cuda/bin:$PATH
nvcc --version | head -1 && ok "nvcc available" || warn "nvcc not in PATH yet — re-source .bashrc"

# ── Step 5: Docker + NVIDIA Container Toolkit ─────────────────────────────────
step "Step 5/8 — Docker + NVIDIA Container Toolkit"

if ! command -v docker &>/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  ok "Docker installed"
else
  ok "Docker already installed ($(docker --version | awk '{print $3}' | tr -d ','))"
fi

# Add user to docker group
if ! groups "$USER" | grep -q docker; then
  sudo usermod -aG docker "$USER"
  warn "Added $USER to docker group — will take effect on next login"
else
  ok "$USER already in docker group"
fi

# NVIDIA Container Toolkit
if ! dpkg -l nvidia-container-toolkit &>/dev/null; then
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -sL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list > /dev/null
  sudo apt-get update -q
  sudo apt-get install -y -q nvidia-container-toolkit
  ok "nvidia-container-toolkit installed"
else
  ok "nvidia-container-toolkit already installed"
fi

sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
ok "Docker NVIDIA runtime configured"

# Smoke test
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu22.04 nvidia-smi \
  && ok "Docker GPU access verified" \
  || fail "Docker GPU test failed — check nvidia-container-toolkit config"

# ── Step 6: NCCL config + Docker daemon.json ──────────────────────────────────
step "Step 6/8 — NCCL config & Docker daemon"

sudo mkdir -p /etc/nccl
sudo tee /etc/nccl/nccl.conf > /dev/null <<'EOF'
NCCL_P2P_LEVEL=NVL
NCCL_SHM_DISABLE=0
NCCL_MIN_NCHANNELS=4
EOF
ok "NCCL config written to /etc/nccl/nccl.conf"

# Write Docker daemon.json (merge-safe: only write if not already present)
DAEMON_JSON=/etc/docker/daemon.json
if [[ ! -f "$DAEMON_JSON" ]] || ! grep -q '"default-runtime"' "$DAEMON_JSON"; then
  sudo mkdir -p /etc/docker
  sudo tee "$DAEMON_JSON" > /dev/null <<'EOF'
{
  "default-runtime": "nvidia",
  "runtimes": {
    "nvidia": {
      "path": "nvidia-container-runtime",
      "runtimeArgs": []
    }
  },
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  }
}
EOF
  sudo systemctl restart docker
  ok "Docker daemon.json written"
else
  ok "Docker daemon.json already configured"
fi

# ── Step 7: NVLink validation script ─────────────────────────────────────────
step "Step 7/8 — NVLink validation script"

sudo mkdir -p /opt/scripts
sudo cp "$REPO_ROOT/configs/drivers/validate-nvlink.py" /opt/scripts/validate-nvlink.py \
  2>/dev/null || \
  sudo tee /opt/scripts/validate-nvlink.py > /dev/null <<'PYEOF'
#!/usr/bin/env python3
"""NVLink bandwidth validation for 4x RTX A5500. Expected pairs: GPU0<->GPU3, GPU1<->GPU2."""
import torch, time, sys

def measure_bw(a, b, gb=4):
    n = int(gb * 1024**3 / 4)
    src = torch.zeros(n, dtype=torch.float32, device=f'cuda:{a}')
    dst = torch.zeros_like(src, device=f'cuda:{b}')
    for _ in range(3): dst.copy_(src)
    torch.cuda.synchronize()
    t = time.perf_counter()
    for _ in range(10): dst.copy_(src)
    torch.cuda.synchronize()
    return gb / ((time.perf_counter() - t) / 10)

NVLINK_PAIRS = [(0, 3), (3, 0), (1, 2), (2, 1)]
PCIE_PAIRS   = [(0, 1), (1, 0), (2, 3), (3, 2)]
print(f"GPU count: {torch.cuda.device_count()}\n")
all_pass = True
for a, b in NVLINK_PAIRS:
    bw = measure_bw(a, b)
    ok = bw > 100.0
    print(f"GPU{a}→GPU{b}: {bw:6.1f} GB/s  {'✓ NVLINK' if ok else '✗ PCIe (check bridge!)'}")
    if not ok: all_pass = False
print()
for a, b in PCIE_PAIRS:
    bw = measure_bw(a, b)
    print(f"GPU{a}→GPU{b}: {bw:6.1f} GB/s  (PCIe expected)")
print(f"\nResult: {'ALL NVLINK PAIRS HEALTHY' if all_pass else 'WARNING: CHECK NVLINK BRIDGES'}")
sys.exit(0 if all_pass else 1)
PYEOF
sudo chmod +x /opt/scripts/validate-nvlink.py
ok "NVLink validation script at /opt/scripts/validate-nvlink.py"

# ── Step 8: Storage layout ─────────────────────────────────────────────────────
step "Step 8/8 — Storage layout"

for dir in \
  /data/models/ollama \
  /data/models/vllm \
  /data/models/comfyui/checkpoints \
  /data/models/comfyui/loras \
  /data/models/comfyui/vae \
  /data/models/comfyui/upscale_models \
  /data/checkpoints \
  /data/datasets \
  /data/outputs/comfyui \
  /data/outputs/upscaled \
  /data/backups \
  /data/config \
  /data/n8n-files \
  /data/openhands; do
  sudo mkdir -p "$dir"
done
sudo chown -R "$USER:$USER" /data
ok "Storage layout created under /data"

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║           Phase 02 complete                      ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Validation checklist:"
echo "    nvidia-smi                          → 4x RTX A5500, driver 560+"
echo "    nvidia-smi topo -m                  → NV4 on GPU0↔GPU3, GPU1↔GPU2"
echo "    python3 /opt/scripts/validate-nvlink.py  → all NVLink pairs > 100 GB/s"
echo "    docker run --gpus all nvidia/cuda:... nvidia-smi"
echo "    node --version                      → v22+"
echo "    npm --version                       → 10+"
echo ""
echo "  Next: bash scripts/deploy-phase03.sh"
echo ""
