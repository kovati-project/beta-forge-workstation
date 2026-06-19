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

# Create model directories required by training and studio services
echo "Creating model directories..."
sudo mkdir -p /data/models/comfyui/{loras,checkpoints,vae,controlnet,embeddings,upscale_models}
sudo mkdir -p /data/models/{vllm,hf-cache,whisper,piper,ollama,invokeai}
sudo mkdir -p /data/outputs/{comfyui,invokeai,upscaled,rembg}
sudo mkdir -p /data/audio

# Create notebooks directory
echo "Creating notebooks directory..."
sudo mkdir -p /data/notebooks

# Create agentic service directories (bind mounts instead of named volumes)
echo "Creating agentic service directories..."
sudo mkdir -p /data/n8n
sudo mkdir -p /data/n8n-files

# Set ownership to current user
echo "Setting permissions..."
sudo chown -R "$(id -u):$(id -g)" /data/datasets /data/checkpoints /data/notebooks /data/models /data/outputs /data/audio /data/n8n /data/n8n-files
sudo chmod -R 755 /data/datasets /data/checkpoints /data/notebooks /data/models /data/outputs /data/audio
# n8n runs as uid 1000 inside the container
sudo chown -R 1000:1000 /data/n8n /data/n8n-files

echo ""
echo "✓ All directories created:"
echo "  - /data/datasets/{images,text,audio}/{raw,formatted,etc}"
echo "  - /data/checkpoints/{kohya,axolotl,unsloth}"
echo "  - /data/models/comfyui/{loras,checkpoints,vae,controlnet,embeddings,upscale_models}"
echo "  - /data/models/{vllm,hf-cache,whisper,piper,ollama,invokeai}"
echo "  - /data/outputs/{comfyui,invokeai,upscaled,rembg}"
echo "  - /data/audio"
echo "  - /data/notebooks"
echo ""
echo "Next: Upload training data to these directories"
