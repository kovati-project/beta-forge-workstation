# Phase 04 — Image Inference Stack
[← Text Inference](03-inference-text.md) | [Next: Open WebUI →](05-open-webui.md)

---

## Objective
Deploy ComfyUI as the primary image generation engine (node graph, LoRA loading, API-accessible) and InvokeAI as an alternative studio UI. Assign GPU0 as the dedicated image GPU by default, keeping the NVLink pair [0,3] available for LLM inference when image gen is idle.

---

## Services Deployed

| Service | Port | GPU | Role |
|---------|------|-----|------|
| ComfyUI | 8188 | GPU0 | Primary image gen, node graph, API |
| InvokeAI | 9090 | GPU0 | Studio UI, canvas, workflow |
| Real-ESRGAN | 8189 | GPU0 | Upscaling API |
| Rembg | 8190 | CPU | Background removal (CPU is fine) |

---

## Step 1 — ComfyUI via Docker

```bash
cat <<'EOF' >> ~/ai-workstation/docker/compose.studio.yml
version: '3.8'

services:

  # ── ComfyUI: node-graph image generation ──────────────────────────────────
  comfyui:
    image: ghcr.io/ai-dock/comfyui:latest-cuda
    container_name: comfyui
    restart: unless-stopped
    ports:
      - "8188:8188"
    volumes:
      - /data/models/comfyui/checkpoints:/opt/ComfyUI/models/checkpoints
      - /data/models/comfyui/loras:/opt/ComfyUI/models/loras
      - /data/models/comfyui/vae:/opt/ComfyUI/models/vae
      - /data/models/comfyui/controlnet:/opt/ComfyUI/models/controlnet
      - /data/models/comfyui/embeddings:/opt/ComfyUI/models/embeddings
      - /data/outputs/comfyui:/opt/ComfyUI/output
      - comfyui-custom-nodes:/opt/ComfyUI/custom_nodes
    environment:
      - NVIDIA_VISIBLE_DEVICES=0
      - CLI_ARGS=--listen 0.0.0.0 --port 8188 --preview-method auto
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']
              capabilities: [gpu]

  # ── InvokeAI: professional studio UI ──────────────────────────────────────
  invokeai:
    image: ghcr.io/invoke-ai/invokeai:latest
    container_name: invokeai
    restart: unless-stopped
    ports:
      - "9090:9090"
    volumes:
      - /data/models/invokeai:/invokeai/models
      - /data/outputs/invokeai:/invokeai/outputs
      - invokeai-db:/invokeai/databases
    environment:
      - NVIDIA_VISIBLE_DEVICES=0
      - INVOKEAI_ROOT=/invokeai
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']
              capabilities: [gpu]
    profiles:
      - studio      # only starts with: docker compose --profile studio up

  # ── Real-ESRGAN: upscaling API ────────────────────────────────────────────
  realesrgan:
    image: pablogimenez/realesrgan-api:latest
    container_name: realesrgan
    restart: unless-stopped
    ports:
      - "8189:8000"
    volumes:
      - /data/outputs/upscaled:/app/output
    environment:
      - NVIDIA_VISIBLE_DEVICES=0
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']
              capabilities: [gpu]

  # ── Rembg: background removal (CPU) ───────────────────────────────────────
  rembg:
    image: danielgatis/rembg:latest
    container_name: rembg
    restart: unless-stopped
    ports:
      - "8190:5000"
    volumes:
      - /data/outputs/rembg:/app/output

volumes:
  comfyui-custom-nodes:
  invokeai-db:

EOF
```

---

## Step 2 — Directory Structure

```bash
sudo mkdir -p /data/models/comfyui/{checkpoints,loras,vae,controlnet,embeddings,upscale_models}
sudo mkdir -p /data/models/invokeai
sudo mkdir -p /data/outputs/{comfyui,invokeai,upscaled,rembg}
sudo chown -R $USER:$USER /data/models/comfyui /data/outputs
```

---

## Step 3 — Model Downloads

```bash
# SDXL base checkpoint
huggingface-cli download stabilityai/stable-diffusion-xl-base-1.0 \
  --local-dir /data/models/comfyui/checkpoints/sdxl-base \
  --include "*.safetensors"

# SDXL refiner (optional but useful)
huggingface-cli download stabilityai/stable-diffusion-xl-refiner-1.0 \
  --local-dir /data/models/comfyui/checkpoints/sdxl-refiner \
  --include "*.safetensors"

# FLUX.1-dev (state of the art as of 2025, requires HF license)
huggingface-cli download black-forest-labs/FLUX.1-dev \
  --local-dir /data/models/comfyui/checkpoints/flux1-dev \
  --include "*.safetensors"

# SDXL VAE
huggingface-cli download madebyollin/sdxl-vae-fp16-fix \
  --local-dir /data/models/comfyui/vae \
  --include "*.safetensors"

# ControlNet XL (canny, depth, pose)
huggingface-cli download diffusers/controlnet-canny-sdxl-1.0 \
  --local-dir /data/models/comfyui/controlnet/canny-xl

# Real-ESRGAN upscale models
wget -P /data/models/comfyui/upscale_models \
  https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth
```

---

## Step 4 — ComfyUI Custom Nodes

Essential custom nodes for production use:

```bash
# Start ComfyUI first
docker compose -f ~/ai-workstation/docker/compose.studio.yml up -d comfyui

# Install ComfyUI Manager (installs all other nodes via UI)
docker exec comfyui bash -c "
  cd /opt/ComfyUI/custom_nodes && \
  git clone https://github.com/ltdrdata/ComfyUI-Manager && \
  pip install -r ComfyUI-Manager/requirements.txt
"
docker restart comfyui

# After ComfyUI Manager is installed, install via its UI:
# - ComfyUI Impact Pack     (segmentation, detailers)
# - ComfyUI Efficiency Nodes (prompt scheduling, batch)
# - ComfyUI ControlNet Aux  (preprocessors for ControlNet)
# - WAS Node Suite          (utility nodes)
# - ComfyUI-BRIA-RMBG       (background removal in-graph)
# - ComfyUI Inpaint Anything (SAM-based inpainting)
```

---

## Step 5 — ComfyUI API Integration

ComfyUI exposes a WebSocket + REST API. This is how Open WebUI and the loadout manager query it:

```python
# Test ComfyUI API — queue a simple generation
import requests, json, uuid, websocket

COMFY_URL = "http://localhost:8188"
CLIENT_ID = str(uuid.uuid4())

# Basic txt2img workflow (simplified)
workflow = {
    "3": {
        "inputs": {"seed": 42, "steps": 20, "cfg": 7, "sampler_name": "euler",
                   "scheduler": "normal", "denoise": 1,
                   "model": ["4", 0], "positive": ["6", 0],
                   "negative": ["7", 0], "latent_image": ["5", 0]},
        "class_type": "KSampler"
    },
    "4": {"inputs": {"ckpt_name": "sdxl-base/sd_xl_base_1.0.safetensors"},
          "class_type": "CheckpointLoaderSimple"},
    "5": {"inputs": {"width": 1024, "height": 1024, "batch_size": 1},
          "class_type": "EmptyLatentImage"},
    "6": {"inputs": {"text": "a photo of an astronaut on mars", "clip": ["4", 1]},
          "class_type": "CLIPTextEncode"},
    "7": {"inputs": {"text": "blurry, watermark", "clip": ["4", 1]},
          "class_type": "CLIPTextEncode"},
    "8": {"inputs": {"samples": ["3", 0], "vae": ["4", 2]},
          "class_type": "VAEDecode"},
    "9": {"inputs": {"filename_prefix": "api_test", "images": ["8", 0]},
          "class_type": "SaveImage"}
}

response = requests.post(f"{COMFY_URL}/prompt",
    json={"prompt": workflow, "client_id": CLIENT_ID})
print(response.json())
```

---

## Step 6 — Open WebUI Integration

Once Open WebUI is deployed (Phase 05), connect it to ComfyUI:

```
Open WebUI → Settings → Images
  Engine: ComfyUI
  URL: http://10.10.10.2:8188
  Default workflow: [upload your standard txt2img workflow JSON]
```

---

## Validation Checklist

- [ ] ComfyUI web UI accessible at `:8188`
- [ ] ComfyUI Manager installed, custom nodes loading
- [ ] SDXL checkpoint visible in ComfyUI model list
- [ ] Test generation completes successfully (check `/data/outputs/comfyui/`)
- [ ] GPU0 VRAM shows ~8–12GB usage during SDXL generation
- [ ] ComfyUI API responds at `:8188/system_stats`
- [ ] Rembg API responding at `:8190`
- [ ] No GPU conflict with text inference services (they use GPU1/2/3 by default)

---

## Notes
- FLUX.1-dev requires ~24GB VRAM — it fills GPU0 completely. Use this when LLM inference is idle, or switch to SDXL for simultaneous operation
- ComfyUI workflows are JSON files — version-control your production workflows in the repository under `configs/comfyui-workflows/`
- InvokeAI and ComfyUI should not run simultaneously on GPU0 — the loadout manager handles this in Phase 06
- Real-ESRGAN can run on CPU for low-volume use; move to GPU only if upscaling becomes a bottleneck
