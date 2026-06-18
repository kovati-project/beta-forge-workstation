# AI Workstation

Self-hosted AI stack running on a Threadripper Pro 5955WX / 512GB RAM / 4× RTX A5500 (96GB NVLink VRAM).

**Access:** `kasemo@10.10.10.2` (via jumpbox `10.10.10.1`)

---

## What's running

| Layer | Services |
|---|---|
| Inference | Ollama (11434), vLLM pair A/B/4-GPU (8000/8001/8002), ComfyUI (8188) |
| UI | Open WebUI (3000), SearXNG (8080) |
| Orchestration | Loadout Manager (8800) — VRAM-aware GPU profile switching |
| Agentic | n8n (5678), Dify (3010), MCP servers |
| Training | Kohya_ss (7860), Axolotl, JupyterLab (8888), Label Studio (8081) |
| Storage | MinIO (9000/9001), Qdrant (6333), PostgreSQL, Langfuse (3002) |
| Monitoring | Prometheus (9091), Grafana (3001), DCGM GPU metrics |
| Auth | Authentik (9080), Caddy reverse proxy |
| Voice | Whisper STT (9099), Piper TTS (5000) |
| Code | OpenHands (3003), Continue.dev |

Full port reference: [plan/PROJECT_PLAN.md](plan/PROJECT_PLAN.md#key-ports-reference)

---

## First-time deploy

Run from this repo root on **Windows**:

```powershell
# 1. Sync repo to workstation
.\sync-and-deploy.ps1

# 2. SSH in and run first-time setup
ssh kasemo@10.10.10.2
cd ~/ai-workstation
chmod +x scripts/*.sh scripts/*.py

bash scripts/init-secrets.sh       # generate all secrets
sudo bash scripts/setup-storage.sh # create /data/ directory tree

bash scripts/deploy-all.sh         # deploy phases 03–14
```

`deploy-all.sh` won't run until secrets and `/data/` exist.

### deploy-all.sh flags

```bash
bash scripts/deploy-all.sh                    # all phases (03–14)
bash scripts/deploy-all.sh --from 08          # resume from phase 08
bash scripts/deploy-all.sh --from 08 --to 10  # range
bash scripts/deploy-all.sh --phase 13         # single phase
bash scripts/deploy-all.sh --validate         # run validate-phaseNN.sh after each phase
bash scripts/deploy-all.sh --dry-run          # list phases without executing
```

---

## On-server development

### Sync a code change from Windows

```powershell
# Sync only (no deploy)
.\sync-and-deploy.ps1

# Sync and redeploy a specific phase
.\sync-and-deploy.ps1 -Deploy -Phase 06
```

The sync excludes `plan/`, `.git/`, `.env`, and `node_modules/`.

### Apply changes directly on the server

```bash
ssh kasemo@10.10.10.2
cd ~/ai-workstation

# Redeploy a single phase
bash scripts/deploy-phase06.sh

# Or restart a specific compose stack manually
docker compose -f docker/compose.inference.yml up -d --force-recreate
docker compose -f docker/compose.webui.yml up -d --force-recreate
```

---

## Restarting services

### Restart everything

```bash
bash scripts/start-all.sh
```

Services start in dependency order: storage → monitoring → auth → loadout manager → inference → UI → agentic → voice.

### Restart a single stack

```bash
docker compose -f docker/compose.<stack>.yml restart
```

Stack files in `docker/`:

| File | Services |
|---|---|
| `compose.inference.yml` | Ollama, vLLM, ComfyUI |
| `compose.webui.yml` | Open WebUI, SearXNG |
| `compose.loadout.yml` | Loadout Manager |
| `compose.storage.yml` | MinIO, Qdrant, PostgreSQL, Langfuse |
| `compose.monitoring.yml` | Prometheus, Grafana, DCGM, Node Exporter |
| `compose.auth.yml` | Authentik, Caddy |
| `compose.agentic.yml` | n8n, Dify, MCP servers |
| `compose.training.yml` | Kohya_ss, Axolotl, JupyterLab, Label Studio |
| `compose.codegen.yml` | OpenHands |
| `compose.voice.yml` | Whisper, Piper |

### Restart a single container

```bash
docker restart ollama
docker restart open-webui
docker restart loadout-manager
```

### Check what's failing

```bash
bash scripts/healthcheck.sh        # full health check + GPU status + active loadout
docker ps -a                       # see stopped containers
docker logs <container> --tail 50  # recent logs
```

---

## Updating what's running

### Pull latest Docker images and restart

```bash
bash scripts/update-system.sh images               # all stacks
bash scripts/update-system.sh images compose.inference.yml  # one stack
```

After pulling, force-recreate to apply:

```bash
docker compose -f docker/compose.inference.yml up -d --force-recreate
```

### Add / remove Ollama models

```bash
bash scripts/update-system.sh model-add qwen2.5-coder:32b
bash scripts/update-system.sh model-remove qwen2.5-coder:7b

# Or directly
docker exec ollama ollama pull mistral:7b
docker exec ollama ollama list
```

### Update NVIDIA drivers

```bash
bash scripts/update-system.sh driver latest
```

This stops GPU services, upgrades the driver, and reboots. After reboot: `bash scripts/start-all.sh`.

### Check for available updates

```bash
bash scripts/update-system.sh check
```

---

## Loadout profiles

The Loadout Manager allocates GPUs between workloads. Switch profiles via:

```bash
curl -X POST http://localhost:8800/activate/inference-pair-a
curl http://localhost:8800/status
```

| Profile | GPUs | Use case |
|---|---|---|
| `inference-small` | GPU 0 | 7B–13B Ollama |
| `inference-pair-a` | GPU 0+3 | 34B–40B vLLM TP=2 |
| `inference-pair-b` | GPU 1+2 | Second parallel model |
| `inference-4gpu` | all | 70B+ full precision |
| `image-studio` | GPU 0 | ComfyUI, frees 1/2/3 for LLM |
| `training-lora-image` | GPU 1+2 | Kohya image LoRA |
| `training-lora-text` | all | Axolotl FSDP fine-tune |
| `dual-stack` | 0+3 / 1+2 | Two simultaneous models |

---

## Backup and recovery

```bash
bash scripts/backup.sh             # full backup to /data/backups/YYYYMMDD-HHMMSS/
bash scripts/backup.sh configs     # configs only (fast)
```

Systemd units (installed by `deploy-all.sh` phase 14) run a daily backup automatically.

---

## Manual browser steps after first deploy

These cannot be automated — visit after `deploy-all.sh` finishes:

| Service | URL | Action |
|---|---|---|
| Authentik | `http://10.10.10.2:9080/if/flow/initial-setup/` | Create admin account |
| n8n | `http://10.10.10.2:5678` | Complete owner setup |
| Langfuse | `http://10.10.10.2:3002` | Create admin account |
| Grafana | `http://10.10.10.2:3001` | Import dashboards 12239, 1860, 893 |

---

## Troubleshooting

See [docs/troubleshooting-runbook.md](docs/troubleshooting-runbook.md).

Quick triage:

```bash
bash scripts/healthcheck.sh        # identify failing services
docker logs <container>            # check error output
docker compose -f docker/compose.<stack>.yml config  # validate compose config
```

Common fixes:

| Symptom | Fix |
|---|---|
| Docker not running | `sudo systemctl start docker` |
| Port already in use | `docker ps -a` then `docker rm <id>` |
| GPU not visible | `nvidia-smi` — if fails, reboot and check driver |
| Secrets missing | `bash scripts/init-secrets.sh` |
| `/data/` missing | `sudo bash scripts/setup-storage.sh` |
| Container keeps restarting | `docker logs <name> --tail 100` |
