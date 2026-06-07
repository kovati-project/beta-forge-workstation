# GHC Task: Phase 06 — Loadout Manager
**Brief ID:** P06-001  
**Source doc:** `/plan/steps/06-loadout-manager.md`  
**Write feedback to:** `/plan/ghc-feedback/phase06-loadout-manager.md`

---

## Context

Phases 01–05 are complete. The workstation (`adapress`, 10.10.10.2) has:
- Ubuntu 26.04 LTS, driver 595.71.05, CUDA 13.3
- Ollama at `:11434` (GPU0)
- vLLM pair A at `:8000` (GPU0+GPU3), pair B at `:8001` (GPU1+GPU2), 4-GPU at `:8002`
- ComfyUI at `:8188` (GPU0), Real-ESRGAN at `:8189`, Rembg at `:8190`
- Open WebUI at `:3000`, SearXNG at `:8080`

**NVLink pairs:** GPU0↔GPU3 (pair A), GPU1↔GPU2 (pair B). All four GPUs are 24GB RTX A5500.

There is currently no mechanism to switch between GPU-exclusive workloads without manually stopping and starting containers. This phase builds the custom FastAPI orchestrator that manages which Compose stacks are running, enforces VRAM constraints, and exposes a REST API + minimal web UI for profile switching.

This is the only fully custom-built component in the stack (not a third-party image). It runs on the workstation inside Docker, with the Docker socket mounted so it can manage other containers.

---

## Scope

Create:
1. **`loadout-manager/main.py`** — FastAPI app with `/loadouts`, `/status`, `/activate/{name}`, `/stop`, `/health`, and a minimal HTML web UI at `/`
2. **`loadout-manager/profiles.yaml`** — VRAM-aware profile definitions for all loadout types
3. **`loadout-manager/requirements.txt`** — pinned dependencies
4. **`loadout-manager/Dockerfile`** — container build
5. **`docker/compose.loadout.yml`** — Compose service definition (Docker socket mount, no GPU)
6. **`scripts/deploy-phase06.sh`** — build and start the loadout manager
7. **`scripts/validate-phase06.sh`** — API smoke tests, exits non-zero on failure

**Not in scope:** Scheduler/cron for time-based profile switching, authentication on the loadout API, metrics integration (Phase 10).

---

## Step 1 — `loadout-manager/profiles.yaml`

Include all eight profiles listed in the source doc. Key fields per profile:
- `description` — human-readable label shown in the web UI
- `compose_files` — list of relative paths from repo root (e.g. `../docker/compose.inference.yml`)
- `services` — list of Compose service names to start
- `gpu_assignment` — map of service → GPU indices (for documentation; enforcement is via the compose files)
- `exclusive_gpus` — list of GPU indices claimed by this profile (used for VRAM gate validation)
- `vram_required_gb` — optional; only set for profiles that need ≥88GB (inference-4gpu: 88, training-lora-text: 90)
- `incompatible_with` — optional list of profiles that cannot run simultaneously (set on training profiles)

Profiles to include: `inference-small`, `inference-pair-a`, `inference-pair-b`, `inference-4gpu`, `dual-stack`, `image-studio`, `training-lora-image`, `training-lora-text`.

---

## Step 2 — `loadout-manager/main.py`

FastAPI app. All routes return JSON. One HTML route (`/`) serves the web UI inline (no template files, no static directory mount).

**Routes:**

| Method | Path | Behaviour |
|--------|------|-----------|
| `GET` | `/loadouts` | Returns all profiles from YAML with `active` flag |
| `GET` | `/status` | Returns active profile, switching flag, running services list, GPU info |
| `POST` | `/activate/{profile_name}` | Validates VRAM, stops all managed stacks, starts new profile (async via BackgroundTasks) |
| `POST` | `/stop` | Stops all managed stacks, clears active profile |
| `GET` | `/health` | Returns `status: ok` + GPU info |

**GPU info via pynvml:** for each GPU: index, vram_used_gb, vram_total_gb, vram_free_gb, utilization_pct, temp_c. Round VRAM values to one decimal place.

**Profile switch logic in `do_switch()`:**
1. Set `state["switching"] = True`
2. Iterate `compose.inference.yml`, `compose.training.yml`, `compose.studio.yml`, `compose.agentic.yml` — run `docker compose -f <file> down` on each (ignore errors, timeout 60s per file)
3. `await asyncio.sleep(3)` to allow GPU memory to release
4. Run `docker compose -f <file> ... up -d --remove-orphans` for the new profile's compose files and services
5. Update `state["active_profile"]`, `state["running_services"]`, `state["last_switched"]`
6. Set `state["switching"] = False` in finally block

**VRAM gate** in `/activate/{profile_name}`: if `vram_required_gb` is set, sum `vram_free_gb` across all GPUs before switching. If total free < required, return HTTP 409 with a descriptive message.

**Web UI at `/`**: inline HTML, dark monospace theme. Polls `/status` and `/loadouts` every 5 seconds. Shows:
- Current active profile and switching state
- VRAM bar per GPU (used / total GB, utilization %, temp)
- Each profile as a card with description, GPUs, services, Activate button
- Active profile card highlighted (green border)

**Compose path handling:** the manager container mounts `/app/docker` from the host `docker/` directory. Use `COMPOSE_BASE = Path("/app/docker")` and strip path prefixes from `compose_files` entries (take just the filename).

---

## Step 3 — `loadout-manager/requirements.txt`

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
pyyaml==6.0.1
pynvml==11.5.0
```

---

## Step 4 — `loadout-manager/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py profiles.yaml ./
RUN mkdir -p /app/docker
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8800"]
```

---

## Step 5 — `docker/compose.loadout.yml`

```yaml
services:
  loadout-manager:
    build:
      context: ../loadout-manager
    container_name: loadout-manager
    restart: unless-stopped
    ports:
      - "8800:8800"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ../loadout-manager/profiles.yaml:/app/profiles.yaml
      - ../docker:/app/docker
    environment:
      - NVIDIA_VISIBLE_DEVICES=none
```

**Critical:** `NVIDIA_VISIBLE_DEVICES=none` — the loadout manager itself needs no GPU. Do not add a `deploy.resources.reservations.devices` block.

---

## Step 6 — `scripts/deploy-phase06.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Phase 06: Loadout Manager ==="

# Build and start
docker compose -f "$REPO_ROOT/docker/compose.loadout.yml" up -d --build

# Wait for API
echo "Waiting for API..."
for i in $(seq 1 15); do
    if curl -sf http://localhost:8800/health >/dev/null 2>&1; then
        echo "Loadout Manager ready at http://10.10.10.2:8800"
        break
    fi
    sleep 2
done

echo ""
echo "Available profiles:"
curl -s http://localhost:8800/loadouts | python3 -m json.tool
```

---

## Step 7 — `scripts/validate-phase06.sh`

Validation checks:

| Check | Command |
|-------|---------|
| Container running | `docker ps --filter name=loadout-manager --filter status=running \| grep -q loadout-manager` |
| Health endpoint | `curl -sf http://localhost:8800/health` |
| Returns 4 GPUs | `curl -sf http://localhost:8800/health \| python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d['gpus'])==4"` |
| All 8 profiles present | `curl -sf http://localhost:8800/loadouts \| python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d)==8"` |
| Activate inference-small | `curl -sf -X POST http://localhost:8800/activate/inference-small` |
| Status shows switching/active | `curl -sf http://localhost:8800/status \| grep -q 'active_profile'` |
| Stop endpoint | `curl -sf -X POST http://localhost:8800/stop` |
| Web UI returns HTML | `curl -sf http://localhost:8800/ \| grep -q 'Loadout Manager'` |

Use the same `check()` / `warn()` pattern as validate-phase03.sh. Exit with `$FAIL` count.

Manual checks (warn only):
- Open `http://10.10.10.2:8800` in browser, confirm GPU VRAM bars refresh
- Activate a profile and confirm correct containers start in `docker ps`
- Activate `training-lora-text` and confirm it rejects if VRAM is occupied

---

## Constraints

- The `version: '3.8'` key is deprecated in modern Compose — omit it from `compose.loadout.yml`
- The Docker socket mount (`/var/run/docker.sock`) gives the container full Docker control. Do not expose port 8800 externally or add a firewall exception — it is LAN-only
- Profile switch is async — the `/activate` response returns `"status": "switching"` immediately; the client must poll `/status` to confirm completion
- `compose_files` paths in profiles.yaml use `../docker/` prefix (relative to the `loadout-manager/` directory). Strip to filename only when constructing subprocess commands inside the container
- Do not hardcode `/var/run/docker.sock` in `main.py` — it is already mounted at that path inside the container by the Compose volume

---

## Feedback Template

Write to `/plan/ghc-feedback/phase06-loadout-manager.md`:

```markdown
# GHC Feedback: Phase 06 — Loadout Manager
**Brief:** P06-001 | **Status:** Complete / Partial / Blocked

## Files Created
- [ ] loadout-manager/main.py
- [ ] loadout-manager/profiles.yaml
- [ ] loadout-manager/requirements.txt
- [ ] loadout-manager/Dockerfile
- [ ] docker/compose.loadout.yml
- [ ] scripts/deploy-phase06.sh
- [ ] scripts/validate-phase06.sh

## Deviations from Brief
| Item | Plan | Actual | Reason |

## Validation Results
[paste validate-phase06.sh output]

## Notes
```
