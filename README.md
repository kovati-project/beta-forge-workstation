# AI Workstation

Self-hosted AI stack running on a Threadripper Pro 5955WX / 512GB RAM / 4× RTX A5500 (96GB NVLink VRAM).

**Access:** `kasemo@<WORKSTATION_HOST>` (via jumpbox `10.10.10.1`); the host address is set once in `docker/.env`, see [Changing the workstation host](#changing-the-workstation-host)

---

## What's running

| Layer | Services |
|---|---|
| Inference | vLLM Qwen3.8-27B (8002, default, all 4 GPUs) + embeddings (8003); optional vLLM pair A/B (8000/8001); ComfyUI (8188) |
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
ssh kasemo@<WORKSTATION_HOST>
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
ssh kasemo@<WORKSTATION_HOST>
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
| `compose.inference.yml` | vLLM (4-GPU default + embeddings, pair A/B profiles) |
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
docker restart vllm-4gpu
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

### Add / remove models

Models are Hugging Face checkpoints under `/data/models/vllm/`; a vLLM service
serves whichever one its slot symlink (`current`, `current-b`, `large`) points at.
The loadout manager's Models page does the same as:

```bash
bash scripts/update-system.sh model-add Qwen/Qwen2.5-32B-Instruct qwen2.5-32b
ln -sfn qwen2.5-32b /data/models/vllm/current     # pair A slot
bash scripts/update-system.sh model-remove qwen2.5-14b
```

The default slot `large` holds Qwen3.8-27B-FP8, which VS Code Copilot Chat,
Continue.dev, OpenHands, Open WebUI and n8n all use (`configs/continue/`,
`configs/vscode/chatLanguageModels.json`). `vllm-4gpu`'s flags are specific to
that model family; check them before pointing `large` elsewhere.

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
| `inference-4gpu` | all | **Default.** Qwen3.8-27B (coding + chat) + embeddings |
| `inference-pair-a` | GPU 0+3 | 34B–40B vLLM TP=2 (+ embeddings on GPU 1) |
| `inference-pair-b` | GPU 1+2 | Second parallel model |
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

The UI (Settings → Backups, Storage → Run Backup Now) runs the same `backup.sh all` in a
short-lived helper container and lists the runs found under `/data/backups/`. Restore is
manual: follow the steps in the run's `MANIFEST.txt`, stopping the affected services first.

---

## Manual browser steps after first deploy

These cannot be automated — visit after `deploy-all.sh` finishes:

| Service | URL | Action |
|---|---|---|
| Authentik | `http://<WORKSTATION_HOST>:9080/if/flow/initial-setup/` | Create admin account |
| n8n | `http://<WORKSTATION_HOST>:5678` | Complete owner setup |
| Langfuse | `http://<WORKSTATION_HOST>:3002` | Create admin account |
| Grafana | `http://<WORKSTATION_HOST>:3001` | Import dashboards 12239, 1860, 893 |

---

## Changing the workstation host

Every browser-facing URL (Grafana's root URL, n8n webhooks, Dify's web API
prefix, the SearXNG `base_url`, OAuth redirect URIs shown by the loadout
manager, and the URLs the deploy/validate scripts print) comes from one value,
`WORKSTATION_HOST` in `docker/.env`. It can be an IP or a hostname such as
`kovati.lan`; when unset it falls back to `10.10.10.2`. Service-to-service
traffic (Open WebUI, Caddy, Prometheus, n8n/Dify to Ollama) uses container names
on the Docker networks and does not depend on it.

To move the workstation to a new address:

```bash
# on the workstation
sed -i 's/^WORKSTATION_HOST=.*/WORKSTATION_HOST=192.168.1.102/' docker/.env   # or add the line
bash scripts/init-secrets.sh --render-searxng          # re-renders base_url, keeps the key
docker compose -f docker/compose.agentic.yml up -d     # n8n, Dify
docker compose -f docker/compose.monitoring.yml up -d  # Grafana
docker compose -f docker/compose.webui.yml up -d       # SearXNG
docker compose -f docker/compose.loadout.yml up -d     # loadout manager
```

`up -d` recreates only the containers whose configuration changed. Do not use
`docker compose restart`; it does not re-read `docker/.env`.

Client machines (the Continue.dev configs in `configs/continue/` and
`configs/open-webui/continue-config.json`, and `scripts/test-coding-agent.ps1`)
address the workstation as `kovati.lan`. Add one hosts entry per client, and an
IP change is then a one-line edit there:

```text
# Windows: C:\Windows\System32\drivers\etc\hosts   Linux/macOS: /etc/hosts
192.168.1.102  kovati.lan
```

If you set `WORKSTATION_HOST=kovati.lan` on the workstation too, give the
workstation itself the same hosts entry (or a local DNS record).

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
