# Phase 06 — Loadout Manager

**Service:** Loadout Manager API + Web UI (`:8800`)  
**Compose file:** `docker/compose.loadout.yml`  
**Scripts:** `deploy-phase06.sh`, `validate-phase06.sh`

---

## Prerequisites

- [ ] Phases 03–05 deployed (compose files must exist on workstation)
- [ ] Files on workstation: `scp -r docker scripts configs loadout-manager kasemo@10.10.10.2:~/ai-workstation/`
- [ ] Docker socket accessible: `ssh kasemo@10.10.10.2 "ls -la /var/run/docker.sock"`

Phase 06 is independent of Phases 03–05 being *running* — it only needs their compose files to exist on disk so it can manage them. Phase 06 can deploy before or after the inference services are started.

---

## Step 1 — Copy Files to Workstation

The `loadout-manager/` directory must be copied in addition to the standard `docker/scripts/configs/` directories:

```bash
scp -r docker scripts configs loadout-manager kasemo@10.10.10.2:~/ai-workstation/
```

---

## Step 2 — Build and Start

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/deploy-phase06.sh"
```

The script:
1. Verifies all required compose files are present
2. Builds the `loadout-manager` Docker image (Python 3.11-slim + FastAPI)
3. Starts the container
4. Waits for the API to respond, then prints available profiles

Build takes 1–2 minutes on first run (downloading Python base image + pip install).

---

## Step 3 — Verify API

```bash
# Health check
ssh kasemo@10.10.10.2 "curl -s http://localhost:8800/health | python3 -m json.tool"

# Should return status: ok + GPU info for all 4 GPUs

# List all 8 profiles
ssh kasemo@10.10.10.2 "curl -s http://localhost:8800/loadouts | python3 -m json.tool"
```

---

## Step 4 — Open Web UI

Open `http://10.10.10.2:8800` in a browser.

Confirm:
- All 4 GPUs visible with VRAM bars
- All 8 profiles listed with descriptions
- No profile shows as active yet

---

## Step 5 — Test Profile Switching

```bash
# Activate inference-small (Ollama on GPU0)
ssh kasemo@10.10.10.2 "curl -sX POST http://localhost:8800/activate/inference-small \
  | python3 -m json.tool"

# Response: {"message": "Switching to profile 'inference-small'", "status": "switching"}

# Poll until switching completes (active_profile will be set)
ssh kasemo@10.10.10.2 "curl -s http://localhost:8800/status | python3 -m json.tool"

# Confirm correct services are running
ssh kasemo@10.10.10.2 "docker ps --format 'table {{.Names}}\t{{.Status}}'"

# Stop all services
ssh kasemo@10.10.10.2 "curl -sX POST http://localhost:8800/stop | python3 -m json.tool"
```

Profile switches are async — the API returns immediately. Poll `/status` for `"switching": false` before assuming the switch is done.

---

## Step 6 — Validate

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase06.sh"
```

Expected output:
```
✓ Loadout Manager container running
✓ API responding at :8800
✓ GET /loadouts lists all profiles
✓ GET /status returns GPU info
✓ Web UI loads
✓ 8 profiles defined
✓ inference-small profile exists
✓ training-lora-text profile exists
✓ Docker socket accessible

Result: 8 passed, 0 failed
Phase 06 READY
```

---

## Available Profiles

| Profile | GPUs | Services | Use Case |
|---------|------|----------|----------|
| `inference-small` | 0 | Ollama | 7B–13B chat |
| `inference-pair-a` | 0, 3 | vLLM pair A + Ollama on GPU1 | 32B–40B fast inference |
| `inference-pair-b` | 1, 2 | vLLM pair B | Second 32B–40B model |
| `inference-4gpu` | 0–3 | vLLM 4-GPU | 70B+ models (88GB VRAM required) |
| `dual-stack` | 0–3 | vLLM pair A + pair B | Two simultaneous 32B models |
| `image-studio` | 0, 1, 2 | ComfyUI + vLLM pair B | Image gen + LLM on separate GPUs |
| `training-lora-image` | 1, 2 | Kohya + Label Studio | Image LoRA (pair B) |
| `training-lora-text` | 0–3 | Axolotl FSDP | Full text fine-tune (90GB VRAM required) |

---

## Quick Reference

```bash
# Show current status + GPU VRAM
ssh kasemo@10.10.10.2 "curl -s http://localhost:8800/status | python3 -m json.tool"

# Switch profile
ssh kasemo@10.10.10.2 "curl -sX POST http://localhost:8800/activate/inference-pair-a"

# Stop all managed services
ssh kasemo@10.10.10.2 "curl -sX POST http://localhost:8800/stop"

# Loadout Manager logs
ssh kasemo@10.10.10.2 "docker logs -f loadout-manager"

# Rebuild after code changes
ssh kasemo@10.10.10.2 "docker compose -f ~/ai-workstation/docker/compose.loadout.yml \
  up -d --build"

# Shell aliases (add to ~/.bashrc on workstation)
# alias loadout='curl -s http://localhost:8800/status | python3 -m json.tool'
# alias loadout-list='curl -s http://localhost:8800/loadouts | python3 -m json.tool'
# alias loadout-activate='f(){ curl -sX POST http://localhost:8800/activate/$1 | python3 -m json.tool; }; f'
```

---

## Notes

- The Docker socket mount (`:ro`) gives the container full Docker API access — keep port 8800 LAN-only
- State is in-memory only — active profile is lost on container restart; re-activate after restart
- VRAM gate runs before switching: `inference-4gpu` requires ≥88GB free, `training-lora-text` requires ≥90GB
- Profile switches stop **all** managed compose stacks (inference, training, studio) before starting the new one — expect a ~3 second gap during switching

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Build fails | `docker logs loadout-manager`; check Python dependency versions in `requirements.txt` |
| API not responding after deploy | `docker ps \| grep loadout` — container may have crashed; check logs |
| GPU info missing from `/health` | pynvml version mismatch — `docker exec loadout-manager pip show nvidia-ml-py` |
| Profile switch doesn't stop old services | Docker socket may be read-only but still functional; run `docker ps` to confirm previous services stopped |
| `inference-4gpu` rejected with VRAM error | Stop current profile first: `POST /stop`, wait for GPU memory to clear |
| 8 profiles not listed | `profiles.yaml` may not be mounted correctly — `docker inspect loadout-manager \| grep profiles` |
