# Phase 02 — Host OS & Driver Baseline
[← Jumpbox & Networking](01-jumpbox-networking.md) | [Next: Text Inference →](03-inference-text.md)

---

## Objective
Establish a clean, reproducible Ubuntu host with verified NVIDIA drivers, CUDA toolkit, Docker with GPU runtime, and confirmed NVLink topology. Everything else builds on this.

---

## Prerequisites
- Ubuntu 26.04 LTS Server (minimal install recommended — no desktop)
- Physical or BMC console access during driver install
- 10GbE networking from Phase 01 complete

---

## Step 1 — Base OS Hardening

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y \
  build-essential git curl wget htop nvtop \
  net-tools iperf3 pciutils lshw \
  python3 python3-pip python3-venv \
  nodejs npm \
  tmux vim jq unzip

# Set hostname
sudo hostnamectl set-hostname adapress

# Disable unnecessary services
sudo systemctl disable --now snapd
sudo systemctl disable --now apport

# Configure automatic security updates only
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

## Step 2 — NVIDIA Driver Installation

```bash
# Blacklist nouveau first
cat <<EOF | sudo tee /etc/modprobe.d/blacklist-nouveau.conf
blacklist nouveau
options nouveau modeset=0
EOF
sudo update-initramfs -u

# Add NVIDIA package repository
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2604/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt update

# Install driver (560 is current production for A5500)
sudo apt install -y nvidia-driver-560 nvidia-utils-560

sudo reboot
```

After reboot:

```bash
# Verify driver
nvidia-smi

# Expected output includes:
# Driver Version: 560.x.x
# CUDA Version: 12.x
# 4x NVIDIA RTX A5500 listed

# Verify NVLink
nvidia-smi nvlink --status -i 0
nvidia-smi nvlink --status -i 1
nvidia-smi nvlink --status -i 2
nvidia-smi nvlink --status -i 3
# All should show 4 links at 14.062 GB/s

# Verify topology
nvidia-smi topo -m
```

---

## Step 3 — Enable GPU Persistence Mode

Keeps the GPU initialized between workloads — eliminates cold-start latency and prevents driver state loss between container restarts.

```bash
sudo nvidia-smi -pm 1

# Make persistent across reboots
cat <<EOF | sudo tee /etc/systemd/system/nvidia-persistence.service
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
```

---

## Step 4 — CUDA Toolkit

```bash
sudo apt install -y cuda-toolkit-12-4

# Add to PATH
echo 'export PATH=/usr/local/cuda/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc

# Verify
nvcc --version
```

---

## Step 5 — Docker with NVIDIA Container Runtime

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install NVIDIA Container Toolkit
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt update && sudo apt install -y nvidia-container-toolkit

# Configure Docker runtime
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

# Verify GPU access in Docker
docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu26.04 nvidia-smi
```

---

## Step 6 — NCCL Configuration

NCCL governs GPU-to-GPU communication in multi-GPU training and inference. Tuning it for your NVLink topology significantly improves all-reduce performance.

```bash
# Create system-wide NCCL config
sudo mkdir -p /etc/nccl
cat <<EOF | sudo tee /etc/nccl/nccl.conf
# Prefer NVLink for P2P transfers
NCCL_P2P_LEVEL=NVL
# Enable shared memory for same-node transfers
NCCL_SHM_DISABLE=0
# Use all available NVLink bandwidth
NCCL_MIN_NCHANNELS=4
# Dump topology for debugging (disable in production)
# NCCL_TOPO_DUMP_FILE=/tmp/nccl_topo.xml
EOF

# Add to Docker daemon environment
sudo mkdir -p /etc/docker
cat <<EOF | sudo tee /etc/docker/daemon.json
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
```

---

## Step 7 — NVLink Validation Script

Save this as `/opt/scripts/validate-nvlink.py` for ongoing use:

```python
#!/usr/bin/env python3
"""
NVLink bandwidth validation for 4x RTX A5500
Expected NVLink pairs: GPU0<->GPU3, GPU1<->GPU2
"""
import torch
import time
import sys

def measure_bw(a, b, gb=4):
    n = int(gb * 1024**3 / 4)
    src = torch.zeros(n, dtype=torch.float32, device=f'cuda:{a}')
    dst = torch.zeros_like(src, device=f'cuda:{b}')
    # Warmup
    for _ in range(3):
        dst.copy_(src)
    torch.cuda.synchronize()
    t = time.perf_counter()
    for _ in range(10):
        dst.copy_(src)
    torch.cuda.synchronize()
    elapsed = (time.perf_counter() - t) / 10
    return gb / elapsed

NVLINK_PAIRS = [(0, 3), (3, 0), (1, 2), (2, 1)]
PCIE_PAIRS   = [(0, 1), (1, 0), (2, 3), (3, 2)]
NVLINK_THRESHOLD_GBS = 100.0  # below this = PCIe, not NVLink

print(f"GPU count: {torch.cuda.device_count()}")
print()

all_pass = True
for a, b in NVLINK_PAIRS:
    bw = measure_bw(a, b)
    status = "✓ NVLINK" if bw > NVLINK_THRESHOLD_GBS else "✗ PCIe (check bridge!)"
    print(f"GPU{a}→GPU{b}: {bw:6.1f} GB/s  {status}")
    if bw <= NVLINK_THRESHOLD_GBS:
        all_pass = False

print()
for a, b in PCIE_PAIRS:
    bw = measure_bw(a, b)
    print(f"GPU{a}→GPU{b}: {bw:6.1f} GB/s  (PCIe expected)")

print()
print("Result:", "ALL NVLINK PAIRS HEALTHY" if all_pass else "WARNING: CHECK NVLINK BRIDGES")
sys.exit(0 if all_pass else 1)
```

```bash
sudo mkdir -p /opt/scripts
sudo cp validate-nvlink.py /opt/scripts/
sudo chmod +x /opt/scripts/validate-nvlink.py

# Run validation
python3 /opt/scripts/validate-nvlink.py
```

---

## Step 8 — Storage Layout

```bash
# Recommended mount structure for AI workloads
# Adjust to your actual drive layout

# Fast NVMe for active models and Docker
sudo mkdir -p /data/models      # active model weights
sudo mkdir -p /data/docker      # Docker volumes (configure in daemon.json)
sudo mkdir -p /data/checkpoints # training checkpoints
sudo mkdir -p /data/datasets    # training datasets

# Configure Docker data root to NVMe
sudo tee -a /etc/docker/daemon.json <<EOF
{
  "data-root": "/data/docker"
}
EOF
sudo systemctl restart docker
```

---

## Validation Checklist

- [ ] `nvidia-smi` shows all 4x RTX A5500, driver 560+
- [ ] `nvidia-smi nvlink --status -i [0-3]` shows 4 active links per GPU
- [ ] `nvidia-smi topo -m` shows NV4 on GPU0↔GPU3 and GPU1↔GPU2
- [ ] `validate-nvlink.py` passes — all NVLink pairs >100 GB/s
- [ ] `docker run --gpus all nvidia/cuda:... nvidia-smi` works
- [ ] Persistence mode enabled and survives reboot
- [ ] NCCL config in place
- [ ] Storage mounts confirmed

---

## Notes
- Do not install a desktop environment — it wastes VRAM (the display server allocates from GPU0 by default)
- If a display is needed for local access, use `nvidia-smi` to verify no FB memory is consumed by Xorg
- Driver version 560 is the minimum for full A5500 NVLink support under CUDA 12.4
- Keep `/data/models` on NVMe — model load time from spinning disk is painful at 70B+ parameter sizes
