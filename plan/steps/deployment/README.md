# Deployment Guide — AI Workstation

This directory contains step-by-step operational instructions for deploying each phase to `adapress` (10.10.10.2).

---

## System State

| Component | Value |
|-----------|-------|
| Host | `adapress` — 10.10.10.2 |
| OS | Ubuntu 26.04 LTS |
| NVIDIA Driver | 595.71.05 |
| CUDA | 13.3 |
| Docker | Installed, default runtime = nvidia |
| GPUs | 4× RTX A5500 (96GB VRAM total) |
| NVLink Pair A | GPU0 ↔ GPU3 |
| NVLink Pair B | GPU1 ↔ GPU2 |
| SSH | `ssh kasemo@10.10.10.2` |

Phase 02 (host baseline) is complete. Phases 03–05 are ready to deploy.

---

## Deployment Order

```
Phase 03 — Text Inference     (Ollama + vLLM)
Phase 04 — Image Inference    (ComfyUI + Real-ESRGAN + Rembg)
Phase 05 — Open WebUI         (UI + SearXNG)
```

Phase 04 can be deployed before or after Phase 03 — they use different GPUs by default. Phase 05 requires Phase 03 (Ollama must be running) before its deploy script will pass.

---

## One-Time: Copy Files to Workstation

All config and script files must be on the workstation before any deploy script will run. From this repo root on Windows:

```bash
scp -r docker scripts configs kasemo@10.10.10.2:~/ai-workstation/
```

Re-run this any time files change. The deploy scripts reference `~/ai-workstation/` as their repo root.

---

## Phase Guides

| Phase | Guide |
|-------|-------|
| 03 — Text Inference | [phase03-text-inference.md](phase03-text-inference.md) |
| 04 — Image Inference | [phase04-image-inference.md](phase04-image-inference.md) |
| 05 — Open WebUI | [phase05-open-webui.md](phase05-open-webui.md) |

---

## GPU Conflict Reference

Services must not share GPUs simultaneously. Current default assignments:

| Service | GPU(s) | Compose File |
|---------|--------|--------------|
| Ollama | 0 | compose.inference.yml |
| vLLM pair A | 0, 3 | compose.inference.yml (manual start) |
| vLLM pair B | 1, 2 | compose.inference.yml (profile: pair-b) |
| vLLM 4-GPU | 0, 1, 2, 3 | compose.inference.yml (profile: large) |
| ComfyUI | 0 | compose.studio.yml |
| Real-ESRGAN | 0 | compose.studio.yml |
| InvokeAI | 0 | compose.studio.yml (profile: studio) |
| Rembg | CPU | compose.studio.yml |

The loadout manager (Phase 06) will handle GPU conflict switching automatically. Until then, stop conflicting services manually before starting another.

---

## Secrets — Update Before Production

Two placeholder secrets are in the deployed files. Update them on the workstation before exposing services to any network:

```bash
# 1. SearXNG secret key
#    Generate: openssl rand -hex 32
ssh kasemo@10.10.10.2 "sed -i 's/change-this-to-a-random-32-char-string/YOUR_KEY_HERE/' ~/ai-workstation/configs/searxng/settings.yml"

# 2. Open WebUI secret key
#    Edit ~/ai-workstation/docker/compose.webui.yml on the workstation
#    Replace: WEBUI_SECRET_KEY=change-this-to-a-random-secret
#    Then restart: docker compose -f docker/compose.webui.yml up -d
```

---

## Validate All Phases

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase03.sh"
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase04.sh"
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase05.sh"
```
