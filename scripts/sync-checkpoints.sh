#!/bin/bash
# Sync training checkpoints to MinIO after each training run
# Usage: ./sync-checkpoints.sh [optional: profile name]

set -e

CHECKPOINT_DIR="/data/checkpoints"
MINIO_BUCKET="local/models"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

echo "=== Checkpoint Sync to MinIO ==="
echo "Timestamp: $TIMESTAMP"

# Check if mc (MinIO client) is installed
if ! command -v mc &> /dev/null; then
    echo "ERROR: mc (MinIO client) not found. Install with:"
    echo "  wget https://dl.min.io/client/mc/release/linux-amd64/mc"
    echo "  chmod +x mc && sudo mv mc /usr/local/bin/"
    exit 1
fi

# Verify MinIO is running
if ! mc alias ls local &> /dev/null; then
    echo "ERROR: MinIO alias 'local' not configured. Run:"
    echo "  mc alias set local http://localhost:9000 admin 5c6eb4508af1de3f08b4acdea9d29934
    exit 1
fi

# Sync Axolotl checkpoints
if [ -d "$CHECKPOINT_DIR/axolotl" ] && [ "$(ls -A $CHECKPOINT_DIR/axolotl)" ]; then
    echo "Syncing Axolotl checkpoints..."
    mc mirror --overwrite "$CHECKPOINT_DIR/axolotl/" "$MINIO_BUCKET/axolotl/$TIMESTAMP/"
    echo "  ✓ Axolotl synced"
else
    echo "  ⊘ No Axolotl checkpoints found (skip)"
fi

# Sync Kohya LoRAs
if [ -d "/data/models/comfyui/loras" ] && [ "$(ls -A /data/models/comfyui/loras)" ]; then
    echo "Syncing Kohya LoRAs..."
    mc mirror --overwrite "/data/models/comfyui/loras/" "$MINIO_BUCKET/loras/$TIMESTAMP/"
    echo "  ✓ Kohya LoRAs synced"
else
    echo "  ⊘ No Kohya LoRAs found (skip)"
fi

# Sync Unsloth checkpoints
if [ -d "$CHECKPOINT_DIR/unsloth" ] && [ "$(ls -A $CHECKPOINT_DIR/unsloth)" ]; then
    echo "Syncing Unsloth checkpoints..."
    mc mirror --overwrite "$CHECKPOINT_DIR/unsloth/" "$MINIO_BUCKET/unsloth/$TIMESTAMP/"
    echo "  ✓ Unsloth synced"
else
    echo "  ⊘ No Unsloth checkpoints found (skip)"
fi

# Sync Kohya training outputs (checkpoints)
if [ -d "$CHECKPOINT_DIR/kohya" ] && [ "$(ls -A $CHECKPOINT_DIR/kohya)" ]; then
    echo "Syncing Kohya training outputs..."
    mc mirror --overwrite "$CHECKPOINT_DIR/kohya/" "$MINIO_BUCKET/kohya-outputs/$TIMESTAMP/"
    echo "  ✓ Kohya training outputs synced"
else
    echo "  ⊘ No Kohya training outputs found (skip)"
fi

echo ""
echo "Sync complete. Verify with:"
echo "  mc ls $MINIO_BUCKET/"
