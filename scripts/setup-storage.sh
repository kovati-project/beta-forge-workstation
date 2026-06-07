#!/usr/bin/env bash
# Creates /data/ directory structure for AI workstation.
# Run once on the workstation as a user with sudo.
# Safe to re-run — uses mkdir -p throughout.
set -euo pipefail

sudo mkdir -p /data/models/ollama
sudo mkdir -p /data/models/vllm
sudo mkdir -p /data/models/hf-cache
sudo mkdir -p /data/docker
sudo mkdir -p /data/checkpoints
sudo mkdir -p /data/datasets

# Set ownership so kasemo can write without sudo
sudo chown -R kasemo:kasemo /data/models
sudo chown -R kasemo:kasemo /data/checkpoints
sudo chown -R kasemo:kasemo /data/datasets

echo "Storage layout created:"
df -h /data 2>/dev/null || df -h /
echo ""
echo "Directories:"
ls -la /data/
