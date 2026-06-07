# KOVATI OS — Component Spec 11
## First-Boot Wizard
*Hardware probe · profile recommendation · secret generation · network setup · stack provisioning · validation · handoff*

---

## 1. Purpose

The First-Boot Wizard is a one-time setup flow that runs when KOVATI OS boots for the first time on a new machine (or when the wizard is explicitly re-run from Settings). It transforms a bare OS installation into a fully operational AI stack.

The wizard is the primary "wow moment" for the distro product: an operator with a fresh machine should go from boot to a working multi-GPU AI stack in under 60 minutes, guided by this UI.

It runs at the `/setup` route, which renders **outside** the main Shell (no sidebar, no topbar). After successful completion, it redirects to `/#/dashboard`.

---

## 2. Wizard Steps

```
[1 Hardware] ─── [2 Profile] ─── [3 Secrets] ─── [4 Network] ─── [5 Stack] ─── [6 Validate] ─── [7 Handoff]
```

Progress bar at top. Steps cannot be skipped. Completed steps show a green checkmark. Current step is highlighted in cyan. Failed steps show a red cross with retry option.

---

## 3. Step 1 — Hardware Probe

**Backend call:** `POST /api/setup/probe`

The backend runs:
```python
# api/setup.py
def probe_hardware():
    gpus = []
    pynvml.nvmlInit()
    count = pynvml.nvmlDeviceGetCount()
    for i in range(count):
        handle = pynvml.nvmlDeviceGetHandleByIndex(i)
        name = pynvml.nvmlDeviceGetName(handle).decode()
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        pci = pynvml.nvmlDeviceGetPciInfo(handle)
        gpus.append({
            "index": i,
            "name": name,
            "vram_gb": mem.total / 1e9,
            "bus_id": hex(pci.bus),
        })

    # NVLink topology detection
    nvlink_pairs = _detect_nvlink_pairs(gpus)

    return {
        "cpu": {
            "model": _read_cpu_model(),
            "cores": os.cpu_count(),
            "ram_gb": psutil.virtual_memory().total / 1e9
        },
        "gpus": gpus,
        "nvlink_pairs": nvlink_pairs,
        "total_vram_gb": sum(g["vram_gb"] for g in gpus),
        "storage": {
            "data_path": "/data",
            "total_gb": shutil.disk_usage("/data").total / 1e9,
            "free_gb": shutil.disk_usage("/data").free / 1e9,
        }
    }
```

### NVLink Pair Detection

```python
def _detect_nvlink_pairs():
    # Run: nvidia-smi nvlink --status
    # Parse P2P topology matrix to find bidirectional NVLink connections
    # Returns: [[gpu_a, gpu_b], ...]
    result = subprocess.run(["nvidia-smi", "topo", "-m"], capture_output=True, text=True)
    # Parse NV# entries in the matrix
```

### UI Display

```
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: Hardware Detection                                      │
│                                                                 │
│  ● Detecting GPU configuration...                              │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  CPU    AMD Threadripper Pro 5955WX · 32c/64t · 512 GB  │  │
│  │  GPU 0  RTX A5500 · 24 GB · bus 0x21                    │  │
│  │  GPU 1  RTX A5500 · 24 GB · bus 0x22                    │  │
│  │  GPU 2  RTX A5500 · 24 GB · bus 0x41                    │  │
│  │  GPU 3  RTX A5500 · 24 GB · bus 0x43                    │  │
│  │                                                          │  │
│  │  NVLink  GPU 0 ↔ GPU 3 (Bridge A · 56.25 GB/s)          │  │
│  │          GPU 1 ↔ GPU 2 (Bridge B · 56.25 GB/s)          │  │
│  │                                                          │  │
│  │  Storage  /data/ · 20 TB total · 18.2 TB free           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ✓ Hardware detected successfully                              │
│                                                                 │
│                                              [Next: Profile →]  │
└─────────────────────────────────────────────────────────────────┘
```

**Error case:** If `pynvml` fails (e.g., NVIDIA drivers not installed):
```
⚠ GPU detection failed: NVML library not found.
  Ensure NVIDIA drivers ≥ 525 are installed.
  [Retry] [Skip (CPU-only mode)]
```

---

## 4. Step 2 — Profile Recommendation

**Backend call:** `POST /api/setup/recommend` with hardware probe results.

```python
def recommend_profile(hardware: HardwareProbe) -> str:
    n_gpus = len(hardware.gpus)
    has_nvlink = len(hardware.nvlink_pairs) > 0
    total_vram = hardware.total_vram_gb

    if n_gpus == 4 and has_nvlink and total_vram >= 96:
        return "dual-stack"       # 4× GPU with NVLink — full capability
    elif n_gpus == 4 and not has_nvlink:
        return "inference-4gpu"   # 4× GPU, no NVLink → TP=4
    elif n_gpus == 2 and has_nvlink:
        return "inference-pair-a" # 2-GPU NVLink pair
    elif n_gpus == 2:
        return "inference-pair-b"
    elif n_gpus == 1:
        return "inference-small"
    else:
        return "inference-small"  # fallback
```

### UI Display

```
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: Recommended Profile                                     │
│                                                                 │
│  Based on your hardware (4× RTX A5500 · 96 GB NVLink mesh),    │
│  we recommend:                                                  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  ★  dual-stack                                          │  │
│  │     Two simultaneous 32B models · all GPUs              │  │
│  │     GPU 0+3 (Bridge A) + GPU 1+2 (Bridge B)             │  │
│  │     vllm-pair-a + vllm-pair-b · 96 GB VRAM              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  [Change Profile]  ← shows all 8 profiles with compatibility    │
│                                                                 │
│  This profile will be activated after stack provisioning.       │
│                                                                 │
│                                              [Next: Secrets →]  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Step 3 — Secret Generation

**Backend call:** `POST /api/setup/generate-secrets`

Generates 14 cryptographically random secrets and writes to `docker/.env`.

```python
import secrets as pysecrets

SECRET_KEYS = [
    "POSTGRES_PASSWORD",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_SALT",
    "MINIO_ROOT_PASSWORD",
    "MINIO_SECRET_KEY",
    "AUTHENTIK_SECRET_KEY",
    "AUTHENTIK_BOOTSTRAP_PASSWORD",
    "N8N_ENCRYPTION_KEY",
    "DIFY_SECRET_KEY",
    "GRAFANA_ADMIN_PASSWORD",
    "OPEN_WEBUI_SECRET_KEY",
    "SEARXNG_SECRET_KEY",
    "CADDY_API_KEY",
    "KOVATI_INTERNAL_TOKEN",
]

def generate_secrets():
    values = {k: pysecrets.token_urlsafe(32) for k in SECRET_KEYS}
    _write_env_file(values)
    return {"keys": list(values.keys())}  # Never return values in API response
```

### UI Display

```
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: Secret Generation                                       │
│                                                                 │
│  14 cryptographic secrets will be generated and written to      │
│  docker/.env. This file is gitignored and stays on this machine.│
│                                                                 │
│  ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐   │
│    POSTGRES_PASSWORD     ██████████████████████████████       │
│    LANGFUSE_SECRET_KEY   ██████████████████████████████       │
│    MINIO_ROOT_PASSWORD   ██████████████████████████████       │
│    ... (+11 more)                                              │
│  └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘   │
│                                                                 │
│  ⚠ Secret values are shown only here and never again.          │
│     Download a backup copy before continuing.                   │
│                                                                 │
│  [⬇ Download .env Backup]                                      │
│                                                                 │
│  □ I have saved a secure backup of my secrets                  │
│                                                                 │
│                                              [Next: Network →]  │
└─────────────────────────────────────────────────────────────────┘
```

**The only time secret values are exposed:** In this step, after generation. They are shown once (redacted by default, with a "Reveal All" button). Download creates a `.env` file for secure offline storage.

**Checkbox must be checked to advance.**

---

## 6. Step 4 — Network Setup

**Backend calls:** `POST /api/setup/network`

```
┌─────────────────────────────────────────────────────────────────┐
│ Step 4: Network Configuration                                   │
│                                                                 │
│  Jumpbox / reverse proxy IP                                     │
│  [10.0.0.1________________]                                     │
│                                                                 │
│  This machine's LAN IP (detected):                              │
│  eth0 · 10.0.0.5 (10GbE) ← primary                             │
│  eth1 · 192.168.1.100 (1GbE) ← management/BMC                  │
│                                                                 │
│  WireGuard VPN                                                  │
│  ○ Skip (LAN-only access)                                       │
│  ● Generate WireGuard keypair                                   │
│                                                                 │
│  [Generate Keypair]                                             │
│  Public key:  abc123...xyz789    [Copy]                         │
│  Add this to your WireGuard server's [Peer] config.             │
│                                                                 │
│  Caddy reverse proxy:                                           │
│  ● Enable (recommended for external access)                     │
│  ○ Skip (direct port access only)                               │
│                                                                 │
│                                               [Next: Stack →]   │
└─────────────────────────────────────────────────────────────────┘
```

**WireGuard keypair generation:**
```python
subprocess.run(["wg", "genkey"], capture_output=True)  → private key
subprocess.run(["wg", "pubkey"], input=private_key)    → public key
```

Keys written to `/etc/wireguard/wg0.conf`. Public key displayed to operator for peer config.

**Network config stored in `docker/.env`:**
```
JUMPBOX_IP=10.0.0.1
KOVATI_OS_LAN_IP=10.0.0.5
CADDY_ENABLED=true
```

---

## 7. Step 5 — Stack Provisioner

**Backend call:** `POST /api/setup/provision` (SSE stream)

Pulls all container images in dependency order (based on `start-all.sh` boot sequence). Does not start services yet — only pulls images.

```
┌─────────────────────────────────────────────────────────────────┐
│ Step 5: Stack Provisioning                                      │
│                                                                 │
│  Pulling container images (~15–40 GB depending on models)...    │
│                                                                 │
│  [████████████████████░░░░░░░░░░░░] 14 / 23 images             │
│                                                                 │
│  ✓ postgres:16                          1.2 GB                 │
│  ✓ redis:7-alpine                        42 MB                 │
│  ✓ minio/minio:latest                   180 MB                 │
│  ✓ langfuse/langfuse:latest             620 MB                 │
│  ⟳ vllm/vllm-openai:v0.9.1         ... 4.3 GB / 4.3 GB ✓     │
│  ↓ ollama/ollama:latest                 [████████░░] 60%       │
│  ○ ghcr.io/open-webui/open-webui        (pending)              │
│  ...                                                            │
│                                                                 │
│  Elapsed: 12m 34s    Estimated remaining: ~18 min              │
└─────────────────────────────────────────────────────────────────┘
```

**Pull order (dependency groups, pulled in parallel within group):**

1. Infrastructure: postgres, redis
2. Storage: minio, qdrant
3. Observability: prometheus, grafana, node-exporter, dcgm-exporter, cadvisor
4. Auth: authentik
5. Agentic: n8n, dify, openhands, mcp-*
6. UI: open-webui, searxng, langfuse
7. Voice: whisper, piper
8. Inference: ollama, vllm (largest, pulled last)

**Offline/air-gap mode:** If `KOVATI_AIR_GAP=true`, skip this step and verify local image cache instead.

---

## 8. Step 6 — Validation Suite

**Backend call:** `POST /api/setup/validate` (SSE stream)

Starts all services in the recommended profile and runs smoke tests.

```
┌─────────────────────────────────────────────────────────────────┐
│ Step 6: Stack Validation                                        │
│                                                                 │
│  Starting services and running health checks...                │
│                                                                 │
│  ✓ PostgreSQL        :5432   CREATE DATABASE ok                │
│  ✓ Redis             :6379   PING ok                            │
│  ✓ MinIO             :9000   Bucket listing ok                  │
│  ✓ Qdrant            :6333   /healthz → 200 ok                  │
│  ✓ Authentik         :9080   /api/v3/root/config/ → 200         │
│  ✓ n8n               :5678   /healthz → 200                     │
│  ✓ Prometheus        :9091   /api/v1/query → 200                │
│  ✓ Grafana           :3001   /api/health → 200                  │
│  ⟳ Ollama            :11434  Loading model... (45s)            │
│  ✓ Open WebUI        :3000   /health → 200                      │
│  ✓ vLLM Pair A       :8000   /v1/models → [{name:qwen2.5-32b}] │
│                                                                 │
│  GPU VRAM check:                                                │
│  ✓ GPU 0: 21.4 GB used / 24 GB (vllm-pair-a loaded)            │
│  ✓ GPU 3: 19.8 GB used / 24 GB (vllm-pair-a loaded)            │
│                                                                 │
│  23 / 25 checks passing  ●●●●●●●●●●●●●●●●●●●●●●●○○            │
│                                                                 │
│  ⚠ 2 checks pending (Ollama model load in progress)            │
│                                                                 │
│                                      [Retry Failed] [Continue →]│
└─────────────────────────────────────────────────────────────────┘
```

**Validation checks** (from `healthcheck.sh`):

```python
HEALTH_CHECKS = [
    {"name": "PostgreSQL", "port": 5432, "method": "tcp"},
    {"name": "MinIO", "url": "http://localhost:9000/minio/health/live"},
    {"name": "Qdrant", "url": "http://localhost:6333/healthz"},
    {"name": "Ollama", "url": "http://localhost:11434/api/tags"},
    {"name": "vLLM Pair A", "url": "http://localhost:8000/v1/models"},
    {"name": "Open WebUI", "url": "http://localhost:3000/health"},
    {"name": "n8n", "url": "http://localhost:5678/healthz"},
    {"name": "Prometheus", "url": "http://localhost:9091/-/healthy"},
    {"name": "Grafana", "url": "http://localhost:3001/api/health"},
    {"name": "Authentik", "url": "http://localhost:9080/api/v3/root/config/"},
    {"name": "GPU VRAM", "method": "pynvml"},
    # ... 25 total
]
```

**Continue button** enabled when ≥22/25 checks pass (allows for optional services that may not be configured yet).

---

## 9. Step 7 — Handoff

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  ✓  KOVATI OS is ready.                                         │
│                                                                 │
│  Active profile: dual-stack                                     │
│  23 services running · 2 idle · 0 errors                        │
│                                                                 │
│  Access your services:                                          │
│  Chat UI:    http://10.0.0.5:3000   (Open WebUI)               │
│  Control:    http://10.0.0.5:8800   (this dashboard)           │
│  Monitoring: http://10.0.0.5:3001   (Grafana)                  │
│                                                                 │
│  MCP servers ready for Claude Desktop:                          │
│  [Export claude_desktop_config.json]                            │
│                                                                 │
│  Setup completed at 2026-06-05 14:22:47                         │
│                                                                 │
│                             [Go to Dashboard →]                  │
└─────────────────────────────────────────────────────────────────┘
```

**"Go to Dashboard"** → writes a `setup_complete` flag to a local file (`/data/.kovati-setup-complete`) → redirects to `/#/dashboard`. The flag prevents the wizard from running again on next boot; re-run requires deletion of this file or the Settings > Re-run button.

---

## 10. Wizard State Persistence

Wizard step state is kept in `sessionStorage` (not `localStorage`) so a browser refresh doesn't restart the wizard from step 1. Each step's result is saved:

```js
sessionStorage.setItem('setup_hardware', JSON.stringify(hardwareProbe));
sessionStorage.setItem('setup_profile', selectedProfile);
sessionStorage.setItem('setup_step', currentStep);
```

---

## 11. Re-Run from Settings

When triggered from Settings → "Re-run First-Boot Wizard":
1. Admin confirmation dialog
2. `DELETE /api/setup/completion-flag` (removes `.kovati-setup-complete`)
3. Navigate to `/setup`
4. Wizard detects existing `.env` — shows warning: "Secrets already exist. Re-generating will invalidate existing service data."
5. Step 3 (Secrets) shows: "Regenerate" vs "Keep Existing" option

---

## 12. API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/setup/probe` | POST | Hardware detection |
| `/api/setup/recommend` | POST | Profile recommendation |
| `/api/setup/generate-secrets` | POST | Generate + write .env |
| `/api/setup/network` | POST | Write network config + WireGuard keygen |
| `/api/setup/provision` | POST (SSE) | Pull container images |
| `/api/setup/validate` | POST (SSE) | Start services + health checks |
| `/api/setup/status` | GET | Is setup complete? |
| `/api/setup/completion-flag` | DELETE | Re-run trigger from Settings |
