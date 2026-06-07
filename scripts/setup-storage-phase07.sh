#!/usr/bin/env bash
# Setup Phase 07: Dataset and checkpoint directories
set -euo pipefail

echo "=== Phase 07: Storage Setup ==="
echo ""

# Create dataset directories
echo "Creating dataset directories..."
sudo mkdir -p /data/datasets/{images,text,audio}
sudo mkdir -p /data/datasets/images/{raw,tagged,rejected}
sudo mkdir -p /data/datasets/text/{raw,formatted,validation}
sudo mkdir -p /data/datasets/audio/{raw,processed}

# Create checkpoint directories
echo "Creating checkpoint directories..."
sudo mkdir -p /data/checkpoints/{kohya,axolotl,unsloth}

# Create notebooks directory
echo "Creating notebooks directory..."
sudo mkdir -p /data/notebooks

# Set ownership to current user
echo "Setting permissions..."
sudo chown -R "$(id -u):$(id -g)" /data/datasets /data/checkpoints /data/notebooks
sudo chmod -R 755 /data/datasets /data/checkpoints /data/notebooks

echo ""
echo "✓ All directories created:"
echo "  - /data/datasets/{images,text,audio}/{raw,formatted,etc}"
echo "  - /data/checkpoints/{kohya,axolotl,unsloth}"
echo "  - /data/notebooks"
echo ""
echo "Next: Upload training data to these directories"
