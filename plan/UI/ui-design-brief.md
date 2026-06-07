# AI Workstation Platform — UI Design Brief

> **Purpose:** This document is a self-contained design specification for the unified control-plane UI of the AI Workstation platform. It is intended to be handed to an AI design agent (e.g. Claude.ai desktop) with no access to the codebase. Every service, API, constraint, and design requirement is documented here.

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

### Target Product Context (Phase 15 — Linux Distro)

This UI is being designed not just for the current workstation but as the **first-class control plane for a bootable Linux distribution** — an AI Inference Appliance OS based on Ubuntu 26.04 LTS. The distro productizes the entire 15-phase build plan into a bootable ISO. The UI must work in two modes:

- **Workstation mode:** User owns the machine, full access to all settings
- **Appliance mode:** Managed deployment, restricted settings panel, SSO enforced

The UI is served at `:8800` (or a new dedicated port) on a headless server — accessed via browser over LAN or WireGuard tunnel. No desktop environment exists on the server.

### Design Tone

- **Audience:** ML engineers, researchers, power users — not beginners
- **Aesthetic:** Dark, dense, technical — think `nvtop` + Grafana + a GPU spec sheet
- **Existing color language** (from the current Loadout Manager prototype):
  - Background: `#0a0e27` (deep navy)
  - Surface: `#1a1f3a`
  - Accent: `#00d9ff` (cyan)
  - Text: `#e0e0e0`
  - Monospace font throughout
- **Density:** Operators want information density. Compact cards, tight spacing.
- **Real-time:** GPU stats refresh every 3s. Service health every 10s. Training logs stream.

---

## 2. Hardware Context

The entire UI is built around one fixed hardware configuration. Understanding it is essential.

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

### NVLink Topology Diagram

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

**This topology is the single most important constraint in the UI.** Every loadout profile is defined by which GPUs it claims. NVLink pairs must not be split across profiles.

---

## 3. Full Service Catalog

All services are Docker containers managed via modular Compose files. Each service has its own port, role, and resource tier.

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

The **Loadout Manager** (FastAPI, port 8800) is the backend for all profile switching. Profiles are defined in `profiles.yaml`. Switching is an async background task (~3–5 seconds: stop all services → wait for GPU VRAM drain → start new profile's services).

### 4.1 Profile Definitions

| Profile Name | GPUs Claimed | Services Started | VRAM Required | Use Case |
|-------------|-------------|-----------------|--------------|---------|
| `inference-small` | [0] | ollama | ~8 GB | 7B–13B chat, lowest latency |
| `inference-pair-a` | [0, 3] | vllm-pair-a, ollama on GPU 1 | ~48 GB | 32B–40B fast inference (NVLink A) |
| `inference-pair-b` | [1, 2] | vllm-pair-b | ~48 GB | Second 32B–40B model (NVLink B) |
| `inference-4gpu` | [0, 1, 2, 3] | vllm-4gpu | 88 GB | 70B+ full precision |
| `dual-stack` | [0, 3] + [1, 2] | vllm-pair-a + vllm-pair-b | ~96 GB | Two simultaneous 32B models |
| `image-studio` | [0] + [1, 2] | comfyui + vllm-pair-b | ~72 GB | Image gen + text inference together |
| `training-lora-image` | [1, 2] | kohya, label-studio | ~48 GB | Image LoRA fine-tuning (NVLink B) |
| `training-lora-text` | [0, 1, 2, 3] | axolotl | 90 GB | Full text fine-tune FSDP — exclusive |

### 4.2 Compatibility Matrix

| Profile | Incompatible With |
|---------|-----------------|
| `inference-small` | `training-lora-text` |
| `inference-pair-a` | `training-lora-text`, `training-lora-image` |
| `inference-pair-b` | `training-lora-text`, `training-lora-image` |
| `inference-4gpu` | everything else |
| `dual-stack` | everything else |
| `image-studio` | `training-lora-text`, `training-lora-image` |
| `training-lora-image` | `inference-pair-b`, `inference-4gpu`, `dual-stack` |
| `training-lora-text` | everything else — fully exclusive |

### 4.3 Loadout Manager REST API

The UI backend calls these endpoints on `:8800`:

```
GET  /loadouts              → All profiles with metadata (active flag, VRAM, services, compat lists)
GET  /status                → Current profile, switching state, GPU VRAM/util/temp per card
POST /activate/{name}       → Switch to profile (async background task, returns immediately)
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
    { "index": 0, "vram_used_gb": 42.1, "vram_total_gb": 24.0,
      "vram_free_gb": 1.9, "utilization_pct": 87, "temp_c": 71 },
    ...
  ]
}
```

---

## 5. UI Functional Requirements

### 5.1 Top-Level Navigation

Seven primary sections, always visible in a left sidebar or top nav:

| Section | Icon Concept | Purpose |
|---------|-------------|---------|
| **Dashboard** | Grid/pulse | System health at a glance — GPUs, services, recent activity |
| **Loadout** | GPU chip | Profile switcher — the primary operator action |
| **Tools** | Wrench/plug | Per-service cards with status, launch, and enable/disable |
| **Training** | Graduation cap / neural net | Fine-tuning workflows (text LoRA + image LoRA) |
| **Resources** | Database / folder | Models, datasets, checkpoints, vector collections |
| **Expose** | Radio tower | MCP endpoints + API surface management |
| **Monitor** | Chart / eye | Metrics, GPU telemetry, LLM traces, logs |
| **Settings** | Gear | Secrets, network, auth, stack updates, backups |

---

### 5.2 Dashboard

The landing view. Operator opens the UI and immediately sees system state.

**GPU Status Row** — 4 cards, one per GPU:
- GPU index + NVLink pair label (e.g. "GPU 0 — Bridge A")
- VRAM bar: used / total with GB labels
- Utilization % with a spark bar or ring gauge
- Temperature with color: green <60°C, amber 60–75°C, red >75°C
- Active service label (e.g. "vllm-pair-a") or "idle"

**Active Loadout Banner:**
- Current profile name in large type
- One-click "Switch Profile" button → opens Loadout panel inline
- Time since last switch

**Service Health Grid:**
- 25+ service tiles in a compact grid
- Each tile: service name + colored dot (green = healthy, amber = degraded, red = down, gray = disabled/stopped)
- Clicking a tile opens the Tools panel pre-scrolled to that service

**Recent Activity Feed** (right column):
- Last 10 events: profile switches, training job completions, service restarts, backup runs
- Timestamp + brief description

---

### 5.3 Loadout Switcher

The most important operator action. Deserves a dedicated full-page view.

**Visual GPU Topology Diagram:**
- Four GPU boxes arranged in the physical layout (2 rows × 2 cols or linear)
- NVLink bridges drawn as lines connecting GPU 0↔3 and GPU 1↔2
- Real-time VRAM fill bars inside each GPU box
- Color-coded by current assignment (idle = gray, inference = cyan, training = amber, image = purple)

**Profile Cards Grid:**
- One card per profile (8 total)
- Each card shows:
  - Profile name (bold)
  - Description (single line)
  - GPU assignment visualization: mini 4-GPU diagram with claimed GPUs highlighted
  - Services that will start (chip tags)
  - VRAM required vs. available
  - Active state: thick cyan border + "ACTIVE" badge
  - Incompatible state: dimmed + lock icon + tooltip listing conflicting profiles
  - "Activate" button — disabled if switching in progress or incompatible

**Switching State:**
- Full-width progress banner when switching is active: `stopping services → draining VRAM → starting services`
- Individual GPU cards pulse during drain phase
- Auto-refreshes via polling `/status` every 1s during switch, 3s otherwise

**VRAM Pre-Check:**
- On hover over "Activate", show a tooltip: `Requires 88 GB — 96 GB available ✓` or `Requires 88 GB — 72 GB available (24 GB in use — stop inference-pair-a first)`

---

### 5.4 Tools Panel

Browse and control all services grouped by category. 

**Layout:** Accordion groups (collapsible), one per category. Default: all expanded.

**Categories and their services:**
1. **Text Inference** — Ollama, vLLM Pair A, vLLM Pair B, vLLM 4-GPU
2. **Image Studio** — ComfyUI, InvokeAI, Real-ESRGAN, Rembg
3. **Training** — Kohya_ss, Axolotl, Unsloth, Label Studio, JupyterLab
4. **Agentic** — n8n, Dify, OpenHands, MCP Filesystem, MCP Browser, MCP Code-Exec, MCP Fetch
5. **Voice** — Whisper STT, Piper TTS
6. **Chat UI** — Open WebUI, SearXNG
7. **Storage** — MinIO, Qdrant, PostgreSQL, Langfuse
8. **Observability** — Prometheus, Grafana, DCGM, Node Exporter, cAdvisor
9. **Auth** — Authentik

**Each Service Card:**
- Service name + version tag
- Status indicator: running / stopped / starting / error
- Port badge (e.g. `:8188`)
- GPU assignment chips (e.g. `GPU0` `GPU1`) — only shown if GPU-consuming
- "Open" button → opens service UI in new tab (or embedded iframe for services that support it)
- "Enable / Disable" toggle → starts or stops the container via Compose API
- Expand chevron → shows: container image, uptime, CPU %, memory usage, last log lines (3 lines)

**Loadout Dependency Warning:**
- If a service is part of the active loadout profile, disable the toggle and show: "Managed by loadout — switch profile to change"

---

### 5.5 Training Workflows

A guided wizard interface for launching fine-tuning jobs.

**Mode Selector:**
- Two large cards: `Text Model (LLM LoRA)` and `Image Model (Diffusion LoRA)`
- Selecting one reveals the appropriate multi-step form

#### Text LoRA Workflow (Axolotl / Unsloth)

**Step 1 — Dataset**
- Upload `.jsonl` file (Alpaca format: `instruction`, `input`, `output` fields) or browse MinIO `/data/training/text/formatted/`
- Format preview: first 3 rows of the dataset in a table
- Record count

**Step 2 — Base Model**
- Dropdown of available models (pulled from Ollama registry + vLLM loaded models)
- Recommended: Qwen2.5-32B (pre-configured in axolotl config)
- VRAM estimate shown for selected model

**Step 3 — LoRA Config**
- LoRA rank (slider: 8–128, default 64)
- LoRA alpha (slider: 16–256, default 128)
- Learning rate (text input, default 2e-5)
- Epochs (number, default 3)
- Batch size micro (default 2)
- Gradient accumulation (default 4)

**Step 4 — GPU Assignment**
- Auto-select loadout: recommends `training-lora-text` (all 4 GPUs, FSDP)
- Warns: "This will stop all inference services"
- Confirm checkbox: "I understand active inference will be interrupted"

**Step 5 — Launch**
- "Start Training" button → switches loadout → launches Axolotl container → streams logs
- Live log panel (scrolling terminal output)
- Progress bar (epoch X/N, step X/Y)
- Per-GPU VRAM and utilization bars (real-time)
- ETA estimate
- "Stop Training" button with confirmation

**Post-Training:**
- Export LoRA checkpoint → MinIO `/data/checkpoints/text/{run-name}/`
- Load into Ollama or vLLM (optional one-click merge)

#### Image LoRA Workflow (Kohya_ss)

**Step 1 — Dataset**
- Upload image folder (zip) or browse MinIO `/data/training/images/`
- Thumbnail grid preview

**Step 2 — Annotation (optional)**
- "Open Label Studio" button → launches Label Studio (:8081) for tagging
- Label Studio is started automatically if stopped

**Step 3 — Training Config**
- Base model: SDXL 1.0 (default) or custom checkpoint path in MinIO
- LoRA network rank (default 32)
- Steps (default 1000)
- Learning rate (default 1e-4)
- Resolution (512, 768, 1024)

**Step 4 — GPU Assignment**
- Auto-select: `training-lora-image` (GPU 1+2, NVLink B)
- GPU 0+3 remain free for inference if needed

**Step 5 — Launch**
- Opens Kohya_ss UI (:7860) in embedded iframe for direct control
- Or: submit job via Kohya API and show log stream inline

---

### 5.6 Resources Panel

Manage all stored artifacts.

**Sub-tabs:** Models | Datasets | Checkpoints | Vectors | Storage

#### Models
- Ollama models table: name, size, quantization, last used, "Delete" + "Set Default" buttons
- vLLM loaded models: endpoint, model ID, tensor-parallel config
- Custom LoRA adapters in MinIO: filename, base model, training date, size

#### Datasets
- MinIO bucket browser for `/data/training/`
- Subfolders: `text/raw/`, `text/formatted/`, `images/`
- File list: name, size, modified date, upload/delete buttons
- Drag-and-drop upload zone

#### Checkpoints
- MinIO bucket browser for `/data/checkpoints/`
- Grouped by run name
- Load checkpoint button (triggers Ollama pull or vLLM model swap)

#### Vectors
- Qdrant collection list: name, vector count, dimension (768), disk size
- "Re-embed" button per collection (triggers re-ingestion pipeline)
- "Delete" collection button with confirmation

#### Storage
- Total MinIO usage (GB) with breakdown by bucket
- PostgreSQL database sizes (Langfuse, n8n, Dify)
- Disk usage bar: `/data/` partition used vs. total
- Last backup timestamp + "Run Backup Now" button

---

### 5.7 Expose — MCP & API Management

Control what is accessible from outside (or from Claude Desktop / Claude Code).

**OpenAI-Compatible Endpoints Table:**

| Service | Base URL | Status | Copy |
|---------|----------|--------|------|
| Ollama | `http://host:11434/v1` | Running | 📋 |
| vLLM Pair A | `http://host:8000/v1` | Running | 📋 |
| vLLM Pair B | `http://host:8001/v1` | Stopped | 📋 |
| vLLM 4-GPU | `http://host:8002/v1` | Stopped | 📋 |
| Whisper STT | `http://host:9099/v1` | Running | 📋 |
| Piper TTS | `http://host:5000/v1` | Running | 📋 |

**MCP Servers Panel:**

Each MCP server shows:
- Name and role
- Port
- Connection string for Claude Desktop: `{"type": "streamable_http", "url": "http://host:3100/mcp"}`
- One-click copy to clipboard
- Enable/disable toggle
- "Test Connection" button (fires a test request, shows result inline)

MCP servers:
- **Filesystem** (:3100) — read/write `/data/` directory tree
- **Browser** (:3101) — Playwright headless browsing
- **Code Exec** (:3102) — Sandboxed Python/shell execution
- **Fetch** (:3103) — HTTP fetch and web scraping

**API Keys:**
- Create named API tokens (scoped per service)
- Table: token name, service scope, created date, last used, "Revoke" button
- Tokens used for external API access when Authentik forward-auth is enabled

**External Access Toggle:**
- Which services are exposed beyond localhost (requires Caddy reverse proxy config update)
- Shows current Caddy routing state per service

---

### 5.8 Monitor

**GPU Telemetry** (real-time, 3s refresh):
- 4-panel chart: VRAM over time (last 30 min) per GPU
- Utilization % sparklines per GPU
- Temperature trend per GPU
- Power draw (watts) per GPU

Data source: `GET /status` from Loadout Manager (wraps pynvml)

**System Metrics** (10s refresh, Prometheus):
- CPU utilization (all cores heatmap)
- System memory used/total
- Disk I/O for `/data/`
- Network throughput (LAN interface)

**LLM Traces** (Langfuse API, `:3002`):
- Table: timestamp, model, prompt tokens, completion tokens, latency ms, cost estimate
- Click row → expand to show full prompt/completion (redacted by default)
- Filter by model, date range, latency threshold

**Container Health** (cAdvisor, Prometheus):
- Container restart count table
- Memory usage per container
- CPU throttle events

**Log Viewer:**
- Service dropdown (select any running container)
- Last 200 lines of logs, auto-scroll
- Filter by log level (ERROR, WARN, INFO)
- Search/grep input

**Alerts:**
- Active Prometheus alerts table: name, severity, description, firing since
- Alert history (last 7 days)

---

### 5.9 Settings

**Secrets Panel:**
- 14 secret keys displayed (names only, values redacted as `••••••••`)
- "Rotate" button per secret — generates new value, restarts affected service
- Secrets stored in `docker/.env` (gitignored)

**Network:**
- Jumpbox IP address (editable)
- WireGuard status: connected / disconnected + peer count
- Caddy reverse proxy: running / stopped + current routes list

**Auth:**
- Authentik SSO: running / stopped
- User list: username, email, last login, role (admin / user)
- "Add User" button → opens Authentik admin in new tab
- Forward auth toggle per service

**Stack Management:**
- "Update All Services" button → pulls latest container images + restarts (calls `update-system.sh`)
- Shows current image digest per service
- Last update timestamp
- Rollback: previous image digest stored, "Rollback" button per service

**Backups:**
- Last backup: timestamp + size
- "Run Backup Now" → archives volumes to `/data/backups/YYYYMMDD-HHMMSS/`
- Backup schedule: current cron expression (editable)
- Backup history list (last 10 with size + delete button)

**First-Boot Wizard** (distro appliance mode only):
- Hardware probe results: GPU count, VRAM, NVLink topology detected
- Profile recommendation: based on detected hardware
- Re-run wizard button (for reconfiguration)

---

## 6. Backend Architecture for the UI

The UI needs a lightweight backend to aggregate data from multiple services. Recommended pattern: a FastAPI service that extends or replaces the current Loadout Manager.

### API Calls the UI Backend Makes

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

### Real-Time Updates

- **GPU stats**: poll `GET /status` every 3s (WebSocket upgrade optional for v2)
- **Service health**: poll Docker API every 10s
- **Training logs**: Server-Sent Events (SSE) stream from Axolotl/Kohya_ss container logs
- **Switching state**: poll `GET /status` every 1s when `switching: true`, drop back to 3s when false

---

## 7. Linux Distro Target State (Phase 15)

This UI is the primary differentiator of the planned bootable Linux distribution.

### Product Summary

| Attribute | Value |
|-----------|-------|
| Working name | TBD (not yet named) |
| Base | Ubuntu 26.04 LTS (minimal server, no desktop) |
| Business model | Open Core — Community (free) / Professional / Enterprise |
| Primary market | AI/ML teams, MSPs, defense/gov air-gap, research labs |
| Key differentiator | Bootable ISO: bare metal → fully operational AI stack in <60 min |
| Phase | 3–6 months of productization after Phases 1–14 are complete |

### Distro Tiers and UI Impact

| Tier | Price | UI Differences |
|------|-------|---------------|
| Community | Free | Full feature set, no restrictions |
| Professional | ~$499–$999/node/yr | Adds: validated upgrade paths, loadout profile library, stack compatibility matrix |
| Enterprise | Custom | Adds: FIPS kernel profile, LDAP/AD integration in Authentik, air-gap mode, custom ISO builder |

### First-Boot Wizard Flow (UI must support)

1. **Hardware Probe** — detect GPU count, VRAM per card, NVLink topology
2. **Profile Recommendation** — map hardware to best default loadout (e.g. 4× A5500 + NVLink → `dual-stack`)
3. **Secret Generation** — generate 14 secrets, show once, write to `docker/.env`
4. **Network Setup** — set jumpbox IP, generate WireGuard keypair
5. **Stack Provisioner** — pull pinned container images, configure compose files
6. **Validation Suite** — smoke-test all services before handoff
7. **Handoff** — show dashboard with all services green

### Appliance Mode (Enterprise/MSP deployments)

When deployed as a managed appliance:
- Settings panel is restricted (no secret rotation, no network changes without admin role)
- First-boot wizard is locked after completion (re-run requires admin auth)
- Authentik SSO is mandatory (no local login bypass)
- Update mechanism is tied to validated stack snapshots (not arbitrary `docker pull`)

---

## 8. Design Constraints & Decisions

### Technology Recommendations

| Concern | Recommendation | Reason |
|---------|---------------|--------|
| Frontend framework | React + shadcn/ui or SvelteKit | shadcn gives dense, accessible components; SvelteKit is lighter for a single-operator tool |
| Backend | Extend existing FastAPI (Loadout Manager) | Already has GPU data, profile logic, Docker integration |
| Real-time | Polling (3s) for MVP; SSE for training logs | WebSocket adds complexity for marginal gain at 3s polling |
| Charts | Recharts (React) or Chart.js | Lightweight, no external Grafana embed dependency for MVP |
| Existing UI | Inline HTML in `loadout-manager/main.py` — replace entirely | The monospace/dark/cyan aesthetic is right, but the HTML is not maintainable |

### Aesthetic Reference: Current Loadout Manager UI

The existing prototype (served at `:8800/`) establishes the visual language to extend:

```css
body { font-family: monospace; background: #0a0e27; color: #e0e0e0; }
/* Surface cards */  background: #1a1f3a; border: 1px solid #333;
/* Active accent */  border: 2px solid #00d9ff;
/* Buttons */        background: #2a3f5f; color: #00d9ff; border: 1px solid #00d9ff;
/* Alert/hot */      border-color: #ff6b6b;
```

Extend this with:
- Amber `#ffb347` for training/warm states
- Purple `#c084fc` for image generation states
- Green `#4ade80` for healthy/ready states
- Red `#f87171` for errors/stopped

### Responsiveness

- Primary: 1920×1080 browser (operator at workstation or via LAN)
- Secondary: 1280×800 laptop (remote management)
- Tertiary: iPad (remote access via WireGuard — touch-friendly hit targets on key controls)
- Not targeted: mobile phone

### Accessibility

Not a primary concern for v1.0 — this is a technical operator tool. Keyboard navigability for power users is desirable.

---

## 9. Files & Repository Context

All source files live in `d:/src/ai-workstation-project/` (Windows path) = `/home/kasemo/ai-workstation/` (server path).

| Path | Contents |
|------|---------|
| `loadout-manager/main.py` | Existing FastAPI backend + inline HTML UI — the UI replaces this HTML |
| `loadout-manager/profiles.yaml` | All 8 GPU profiles — source of truth for loadout data |
| `docker/compose.*.yml` | 10 modular Compose files — one per capability category |
| `docker/.env` | Runtime secrets (gitignored) — 14 generated keys |
| `scripts/healthcheck.sh` | Checks ~30 service endpoints + GPU status — mirrors what Dashboard needs |
| `scripts/start-all.sh` | Boot sequence — reveals correct service dependency order |
| `configs/prometheus/prometheus.yml` | All 15+ Prometheus scrape targets |
| `configs/continue/config.json` | IDE plugin config — not UI-managed but exposed as a downloadable config |
| `plan/steps/15-distro-product-spec.md` | Full distro product specification |
| `plan/PROJECT_PLAN.md` | 15-phase master overview |

---

## 10. Open Questions for the Design Agent

These are unresolved decisions that the design agent should address or flag:

1. **Port for the new UI** — Keep `:8800` (replacing Loadout Manager inline HTML) or use a new dedicated port (e.g. `:8900`) and keep Loadout Manager API-only?

2. **Iframe embeds vs. links** — For services with their own full UIs (ComfyUI, Grafana, Open WebUI), should the Tools panel embed them in an iframe (complex, CSP issues) or simply open a new tab? Recommendation: new tab for v1, iframe for v2 with a "focus mode" layout.

3. **Training wizard vs. direct tool launch** — For Axolotl and Kohya, should the UI present a wizard (guided form → launch) or simply start the container and redirect to Kohya's native UI (:7860)? Mixed approach: simple wizard for common configs, escape hatch to native UI.

4. **MCP protocol version** — The MCP servers use streamable HTTP. Claude Desktop and Claude Code both support this. Confirm connection string format for latest MCP spec before finalizing the Expose panel.

5. **First-boot wizard placement** — Separate route (`/setup`) that redirects after completion, or a modal overlay on Dashboard that can be re-triggered from Settings?

6. **Product name** — Must be chosen before the distro UI is branded. The design agent should leave name/logo as a placeholder.

---

*Document last updated: 2026-06-05. Corresponds to project at `d:/src/ai-workstation-project/` — 15-phase build plan, Phases 1–14 designed, Phase 15 (distro) specification complete. Hardware: AMD Threadripper Pro 5955WX + 4× RTX A5500 / 96 GB NVLink VRAM.*
