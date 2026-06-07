# Phase 10 — Monitoring & Observability
[← Storage & RAG](09-storage-rag.md) | [Next: Code Generation →](11-code-generation.md)

---

## Objective
Deploy Prometheus + Grafana with DCGM GPU exporter for full hardware observability, nvitop for CLI monitoring, and node exporter for system metrics. Build dashboards covering GPU VRAM, tensor core utilization, NVLink bandwidth, temperatures, and service health.

---

## Step 1 — Docker Compose: Monitoring Stack

```bash
mkdir -p ~/ai-workstation/configs/{prometheus,grafana/provisioning/{datasources,dashboards}}

cat <<'EOF' > ~/ai-workstation/docker/compose.monitoring.yml
version: '3.8'

services:

  # ── Prometheus: metrics collection ────────────────────────────────────────
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    restart: unless-stopped
    ports:
      - "9091:9090"
    volumes:
      - ./configs/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=90d'
      - '--web.enable-lifecycle'

  # ── Grafana: dashboards ────────────────────────────────────────────────────
  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    restart: unless-stopped
    ports:
      - "3001:3000"
    volumes:
      - grafana-data:/var/lib/grafana
      - ./configs/grafana/provisioning:/etc/grafana/provisioning
    environment:
      - GF_SECURITY_ADMIN_USER=admin
      - GF_SECURITY_ADMIN_PASSWORD=changeme
      - GF_SERVER_ROOT_URL=https://ai.local/grafana/
      - GF_SERVER_SERVE_FROM_SUB_PATH=true
      - GF_USERS_ALLOW_SIGN_UP=false
    depends_on:
      - prometheus

  # ── DCGM Exporter: deep GPU metrics ───────────────────────────────────────
  dcgm-exporter:
    image: nvcr.io/nvidia/k8s/dcgm-exporter:3.3.6-3.4.2-ubuntu26.04
    container_name: dcgm-exporter
    restart: unless-stopped
    ports:
      - "9400:9400"
    cap_add:
      - SYS_ADMIN
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    environment:
      - DCGM_EXPORTER_LISTEN=:9400
      - DCGM_EXPORTER_KUBERNETES=false

  # ── Node Exporter: system metrics ─────────────────────────────────────────
  node-exporter:
    image: prom/node-exporter:latest
    container_name: node-exporter
    restart: unless-stopped
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'

  # ── cAdvisor: Docker container metrics ────────────────────────────────────
  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    container_name: cadvisor
    restart: unless-stopped
    ports:
      - "8989:8080"
    volumes:
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
    privileged: true

volumes:
  prometheus-data:
  grafana-data:

EOF
```

---

## Step 2 — Prometheus Configuration

```yaml
# ~/ai-workstation/configs/prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:

  - job_name: 'gpu-dcgm'
    static_configs:
      - targets: ['dcgm-exporter:9400']
    scrape_interval: 5s    # faster for GPU metrics

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

---

## Step 3 — Grafana Datasource Provisioning

```yaml
# ~/ai-workstation/configs/grafana/provisioning/datasources/prometheus.yml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
```

---

## Step 4 — Key DCGM Metrics to Dashboard

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `DCGM_FI_DEV_FB_FREE` | Free framebuffer (VRAM) MB | < 2000 MB |
| `DCGM_FI_DEV_FB_USED` | Used VRAM MB | > 22000 MB (per GPU) |
| `DCGM_FI_DEV_GPU_UTIL` | GPU utilization % | — |
| `DCGM_FI_DEV_SM_CLOCK` | SM clock frequency MHz | — |
| `DCGM_FI_DEV_MEM_CLOCK` | Memory clock MHz | — |
| `DCGM_FI_DEV_GPU_TEMP` | GPU temperature °C | > 83°C |
| `DCGM_FI_DEV_POWER_USAGE` | Power draw watts | > 220W (A5500 TDP) |
| `DCGM_FI_DEV_NVLINK_BANDWIDTH_TOTAL` | NVLink bandwidth GB/s | — |
| `DCGM_FI_DEV_PCIE_TX_THROUGHPUT` | PCIe TX throughput | — |
| `DCGM_FI_DEV_PCIE_RX_THROUGHPUT` | PCIe RX throughput | — |
| `DCGM_FI_DEV_TENSOR_ACTIVE` | Tensor core active % | — |
| `DCGM_FI_DEV_ECC_DBE_VOL_TOTAL` | Double-bit ECC errors | > 0 |

---

## Step 5 — Grafana Dashboard Import

```bash
# Start the monitoring stack
docker compose -f ~/ai-workstation/docker/compose.monitoring.yml up -d

# Access Grafana at http://10.10.10.2:3001
# Login: admin / changeme
```

Import these dashboard IDs from grafana.com:

| Dashboard | ID | Purpose |
|-----------|-----|---------|
| NVIDIA DCGM Exporter | 12239 | GPU metrics (official NVIDIA) |
| Node Exporter Full | 1860 | System CPU/RAM/disk/network |
| Docker Container Stats | 893 | Per-container resource usage |

To import: Dashboards → Import → Enter ID → Load → Select Prometheus datasource → Import

---

## Step 6 — Custom GPU Dashboard Panels

Add these PromQL queries to a custom "AI Workstation" dashboard:

```promql
# VRAM usage per GPU (GB)
DCGM_FI_DEV_FB_USED{} / 1024

# GPU utilization heatmap
DCGM_FI_DEV_GPU_UTIL{}

# NVLink total bandwidth (all GPUs)
sum(DCGM_FI_DEV_NVLINK_BANDWIDTH_TOTAL{})

# Tensor core activity per GPU
DCGM_FI_DEV_TENSOR_ACTIVE{}

# Power draw per GPU
DCGM_FI_DEV_POWER_USAGE{}

# Temperature with threshold line at 83°C
DCGM_FI_DEV_GPU_TEMP{}

# Total free VRAM across all GPUs
sum(DCGM_FI_DEV_FB_FREE{}) / 1024

# Memory bandwidth utilization
DCGM_FI_DEV_MEM_COPY_UTIL{}
```

---

## Step 7 — Alerting Rules

```yaml
# ~/ai-workstation/configs/prometheus/alerts.yml
groups:
  - name: gpu_alerts
    rules:
      - alert: GPUHighTemp
        expr: DCGM_FI_DEV_GPU_TEMP > 83
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "GPU {{ $labels.gpu }} temperature {{ $value }}°C"

      - alert: GPUVRAMCritical
        expr: DCGM_FI_DEV_FB_FREE < 1024
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "GPU {{ $labels.gpu }} VRAM nearly full ({{ $value }}MB free)"

      - alert: GPUECCError
        expr: DCGM_FI_DEV_ECC_DBE_VOL_TOTAL > 0
        for: 0m
        labels:
          severity: critical
        annotations:
          summary: "GPU {{ $labels.gpu }} has double-bit ECC errors — hardware fault"

      - alert: HighSystemTemp
        expr: node_hwmon_temp_celsius{chip=~".*coretemp.*"} > 85
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "CPU temperature {{ $value }}°C"
```

Add to prometheus.yml:
```yaml
rule_files:
  - /etc/prometheus/alerts.yml
```

---

## Step 8 — CLI Monitoring Tools

```bash
# nvitop: rich TUI GPU monitor (install on host)
pip3 install nvitop
nvitop    # full TUI
nvitop -m full   # all metrics

# GPU monitoring one-liner
watch -n 1 nvidia-smi

# DCGM continuous monitoring
dcgmi dmon -e 203,204,1001,1002,1003,1004 -d 1000
# 203=SM util, 204=mem util, 1001=FB used, 1002=FB free, 1003=temp, 1004=power

# NVLink stats live
nvidia-smi nvlink --get-counters -i 0
nvidia-smi nvlink --get-counters -i 1
```

---

## Step 9 — Grafana Alerting to n8n

```bash
# In Grafana: Alerting → Contact Points → Add
# Type: Webhook
# URL: http://10.10.10.2:5678/webhook/grafana-alerts
# Method: POST

# In n8n: create webhook trigger at /grafana-alerts
# Parse alert payload → send notification (email/Slack/SMS/etc.)
```

---

## Validation Checklist

- [ ] Prometheus accessible at `:9091`, scraping all targets (Status → Targets)
- [ ] DCGM exporter scrape succeeds — GPU metrics visible in Prometheus
- [ ] Node exporter scrape succeeds — CPU/RAM/disk metrics visible
- [ ] Grafana accessible at `:3001`, Prometheus datasource connected
- [ ] NVIDIA DCGM dashboard (ID 12239) imported and showing all 4 GPUs
- [ ] Node Exporter Full dashboard (ID 1860) showing system metrics
- [ ] Alert rules loaded in Prometheus (`/rules`)
- [ ] Temperature alert fires if GPU artificially loaded
- [ ] nvitop running cleanly on host

---

## Notes
- DCGM exporter requires `SYS_ADMIN` capability and direct GPU access — it runs privileged
- `DCGM_FI_DEV_TENSOR_ACTIVE` is the most useful metric during inference — it tells you if the model is actually utilizing the hardware efficiently
- ECC errors on an A5500 are serious — if you see any double-bit errors, stop workloads and investigate immediately
- Grafana's `GF_SERVER_SERVE_FROM_SUB_PATH=true` is required for the Caddy reverse proxy path routing to work correctly
