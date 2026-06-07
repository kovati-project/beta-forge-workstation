# Deployment Plans — AI Workstation

Operational deployment guides for all completed phases. Each guide covers prerequisites, step-by-step commands, validation, and troubleshooting.

---

## System Reference

| Component | Value |
| --------- | ----- |
| Host | `adapress` — 10.10.10.2 |
| OS | Ubuntu 26.04 LTS |
| NVIDIA Driver | 595.71.05 |
| CUDA | 13.3 |
| Docker | Installed, default runtime = nvidia |
| GPUs | 4× RTX A5500 (24GB each = 96GB total) |
| NVLink Pair A | GPU0 ↔ GPU3 (14.062 GB/s) |
| NVLink Pair B | GPU1 ↔ GPU2 (14.062 GB/s) |
| SSH | `ssh kasemo@10.10.10.2` |

---

## Phase Status

| Phase | Guide | Status |
| ----- | ----- | ------ |
| 02 — Host Baseline | [phase02-host-baseline.md](phase02-host-baseline.md) | ✓ Deployed |
| 03 — Text Inference | [phase03-text-inference.md](phase03-text-inference.md) | Ready to deploy |
| 04 — Image Inference | [phase04-image-inference.md](phase04-image-inference.md) | Ready to deploy |
| 05 — Open WebUI | [phase05-open-webui.md](phase05-open-webui.md) | Ready to deploy |
| 06 — Loadout Manager | [phase06-loadout-manager.md](phase06-loadout-manager.md) | Ready to deploy |
| 07 — Training Pipeline | [phase07-training-pipeline.md](phase07-training-pipeline.md) | Ready to deploy |
| 08 — Agentic Workflows & MCP | [phase08-agentic-mcp.md](phase08-agentic-mcp.md) | Ready to deploy |
| 09 — Storage, Vector DB & RAG | [phase09-storage-rag.md](phase09-storage-rag.md) | Ready to deploy |
| 10 — Monitoring & Observability | [phase10-monitoring.md](phase10-monitoring.md) | Ready to deploy |
| 11 — Code Generation | [phase11-code-generation.md](phase11-code-generation.md) | Ready to deploy |
| 12 — Voice I/O | [phase12-voice-io.md](phase12-voice-io.md) | Ready to deploy |
| 13 — Security Hardening | [phase13-security-hardening.md](phase13-security-hardening.md) | Ready to deploy |
| 14 — Operations Runbook | [phase14-operations-runbook.md](phase14-operations-runbook.md) | Ready to deploy |
| 15 — Distro / Product Spec | *(no deployment — spec docs only in `distro/`)* | N/A |

Phase 02 is already live on the workstation. Phases 03–14 files are written and ready — copy them to the workstation and run the deploy scripts.

---

## One-Time: Copy Files to Workstation

Run once from this repo root on Windows before deploying any phase:

```bash
scp -r docker scripts configs loadout-manager kasemo@10.10.10.2:~/ai-workstation/
```

Re-run any time files change. All deploy scripts reference `~/ai-workstation/` as root.

---

## Deployment Order

```text
Phase 03 — Text Inference          (Ollama + vLLM)
Phase 04 — Image Inference         (ComfyUI + Real-ESRGAN + Rembg)
Phase 05 — Open WebUI              (UI + SearXNG)
Phase 06 — Loadout Manager         (GPU profile orchestrator)
Phase 07 — Training Pipeline       (Kohya + Axolotl + JupyterLab)
Phase 08 — Agentic Workflows & MCP (n8n + 4 MCP servers + Dify)
Phase 09 — Storage, Vector DB, RAG (MinIO + Qdrant + Postgres + Langfuse)
Phase 10 — Monitoring              (Prometheus + Grafana + DCGM)
Phase 11 — Code Generation         (OpenHands + Continue.dev)
Phase 12 — Voice I/O               (Whisper STT + Piper TTS)
Phase 13 — Security Hardening      (Authentik + UFW + auditd)
Phase 14 — Operations Runbook      (systemd auto-start + backup + healthcheck)
```

**Ordering notes:**

- Phase 04 can deploy before or after Phase 03.
- Phase 05 requires Phase 03 (Ollama).
- Phase 06 must be running before Phase 07 training profiles work. Phase 07 always-on services (Label Studio, JupyterLab) deploy without Phase 06.
- Phase 09 Postgres is separate from Phase 13 Authentik Postgres — both can run simultaneously.
- Phase 10 is best deployed early but can be added at any point.
- Phase 11 requires Phase 03 (vLLM on `:8000` and Ollama on `:11434`).
- Phase 12 competes with Ollama for GPU 0 — use a loadout profile if both need GPU 0 simultaneously.
- Phase 13 can deploy at any point after Phase 05.
- Phase 14 is last — it wraps and auto-starts all other phases.

---

## GPU Conflict Reference

| Service | GPU(s) | Compose File |
| ------- | ------ | ------------ |
| Ollama | 0 | compose.inference.yml |
| vLLM pair A | 0, 3 | compose.inference.yml |
| vLLM pair B | 1, 2 | compose.inference.yml (profile: pair-b) |
| vLLM 4-GPU | 0–3 | compose.inference.yml (profile: large) |
| ComfyUI | 0 | compose.studio.yml |
| Real-ESRGAN | 0 | compose.studio.yml |
| InvokeAI | 0 | compose.studio.yml (profile: studio) |
| Rembg | CPU | compose.studio.yml |
| Kohya | 1, 2 | compose.training.yml |
| Axolotl | 0–3 | compose.training.yml (profile: training) |
| Unsloth | 0, 3 | compose.training.yml (profile: training) |
| JupyterLab | 0 | compose.training.yml |
| Loadout Manager | none | compose.loadout.yml |

Phase 06 (Loadout Manager) handles conflict switching automatically once deployed. Until then, stop conflicting services manually.

---

## Validate All Phases

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase03.sh"
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase04.sh"
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase05.sh"
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase06.sh"
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase07.sh"
```
