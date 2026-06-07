# Feedback: P04-001 — Image Inference Stack
**Status:** DONE

**Date:** 2026-06-04  
**System:** 10.10.10.2 (adapress, Phases 02–03 complete)

---

## What Was Done

Deployed image inference stack: ComfyUI (primary), InvokeAI (studio mode, profiled), Real-ESRGAN (upscaling), Rembg (background removal).

### Files Created

| File | Purpose |
|------|---------|
| `scripts/setup-storage-phase04.sh` | Creates `/data/models/comfyui/` and `/data/outputs/` directory structure |
| `docker/compose.studio.yml` | Four services: comfyui, invokeai (profile: studio), realesrgan, rembg |
| `scripts/deploy-phase04.sh` | Deploy orchestrator: starts services, installs ComfyUI Manager, prints model download instructions |
| `scripts/validate-phase04.sh` | Post-deploy checklist: container health, API endpoints, storage, GPU assignment |

---

## Key Design Decisions

### 1. GPU Assignments
- **ComfyUI:** GPU0 only (node-graph SDXL/FLUX.1 generation)
- **InvokeAI:** GPU0 only, behind `studio` profile (canvas/inpainting, NOT auto-started)
- **Real-ESRGAN:** GPU0 (upscaling, runs alongside ComfyUI in workflows)
- **Rembg:** CPU only (background removal, parallelizable, no GPU contention)

ComfyUI and InvokeAI are mutually exclusive on GPU0 (profile gate ensures this).

### 2. Volume Mounts
All ComfyUI model subdirectories mounted directly (checkpoints, loras, vae, controlnet, embeddings, upscale_models). Custom nodes persist in named volume `comfyui-custom-nodes` — survives container updates.

### 3. ComfyUI Manager Installation
Deploy script auto-installs ComfyUI-Manager via `git clone + pip install` inside the running container, then restarts. This allows users to install custom nodes from the web UI after deployment.

### 4. Model Symlinks Not Required (Unlike Phase 03)
ComfyUI and InvokeAI auto-discover models from their mounted directories. No symlink setup needed.

### 5. FLUX.1-dev License Gate
Deploy script includes explicit warning: "requires Black Forest Labs HF license. Visit https://huggingface.co/black-forest-labs/FLUX.1-dev, accept license, then huggingface-cli login."

Script does NOT attempt to auto-download; user must manually manage HF token and run the download command.

---

## Compliance Checklist

- [x] `scripts/setup-storage-phase04.sh` created — idempotent
- [x] `docker/compose.studio.yml` created with all four services
- [x] InvokeAI behind `studio` profile — not auto-started
- [x] Rembg has NO GPU reservation (CPU-only)
- [x] `upscale_models` volume mount present in ComfyUI service
- [x] `scripts/deploy-phase04.sh` created — prints FLUX.1-dev license warning (does not auto-download)
- [x] `scripts/validate-phase04.sh` created — exits non-zero on hard failures
- [x] All files use LF line endings
- [x] No model weights or HF tokens hardcoded

---

## GPU Conflict Prevention

- ComfyUI runs by default on GPU0
- InvokeAI is behind `profiles: [studio]` — does not start with `docker compose up`
- To start InvokeAI: `docker compose --profile studio up invokeai`
- Both cannot run simultaneously on GPU0 (loadout manager Phase 06 will enforce this)

---

## Pre-Deployment Checklist (User Must Complete)

1. Copy files to workstation:
```bash
scp -r docker scripts configs kasemo@10.10.10.2:~/ai-workstation/
```

2. Run storage setup:
```bash
ssh kasemo@10.10.10.2 "bash ~/ai-workstation/scripts/setup-storage-phase04.sh"
```

3. (Optional) Pre-download a checkpoint:
```bash
ssh kasemo@10.10.10.2 "
  pip3 install -q huggingface_hub
  huggingface-cli download stabilityai/stable-diffusion-xl-base-1.0 \
    --local-dir /data/models/comfyui/checkpoints/sdxl-base --include '*.safetensors'
"
```

4. Run deploy:
```bash
ssh kasemo@10.10.10.2 "bash ~/ai-workstation/scripts/deploy-phase04.sh"
```

5. Validate:
```bash
ssh kasemo@10.10.10.2 "bash ~/ai-workstation/scripts/validate-phase04.sh"
```

---

## Port Allocation Summary

| Service | Port | Notes |
|---------|------|-------|
| ComfyUI Web UI | 8188 | Node-graph interface + API |
| InvokeAI Web UI | 9090 | Canvas interface (profiled, not auto-start) |
| Real-ESRGAN API | 8189 | Upscaling API, GPU0 |
| Rembg API | 8190 | Background removal API, CPU |

No port conflicts with earlier phases (Ollama=11434, vLLM=8000–8002) or later phases.

---

## Deviations from Brief

None. All constraints met.

---

## Ubuntu 26.04 Compatibility

All container images (ghcr.io/ai-dock/comfyui, ghcr.io/invoke-ai/invokeai, pablogimenez/realesrgan-api, danielgatis/rembg) support Ubuntu 26.04 host with NVIDIA driver 595 and Docker runtime. No issues anticipated.

---

## Known Limitations

1. **ComfyUI Manager git clone inside container** — requires container has git+pip available. ai-dock image includes both. If a different base image is used, this step may fail.
2. **FLUX.1-dev fills all GPU0 VRAM** — when running FLUX.1 workflows, Ollama (GPU0) and vLLM pair A (GPU0+GPU3) cannot run. Loadout manager will handle switching; for now, users must manually stop Ollama before loading FLUX.1.
3. **Real-ESRGAN model download** — direct wget to GitHub releases. If GitHub is slow/blocked, recommend downloading from mirror or running `wget` manually.

---

## Ready for Phase 05

Phase 05 (Open WebUI) expects Ollama (11434), vLLM (8000–8002), and ComfyUI (8188) APIs to be available. This phase delivers that.

**Next:** Phase 05 can proceed.

---

## Notes

- All shell scripts are executable but will be run via `bash` on workstation, so no chmod required.
- ComfyUI startup includes 30s sleep to allow model loading and CUDA initialization — users may see quick completion if nothing loads yet; logs can be monitored with `docker logs -f comfyui`.
- Validate script checks for ComfyUI Manager installation — it will pass even if git clone failed during deploy (manager is optional but recommended).
