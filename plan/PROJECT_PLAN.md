# AI Workstation Build Plan
## Threadripper Pro 5955WX · 512GB RAM · 4× RTX A5500 · 96GB NVLink VRAM

---

### Hardware Summary
- **CPU:** AMD Threadripper Pro 5955WX (32-core, WRX80, M12SWA-TF)
- **RAM:** 512GB DDR4 ECC
- **GPUs:** 4× NVIDIA RTX A5500 (24GB VRAM each = 96GB total)
- **NVLink:** 2× bridges — GPU0↔GPU3 and GPU1↔GPU2 (full mesh confirmed)
- **Networking:** 10GbE (via jumpbox) + 1GbE management/BMC
- **Jumpbox:** Ryzen 5800/5600, no GPU, reverse proxy + tunnel entry point

---

### Phase Overview

| Phase | Title | Focus | Est. Duration |
|-------|-------|-------|--------------|
| [01](steps/01-jumpbox-networking.md) | Jumpbox & Networking | Entry point, reverse proxy, tunnel | 1–2 days |
| [02](steps/02-host-baseline.md) | Host OS & Driver Baseline | Ubuntu, NVIDIA drivers, Docker, CUDA | 1 day |
| [03](steps/03-inference-text.md) | Text Inference Stack | Ollama, vLLM, NVLink tensor parallelism | 1–2 days |
| [04](steps/04-inference-image.md) | Image Inference Stack | ComfyUI, InvokeAI, upscaling, bg removal | 1 day |
| [05](steps/05-open-webui.md) | Primary UI | Open WebUI, Continue.dev, model management | 1 day |
| [06](steps/06-loadout-manager.md) | Loadout Manager | Custom FastAPI orchestrator, VRAM-aware profiles | 2–3 days |
| [07](steps/07-training-pipeline.md) | Training & Fine-Tuning | Kohya_ss, Axolotl, Unsloth, Label Studio | 2 days |
| [08](steps/08-agentic-mcp.md) | Agentic Workflows & MCP | n8n, Dify, MCP sidecars, Open WebUI pipes | 2 days |
| [09](steps/09-storage-rag.md) | Storage, Vector DB & RAG | MinIO, Qdrant, Open WebUI RAG pipeline | 1 day |
| [10](steps/10-monitoring.md) | Monitoring & Observability | Prometheus, Grafana, DCGM, Langfuse, nvitop | 1–2 days |
| [11](steps/11-code-generation.md) | Code Generation | Continue.dev config, OpenHands, model selection | 1 day |
| [12](steps/12-voice-io.md) | Voice I/O | Whisper.cpp, Piper TTS, Open WebUI integration | 1 day |
| [13](steps/13-security-hardening.md) | Security Hardening | mTLS, auth, network segmentation, BMC lockdown | 1–2 days |
| [14](steps/14-operations-runbook.md) | Operations Runbook | Startup order, backup, updates, troubleshooting | Ongoing |
| [15](steps/15-distro-product-spec.md) | Linux Distro Product Spec | Open core distro productizing Phases 1–14; Ubuntu 26.04 base; Community / Professional / Enterprise tiers | 3-6 Months |

---

### Build Order Rationale

Phases 01 and 02 are strict prerequisites — nothing else works without network access and a clean driver baseline. Phases 03–05 form the first usable milestone: text inference, image inference, and a UI to access both. Phase 06 (loadout manager) gates anything requiring profile switching. Phases 07–12 can be done in any order after 06. Phases 13–14 are ongoing but should begin no later than Phase 05.

---

### GPU Topology Reference

```
GPU0 (bus 0x21) ←—NVLink—→ GPU3 (bus 0x43)
GPU1 (bus 0x22) ←—NVLink—→ GPU2 (bus 0x41)

NVLink pairs for tensor parallelism:
  Pair A: [0, 3]  — 4 links × 14.06 GB/s = 56.25 GB/s per direction
  Pair B: [1, 2]  — 4 links × 14.06 GB/s = 56.25 GB/s per direction
  Full 4-GPU TP: valid — use pipeline_parallel=2 across pairs for >65B models
```

---

### Loadout Profiles Reference

| Profile | GPUs | Engine | Use Case |
|---------|------|--------|----------|
| `inference-small` | [0] or [1] | Ollama | 7B–13B single-GPU chat |
| `inference-pair-a` | [0, 3] | vLLM TP=2 | 34B–40B fast inference |
| `inference-pair-b` | [1, 2] | vLLM TP=2 | Parallel second model |
| `inference-4gpu` | [0,1,2,3] | vLLM TP=4 | 70B+ full precision |
| `inference-4gpu-large` | [0,1,2,3] | vLLM TP=2 PP=2 | 130B+ pipeline parallel |
| `image-studio` | [0] | ComfyUI | SDXL/image gen, frees 1/2/3 for LLM |
| `training-lora-image` | [1, 2] | Kohya_ss | Image LoRA, pair B NVLink |
| `training-lora-text` | [0,1,2,3] | Axolotl FSDP | Full fine-tune, all GPUs |
| `dual-stack` | [0,3]+[1,2] | vLLM×2 | Two simultaneous models |

---

### Key Ports Reference

| Service | Port | Notes |
|---------|------|-------|
| Open WebUI | 3000 | Primary UI |
| Grafana | 3001 | Metrics dashboard |
| Langfuse | 3002 | Prompt observability |
| OpenHands | 3003 | Autonomous coding agent |
| Dify Web | 3010 | LLM pipeline UI |
| Piper TTS | 5000 | TTS endpoint |
| n8n | 5678 | Workflow UI |
| Qdrant | 6333 | Vector DB API |
| Qdrant gRPC | 6334 | Vector DB gRPC |
| Kohya_ss | 7860 | Image LoRA training UI |
| vLLM API (pair A) | 8000 | OpenAI-compatible, GPU0+GPU3 |
| vLLM API (pair B) | 8001 | OpenAI-compatible, GPU1+GPU2 |
| vLLM API (4-GPU) | 8002 | OpenAI-compatible, all GPUs |
| Label Studio | 8081 | Data tagging UI |
| ComfyUI | 8188 | Web UI + API |
| Real-ESRGAN | 8189 | Upscaling API |
| Rembg | 8190 | Background removal |
| Loadout Manager | 8800 | Custom FastAPI |
| JupyterLab | 8888 | Notebook environment |
| MinIO S3 API | 9000 | S3-compatible object store |
| MinIO Console | 9001 | Web UI |
| InvokeAI | 9090 | Image studio Web UI |
| Prometheus | 9091 | Metrics scrape (host port) |
| DCGM Exporter | 9400 | GPU metrics |
| Ollama API | 11434 | OpenAI-compatible |
| Whisper STT | 9099 | STT endpoint (OpenAI-compatible) |

---

### Repository Structure

```
ai-workstation/
├── docker/
│   ├── compose.inference.yml
│   ├── compose.training.yml
│   ├── compose.studio.yml
│   ├── compose.agentic.yml
│   ├── compose.monitoring.yml
│   └── compose.storage.yml
├── loadout-manager/
│   ├── main.py
│   ├── profiles.yaml
│   ├── requirements.txt
│   └── Dockerfile
├── configs/
│   ├── nginx/
│   ├── prometheus/
│   ├── grafana/
│   └── nccl/
├── scripts/
│   ├── validate-nvlink.py
│   ├── benchmark-gpus.py
│   └── healthcheck.sh
└── docs/
    └── [this plan]
```
