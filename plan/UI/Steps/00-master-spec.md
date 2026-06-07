# KOVATI OS — AI Workstation Platform
## Master Specification · v1.1
*Last updated: 2026-06-05 — augmented from ui-design-brief.md to incorporate prototype decisions*

---

## 1. Platform Identity & Vision

### What This Is

A single browser-based UI that acts as the **control plane for a bare-metal multi-GPU AI workstation**. It replaces the need to navigate 20+ individual service UIs on different ports. The operator opens one URL and from there can:

- Monitor all GPU resources in real time
- Switch between GPU allocation profiles (loadouts) with one click
- Enable/disable individual tools and services
- Launch training jobs (LoRA fine-tuning for text and image models)
- Browse and manage models, datasets, checkpoints, and vector collections
- Expose selected tools as MCP servers or OpenAI-compatible API endpoints
- View metrics, logs, and LLM traces

### Product Name

**KOVATI OS** (working name established in prototype, v1.0.0-beta). Name and logo are placeholders — final branding TBD before distro launch. All references to the product in UI copy, page titles, and the boot wizard use the `KOVATI_OS_PRODUCT_NAME` environment variable so the name can be swapped without code changes.

### Target Product Context (Phase 15 — Linux Distro)

This UI is being designed not just for the current workstation but as the **first-class control plane for a bootable Linux distribution** — an AI Inference Appliance OS based on Ubuntu 26.04 LTS. The distro productizes the entire 15-phase build plan into a bootable ISO. The UI must work in two modes:

- **Workstation mode:** User owns the machine, full access to all settings
- **Appliance mode:** Managed deployment, restricted settings panel, SSO enforced

The UI is served at `:8800` (replacing the existing Loadout Manager inline HTML). The FastAPI backend continues to run at `:8800`; the new frontend replaces only the HTML layer. Accessed via browser over LAN or WireGuard tunnel. No desktop environment exists on the server.

### Design Tone

- **Audience:** ML engineers, researchers, power users — not beginners
- **Aesthetic:** Dark, dense, technical — nvtop + Grafana + GPU spec sheet
- **Font:** JetBrains Mono throughout (imported from Google Fonts). IBM Plex Mono as fallback. Monospace-first is a hard requirement — this is an operator tool.
- **Density:** Operators want information density. Compact cards, tight spacing.
- **Real-time:** GPU stats refresh every 3s. Service health every 10s. Training logs stream.

### Color Tokens (Canonical)

```css
--bg:         #0a0e27   /* deep navy, page background */
--surface:    #1a1f3a   /* primary card surface */
--surface2:   #232844   /* secondary surface, nested cards */
--surface3:   #2a3050   /* tertiary surface, input backgrounds */
--border:     #2e3560   /* default border */
--border2:    #3d4580   /* hover / emphasis border */

/* Semantic accent colors */
--cyan:       #00d9ff   /* inference, active, primary accent */
--cyan-dim:   rgba(0,217,255,0.12)
--amber:      #ffb347   /* training, warm, warning states */
--amber-dim:  rgba(255,179,71,0.12)
--purple:     #c084fc   /* image generation states */
--purple-dim: rgba(192,132,252,0.12)
--green:      #4ade80   /* healthy, ready, success */
--green-dim:  rgba(74,222,128,0.12)
--red:        #f87171   /* error, stopped, danger */
--red-dim:    rgba(248,113,113,0.12)

/* Text */
--text:       #e0e0e0   /* primary text */
--text2:      #9aa0c0   /* secondary / muted */
--text3:      #6b7298   /* tertiary / disabled */

/* Radius */
--radius:     6px
```

---

## 2. Hardware Context

The entire UI is built around one fixed hardware configuration.

| Component | Spec |
|-----------|------|
| CPU | AMD Threadripper Pro 5955WX — 32 cores / 64 threads |
| RAM | 512 GB DDR4 ECC |
| GPU 0 | NVIDIA RTX A5500 — 24 GB VRAM (bus 0x21) |
| GPU 1 | NVIDIA RTX A5500 — 24 GB VRAM (bus 0x22) |
| GPU 2 | NVIDIA RTX A5500 — 24 GB VRAM (bus 0x41) |
| GPU 3 | NVIDIA RTX A5500 — 24 GB VRAM (bus 0x43) |
| Total VRAM | 96 GB |
| NVLink Bridge A | GPU 0 ↔ GPU 3 — 56.25 GB/s per direction |
| NVLink Bridge B | GPU 1 ↔ GPU 2 — 56.25 GB/s per direction |
| Storage | `/data/` — models, checkpoints, datasets, backups |
| Network | 10GbE via jumpbox reverse proxy; 1GbE management/BMC |

### NVLink Topology

```
  ┌─────────┐   NVLink Bridge A   ┌─────────┐
  │  GPU 0  │◄──────────────────►│  GPU 3  │
  │  24 GB  │   56.25 GB/s ×2    │  24 GB  │
  └─────────┘                     └─────────┘

  ┌─────────┐   NVLink Bridge B   ┌─────────┐
  │  GPU 1  │◄──────────────────►│  GPU 2  │
  │  24 GB  │   56.25 GB/s ×2    │  24 GB  │
  └─────────┘                     └─────────┘

  Full 4-GPU mesh valid for TP=4 (70B+ models via pipeline parallelism)
```

**NVLink pairs must never be split across profiles.**

---

## 3. Full Service Catalog

All services are Docker containers managed via modular Compose files.

### 3.1 Text Inference

| Service | Port | Compose File | Role | API Compat | GPU Tier |
|---------|------|-------------|------|-----------|---------|
| Ollama | 11434 | compose.inference.yml | Hot-swap model serving, 7B–14B | OpenAI `/v1` | Low (1 GPU) |
| vLLM Pair A | 8000 | compose.inference.yml | Tensor-parallel, GPU 0+3, 32B–40B | OpenAI `/v1` | Medium (2 GPU) |
| vLLM Pair B | 8001 | compose.inference.yml | Tensor-parallel, GPU 1+2, 32B–40B | OpenAI `/v1` | Medium (2 GPU) |
| vLLM 4-GPU | 8002 | compose.inference.yml | Full mesh TP=4, 70B+ models | OpenAI `/v1` | High (4 GPU) |

### 3.2 Image Inference

| Service | Port | Compose File | Role | API | GPU Tier |
|---------|------|-------------|------|-----|---------|
| ComfyUI | 8188 | compose.studio.yml | Node-graph image gen (SDXL, ControlNet) | REST + WebSocket | Medium (1 GPU) |
| InvokeAI | 9090 | compose.studio.yml | Professional image studio, canvas/inpaint | REST | Medium (1 GPU) |
| Real-ESRGAN | 8189 | compose.studio.yml | 2×–4× image upscaling | REST | Low (1 GPU) |
| Rembg | 8190 | compose.studio.yml | Background removal | REST | None (CPU) |

### 3.3 Training & Fine-Tuning

| Service | Port | Compose File | Role | GPU Tier |
|---------|------|-------------|------|---------|
| Kohya_ss | 7860 | compose.training.yml | Image LoRA training UI (SDXL) | High (GPU 1+2 NVLink) |
| Axolotl | — | compose.training.yml | Text fine-tuning, FSDP, Qwen2.5-32B base | Exclusive (all 4 GPUs) |
| Unsloth | 8501 | compose.training.yml | Fast text LoRA, GPU 0+3 | High (2 GPU) |
| Label Studio | 8081 | compose.training.yml | Data annotation / tagging UI | None (CPU) |
| JupyterLab | 8888 | compose.training.yml | Notebook env, PyTorch + CUDA | Optional GPU |

### 3.4 Agentic & Workflow

| Service | Port | Compose File | Role |
|---------|------|-------------|------|
| n8n | 5678 | compose.agentic.yml | Workflow automation (400+ integrations) |
| Dify | 3010 | compose.agentic.yml | Visual LLM pipeline builder |
| MCP Filesystem | 3100 | compose.agentic.yml | File system access for agents |
| MCP Browser | 3101 | compose.agentic.yml | Playwright headless browser for agents |
| MCP Code-Exec | 3102 | compose.agentic.yml | Sandboxed code execution for agents |
| MCP Fetch | 3103 | compose.agentic.yml | HTTP fetch/scraping for agents |
| OpenHands | 3003 | compose.codegen.yml | Autonomous coding agent with Docker sandbox |

### 3.5 Storage & Vector

| Service | Port | Compose File | Role |
|---------|------|-------------|------|
| MinIO S3 API | 9000 | compose.storage.yml | S3-compatible object storage |
| MinIO Console | 9001 | compose.storage.yml | Bucket management web UI |
| Qdrant REST | 6333 | compose.storage.yml | Vector database (768-dim, nomic-embed-text) |
| Qdrant gRPC | 6334 | compose.storage.yml | High-throughput vector access |
| PostgreSQL | 5432 | compose.storage.yml | Shared relational DB (Langfuse, n8n, Dify) |
| Langfuse | 3002 | compose.storage.yml | LLM observability, prompt versioning, evals |

### 3.6 UI & Access

| Service | Port | Compose File | Role |
|---------|------|-------------|------|
| Open WebUI | 3000 | compose.webui.yml | Primary chat UI — connects to Ollama + vLLM + ComfyUI |
| SearXNG | 8080 | compose.webui.yml | Self-hosted metasearch (used by Open WebUI RAG) |

### 3.7 Voice I/O

| Service | Port | Compose File | Role | API Compat |
|---------|------|-------------|------|-----------|
| Faster-Whisper STT | 9099 | compose.voice.yml | Speech-to-text, large-v3 model | OpenAI `/v1/audio` |
| Piper TTS | 5000 | compose.voice.yml | Text-to-speech, multiple voices | OpenAI `/v1/audio/speech` |

### 3.8 Observability

| Service | Port | Compose File | Role |
|---------|------|-------------|------|
| Prometheus | 9091 | compose.monitoring.yml | Time-series metrics, scrapes 15+ targets |
| Grafana | 3001 | compose.monitoring.yml | Dashboards & alerting |
| DCGM Exporter | 9400 | compose.monitoring.yml | GPU metrics (VRAM, temp, power, utilization) |
| Node Exporter | 9100 | compose.monitoring.yml | System metrics (CPU, memory, disk, network) |
| cAdvisor | 8989 | compose.monitoring.yml | Per-container resource metrics |

### 3.9 Auth & Security

| Service | Port | Compose File | Role |
|---------|------|-------------|------|
| Authentik Server | 9080 / 9443 | compose.auth.yml | OAuth2/OIDC provider, SSO, forward auth |
| Authentik Worker | — | compose.auth.yml | Background task processor |

---

## 4. GPU Loadout Profiles

### 4.1 Profile Definitions

| Profile Name | GPUs Claimed | Services Started | VRAM Required | Use Case | Accent Color |
|-------------|-------------|-----------------|--------------|---------|--------------|
| `inference-small` | [0] | ollama | ~8 GB | 7B–13B chat, lowest latency | cyan |
| `inference-pair-a` | [0, 3] | vllm-pair-a, ollama on GPU 1 | ~48 GB | 32B–40B fast inference (NVLink A) | cyan |
| `inference-pair-b` | [1, 2] | vllm-pair-b | ~48 GB | Second 32B–40B model (NVLink B) | cyan |
| `inference-4gpu` | [0, 1, 2, 3] | vllm-4gpu | 88 GB | 70B+ full precision (TP=4) | cyan |
| `inference-4gpu-large` | [0, 1, 2, 3] | vllm-4gpu (TP=2 PP=2) | 96 GB | 130B+ pipeline-parallel — exclusive | cyan |
| `dual-stack` | [0, 3] + [1, 2] | vllm-pair-a + vllm-pair-b | ~96 GB | Two simultaneous 32B models | cyan |
| `image-studio` | [0] + [1, 2] | comfyui, real-esrgan, rembg, vllm-pair-b | ~72 GB | Image gen + text inference together | purple/cyan |
| `training-lora-image` | [1, 2] | kohya, label-studio | ~48 GB | Image LoRA fine-tuning (NVLink B) | amber |
| `training-lora-text` | [0, 1, 2, 3] | axolotl | 90 GB | Full text fine-tune FSDP — exclusive | amber |
| `training-unsloth` | [0, 3] | unsloth | ~48 GB | Fast LoRA fine-tuning (NVLink A) | amber |

### 4.2 Compatibility Matrix

| Profile | Incompatible With |
|---------|-----------------|
| `inference-small` | `inference-4gpu`, `inference-4gpu-large`, `dual-stack`, `training-lora-text` |
| `inference-pair-a` | `inference-4gpu`, `inference-4gpu-large`, `dual-stack`, `training-lora-text`, `training-lora-image`, `training-unsloth` |
| `inference-pair-b` | `inference-4gpu`, `inference-4gpu-large`, `dual-stack`, `training-lora-text`, `training-lora-image` |
| `inference-4gpu` | everything else |
| `inference-4gpu-large` | everything else — fully exclusive (all GPUs, PP=2) |
| `dual-stack` | everything else |
| `image-studio` | `inference-4gpu`, `inference-4gpu-large`, `dual-stack`, `training-lora-text`, `training-lora-image` |
| `training-lora-image` | `inference-pair-b`, `inference-4gpu`, `inference-4gpu-large`, `dual-stack`, `training-lora-text`, `training-unsloth` |
| `training-lora-text` | everything else — fully exclusive |
| `training-unsloth` | `inference-pair-a`, `inference-small`, `inference-4gpu`, `inference-4gpu-large`, `dual-stack`, `training-lora-text`, `training-lora-image` |

### 4.3 Always-On Services

Some services run independently of loadout profiles — they are not started or stopped by profile activation and claim no GPUs. The backend `api/services.py` must distinguish these from profile-managed services.

| Service | Port | Reason Always-On |
|---------|------|-----------------|
| Open WebUI | 3000 | Primary chat UI — must be accessible regardless of inference state |
| SearXNG | 8080 | Search backend for Open WebUI RAG |
| PostgreSQL | 5432 | Shared DB for Langfuse, n8n, Dify — must not be cycled |
| Prometheus | 9091 | Metrics collection — must be running to scrape profile switches |
| Grafana | 3001 | Dashboard — no GPU needed |
| Node Exporter | 9100 | System metrics — always running |
| cAdvisor | 8989 | Container metrics — always running |
| Authentik Server | 9080 | SSO — must be up for any authenticated request |
| n8n | 5678 | Workflow automation — runs independently of GPU allocation |
| Langfuse | 3002 | LLM observability — must capture traces from all inference services |

**Backend implication:** `profiles.yaml` should carry an `always_on: true` flag on these services. `POST /activate/{name}` must never stop always-on services. The UI Tools panel should render always-on services with a distinct badge (e.g., `SYSTEM`) rather than enable/disable toggles.

**Real-ESRGAN and Rembg** are assigned to the `image-studio` profile (CPU-only, included in its `services` list). They start and stop with image-studio. They are not always-on.

---

### 4.4 Loadout Manager REST API

```
GET  /loadouts              → All profiles with metadata
GET  /status                → Current profile, switching state, GPU VRAM/util/temp per card
POST /activate/{name}       → Switch to profile (async background task)
POST /stop                  → Stop all managed services
GET  /health                → Health check + GPU info
```

**`GET /status` response shape:**
```json
{
  "active_profile": "inference-pair-a",
  "switching": false,
  "last_switched": 1748000000.0,
  "running_services": ["vllm-pair-a", "ollama"],
  "gpus": [
    { "index": 0, "vram_used_gb": 21.4, "vram_total_gb": 24.0,
      "vram_free_gb": 2.6, "utilization_pct": 92, "temp_c": 74,
      "power_w": 198, "nvlink_bridge": "A" },
    { "index": 1, "vram_used_gb": 1.2, "vram_total_gb": 24.0,
      "vram_free_gb": 22.8, "utilization_pct": 3, "temp_c": 42,
      "power_w": 45, "nvlink_bridge": "B" },
    { "index": 2, "vram_used_gb": 0.8, "vram_total_gb": 24.0,
      "vram_free_gb": 23.2, "utilization_pct": 1, "temp_c": 39,
      "power_w": 38, "nvlink_bridge": "B" },
    { "index": 3, "vram_used_gb": 19.8, "vram_total_gb": 24.0,
      "vram_free_gb": 4.2, "utilization_pct": 88, "temp_c": 71,
      "power_w": 189, "nvlink_bridge": "A" }
  ]
}
```

*Note: `nvlink_bridge` field added in v1.1 to support topology diagram coloring.*

---

## 5. UI Navigation Structure

Eight primary sections in left sidebar:

| Section | Purpose | Prototype Status |
|---------|---------|-----------------|
| **Dashboard** | System health at a glance | ✅ Implemented |
| **Loadout** | Profile switcher — primary operator action | ✅ Implemented |
| **Tools** | Per-service cards with status, launch, enable/disable | ✅ Implemented |
| **Training** | Fine-tuning workflows (text LoRA + image LoRA) | ✅ Implemented |
| **Resources** | Models, datasets, checkpoints, vectors, storage | ✅ Implemented |
| **Expose** | MCP endpoints + API surface management | ✅ Implemented |
| **Monitor** | Metrics, GPU telemetry, LLM traces, logs | ✅ Implemented |
| **Settings** | Secrets, network, auth, stack updates, backups | ✅ Implemented |

### Navigation State

- Active section highlighted with left border in `--cyan` + `--cyan-dim` background
- Alert badge on Monitor section when Prometheus alerts are firing (red pill, count)
- Global topbar shows: current page breadcrumb, active loadout tag, running service count, idle count, live clock
- Sidebar footer shows: animated pulse dot + GPU summary + uptime

---

## 6. Backend Architecture

The UI requires a lightweight aggregation backend extending the existing Loadout Manager FastAPI service.

### API Surface the UI Consumes

| Data | Source | Endpoint |
|------|--------|----------|
| GPU stats | Loadout Manager | `GET :8800/status` |
| Loadout profiles | Loadout Manager | `GET :8800/loadouts` |
| Activate profile | Loadout Manager | `POST :8800/activate/{name}` |
| Service health | Docker Engine API | `GET /containers/json` |
| Container logs | Docker Engine API | `GET /containers/{id}/logs` |
| Container start/stop | Docker Compose CLI | `docker compose up/down` |
| Metrics | Prometheus HTTP API | `GET :9091/api/v1/query` |
| LLM traces | Langfuse API | `GET :3002/api/traces` |
| Models list | Ollama API | `GET :11434/api/tags` |
| File storage | MinIO S3 API | `GET :9000/{bucket}` |
| Vector collections | Qdrant REST API | `GET :6333/collections` |
| GPU persistence | pynvml (via Loadout Manager) | wrapped in `/status` |

### New Backend Endpoints Required (v1.1 additions)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/services` | GET | Aggregated service health from Docker API |
| `/api/services/{name}/start` | POST | Start individual service container |
| `/api/services/{name}/stop` | POST | Stop individual service container |
| `/api/services/{name}/logs` | GET | Last N log lines for a container |
| `/api/services/{name}/logs/stream` | GET (SSE) | Streaming log tail |
| `/api/metrics/gpu` | GET | GPU telemetry history (last 30 min, 3s resolution) |
| `/api/metrics/system` | GET | CPU/RAM/disk/network from Prometheus |
| `/api/traces` | GET | LLM traces from Langfuse (paginated) |
| `/api/models` | GET | Merged model list from Ollama + vLLM |
| `/api/storage/buckets` | GET | MinIO bucket summary |
| `/api/vectors/collections` | GET | Qdrant collection list |
| `/api/alerts` | GET | Active Prometheus alerts |
| `/api/secrets` | GET | Secret key names only (never values) |
| `/api/secrets/{key}/rotate` | POST | Rotate a single secret, restart affected containers |
| `/api/stack/update` | POST | Pull latest images + restart |
| `/api/stack/rollback/{service}` | POST | Rollback a service to previous image digest |
| `/api/backup/run` | POST | Trigger backup script |
| `/api/backup/history` | GET | Last 10 backup records |
| `/api/mcp/{name}/test` | POST | Fire a test request to an MCP server |
| `/api/network` | GET | WireGuard status, Caddy routes, jumpbox IP |
| `/api/network` | PATCH | Update jumpbox IP |

### Real-Time Update Strategy

| Data | Mechanism | Interval |
|------|-----------|----------|
| GPU stats | Frontend polling `GET /status` | 3s (1s during profile switch) |
| Service health | Frontend polling `GET /api/services` | 10s |
| Training logs | SSE `GET /api/services/{name}/logs/stream` | continuous |
| Alert count | Frontend polling `GET /api/alerts` | 30s |
| Switching state | Frontend polling `GET /status` | 1s while `switching: true` |

---

## 7. Technology Stack Decisions

| Concern | Decision | Rationale |
|---------|----------|-----------|
| Frontend framework | React 18 + Vite | Ecosystem, component reuse, shadcn/ui optional |
| Backend | Extend existing FastAPI (Loadout Manager at :8800) | Already has GPU data, profile logic, Docker integration |
| Styling | CSS custom properties, no Tailwind | Zero build-time dependency, monospace font requirement, custom token system |
| Real-time | Polling for MVP; SSE for training logs | WebSocket adds complexity for marginal gain at 3s polling |
| Charts | Vanilla canvas charts (no library for MVP) | Lightweight; recharts as upgrade path |
| State management | React Context + useReducer | No Redux overhead needed for single-operator tool |
| Routing | React Router v6, hash-mode | Works without server-side route config |
| Build output | Static files served by FastAPI `/static` | Single deployment unit, no separate static server |
| MCP connection string format | `{"type":"streamable_http","url":"http://host:{port}/mcp"}` | Confirmed 2025-03 MCP spec |
| External service links | New tab (not iframe) for v1 | Avoids CSP issues with ComfyUI, Grafana, etc. |
| Port | `:8800` (no change) | Replaces inline HTML, not the FastAPI backend |

---

## 8. Open Decisions (Resolved)

| Question | Resolution |
|----------|-----------|
| Port for new UI | Keep `:8800` — replace inline HTML, API-only FastAPI continues |
| Iframe vs links | New tab for v1; iframe + focus mode deferred to v2 |
| Training wizard vs direct launch | Mixed: wizard for common configs, escape hatch to native UI (Kohya `:7860`) |
| MCP protocol version | `streamable_http` per 2025-03 spec |
| First-boot wizard placement | Separate `/setup` route, redirect after completion; re-trigger from Settings |
| Product name | "KOVATI OS" as placeholder; `KOVATI_OS_PRODUCT_NAME` env var for final name |
| Loadout accent color scheme | cyan=inference, amber=training, purple=image; gray=idle |

---

## 9. Linux Distro Target (Phase 15)

| Attribute | Value |
|-----------|-------|
| Working name | KOVATI OS (placeholder) |
| Base | Ubuntu 26.04 LTS (minimal server, no desktop) |
| Business model | Open Core — Community (free) / Professional / Enterprise |
| Primary market | AI/ML teams, MSPs, defense/gov air-gap, research labs |
| Key differentiator | Bootable ISO: bare metal → fully operational AI stack in <60 min |

### Tier Definitions

| Tier | Price | UI Differences |
|------|-------|---------------|
| Community | Free | Full feature set, no restrictions |
| Professional | ~$499–$999/node/yr | Adds: validated upgrade paths, loadout profile library, stack compatibility matrix |
| Enterprise | Custom | Adds: FIPS kernel profile, LDAP/AD in Authentik, air-gap mode, custom ISO builder |

### First-Boot Wizard Flow

1. Hardware Probe — detect GPU count, VRAM, NVLink topology
2. Profile Recommendation — map hardware to best default loadout
3. Secret Generation — generate 14 secrets, show once, write to `docker/.env`
4. Network Setup — set jumpbox IP, generate WireGuard keypair
5. Stack Provisioner — pull pinned container images
6. Validation Suite — smoke-test all services
7. Handoff — dashboard with all services green

### Appliance Mode Constraints

- Settings panel restricted (no secret rotation, no network changes without admin role)
- First-boot wizard locked after completion (re-run requires admin auth)
- Authentik SSO mandatory
- Update mechanism tied to validated stack snapshots

---

## 10. File & Repository Layout

```
ai-workstation-project/
├── loadout-manager/
│   ├── main.py                  # FastAPI backend — extend, don't replace
│   ├── profiles.yaml            # GPU profile source of truth
│   └── api/                     # New: split API routes into modules
│       ├── services.py
│       ├── metrics.py
│       ├── storage.py
│       ├── training.py
│       └── settings.py
├── ui/                          # New: React frontend
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── tokens.css           # CSS custom property tokens
│   │   ├── components/
│   │   │   ├── Shell.jsx        # Sidebar + topbar layout
│   │   │   ├── Dashboard.jsx
│   │   │   ├── Loadout.jsx
│   │   │   ├── Tools.jsx
│   │   │   ├── Training.jsx
│   │   │   ├── Resources.jsx
│   │   │   ├── Expose.jsx
│   │   │   ├── Monitor.jsx
│   │   │   ├── Settings.jsx
│   │   │   └── Setup.jsx        # First-boot wizard
│   │   └── hooks/
│   │       ├── useGpuStatus.js
│   │       ├── useServices.js
│   │       └── useTrainingLog.js
│   ├── public/
│   └── vite.config.js
├── docker/
│   ├── compose.inference.yml
│   ├── compose.studio.yml
│   ├── compose.training.yml
│   ├── compose.agentic.yml
│   ├── compose.storage.yml
│   ├── compose.webui.yml
│   ├── compose.voice.yml
│   ├── compose.monitoring.yml
│   ├── compose.auth.yml
│   └── .env                     # gitignored, 14 generated secrets
├── scripts/
│   ├── healthcheck.sh
│   ├── start-all.sh
│   └── update-system.sh
└── configs/
    ├── prometheus/prometheus.yml
    └── caddy/Caddyfile
```

---

## 11. Component Specification Index

Each component has a dedicated spec document:

| Doc | Component | Description |
|-----|-----------|-------------|
| `01-frontend-shell.md` | Frontend Shell | App layout, routing, design tokens, shared components |
| `02-dashboard.md` | Dashboard | GPU cards, service grid, activity feed, loadout banner |
| `03-loadout-manager.md` | Loadout Manager | Profile switcher, topology diagram, switching state machine |
| `04-tools-panel.md` | Tools Panel | Service catalog, accordion groups, per-service card |
| `05-training-workflows.md` | Training Workflows | Text LoRA wizard, image LoRA wizard, live log view |
| `06-resources-panel.md` | Resources Panel | Models, datasets, checkpoints, vectors, storage tabs |
| `07-expose-panel.md` | Expose Panel | OpenAI endpoints, MCP servers, API key management |
| `08-monitor-panel.md` | Monitor Panel | GPU telemetry, traces, log viewer, alerts |
| `09-settings-panel.md` | Settings Panel | Secrets, network, auth, stack management, backups |
| `10-backend-api.md` | Backend API | FastAPI extension, all routes, SSE, Docker integration |
| `11-firstboot-wizard.md` | First-Boot Wizard | Hardware probe, secret gen, network setup, validation |
| `12-distro-productization.md` | Distro & Productization | ISO build, tier enforcement, appliance mode, branding |
