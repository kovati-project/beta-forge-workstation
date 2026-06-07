# Phase 06 — Loadout Manager
[← Open WebUI](05-open-webui.md) | [Next: Training Pipeline →](07-training-pipeline.md)

---

## Objective
Build the custom FastAPI service that orchestrates which Docker Compose stacks are running based on VRAM-aware loadout profiles. This is the only fully custom component in the stack. It provides a REST API and a lightweight web UI for quick-switching between inference, training, and studio configurations.

---

## Architecture

```
Client (browser / CLI / cron)
        │
        ▼
Loadout Manager API  :8800
        │
        ├── GET  /loadouts          → list all profiles
        ├── GET  /status            → current running profile + GPU state
        ├── POST /activate/{name}   → switch to named profile
        ├── POST /stop              → stop all managed services
        └── GET  /health            → GPU VRAM, temp, utilization
        │
        ▼
Docker Compose (subprocess)
        ├── compose.inference.yml
        ├── compose.training.yml
        ├── compose.studio.yml
        └── compose.agentic.yml
```

---

## Step 1 — Project Structure

```bash
mkdir -p ~/ai-workstation/loadout-manager
cd ~/ai-workstation/loadout-manager
```

---

## Step 2 — `profiles.yaml`

```yaml
# ~/ai-workstation/loadout-manager/profiles.yaml

profiles:

  inference-small:
    description: "Single GPU chat — 7B-13B models, lowest latency"
    compose_files:
      - ../docker/compose.inference.yml
    services:
      - ollama
    gpu_assignment:
      ollama: ["0"]
    exclusive_gpus: ["0"]
    compatible_with: [image-studio]   # can run simultaneously

  inference-pair-a:
    description: "NVLink pair A [GPU0,GPU3] — 32B-40B models"
    compose_files:
      - ../docker/compose.inference.yml
    services:
      - vllm-pair-a
      - ollama
    gpu_assignment:
      vllm-pair-a: ["0", "3"]
      ollama: ["1"]
    exclusive_gpus: ["0", "3"]

  inference-pair-b:
    description: "NVLink pair B [GPU1,GPU2] — 32B-40B second model"
    compose_files:
      - ../docker/compose.inference.yml
    services:
      - vllm-pair-b
    gpu_assignment:
      vllm-pair-b: ["1", "2"]
    exclusive_gpus: ["1", "2"]

  inference-4gpu:
    description: "Full NVLink mesh [all 4 GPUs] — 70B+ models"
    compose_files:
      - ../docker/compose.inference.yml
    services:
      - vllm-4gpu
    gpu_assignment:
      vllm-4gpu: ["0", "1", "2", "3"]
    exclusive_gpus: ["0", "1", "2", "3"]
    vram_required_gb: 88

  dual-stack:
    description: "Two simultaneous models — pair A + pair B"
    compose_files:
      - ../docker/compose.inference.yml
    services:
      - vllm-pair-a
      - vllm-pair-b
    gpu_assignment:
      vllm-pair-a: ["0", "3"]
      vllm-pair-b: ["1", "2"]
    exclusive_gpus: ["0", "1", "2", "3"]

  image-studio:
    description: "ComfyUI on GPU0, LLM inference on GPU1/2/3"
    compose_files:
      - ../docker/compose.studio.yml
      - ../docker/compose.inference.yml
    services:
      - comfyui
      - vllm-pair-b
    gpu_assignment:
      comfyui: ["0"]
      vllm-pair-b: ["1", "2"]
    exclusive_gpus: ["0", "1", "2"]

  training-lora-image:
    description: "Kohya_ss image LoRA on NVLink pair B"
    compose_files:
      - ../docker/compose.training.yml
    services:
      - kohya
      - label-studio
    gpu_assignment:
      kohya: ["1", "2"]
    exclusive_gpus: ["1", "2"]
    incompatible_with: [inference-4gpu, dual-stack]

  training-lora-text:
    description: "Axolotl text fine-tuning — all 4 GPUs FSDP"
    compose_files:
      - ../docker/compose.training.yml
    services:
      - axolotl
    gpu_assignment:
      axolotl: ["0", "1", "2", "3"]
    exclusive_gpus: ["0", "1", "2", "3"]
    vram_required_gb: 90
    incompatible_with: [inference-small, inference-pair-a, inference-pair-b,
                        inference-4gpu, dual-stack, image-studio]
```

---

## Step 3 — `main.py`

```python
# ~/ai-workstation/loadout-manager/main.py

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import subprocess, yaml, asyncio, time
from pathlib import Path
from typing import Optional
import pynvml

app = FastAPI(title="Loadout Manager", version="1.0.0")

CONFIG_PATH = Path("/app/profiles.yaml")
COMPOSE_BASE = Path("/app/docker")

# ── State ────────────────────────────────────────────────────────────────────
state = {
    "active_profile": None,
    "switching": False,
    "last_switched": None,
    "running_services": []
}

def load_profiles():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)["profiles"]

def get_gpu_info():
    pynvml.nvmlInit()
    gpus = []
    for i in range(pynvml.nvmlDeviceGetCount()):
        handle = pynvml.nvmlDeviceGetHandleByIndex(i)
        mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
        util = pynvml.nvmlDeviceGetUtilizationRates(handle)
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        gpus.append({
            "index": i,
            "vram_used_gb": round(mem.used / 1024**3, 1),
            "vram_total_gb": round(mem.total / 1024**3, 1),
            "vram_free_gb": round(mem.free / 1024**3, 1),
            "utilization_pct": util.gpu,
            "temp_c": temp
        })
    pynvml.nvmlShutdown()
    return gpus

def run_compose(compose_files: list, services: list, action: str):
    """Run docker compose up/down for specified files and services."""
    cmd = ["docker", "compose"]
    for f in compose_files:
        cmd += ["-f", str(COMPOSE_BASE / f.split("/")[-1])]
    
    if action == "up":
        cmd += ["up", "-d", "--remove-orphans"] + services
    elif action == "down":
        cmd += ["down", "--remove-orphans"]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Compose failed: {result.stderr}")
    return result.stdout

async def do_switch(profile_name: str):
    profiles = load_profiles()
    profile = profiles[profile_name]
    
    state["switching"] = True
    try:
        # Stop all currently managed services
        for compose_file in ["compose.inference.yml", "compose.training.yml",
                              "compose.studio.yml"]:
            try:
                subprocess.run(
                    ["docker", "compose", "-f", str(COMPOSE_BASE / compose_file), "down"],
                    capture_output=True, timeout=60
                )
            except Exception:
                pass
        
        await asyncio.sleep(3)  # allow GPU memory to release
        
        # Start new profile
        run_compose(profile["compose_files"], profile["services"], "up")
        
        state["active_profile"] = profile_name
        state["running_services"] = profile["services"]
        state["last_switched"] = time.time()
    finally:
        state["switching"] = False

# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/loadouts")
def list_loadouts():
    profiles = load_profiles()
    return {
        name: {
            "description": p.get("description", ""),
            "services": p.get("services", []),
            "exclusive_gpus": p.get("exclusive_gpus", []),
            "vram_required_gb": p.get("vram_required_gb", None),
            "active": name == state["active_profile"]
        }
        for name, p in profiles.items()
    }

@app.get("/status")
def get_status():
    return {
        "active_profile": state["active_profile"],
        "switching": state["switching"],
        "last_switched": state["last_switched"],
        "running_services": state["running_services"],
        "gpus": get_gpu_info()
    }

@app.post("/activate/{profile_name}")
async def activate_profile(profile_name: str, background_tasks: BackgroundTasks):
    profiles = load_profiles()
    if profile_name not in profiles:
        raise HTTPException(404, f"Profile '{profile_name}' not found")
    if state["switching"]:
        raise HTTPException(409, "Profile switch already in progress")
    
    # Check VRAM requirement
    profile = profiles[profile_name]
    if "vram_required_gb" in profile:
        gpus = get_gpu_info()
        total_free = sum(g["vram_free_gb"] for g in gpus)
        if total_free < profile["vram_required_gb"]:
            raise HTTPException(
                409,
                f"Insufficient free VRAM: {total_free:.1f}GB available, "
                f"{profile['vram_required_gb']}GB required"
            )
    
    background_tasks.add_task(do_switch, profile_name)
    return {"message": f"Switching to profile '{profile_name}'", "status": "switching"}

@app.post("/stop")
async def stop_all():
    if state["switching"]:
        raise HTTPException(409, "Profile switch in progress")
    for compose_file in ["compose.inference.yml", "compose.training.yml",
                          "compose.studio.yml"]:
        subprocess.run(
            ["docker", "compose", "-f", str(COMPOSE_BASE / compose_file), "down"],
            capture_output=True
        )
    state["active_profile"] = None
    state["running_services"] = []
    return {"message": "All services stopped"}

@app.get("/health")
def health():
    return {"status": "ok", "gpus": get_gpu_info()}

# ── Minimal Web UI ───────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def ui():
    return """
<!DOCTYPE html>
<html>
<head>
  <title>Loadout Manager</title>
  <style>
    body { font-family: monospace; background: #111; color: #eee; padding: 2rem; }
    h1 { color: #7fdbff; }
    .profile { border: 1px solid #333; padding: 1rem; margin: 0.5rem 0; border-radius: 4px; }
    .profile.active { border-color: #2ecc71; }
    button { background: #333; color: #eee; border: 1px solid #555;
             padding: 0.4rem 1rem; cursor: pointer; border-radius: 3px; }
    button:hover { background: #444; }
    .gpu { display: inline-block; margin: 0.5rem; padding: 0.5rem;
           background: #1a1a2e; border-radius: 4px; min-width: 140px; }
    .status { color: #7fdbff; margin-bottom: 1rem; }
  </style>
</head>
<body>
  <h1>⚡ Loadout Manager</h1>
  <div class="status" id="status">Loading...</div>
  <div id="gpus"></div>
  <h2>Profiles</h2>
  <div id="profiles"></div>
  <script>
    async function refresh() {
      const [status, loadouts] = await Promise.all([
        fetch('/status').then(r=>r.json()),
        fetch('/loadouts').then(r=>r.json())
      ]);
      
      document.getElementById('status').innerHTML =
        `Active: <b>${status.active_profile || 'none'}</b> | ` +
        `${status.switching ? '⏳ Switching...' : '✓ Idle'}`;
      
      document.getElementById('gpus').innerHTML = status.gpus.map(g =>
        `<div class="gpu">GPU${g.index}<br>${g.vram_used_gb}/${g.vram_total_gb}GB<br>` +
        `${g.utilization_pct}% | ${g.temp_c}°C</div>`
      ).join('');
      
      document.getElementById('profiles').innerHTML = Object.entries(loadouts).map(
        ([name, p]) => `
          <div class="profile ${p.active ? 'active' : ''}">
            <b>${name}</b> ${p.active ? '← active' : ''}
            <br>${p.description}
            <br>GPUs: ${p.exclusive_gpus.join(', ')} | Services: ${p.services.join(', ')}
            <br><button onclick="activate('${name}')">Activate</button>
          </div>`
      ).join('');
    }
    
    async function activate(name) {
      await fetch('/activate/' + name, {method: 'POST'});
      setTimeout(refresh, 500);
    }
    
    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>
"""
```

---

## Step 4 — `requirements.txt`

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
pyyaml==6.0.1
pynvml==11.5.0
```

---

## Step 5 — `Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY main.py profiles.yaml ./
RUN mkdir -p /app/docker
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8800"]
```

---

## Step 6 — Docker Compose Entry

```bash
cat <<'EOF' >> ~/ai-workstation/docker/compose.loadout.yml
version: '3.8'

services:
  loadout-manager:
    build: ../loadout-manager
    container_name: loadout-manager
    restart: unless-stopped
    ports:
      - "8800:8800"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock  # needs Docker socket
      - ../loadout-manager/profiles.yaml:/app/profiles.yaml
      - ../docker:/app/docker
    environment:
      - NVIDIA_VISIBLE_DEVICES=none   # manager itself needs no GPU

EOF

cd ~/ai-workstation
docker compose -f docker/compose.loadout.yml up -d --build
```

---

## Step 7 — CLI Alias

```bash
# Add to ~/.bashrc
alias loadout='curl -s http://localhost:8800/status | python3 -m json.tool'
alias loadout-activate='f(){ curl -sX POST http://localhost:8800/activate/$1 | python3 -m json.tool; }; f'
alias loadout-list='curl -s http://localhost:8800/loadouts | python3 -m json.tool'

# Usage:
# loadout                          → show current status + GPU state
# loadout-list                     → show all profiles
# loadout-activate inference-4gpu  → switch to 4-GPU profile
```

---

## Validation Checklist

- [ ] Loadout Manager API running at `:8800`
- [ ] Web UI accessible at `http://10.10.10.2:8800`
- [ ] `GET /loadouts` returns all profiles from YAML
- [ ] `GET /status` returns GPU VRAM/utilization/temp for all 4 GPUs
- [ ] `POST /activate/inference-small` successfully starts Ollama
- [ ] `POST /activate/inference-4gpu` stops previous services, starts vllm-4gpu
- [ ] VRAM gate rejects activation when insufficient free memory
- [ ] CLI aliases working on workstation

---

## Notes
- The Docker socket mount gives the loadout manager full Docker control — treat it as a privileged service
- Profile switches are async — poll `/status` for `switching: false` before assuming the switch is complete
- Add `--no-healthcheck` to compose commands if healthchecks slow down startup during switching
- Future enhancement: add a scheduler (cron-style) to auto-switch profiles on a time schedule (e.g. training overnight)
