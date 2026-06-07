#!/usr/bin/env bash
# install-nvidia.sh — Phase 02 Step 2
# Brief ID: P02S2-001
#
# Installs NVIDIA driver 560 on Ubuntu 26.04 LTS Server.
# Run as a normal user with sudo privileges from the physical/BMC console.
# Safe to re-run (idempotent).
#
# Does NOT install CUDA toolkit (Step 4) or Docker (Step 5).

set -euo pipefail

DRIVER_VERSION="560"
CUDA_KEYRING_DEB="cuda-keyring_1.1-1_all.deb"
CUDA_REPO_URL="https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2604/x86_64"

# ---------------------------------------------------------------------------
# 1. Blacklist nouveau
# ---------------------------------------------------------------------------
BLACKLIST_FILE="/etc/modprobe.d/blacklist-nouveau.conf"

if [[ ! -f "$BLACKLIST_FILE" ]]; then
    echo "[1/4] Blacklisting nouveau driver..."
    cat <<EOF | sudo tee "$BLACKLIST_FILE"
blacklist nouveau
options nouveau modeset=0
EOF
    sudo update-initramfs -u
    echo "      nouveau blacklisted and initramfs updated."
else
    echo "[1/4] nouveau already blacklisted — skipping."
fi

# ---------------------------------------------------------------------------
# 2. Add NVIDIA/CUDA package repository
# ---------------------------------------------------------------------------
if ! dpkg -l cuda-keyring &>/dev/null; then
    echo "[2/4] Adding NVIDIA CUDA package repository..."
    TMP_DEB="$(mktemp -d)/${CUDA_KEYRING_DEB}"
    wget -q -O "$TMP_DEB" "${CUDA_REPO_URL}/${CUDA_KEYRING_DEB}"
    sudo dpkg -i "$TMP_DEB"
    rm -f "$TMP_DEB"
    sudo apt-get update -q
    echo "      CUDA repository added."
else
    echo "[2/4] CUDA repository keyring already installed — skipping."
    sudo apt-get update -q
fi

# ---------------------------------------------------------------------------
# 3. Install NVIDIA driver
# ---------------------------------------------------------------------------
if ! dpkg -l "nvidia-driver-${DRIVER_VERSION}" &>/dev/null; then
    echo "[3/4] Installing nvidia-driver-${DRIVER_VERSION} and nvidia-utils-${DRIVER_VERSION}..."
    sudo apt-get install -y \
        "nvidia-driver-${DRIVER_VERSION}" \
        "nvidia-utils-${DRIVER_VERSION}"
    echo "      Driver installed."
else
    echo "[3/4] nvidia-driver-${DRIVER_VERSION} already installed — skipping."
fi

# ---------------------------------------------------------------------------
# 4. Install and enable persistence service
# ---------------------------------------------------------------------------
SERVICE_SRC="$(dirname "$(realpath "$0")")/nvidia-persistence.service"
SERVICE_DST="/etc/systemd/system/nvidia-persistence.service"

echo "[4/4] Installing nvidia-persistence.service..."
if [[ -f "$SERVICE_SRC" ]]; then
    sudo cp "$SERVICE_SRC" "$SERVICE_DST"
    sudo systemctl daemon-reload
    sudo systemctl enable nvidia-persistence.service
    echo "      Persistence service installed and enabled (starts after next reboot)."
else
    echo "      WARNING: nvidia-persistence.service not found at $SERVICE_SRC"
    echo "      Copy it manually to $SERVICE_DST and run:"
    echo "        sudo systemctl daemon-reload && sudo systemctl enable nvidia-persistence.service"
fi

# ---------------------------------------------------------------------------
# Done — prompt reboot
# ---------------------------------------------------------------------------
echo ""
echo "================================================================"
echo "  Installation complete."
echo "  A reboot is required to load the new driver and drop nouveau."
echo ""
echo "  After reboot, run:"
echo "    bash verify-drivers.sh"
echo "================================================================"
echo ""
read -rp "Reboot now? [y/N] " REBOOT_ANSWER
if [[ "${REBOOT_ANSWER,,}" == "y" ]]; then
    sudo reboot
fi
