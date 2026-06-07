# Phase 14 — Operations Runbook
[← Security Hardening](13-security-hardening.md) | [↑ Project Plan](../PROJECT_PLAN.md)

---

## Objective
Day-to-day operational procedures: service startup order, health checks, backup and restore, driver and model updates, troubleshooting playbooks, and capacity planning.

---

## Service Startup Order

Hard dependencies require this order. The loadout manager handles inference/training/studio services; this covers the foundational layer.

```bash
#!/bin/bash
# ~/ai-workstation/scripts/start-all.sh

set -e
COMPOSE="docker compose"
BASE="$HOME/ai-workstation/docker"

echo "=== Starting AI Workstation ==="

# 1. Storage (everything depends on this)
echo "[1/6] Storage stack..."
$COMPOSE -f $BASE/compose.storage.yml up -d
sleep 5

# 2. Monitoring (start early to catch startup metrics)
echo "[2/6] Monitoring stack..."
$COMPOSE -f $BASE/compose.monitoring.yml up -d
sleep 3

# 3. Auth (before any user-facing services)
echo "[3/6] Auth (Authentik)..."
$COMPOSE -f $BASE/compose.auth.yml up -d
sleep 5

# 4. Loadout manager
echo "[4/6] Loadout manager..."
$COMPOSE -f $BASE/compose.loadout.yml up -d
sleep 3

# 5. Default inference profile
echo "[5/6] Activating default inference profile..."
curl -sX POST http://localhost:8800/activate/inference-pair-a
sleep 15  # allow model to load

# 6. UI and agents
echo "[6/6] UI and agentic services..."
$COMPOSE -f $BASE/compose.webui.yml up -d
$COMPOSE -f $BASE/compose.agentic.yml up -d n8n mcp-filesystem mcp-fetch mcp-browser
$COMPOSE -f $BASE/compose.voice.yml up -d

echo "=== Startup complete ==="
echo "Open WebUI: https://ai.local"
echo "Status:     http://localhost:8800"
```

```bash
sudo chmod +x ~/ai-workstation/scripts/start-all.sh

# Enable as systemd service for auto-start on boot
cat <<EOF | sudo tee /etc/systemd/system/ai-workstation.service
[Unit]
Description=AI Workstation Services
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=$USER
WorkingDirectory=$HOME/ai-workstation
ExecStart=$HOME/ai-workstation/scripts/start-all.sh
ExecStop=docker compose -f $HOME/ai-workstation/docker/compose.webui.yml -f $HOME/ai-workstation/docker/compose.agentic.yml -f $HOME/ai-workstation/docker/compose.voice.yml -f $HOME/ai-workstation/docker/compose.storage.yml -f $HOME/ai-workstation/docker/compose.monitoring.yml down

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable ai-workstation
```

---

## Health Check Script

```bash
#!/bin/bash
# ~/ai-workstation/scripts/healthcheck.sh

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

check() {
    local name=$1; local url=$2; local expect=$3
    local result=$(curl -sf -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)
    if [ "$result" = "$expect" ]; then
        echo -e "${GREEN}✓${NC} $name ($result)"
    else
        echo -e "${RED}✗${NC} $name (got $result, expected $expect)"
    fi
}

echo "=== Service Health ==="
check "Loadout Manager"   "http://localhost:8800/health"    "200"
check "Open WebUI"        "http://localhost:3000"           "200"
check "Ollama"            "http://localhost:11434/api/tags" "200"
check "vLLM pair A"       "http://localhost:8000/health"    "200"
check "ComfyUI"           "http://localhost:8188/system_stats" "200"
check "Grafana"           "http://localhost:3001/api/health" "200"
check "Prometheus"        "http://localhost:9091/-/healthy"  "200"
check "MinIO"             "http://localhost:9000/minio/health/live" "200"
check "Qdrant"            "http://localhost:6333/"          "200"
check "n8n"               "http://localhost:5678/healthz"   "200"
check "Whisper"           "http://localhost:9099/health"    "200"
check "Label Studio"      "http://localhost:8081/api/health" "200"

echo ""
echo "=== GPU Status ==="
nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.free \
  --format=csv,noheader,nounits | \
  awk -F', ' '{printf "GPU%s: %s | %s°C | %s%% util | %sMB used | %sMB free\n", $1,$2,$3,$4,$5,$6}'

echo ""
echo "=== Active Loadout ==="
curl -sf http://localhost:8800/status | python3 -c "
import json,sys
s=json.load(sys.stdin)
print(f'Profile: {s[\"active_profile\"]}')
print(f'Services: {s[\"running_services\"]}')
"

echo ""
echo "=== Disk Usage ==="
df -h /data | awk 'NR>1{printf "Models+Data: %s used of %s (%s full)\n",$3,$2,$5}'
```

```bash
sudo chmod +x ~/ai-workstation/scripts/healthcheck.sh
# Add alias
echo "alias health='~/ai-workstation/scripts/healthcheck.sh'" >> ~/.bashrc
```

---

## Backup Procedures

### What to Back Up

| Data | Location | Priority | Method |
|------|----------|----------|--------|
| Open WebUI conversations | Docker volume `open-webui-data` | High | Daily |
| n8n workflows & credentials | Docker volume `n8n-data` | Critical | Daily |
| Authentik config | Docker volume | Critical | Daily |
| Label Studio annotations | Docker volume `label-studio-data` | Critical | Daily |
| Qdrant vector collections | Docker volume `qdrant-data` | Medium | Weekly |
| Training configs (.toml/.yml) | `~/ai-workstation/configs/` | High | Git |
| LoRA adapters | `/data/models/comfyui/loras/` | High | MinIO + offsite |
| Model weights | `/data/models/` | Low | Redownloadable |

### Backup Script

```bash
#!/bin/bash
# ~/ai-workstation/scripts/backup.sh

BACKUP_ROOT="/data/backups"
DATE=$(date +%Y%m%d-%H%M)
BACKUP_DIR="$BACKUP_ROOT/$DATE"
mkdir -p "$BACKUP_DIR"

echo "=== Backup $DATE ==="

# 1. Docker volumes — stop services for consistency, snapshot, restart
backup_volume() {
    local vol=$1; local name=$2
    echo "Backing up volume: $name..."
    docker run --rm \
        -v "$vol":/source:ro \
        -v "$BACKUP_DIR":/backup \
        alpine tar czf "/backup/${name}.tar.gz" -C /source .
}

backup_volume open-webui-data    open-webui
backup_volume n8n-data           n8n
backup_volume label-studio-data  label-studio
backup_volume qdrant-data        qdrant
backup_volume prometheus-data    prometheus
backup_volume grafana-data       grafana

# 2. Configs and scripts (git repo is canonical but back up anyway)
tar czf "$BACKUP_DIR/configs.tar.gz" -C ~/ai-workstation .

# 3. LoRA adapters
tar czf "$BACKUP_DIR/loras.tar.gz" -C /data/models/comfyui/loras .

# 4. Training configs
tar czf "$BACKUP_DIR/training-configs.tar.gz" -C /data/configs .

# 5. Sync to MinIO
mc mirror --overwrite "$BACKUP_DIR/" "local/backups/$DATE/"

# 6. Prune local backups older than 30 days
find "$BACKUP_ROOT" -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +

echo "=== Backup complete: $BACKUP_DIR ==="
du -sh "$BACKUP_DIR"
```

```bash
# Schedule daily backup at 2am
(crontab -l 2>/dev/null; echo "0 2 * * * $HOME/ai-workstation/scripts/backup.sh >> /var/log/ai-backup.log 2>&1") | crontab -
```

---

## Update Procedures

### Updating Docker Images

```bash
# Pull latest images for all services
docker compose -f ~/ai-workstation/docker/compose.inference.yml pull
docker compose -f ~/ai-workstation/docker/compose.webui.yml pull
docker compose -f ~/ai-workstation/docker/compose.monitoring.yml pull
# ... repeat for each compose file

# Recreate updated containers
docker compose -f ~/ai-workstation/docker/compose.webui.yml up -d --force-recreate

# Clean up old images
docker image prune -f
```

### Updating NVIDIA Drivers

```bash
# ALWAYS back up first
~/ai-workstation/scripts/backup.sh

# Stop all GPU workloads
curl -X POST http://localhost:8800/stop
docker compose -f ~/ai-workstation/docker/compose.webui.yml down

# Update driver
sudo apt update
sudo apt install -y nvidia-driver-560  # or latest

sudo reboot

# After reboot: validate NVLink before starting services
python3 /opt/scripts/validate-nvlink.py

# Restart services
~/ai-workstation/scripts/start-all.sh
```

### Adding a New Model

```bash
# Via Ollama (simplest)
docker exec ollama ollama pull <model-name>

# Via Hugging Face (for vLLM)
huggingface-cli download <org>/<model> \
  --local-dir /data/models/vllm/<model-name> \
  --exclude "*.gguf"

# Update loadout profiles if new model needs specific GPU assignment
nano ~/ai-workstation/loadout-manager/profiles.yaml

# Reload loadout manager
docker restart loadout-manager
```

---

## Troubleshooting Playbooks

### GPU Out of Memory (OOM)

```bash
# 1. Identify what's using VRAM
nvidia-smi
nvitop

# 2. Check loadout state
curl http://localhost:8800/status

# 3. If stuck process: find and kill
nvidia-smi --query-compute-apps=pid,used_memory,name --format=csv,noheader
kill -9 <pid>

# 4. Force stop all containers
curl -X POST http://localhost:8800/stop
sleep 5

# 5. Verify VRAM is released
nvidia-smi --query-gpu=memory.used --format=csv,noheader
# Should show <1000 MB per GPU

# 6. Reactivate desired profile
curl -X POST http://localhost:8800/activate/inference-small
```

### vLLM Failing to Start

```bash
docker logs vllm-pair-a 2>&1 | tail -50

# Common causes:
# "CUDA out of memory" → model too large for GPU pair, reduce --gpu-memory-utilization
# "No module named vllm" → image pull needed: docker pull vllm/vllm-openai:latest
# "NCCL error" → check NCCL env vars, verify NVLink: validate-nvlink.py
# "Model not found" → check /data/models/vllm/current symlink
ls -la /data/models/vllm/current
```

### NVLink Validation Failure

```bash
# Run full validation
python3 /opt/scripts/validate-nvlink.py

# If a pair fails: check nvlink status
nvidia-smi nvlink --status -i 0
nvidia-smi nvlink --status -i 1
nvidia-smi nvlink --status -i 2
nvidia-smi nvlink --status -i 3

# Check for errors
nvidia-smi nvlink --get-counters -i 0 | grep -i error

# If errors present: power cycle (not just reboot)
# Pull the power plug for 30 seconds — NVLink bridges need full discharge
```

### Loadout Manager Not Switching

```bash
docker logs loadout-manager 2>&1 | tail -20

# Check if a service is stuck
docker ps -a | grep -v Up

# Force remove stuck containers
docker rm -f <container_name>

# Restart loadout manager
docker restart loadout-manager
```

### Disk Full

```bash
df -h /data

# Check what's consuming space
du -sh /data/* | sort -rh | head -20

# Quick wins:
docker system prune -f          # remove unused images/containers/networks
rm -rf /data/outputs/comfyui/*  # clear image outputs
find /data/checkpoints -name "*.bin" -mtime +30 -delete  # old checkpoints

# Move models to MinIO if local NVMe is full
mc cp /data/models/vllm/old-model/ local/models/archive/old-model/
rm -rf /data/models/vllm/old-model
```

---

## Capacity Planning

### Current VRAM Budget (96GB total)

| Scenario | GPU0 | GPU1 | GPU2 | GPU3 | Total |
|----------|------|------|------|------|-------|
| Idle | 0 | 0 | 0 | 0 | 0 GB |
| Chat (7B Ollama) | 6 | 0 | 0 | 0 | 6 GB |
| Chat + Image | 12+8 | 0 | 0 | 0 | 20 GB |
| 32B vLLM pair A | 22 | 0 | 0 | 22 | 44 GB |
| Dual 32B | 22 | 22 | 22 | 22 | 88 GB |
| 70B vLLM 4GPU | 22 | 22 | 22 | 22 | 88 GB |
| Training (Axolotl FSDP) | 22 | 22 | 22 | 22 | 88 GB |
| Image LoRA (Kohya pair B) | 0 | 20 | 20 | 0 | 40 GB |

### When to Consider Expansion

- **VRAM:** If you regularly need to run 70B inference while training — consider a second workstation or upgrade to A6000 (48GB) for any GPU slot
- **System RAM:** 512GB is extremely generous — unlikely to be a bottleneck
- **Storage:** At 70B model weights (~140GB fp16 each), NVMe fills quickly. Budget 4TB+ for models; 2TB for datasets and checkpoints
- **Network:** 10GbE is sufficient for current load. If running multiple clients with real-time voice + streaming inference, consider RDMA/RoCE

---

## Weekly Maintenance Checklist

- [ ] Run `healthcheck.sh` and review output
- [ ] Check Grafana for temperature anomalies or ECC errors
- [ ] Review n8n workflow execution logs for failures
- [ ] Verify backup completed successfully (`/var/log/ai-backup.log`)
- [ ] Check disk usage trends (`df -h /data`)
- [ ] Review Langfuse for model performance regressions
- [ ] Check for NVIDIA driver updates: `apt list --upgradable | grep nvidia`
- [ ] Pull latest Docker images for active services
- [ ] Rotate any API keys or credentials approaching age limit
- [ ] Review Prometheus alerts for any silenced or ignored conditions
