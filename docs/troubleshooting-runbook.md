# Phase 14 — Operations Runbook: Troubleshooting Guide

[← Security Hardening](../steps/13-security-hardening.md) | [↑ Project Plan](../PROJECT_PLAN.md)

---

## Quick Reference

**Before troubleshooting anything:**
1. Run `bash scripts/healthcheck.sh` to identify failing services
2. Run `bash scripts/backup.sh` to preserve state before changes
3. Check Grafana dashboards for temperature/performance anomalies
4. Review `docker logs <container>` for error messages

---

## Service Startup Failures

### AI Workstation Won't Start (`start-all.sh` fails)

**Symptom:** Script exits partway through with an error

**Diagnosis:**
```bash
# Check Docker is running
docker info

# Check specific compose file
docker compose -f docker/compose.storage.yml config

# Watch startup in detail (remove 'set -e' from start-all.sh temporarily)
bash -x scripts/start-all.sh 2>&1 | head -100
```

**Common Causes & Fixes:**

| Error | Cause | Fix |
|-------|-------|-----|
| `Cannot connect to Docker` | Docker daemon not running | `sudo systemctl start docker` |
| `file not found` | Compose file missing | Check `docker/` directory exists |
| `port already in use` | Service already running or port conflict | `docker ps -a` and `docker rm <id>` |
| `image not found` | Image pull failed (network) | `docker pull <image>` manually |

### Services Start But Don't Respond

**Symptom:** Container running but HTTP checks timeout

**Diagnosis:**
```bash
# Check container logs
docker logs <service-name>

# Check if container is actually running
docker ps | grep <service-name>

# Check port mappings
docker port <service-name>

# Test connectivity
curl -v http://localhost:<port>
```

**Examples:**

**Authentik stuck on startup:**
```bash
docker logs authentik-server | tail -50

# Look for:
# - "psycopg2.OperationalError" → PostgreSQL not running
# - "Connection refused" → Redis not running
# - "Schema migration failed" → Database corruption (nuclear option: delete volume)

# Fix: Start dependencies first
docker compose -f docker/compose.auth.yml up -d postgres redis
sleep 10
docker compose -f docker/compose.auth.yml up -d
```

**Loadout Manager won't start:**
```bash
docker logs loadout-manager | tail -50

# Look for:
# - "Docker socket not found" → Docker socket not mounted
# - "Permission denied" → User doesn't have Docker access

# Fix: Check user is in docker group
groups $USER | grep docker
# If not: sudo usermod -aG docker $USER && newgrp docker
```

**Open WebUI shows 502 Bad Gateway:**
```bash
docker logs open-webui | tail -50

# Likely cause: Cannot reach backend services (Ollama, Loadout Manager)
# Check they're running: docker ps | grep -E 'ollama|loadout'

# If missing, start inference:
docker compose -f docker/compose.inference.yml up -d
```

---

## GPU & CUDA Issues

### GPU Out of Memory (CUDA OOM)

**Symptom:** `RuntimeError: CUDA out of memory` or service suddenly crashes

**Diagnosis:**
```bash
# Check current GPU memory usage
nvidia-smi

# See what processes are using VRAM
nvidia-smi --query-compute-apps=pid,used_memory,name --format=csv,noheader

# Check loadout state
curl http://localhost:8800/status | jq '.running_services'
```

**Recovery Steps:**

1. **Stop all GPU-using services**
   ```bash
   curl -X POST http://localhost:8800/stop  # Stop all loadout services
   sleep 5
   docker compose -f docker/compose.training.yml down  # Stop training if running
   ```

2. **Verify VRAM is released**
   ```bash
   nvidia-smi --query-gpu=memory.used --format=csv,noheader
   # Should show <1000 MB on all GPUs
   ```

3. **Identify which service caused OOM**
   ```bash
   docker logs <service> | grep -i "cuda\|out of memory" | tail -10
   ```

4. **Fix and restart**

   **If Ollama OOM:** (usually just needs restart)
   ```bash
   docker compose -f docker/compose.inference.yml down ollama
   docker compose -f docker/compose.inference.yml up -d ollama
   sleep 10
   curl -X POST http://localhost:8800/activate/inference-ollama
   ```

   **If vLLM OOM:** Model too large for GPU pair
   ```bash
   # Option A: Use smaller model
   docker compose -f docker/compose.inference.yml up -d --force-recreate
   # (restart with different model via Loadout Manager UI)

   # Option B: Reduce GPU memory utilization
   # Edit docker/compose.inference.yml, change:
   # VLLM_GPU_MEMORY_UTILIZATION=0.9  →  VLLM_GPU_MEMORY_UTILIZATION=0.75
   docker compose -f docker/compose.inference.yml up -d --force-recreate vllm-pair-a
   ```

### NVLink Issues

**Symptom:** vLLM fails to start with `NCCL` errors or poor multi-GPU performance

**Diagnosis:**
```bash
# Check NVLink status
nvidia-smi nvlink --status -i 0

# Check for link errors
nvidia-smi nvlink --get-counters -i 0 | grep -i error

# Test NCCL connectivity
python3 -c "
import torch
from torch.distributed import init_process_group
print(f'GPUs: {torch.cuda.device_count()}')
for i in range(torch.cuda.device_count()):
    print(f'GPU {i}: {torch.cuda.get_device_name(i)}')
"
```

**Common Causes:**

| Symptom | Cause | Fix |
|---------|-------|-----|
| `NCCL operation timed out` | NVLink disabled in BIOS | Check motherboard BIOS: NVLink Settings = Enabled |
| `NCCL backend not available` | NCCL library missing | `apt install libnccl2` (requires NVIDIA repos) |
| `Link 0: Down` | Hardware failure or power issue | Power cycle: unplug PSU for 30s, reconnect |
| `Link CRC errors` | Thermal throttling | Check temperatures: `nvidia-smi` should show <80°C |

**Nuclear option (if NVLink completely broken):**
```bash
# Disable NVLink, use PCIe P2P instead (much slower)
export NCCL_P2P_LEVEL=PIX  # Instead of NVL
docker compose -f docker/compose.inference.yml up -d --force-recreate
```

### GPU Temperature Issues

**Symptom:** `nvidia-smi` shows >85°C or thermal throttling messages

**Diagnosis:**
```bash
# Check temperatures
nvidia-smi --query-gpu=index,temperature.gpu --format=csv,noheader

# Check for throttling
nvidia-smi --query-gpu=index,clocks_throttle_reasons.all --format=csv,noheader

# Check fan speeds (A5500 has active cooling)
nvidia-smi --query-gpu=index,fan.speed --format=csv,noheader
```

**Fixes:**

1. **Stop heavy workloads**
   ```bash
   curl -X POST http://localhost:8800/stop
   ```

2. **Clean GPU heatsinks** (A5500 has passive/active cooling)
   ```bash
   # Check fan is spinning
   # Shut down if overheating persists
   sudo shutdown now
   # After shutdown: check for dust/blockage in cooling paths
   ```

3. **Check ambient temperature**
   - If room is >30°C, add AC or move workstation
   - A5500 designed for <25°C ambient

4. **Resume when cool**
   ```bash
   # Wait 30 minutes with system off
   # Power on and verify temps <70°C idle
   sudo poweroff
   # (power on manually)
   bash scripts/start-all.sh
   ```

---

## Storage Issues

### Disk Full

**Symptom:** `No space left on device` or operations mysteriously fail

**Diagnosis:**
```bash
# Check usage
df -h /data

# Find what's consuming space
du -sh /data/* | sort -rh | head -10

# Check specific categories
du -sh /data/models/
du -sh /data/outputs/
du -sh /data/checkpoints/
```

**Quick Fixes (safe, reversible):**

```bash
# Remove old Docker build caches
docker system prune -f --all

# Clear image generation outputs (safest, most storage)
rm -rf /data/outputs/comfyui/*
rm -rf /data/outputs/inference/*

# Remove old training checkpoints (>30 days)
find /data/checkpoints -name "*.bin" -o -name "*.pt" | xargs -I {} ls -l {} | awk '{print $6, $7, $8, $9}' | awk '$1 < "'$(date -d '30 days ago' +%s)'" {print $4}' | xargs rm
```

**Medium-term Fixes:**

```bash
# Move old models to MinIO for long-term storage
mc cp /data/models/vllm/old-model/ local/models/archive/

# Clean up unused Docker images
docker image prune -a -f

# Delete local LoRA adapters not used in 90 days
find /data/models/comfyui/loras -mtime +90 -delete
```

**Long-term (Hardware):**
- Add external NVMe storage (USB 3.1 Gen 2 adapter)
- Move `/data/models` to secondary SSD
- Set up network storage (NFS from jump box)

### Docker Volume Corruption

**Symptom:** Volume operations fail or PostgreSQL won't start

**Diagnosis:**
```bash
# Check volume integrity
docker volume inspect <volume-name>

# Try to inspect the actual files
docker run --rm -v <volume-name>:/data alpine ls -la /data | head -20

# Check filesystem
docker run --rm -v <volume-name>:/data alpine fsck -n /dev/mapper/docker-...
```

**Fix (if corrupted):**

```bash
# Backup the volume first
docker run --rm -v <volume-name>:/source -v /data/backups:/backup \
  alpine tar czf /backup/corrupted-volume.tar.gz -C /source .

# Delete the volume
docker volume rm <volume-name>

# Recreate it
docker volume create <volume-name>

# Restart the service
docker compose -f docker/compose.*.yml up -d --force-recreate
```

---

## Network & Connectivity Issues

### Services Can't Communicate

**Symptom:** "Connection refused" between containers or services timeout

**Diagnosis:**
```bash
# Check network connectivity
docker network ls

# Verify service is on required networks
docker inspect <container> | grep -A 5 '"Networks"'

# Test connectivity from another container
docker run --net ai-inference --rm alpine ping <service-name>

# Check DNS resolution
docker run --net ai-inference --rm alpine nslookup <service-name>
```

**Fixes:**

1. **Service not on correct network**
   ```bash
   # Check docker-compose file has correct networks:
   grep "networks:" docker/compose.*.yml

   # If missing, add to service:
   services:
     my-service:
       networks:
         - ai-inference
         - ai-storage
   ```

2. **Ports not exposed correctly**
   ```bash
   # Check ports section
   docker port <service-name>

   # If missing, add to compose:
   services:
     my-service:
       ports:
         - "8000:8000"  # host:container
   ```

3. **Firewall blocking (unlikely in Docker network)**
   ```bash
   # Check host firewall
   sudo ufw show added

   # If too restrictive, allow container subnet
   sudo ufw allow from 172.17.0.0/16  # Docker default
   ```

### Can't Reach Services from Host/Jumpbox

**Symptom:** `curl http://localhost:3000` works but `curl http://ai.local/webui` fails

**Diagnosis:**
```bash
# Check if service is listening
docker port <service-name>

# Check if DNS resolves
nslookup ai.local
dig ai.local

# Test direct IP
curl http://10.10.10.2:3000

# Test via Caddy proxy (if set up)
curl -k https://ai.local/webui
```

**Fixes:**

1. **Caddy not configured**
   ```bash
   # Verify Caddy is running
   docker ps | grep caddy

   # Check Caddyfile is mounted
   docker inspect <caddy-container> | grep Caddyfile

   # Reload configuration
   docker exec <caddy-container> caddy reload
   ```

2. **DNS resolution failing**
   ```bash
   # Add to /etc/hosts on jumpbox
   echo "10.10.10.2  ai.local" | sudo tee -a /etc/hosts

   # Or configure DNS server if available
   nslookup ai.local <dns-server>
   ```

3. **Port not exposed on host**
   ```bash
   # If using a reverse proxy, check that port
   netstat -tlnp | grep LISTEN | grep caddy

   # Expose different port if needed
   docker compose -f docker/compose.caddy.yml down
   # Edit: ports: ["80:80", "443:443"]
   docker compose -f docker/compose.caddy.yml up -d
   ```

---

## Agentic Services Issues

### n8n Workflows Not Executing

**Symptom:** Workflows stuck or not triggering

**Diagnosis:**
```bash
# Check n8n logs
docker logs n8n | tail -50

# Check webhook endpoints
curl -i http://localhost:5678/hook/test

# Verify database connectivity
docker exec n8n npm run start
```

**Fixes:**

1. **Database connection issue**
   ```bash
   # Restart with fresh connection
   docker compose -f docker/compose.agentic.yml restart n8n
   ```

2. **Webhook not triggering**
   ```bash
   # Check webhook URL is accessible
   curl -X POST http://localhost:5678/hook/my-webhook-id

   # If external: verify DNS and firewall
   nslookup ai.local
   telnet ai.local 443
   ```

3. **Missing credentials**
   ```bash
   # Verify credentials are configured in n8n UI
   # Open WebUI → Settings → Credentials
   # Re-save any that show errors
   ```

### OpenHands Can't Access Docker

**Symptom:** `docker: permission denied while trying to connect` or container creation fails

**Diagnosis:**
```bash
# Check Docker socket is mounted
docker inspect openhands | grep docker.sock

# Check user permissions
id $USER
groups $USER

# Test Docker access
docker ps
```

**Fix:**
```bash
# Add user to docker group (one-time)
sudo usermod -aG docker $USER

# Apply group changes
newgrp docker

# Or restart the session
# Then restart OpenHands
docker restart openhands
```

---

## Training Pipeline Issues

### Out of VRAM During Training

**Symptom:** Training starts then crashes with CUDA OOM after N steps

**Diagnosis:**
```bash
# Check training logs
docker logs axolotl | tail -100 | grep -i "memory\|cuda\|oom"

# Check VRAM usage during training
nvidia-smi -l 1  # Refresh every 1s
```

**Fixes:**

1. **Reduce batch size**
   ```bash
   # Edit /data/configs/training.yml or training compose file
   # batch_size: 16  →  batch_size: 8
   docker compose -f docker/compose.training.yml up -d --force-recreate
   ```

2. **Reduce gradient accumulation**
   ```bash
   # gradient_accumulation_steps: 4  →  gradient_accumulation_steps: 2
   ```

3. **Use smaller model**
   ```bash
   # model: meta-llama/Llama-2-70b  →  model: meta-llama/Llama-2-7b
   ```

4. **Enable gradient checkpointing** (slower but saves memory)
   ```yaml
   # In training config:
   gradient_checkpointing: true
   ```

### Training Checkpoint Corruption

**Symptom:** Can't resume training or checkpoint won't load

**Diagnosis:**
```bash
# List checkpoints
ls -lh /data/checkpoints/

# Check checkpoint integrity
python3 -c "
import torch
ckpt = torch.load('/data/checkpoints/latest.pt', map_location='cpu')
print('Keys:', list(ckpt.keys())[:5])
"
```

**Fix:**

```bash
# Backup corrupted checkpoint
mv /data/checkpoints/latest.pt /data/checkpoints/latest.pt.corrupted

# Remove it from training config
# model_name_or_path: /data/checkpoints/latest  →  model_name_or_path: original-model

# Restart training from previous checkpoint or base model
docker compose -f docker/compose.training.yml restart axolotl
```

---

## Authentication Issues

### Can't Log into Open WebUI

**Symptom:** "Invalid username/password" or "Database error"

**Diagnosis:**
```bash
# Check Open WebUI logs
docker logs open-webui | tail -50

# Check database
docker exec postgres psql -U webui_user -d open_webui_db -c "SELECT id, email FROM auth_user LIMIT 5;"
```

**Fixes:**

1. **Reset password**
   ```bash
   # Via docker exec
   docker exec open-webui python3 -c "
   from apps.web.models import User
   user = User.find_by_email('your@email.com')
   user.set_password('newpassword')
   user.save()
   print('Password reset')
   "
   ```

2. **Database corrupted**
   ```bash
   # Backup then reset database
   docker compose -f docker/compose.webui.yml down
   docker volume rm open-webui-data
   docker volume create open-webui-data
   docker compose -f docker/compose.webui.yml up -d
   # Create new account (default admin)
   ```

### Authentik Login Not Working

**Symptom:** Login redirects loop or "provider not found"

**Diagnosis:**
```bash
# Check Authentik logs
docker logs authentik-server | tail -50

# Check Authentik UI
curl -i http://localhost:9000/api/v3/tenants/
```

**Fixes:**

1. **Provider not configured**
   ```bash
   # In Authentik UI (http://localhost:9000)
   # Admin → Providers → Create new OAuth2 provider
   # Set redirect URI to: https://ai.local/webui
   # Copy Client ID and Client Secret
   # Then add to application
   ```

2. **Database issue**
   ```bash
   # Restart Authentik PostgreSQL
   docker compose -f docker/compose.auth.yml restart authentik-postgres
   sleep 10
   docker compose -f docker/compose.auth.yml up -d
   ```

---

## Monitoring & Observability

### Prometheus Not Scraping Targets

**Symptom:** Prometheus shows "DOWN" for some targets

**Diagnosis:**
```bash
# Check Prometheus targets
curl http://localhost:9091/api/v1/targets | jq '.data.activeTargets[] | select(.health=="down")'

# Check what it's trying to reach
curl http://localhost:9091/api/v1/query?query=up | jq '.data.result[] | select(.value[1]=="0")'
```

**Fixes:**

1. **Target service not running**
   ```bash
   # Check if service is running
   docker ps | grep <service-name>

   # Start it
   docker compose -f docker/compose.*.yml up -d <service-name>
   ```

2. **Metrics endpoint changed**
   ```bash
   # Update prometheus config (if you have scrape config)
   # Check service port: docker port <service> | grep <expected-port>
   ```

### Grafana Dashboards Blank

**Symptom:** Grafana dashboard shows "No data"

**Diagnosis:**
```bash
# Check Prometheus can be reached from Grafana
docker exec grafana curl -i http://prometheus:9091

# Check if data exists in Prometheus
curl 'http://localhost:9091/api/v1/query?query=node_cpu_seconds_total' | jq '.status'
```

**Fixes:**

1. **Prometheus datasource not configured**
   ```bash
   # In Grafana UI (http://localhost:3001)
   # Admin → Configuration → Data Sources → Prometheus
   # Set URL: http://prometheus:9091
   # Test connection
   ```

2. **Metrics not being scraped**
   ```bash
   # Verify targets in Prometheus
   curl http://localhost:9091/targets
   ```

---

## Quick Recovery Playbook

**When everything breaks:**

```bash
# 1. Don't panic, backup current state
bash scripts/backup.sh volumes

# 2. Identify the problem
bash scripts/healthcheck.sh > /tmp/health.txt
cat /tmp/health.txt

# 3. Stop everything
docker compose -f docker/compose.*.yml down

# 4. Check logs
docker logs <failing-service> > /tmp/logs.txt
cat /tmp/logs.txt

# 5. Try to restart just the failing service
docker compose -f docker/compose.<tier>.yml up -d <service>

# 6. If that fails, restart the entire tier
docker compose -f docker/compose.<tier>.yml down
docker compose -f docker/compose.<tier>.yml up -d

# 7. If that fails, consider restore from backup
# Restore scripts are in /data/backups/

# 8. Last resort: contact support with:
# - /tmp/health.txt
# - /tmp/logs.txt
# - Output of: nvidia-smi, df -h, docker ps -a
```

---

## When to Escalate

Contact support if:
- NVLink status shows persistent errors despite power cycle
- Multiple GPU ECC errors detected
- Disk corruption suspected (fsck errors)
- Network isolation rules blocking legitimate traffic
- Authentik PostgreSQL won't start (likely data corruption)

Provide:
- Output of `bash scripts/healthcheck.sh`
- Last 100 lines of relevant service logs
- Hardware status (nvidia-smi, temp, clocks)
- Disk space status (df -h, du -sh)
