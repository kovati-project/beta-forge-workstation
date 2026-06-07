# GHC Task: Phase 10 — Monitoring & Observability
**Brief ID:** P10-001  
**Source doc:** `/plan/steps/10-monitoring.md`  
**Write feedback to:** `/plan/ghc-feedback/phase10-monitoring.md`

---

## Context

Phases 01–09 are complete. The workstation has:
- Ubuntu 26.04 LTS, driver 595.71.05, CUDA 13.3
- 4× RTX A5500 with NVLink pairs (GPU0↔GPU3, GPU1↔GPU2)
- All inference, training, storage, and agentic services deployed

**Phase 01 (Caddy reverse proxy) is tabled.** There is no `https://ai.local` proxy. Grafana and Prometheus are accessed by direct IP. Any URL referencing `https://ai.local` must use `http://10.10.10.2:<port>`.

This phase deploys Prometheus, Grafana, DCGM GPU exporter, Node Exporter, and cAdvisor for full hardware and service observability.

---

## Scope

Create:
1. **`docker/compose.monitoring.yml`** — Prometheus, Grafana, DCGM Exporter, Node Exporter, cAdvisor
2. **`configs/prometheus/prometheus.yml`** — scrape config for all targets
3. **`configs/prometheus/alerts.yml`** — GPU temp, VRAM, ECC, and CPU temperature alert rules
4. **`configs/grafana/provisioning/datasources/prometheus.yml`** — auto-provision Prometheus datasource
5. **`scripts/deploy-phase10.sh`** — create config dirs, start stack, verify services
6. **`scripts/validate-phase10.sh`** — endpoint checks and scrape target verification; exits non-zero on failure

**Not in scope:** Grafana dashboard JSON imports (done in browser), Grafana alerting contact point setup (done in browser), Langfuse integration (already in Phase 09).

---

## Step 1 — `docker/compose.monitoring.yml`

**prometheus service:**
- Image: `prom/prometheus:latest`
- Port: `9091:9090`
- `restart: unless-stopped`
- Volumes: `../configs/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml`, `prometheus-data:/prometheus`
- Command flags: `--config.file=...`, `--storage.tsdb.path=/prometheus`, `--storage.tsdb.retention.time=90d`, `--web.enable-lifecycle`

**grafana service:**
- Image: `grafana/grafana:latest`
- Port: `3001:3000`
- `restart: unless-stopped`
- Volumes: `grafana-data:/var/lib/grafana`, `../configs/grafana/provisioning:/etc/grafana/provisioning`
- Environment:
  - `GF_SECURITY_ADMIN_USER=admin`
  - `GF_SECURITY_ADMIN_PASSWORD=changeme` ← placeholder; add comment to change before use
  - `GF_SERVER_ROOT_URL=http://10.10.10.2:3001/` ← **must use direct IP**, not `https://ai.local/grafana/` (Phase 01 tabled)
  - `GF_SERVER_SERVE_FROM_SUB_PATH=false` ← **must be false** without a reverse proxy sub-path; setting true without a proxy causes broken asset URLs
  - `GF_USERS_ALLOW_SIGN_UP=false`
- `depends_on: [prometheus]`

**dcgm-exporter service:**
- Image: `nvcr.io/nvidia/k8s/dcgm-exporter:3.3.6-3.4.2-ubuntu22.04` ← use `ubuntu22.04` tag; no `ubuntu26.04` variant exists on NVCR
- Port: `9400:9400`
- `restart: unless-stopped`
- `cap_add: [SYS_ADMIN]`
- GPU reservation: `driver: nvidia`, `count: all`, `capabilities: [gpu]`
- Environment: `DCGM_EXPORTER_LISTEN=:9400`, `DCGM_EXPORTER_KUBERNETES=false`

**node-exporter service:**
- Image: `prom/node-exporter:latest`
- Port: `9100:9100`
- `restart: unless-stopped`
- Volumes: `/proc:/host/proc:ro`, `/sys:/host/sys:ro`, `/:/rootfs:ro`
- Command: `--path.procfs=/host/proc`, `--path.sysfs=/host/sys`, `--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)`

**cadvisor service:**
- Image: `gcr.io/cadvisor/cadvisor:latest`
- Port: `8989:8080`
- `restart: unless-stopped`
- `privileged: true`
- Volumes: `/:/rootfs:ro`, `/var/run:/var/run:ro`, `/sys:/sys:ro`, `/var/lib/docker/:/var/lib/docker:ro`

**Volumes:** `prometheus-data`, `grafana-data`  
**Do not include `version: '3.8'`** — deprecated.

**Volume mount paths** — the compose file lives in `docker/`, so paths relative to it must use `../` to reach the repo root: `../configs/prometheus/prometheus.yml`, `../configs/grafana/provisioning`.

---

## Step 2 — `configs/prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - /etc/prometheus/alerts.yml

scrape_configs:

  - job_name: 'gpu-dcgm'
    static_configs:
      - targets: ['dcgm-exporter:9400']
    scrape_interval: 5s

  - job_name: 'node'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'docker-containers'
    static_configs:
      - targets: ['cadvisor:8080']

  - job_name: 'loadout-manager'
    static_configs:
      - targets: ['10.10.10.2:8800']
    metrics_path: /health
    scrape_interval: 10s

  - job_name: 'ollama'
    static_configs:
      - targets: ['10.10.10.2:11434']
    metrics_path: /metrics
    scrape_interval: 15s

  - job_name: 'vllm-pair-a'
    static_configs:
      - targets: ['10.10.10.2:8000']
    metrics_path: /metrics
    scrape_interval: 15s
```

Note: `rule_files` must reference the alerts file by its **container path** (`/etc/prometheus/alerts.yml`). Add a second volume mount for it: `../configs/prometheus/alerts.yml:/etc/prometheus/alerts.yml`.

---

## Step 3 — `configs/prometheus/alerts.yml`

Use the exact alert rules from the source doc (GPUHighTemp, GPUVRAMCritical, GPUECCError, HighSystemTemp). Threshold values:
- `GPUHighTemp`: `DCGM_FI_DEV_GPU_TEMP > 83`, for 2m
- `GPUVRAMCritical`: `DCGM_FI_DEV_FB_FREE < 1024`, for 1m
- `GPUECCError`: `DCGM_FI_DEV_ECC_DBE_VOL_TOTAL > 0`, for 0m (fires immediately)
- `HighSystemTemp`: `node_hwmon_temp_celsius{chip=~".*coretemp.*"} > 85`, for 5m

---

## Step 4 — `configs/grafana/provisioning/datasources/prometheus.yml`

```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
```

This file is mounted into the container and auto-provisions the Prometheus datasource on first start. Grafana discovers it without manual UI steps.

---

## Step 5 — `scripts/deploy-phase10.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Phase 10: Monitoring & Observability ==="

# Create config directories
mkdir -p "$REPO_ROOT/configs/prometheus"
mkdir -p "$REPO_ROOT/configs/grafana/provisioning/datasources"
mkdir -p "$REPO_ROOT/configs/grafana/provisioning/dashboards"

# Start stack
docker compose -f "$REPO_ROOT/docker/compose.monitoring.yml" up -d

# Wait for Prometheus
echo "Waiting for Prometheus..."
for i in $(seq 1 15); do
    if curl -sf http://localhost:9091/-/healthy >/dev/null 2>&1; then
        echo "Prometheus ready"
        break
    fi
    sleep 3
done

# Wait for Grafana
echo "Waiting for Grafana..."
for i in $(seq 1 20); do
    if curl -sf http://localhost:3001/api/health >/dev/null 2>&1; then
        echo "Grafana ready"
        break
    fi
    sleep 3
done

echo ""
echo "Services running:"
echo "  Prometheus   → http://10.10.10.2:9091"
echo "  Grafana      → http://10.10.10.2:3001  (admin / changeme)"
echo "  DCGM         → http://10.10.10.2:9400/metrics"
echo "  Node Export  → http://10.10.10.2:9100/metrics"
echo "  cAdvisor     → http://10.10.10.2:8989"
echo ""
echo "Grafana dashboards to import (Dashboards → Import → ID):"
echo "  12239 — NVIDIA DCGM Exporter"
echo "   1860 — Node Exporter Full"
echo "    893 — Docker Container Stats"
```

---

## Step 6 — `scripts/validate-phase10.sh`

Automated checks:

| Check | Command |
|-------|---------|
| Prometheus running | `docker ps --filter name=prometheus --filter status=running \| grep -q prometheus` |
| Prometheus healthy | `curl -sf http://localhost:9091/-/healthy` |
| Grafana running | `docker ps --filter name=grafana --filter status=running \| grep -q grafana` |
| Grafana healthy | `curl -sf http://localhost:3001/api/health` |
| DCGM exporter running | `docker ps --filter name=dcgm-exporter --filter status=running \| grep -q dcgm` |
| DCGM metrics exposed | `curl -sf http://localhost:9400/metrics \| grep -q DCGM_FI_DEV_GPU_TEMP` |
| Node exporter running | `docker ps --filter name=node-exporter --filter status=running \| grep -q node-exporter` |
| Node metrics exposed | `curl -sf http://localhost:9100/metrics \| grep -q node_cpu_seconds_total` |
| cAdvisor running | `docker ps --filter name=cadvisor --filter status=running \| grep -q cadvisor` |
| Prometheus config valid | `curl -sf http://localhost:9091/api/v1/status/config \| grep -q scrape_configs` |
| Alert rules loaded | `curl -sf http://localhost:9091/api/v1/rules \| grep -q GPUHighTemp` |
| Grafana password not default | `docker inspect grafana \| grep GF_SECURITY_ADMIN_PASSWORD \| grep -v 'changeme'` |
| Datasource config exists | `test -f configs/grafana/provisioning/datasources/prometheus.yml` |
| Prometheus config exists | `test -f configs/prometheus/prometheus.yml` |
| Alerts config exists | `test -f configs/prometheus/alerts.yml` |

Manual checks (warn only):
- Prometheus Status → Targets: all targets show UP
- Grafana: Prometheus datasource shows green "Data source is working"
- DCGM dashboard (ID 12239) shows all 4 GPUs
- Alert rules visible at `http://10.10.10.2:9091/rules`

Use the same `check()` / `warn()` pattern as prior validate scripts. Exit with `$FAIL` count.

---

## Constraints

1. **`GF_SERVER_ROOT_URL=http://10.10.10.2:3001/`** — Phase 01 (Caddy) is tabled. The source doc sets `https://ai.local/grafana/` which is wrong. Without a reverse proxy, setting a sub-path URL breaks Grafana's asset loading.
2. **`GF_SERVER_SERVE_FROM_SUB_PATH=false`** — source doc sets `true`, which only applies when Grafana is behind a proxy at a sub-path. Without the proxy, this breaks the UI.
3. **DCGM image tag** — use `ubuntu22.04` not `ubuntu26.04`. NVCR does not publish a `ubuntu26.04` tagged variant; the `ubuntu22.04` container runs fine on Ubuntu 26.04 hosts with driver 595.
4. **Volume mount paths** — compose file is in `docker/`, so all config mounts use `../` prefix: `../configs/prometheus/prometheus.yml`, `../configs/grafana/provisioning`. Do not use `./configs/...`.
5. **`rule_files` path in prometheus.yml** — must be the container-internal path `/etc/prometheus/alerts.yml`, not the host path. The alerts file needs its own volume mount line in the compose service.
6. **Prometheus scrapes cAdvisor at `cadvisor:8080`** (internal port), not `cadvisor:8989` (host port). Docker service discovery uses the container's internal port.
7. **Grafana admin password** — `changeme` is a placeholder. The validate script must check it has been changed.

---

## Feedback Template

Write to `/plan/ghc-feedback/phase10-monitoring.md`:

```markdown
# GHC Feedback: Phase 10 — Monitoring & Observability
**Brief:** P10-001 | **Status:** Complete / Partial / Blocked

## Files Created
- [ ] docker/compose.monitoring.yml
- [ ] configs/prometheus/prometheus.yml
- [ ] configs/prometheus/alerts.yml
- [ ] configs/grafana/provisioning/datasources/prometheus.yml
- [ ] scripts/deploy-phase10.sh
- [ ] scripts/validate-phase10.sh

## Deviations from Brief
| Item | Plan | Actual | Reason |

## Validation Results
[paste validate-phase10.sh output]

## Notes
```
