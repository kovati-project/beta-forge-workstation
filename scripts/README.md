# Scripts

All scripts run on the workstation (`kasemo@10.10.10.2`) from the project root (`~/ai-workstation/`), except `sync-to-workstation.sh` which runs on the dev machine.

---

## First-time deployment

```bash
# 1. Copy repo to workstation (run from Windows — Git Bash / WSL / PowerShell)
scp -r . kasemo@10.10.10.2:~/ai-workstation/
# or
bash scripts/sync-to-workstation.sh

# 2. SSH in and run the three pre-flight steps in order
ssh kasemo@10.10.10.2
cd ~/ai-workstation
chmod +x scripts/*.sh scripts/*.py

bash scripts/init-secrets.sh      # generate all secrets, patch compose files
bash scripts/setup-storage.sh     # create /data/ directory tree (requires sudo)
bash scripts/deploy-all.sh        # deploy phases 03–14
```

`deploy-all.sh` guards itself — it exits with a clear error if secrets are still at defaults or `/data/` doesn't exist.

---

## Deployment scripts

### Orchestration

| Script | Runs on | Purpose |
| ------ | ------- | ------- |
| `sync-to-workstation.sh` | dev machine | rsync/scp repo to workstation; chmod +x scripts |
| `init-secrets.sh` | workstation | generate 16 secrets; patch all compose files and configs |
| `setup-storage.sh` | workstation | create `/data/` directory tree (run once, requires sudo) |
| `deploy-all.sh` | workstation | run all phase deploy scripts 03–14 in order |

### deploy-all.sh flags

```bash
bash scripts/deploy-all.sh                    # phases 03–14
bash scripts/deploy-all.sh --from 08          # resume from phase 08
bash scripts/deploy-all.sh --from 08 --to 10  # phases 08–10 only
bash scripts/deploy-all.sh --phase 13         # single phase
bash scripts/deploy-all.sh --validate         # run validate-phaseNN.sh after each phase
bash scripts/deploy-all.sh --dry-run          # list phases that would run, no exec
```

### Per-phase deploy + validate

Each phase has a pair of scripts. Run them directly to deploy or re-deploy a single phase.

| Phase | Deploy | Validate |
| ----- | ------ | -------- |
| 03 — Text Inference | `deploy-phase03.sh` | `validate-phase03.sh` |
| 04 — Image Inference | `deploy-phase04.sh` | `validate-phase04.sh` |
| 05 — Open WebUI | `deploy-phase05.sh` | `validate-phase05.sh` |
| 06 — Loadout Manager | `deploy-phase06.sh` | `validate-phase06.sh` |
| 07 — Training Pipeline | `deploy-phase07.sh` | `validate-phase07.sh` |
| 08 — Agentic Workflows & MCP | `deploy-phase08.sh` | `validate-phase08.sh` |
| 09 — Storage, Vector DB & RAG | `deploy-phase09.sh` | `validate-phase09.sh` |
| 10 — Monitoring | `deploy-phase10.sh` | `validate-phase10.sh` |
| 11 — Code Generation | `deploy-phase11.sh` | `validate-phase11.sh` |
| 12 — Voice I/O | `deploy-phase12.sh` | `validate-phase12.sh` |
| 13 — Security Hardening | `deploy-phase13.sh` | `validate-phase13.sh` |
| 14 — Operations Runbook | `setup-systemd-service.sh` *(sudo)* | — |

### Phase setup scripts (run automatically by deploy)

| Script | Purpose |
| ------ | ------- |
| `setup-storage-phase04.sh` | Create `/data/` subdirs for ComfyUI models |
| `setup-storage-phase07.sh` | Create `/data/` subdirs for training checkpoints |
| `setup-phase08.sh` | Pre-deploy setup for n8n and MCP servers |

---

## Day-to-day operations

| Script | Purpose |
| ------ | ------- |
| `start-all.sh` | Start all services in dependency order (called by systemd on boot) |
| `healthcheck.sh` | Check ~30 service endpoints; print GPU status and active loadout profile |
| `backup.sh` | Archive Docker volumes and configs to `/data/backups/YYYYMMDD-HHMMSS/` |
| `update-system.sh` | Pull latest images and restart services |
| `setup-systemd-service.sh` | Install systemd units for auto-start, daily backup, and 6-hourly health check *(sudo)* |
| `security-hardening-audit.sh` | Audit container privileges, SSH config, UFW, and secret exposure |
| `sync-checkpoints.sh` | Upload training checkpoints from `/data/checkpoints/` to MinIO |

```bash
# Common one-liners
bash scripts/healthcheck.sh
bash scripts/backup.sh
bash scripts/backup.sh configs          # configs only (fast)
sudo bash scripts/setup-systemd-service.sh
```

---

## Data and ML scripts

| Script | Purpose |
| ------ | ------- |
| `setup-qdrant.py` | Create the 4 Qdrant collections (768-dim, `nomic-embed-text`) |
| `ingest-documents.py` | Chunk and embed documents from `/data/documents/` into Qdrant |
| `code-router.py` | Route coding tasks to the appropriate model by complexity |
| `whisper-realtime.py` | Stream microphone audio to Whisper over WebSocket |
| `convert_labelstudio_to_alpaca.py` | Convert Label Studio exports to Alpaca fine-tuning format |

```bash
pip3 install -q qdrant-client requests
python3 scripts/setup-qdrant.py          # initialise Qdrant collections
python3 scripts/ingest-documents.py      # ingest docs from /data/documents/

pip3 install -q pyaudio websockets
python3 scripts/whisper-realtime.py      # live speech transcription
```

---

## What still needs a browser

These steps cannot be automated — visit each URL after `deploy-all.sh` completes:

| Service | URL | Action |
| ------- | --- | ------ |
| Authentik | `http://10.10.10.2:9080/if/flow/initial-setup/` | Create admin account |
| n8n | `http://10.10.10.2:5678` | Complete first-run owner setup |
| Langfuse | `http://10.10.10.2:3002` | Create admin account |
| Grafana | `http://10.10.10.2:3001` | Import dashboards 12239, 1860, 893 |

---

## Model downloads (run in background while services start)

```bash
# vLLM — Qwen2.5 32B for pair A (GPU 0+3)
huggingface-cli download Qwen/Qwen2.5-32B-Instruct \
  --local-dir /data/models/vllm/qwen2.5-32b --exclude '*.gguf'
ln -sf /data/models/vllm/qwen2.5-32b /data/models/vllm/current

# Ollama — minimum set
docker exec ollama ollama pull nomic-embed-text
docker exec ollama ollama pull qwen2.5-coder:7b
docker exec ollama ollama pull qwen2.5-coder:14b
```
