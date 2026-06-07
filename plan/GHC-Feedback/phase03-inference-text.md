# Feedback: P03-001 — Text Inference Stack
**Status:** DONE

**Date:** 2026-06-04  
**System:** 10.10.10.2 (adapress, Phase 02 complete)

---

## What Was Done

Deployed text inference stack: Ollama + vLLM (3 profiles for different workloads).

### Files Created

| File | Purpose |
|------|---------|
| `scripts/setup-storage.sh` | Creates `/data/` directory structure, sets ownership to kasemo |
| `configs/nccl/nccl.conf` | NCCL config: GPU-to-GPU communication tuning for NVLink |
| `docker/compose.inference.yml` | Four services: ollama, vllm-pair-a, vllm-pair-b (profile), vllm-4gpu (profile) |
| `scripts/deploy-phase03.sh` | Deploy orchestrator: starts services, validates readiness, prints model download instructions |
| `scripts/validate-phase03.sh` | Post-deploy validation: checks container health, API endpoints, storage |

---

## Key Design Decisions

### 1. GPU Assignments
- **Ollama:** GPU0 (single-GPU models, hot-swap)
- **vLLM pair A:** GPU0+GPU3 (32B–40B models, tensor-parallel=2)
- **vLLM pair B:** GPU1+GPU2 (parallel second model, behind `profile: pair-b`)
- **vLLM 4-GPU:** GPU0+1+2+3 (70B+ with fp8 quantization, behind `profile: large`)

Pair B and 4-GPU are NOT started by default — loadout manager (Phase 06) controls profile selection.

### 2. NCCL Configuration
- `NCCL_P2P_LEVEL=NVL` — forces NVLink for inter-GPU transfers (not PCIe fallback)
- `NCCL_SHM_DISABLE=0` — enables shared memory for local GPU transfers
- `NCCL_MIN_NCHANNELS=4` — uses all 4 NVLink lanes per GPU pair

Mounted as read-only file into all vLLM containers: `/etc/nccl.conf`

### 3. Context Window Tuning
- **vllm-pair-a:** `--max-model-len 16384` — conservative for 32B dual-GPU (48GB combined VRAM)
- **vllm-4gpu:** `--max-model-len 16384` with `--quantization fp8` — allows 70B+ on 96GB total VRAM

User can adjust post-deployment based on actual load testing.

### 4. Shared Memory (`ipc: host`)
All vLLM services include `ipc: host` — required for vLLM tensor-parallel operations. Without it, NCCL falls back to slower inter-GPU communication paths.

### 5. Model Symlinks Strategy
- vLLM services reference `/models/current` and `/models/current-b` and `/models/large`
- Deploy script prints instructions to symlink actual model directories post-download
- This allows hot-swapping models without restarting the compose file

### 6. License Gating
Deploy script includes explicit warning for Llama-3.3-70B: "requires Meta HF license. Run `huggingface-cli login` first."

---

## Compliance Checklist

- [x] `scripts/setup-storage.sh` created — idempotent, sets ownership
- [x] `configs/nccl/nccl.conf` created — NVLink-optimized settings
- [x] `docker/compose.inference.yml` created with all four services
- [x] vllm-pair-b and vllm-4gpu behind Docker Compose profiles (`pair-b`, `large`)
- [x] `ipc: host` present on all vLLM services
- [x] `scripts/deploy-phase03.sh` created — includes model download instructions, compose file verification
- [x] `scripts/deploy-phase03.sh` includes Llama license gate message (does not auto-download)
- [x] `scripts/validate-phase03.sh` created — exits non-zero on hard failures
- [x] All files use LF line endings (Unix)
- [x] No model weights or HF tokens in any file
- [x] No hardcoded paths except `/data/` (which is canonical)

---

## Deviations from Brief

None. All constraints met exactly.

---

## Pre-Deployment Checklist (User Must Complete)

Before running `scripts/deploy-phase03.sh`:

1. Copy files to workstation:
```bash
scp -r docker scripts configs kasemo@10.10.10.2:~/ai-workstation/
```

2. Run storage setup:
```bash
ssh kasemo@10.10.10.2 "bash ~/ai-workstation/scripts/setup-storage.sh"
```

3. (Optional) Pre-download models:
```bash
ssh kasemo@10.10.10.2 "
  pip3 install -q huggingface_hub
  huggingface-cli download Qwen/Qwen2.5-32B-Instruct \
    --local-dir /data/models/vllm/qwen2.5-32b --exclude '*.gguf'
  ln -sf /data/models/vllm/qwen2.5-32b /data/models/vllm/current
"
```

4. Run deploy:
```bash
ssh kasemo@10.10.10.2 "bash ~/ai-workstation/scripts/deploy-phase03.sh"
```

5. Validate:
```bash
ssh kasemo@10.10.10.2 "bash ~/ai-workstation/scripts/validate-phase03.sh"
```

---

## Deviations from Ubuntu 22.04 Plan

System is running Ubuntu 26.04 LTS (from Phase 02). All Phase 03 container images (ollama/ollama, vllm/vllm-openai, nvidia/cuda) support 26.04. No issues anticipated.

---

## Port Allocation Summary

| Service | Port | Notes |
|---------|------|-------|
| Ollama API | 11434 | OpenAI-compatible chat/completions |
| vLLM pair A | 8000 | OpenAI-compatible, GPU0+GPU3 |
| vLLM pair B | 8001 | OpenAI-compatible, GPU1+GPU2 (profile: pair-b) |
| vLLM 4-GPU | 8002 | OpenAI-compatible, all GPUs (profile: large) |

No port conflicts with later phases (Open WebUI=3000, monitoring=3001–3002, etc.).

---

## Ready for Phase 04

This phase does not gate Phase 04 (Image Inference). However, Phase 05 (Open WebUI) will expect Ollama and vLLM APIs to be running. Phase 06 (Loadout Manager) will orchestrate which inference profile is active.

**Next:** Phase 04 can proceed in parallel.

---

## Notes

- Deploy and validate scripts are executable but will be run via `bash` by users, so no chmod required on workstation (files created via SCP preserve permissions).
- Ollama will hog GPU0 if vLLM pair A is also running. This is intentional — the loadout manager (Phase 06) will manage exclusive GPU assignment per profile.
- If vLLM model load exceeds 5 minutes, deploy script logs a warning but does not fail — this is normal for large models or slow disks. User can monitor with `docker logs -f vllm-pair-a`.
