#!/usr/bin/env bash
# Creates /data/ directories for image inference stack (Phase 04).
# Safe to re-run.
set -euo pipefail

sudo mkdir -p /data/models/comfyui/checkpoints
sudo mkdir -p /data/models/comfyui/loras
sudo mkdir -p /data/models/comfyui/vae
sudo mkdir -p /data/models/comfyui/controlnet
sudo mkdir -p /data/models/comfyui/embeddings
sudo mkdir -p /data/models/comfyui/upscale_models
sudo mkdir -p /data/models/invokeai
sudo mkdir -p /data/outputs/comfyui
sudo mkdir -p /data/outputs/invokeai
sudo mkdir -p /data/outputs/upscaled
sudo mkdir -p /data/outputs/rembg

sudo chown -R kasemo:kasemo /data/models/comfyui /data/models/invokeai /data/outputs

echo "Phase 04 storage layout created."
ls -la /data/models/ /data/outputs/
