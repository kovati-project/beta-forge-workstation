# Phase 04 — Image Inference Deployment

**Services:** ComfyUI (`:8188`), Real-ESRGAN (`:8189`), Rembg (`:8190`)  
**Compose file:** `docker/compose.studio.yml`  
**Scripts:** `setup-storage-phase04.sh`, `deploy-phase04.sh`, `validate-phase04.sh`

---

## Prerequisites

- [ ] Phase 02 complete (driver, CUDA, Docker verified)
- [ ] Files copied to workstation: `scp -r docker scripts configs kasemo@10.10.10.2:~/ai-workstation/`

Phase 04 can run before, after, or in parallel with Phase 03. They use separate services and do not block each other. However, ComfyUI and Ollama both default to GPU0 — do not run them simultaneously until Phase 06 (loadout manager) is deployed.

---

## Step 1 — Create Storage Layout

```bash
ssh kasemo@10.10.10.2 "bash ~/ai-workstation/scripts/setup-storage-phase04.sh"
```

Creates:
- `/data/models/comfyui/{checkpoints,loras,vae,controlnet,embeddings,upscale_models}`
- `/data/models/invokeai`
- `/data/outputs/{comfyui,invokeai,upscaled,rembg}`

---

## Step 2 — Start Services + Install ComfyUI Manager

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/deploy-phase04.sh"
```

This starts ComfyUI, Real-ESRGAN, and Rembg, then installs ComfyUI Manager inside the container. InvokeAI is **not** started (it's behind the `studio` profile).

Monitor ComfyUI startup:

```bash
ssh kasemo@10.10.10.2 "docker logs -f comfyui"
```

---

## Step 3 — Download SDXL Checkpoint

Minimum required for a working image generation test.

```bash
ssh kasemo@10.10.10.2 "pip3 install -q huggingface_hub"

ssh kasemo@10.10.10.2 "huggingface-cli download stabilityai/stable-diffusion-xl-base-1.0 \
  --local-dir /data/models/comfyui/checkpoints/sdxl-base \
  --include '*.safetensors'"
```

---

## Step 4 — Download Supporting Models

```bash
# SDXL VAE (fixes colour issues in SDXL outputs)
ssh kasemo@10.10.10.2 "huggingface-cli download madebyollin/sdxl-vae-fp16-fix \
  --local-dir /data/models/comfyui/vae \
  --include '*.safetensors'"

# Real-ESRGAN upscale model
ssh kasemo@10.10.10.2 "wget -P /data/models/comfyui/upscale_models \
  https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"
```

---

## Step 5 — Download FLUX.1-dev (Optional, Requires License)

FLUX.1-dev fills all 24GB of GPU0. Only use it when LLM inference on GPU0 is idle.

```bash
# Visit https://huggingface.co/black-forest-labs/FLUX.1-dev and accept the license first.
ssh kasemo@10.10.10.2 "huggingface-cli login"

ssh kasemo@10.10.10.2 "huggingface-cli download black-forest-labs/FLUX.1-dev \
  --local-dir /data/models/comfyui/checkpoints/flux1-dev \
  --include '*.safetensors'"
```

---

## Step 6 — Install Custom Nodes (in Browser)

Open `http://10.10.10.2:8188` in a browser after deployment.

Navigate to **Manager → Install Missing Custom Nodes** and install:

| Node | Purpose |
|------|---------|
| ComfyUI Impact Pack | Segmentation, face detailers |
| ComfyUI Efficiency Nodes | Prompt scheduling, batching |
| ComfyUI ControlNet Aux | Preprocessors (canny, depth, pose) |
| WAS Node Suite | Utility nodes |

Restart ComfyUI after installing nodes:

```bash
ssh kasemo@10.10.10.2 "docker restart comfyui"
```

---

## Step 7 — Validate

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase04.sh"
```

Then manually confirm in the browser (`http://10.10.10.2:8188`):
- Checkpoint appears in model list (may need a page refresh after download)
- Queue a simple txt2img workflow and verify output appears in `/data/outputs/comfyui/`
- Check `nvidia-smi` shows GPU0 VRAM at 8–12GB during generation

---

## Quick Reference — Manage Services

```bash
# Start/stop ComfyUI
ssh kasemo@10.10.10.2 "docker compose -f ~/ai-workstation/docker/compose.studio.yml up -d comfyui"
ssh kasemo@10.10.10.2 "docker stop comfyui"

# Start InvokeAI (studio mode — stop ComfyUI first to free GPU0)
ssh kasemo@10.10.10.2 "docker stop comfyui && docker compose -f ~/ai-workstation/docker/compose.studio.yml --profile studio up -d invokeai"

# Check outputs
ssh kasemo@10.10.10.2 "ls -lt /data/outputs/comfyui/ | head -10"

# Monitor GPU during generation
ssh kasemo@10.10.10.2 "nvidia-smi dmon -s u -d 2"
```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Checkpoint not in ComfyUI model list | Confirm `.safetensors` file exists in `/data/models/comfyui/checkpoints/`; restart container |
| ComfyUI Manager missing after container update | Re-run `deploy-phase04.sh` — it re-installs if not found |
| FLUX.1 OOM error | Confirm no other service holds GPU0 VRAM: `nvidia-smi` |
| Real-ESRGAN not responding at `:8189` | `docker logs realesrgan` — image may still be pulling on first start |
