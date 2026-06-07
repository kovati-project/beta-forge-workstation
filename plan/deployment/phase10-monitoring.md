# Phase 10 — Monitoring & Observability

**Services:** Prometheus (`:9091`), Grafana (`:3001`), DCGM Exporter (`:9400`), Node Exporter (`:9100`), cAdvisor (`:8989`)  
**Compose file:** `docker/compose.monitoring.yml`  
**Scripts:** `deploy-phase10.sh`, `validate-phase10.sh`

---

## Prerequisites

- [ ] Phase 03 deployed — Ollama/vLLM running (Prometheus scrapes inference endpoints)
- [ ] Phase 05 deployed — Open WebUI running (scrapes container metrics)
- [ ] Phase 06 deployed — Loadout Manager running at `:8800` (GPU orchestrator metrics; optional but recommended)
- [ ] Config files exist on workstation: `configs/prometheus/prometheus.yml`, `configs/prometheus/alerts.yml`, `configs/grafana/provisioning/`

---

## Step 1 — Change Grafana Admin Password

The compose file ships with `GF_SECURITY_ADMIN_PASSWORD=changeme`. Update before deploying:

```bash
ssh kasemo@10.10.10.2 "nano ~/ai-workstation/docker/compose.monitoring.yml"
```

Replace `changeme` with a strong password. Record it — you'll need it for dashboard logins and Prometheus datasource credentials.

---

## Step 2 — Deploy

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/deploy-phase10.sh"
```

The script:
1. Creates `configs/prometheus/` and `configs/grafana/provisioning/` directories
2. Starts all 5 monitoring containers
3. Waits up to 30s for Prometheus to become healthy
4. Reports the status of each service

Expected output includes `✓ Prometheus running on :9091` and `✓ Grafana ready`.

---

## Step 3 — Verify Endpoints

```bash
# Prometheus health
ssh kasemo@10.10.10.2 "curl -sf http://localhost:9091/-/healthy && echo OK"

# DCGM Exporter — should return hundreds of lines of GPU metrics
ssh kasemo@10.10.10.2 "curl -s http://localhost:9400/metrics | head -20"

# Node Exporter — system metrics
ssh kasemo@10.10.10.2 "curl -s http://localhost:9100/metrics | head -5"

# cAdvisor — container metrics
ssh kasemo@10.10.10.2 "curl -sf http://localhost:8989/api/v1.3/machine | python3 -m json.tool | head -10"
```

---

## Step 4 — Log Into Grafana

Open `http://10.10.10.2:3001` in a browser.

Login: `admin` / (password from Step 1)

Grafana is pre-provisioned with Prometheus as the default datasource. Verify: **Connections → Data sources → Prometheus → Test**.

---

## Step 5 — Import Official Dashboards

In Grafana: **Dashboards → Import → Enter ID**

| Dashboard ID | Name | What it shows |
| ------------ | ---- | -------------- |
| 12239 | NVIDIA DCGM Exporter Dashboard | Per-GPU utilisation, memory, temperature, NVLink bandwidth |
| 1860 | Node Exporter Full | CPU, RAM, disk I/O, network per host |
| 893 | Docker Container Stats | Per-container CPU, memory, network via cAdvisor |

For each import: set the Prometheus datasource to the provisioned `Prometheus` instance.

---

## Step 6 — Verify Prometheus Scrape Targets

In Prometheus: **Status → Targets** (or `http://10.10.10.2:9091/targets`)

All targets should show state `UP`. Expected targets:
- `prometheus:9090` (self-scrape)
- `dcgm-exporter:9400` (DCGM GPU metrics)
- `node-exporter:9100` (host system)
- `cadvisor:8080` (Docker containers)
- `ollama:11434` (if Phase 03 running)
- `loadout-manager:8800` (if Phase 06 running)

If any show `DOWN`, check `docker logs <container>` for that service.

---

## Step 7 — Set Up GPU Alert Thresholds (Optional)

The alert rules in `configs/prometheus/alerts.yml` fire when:
- GPU temperature exceeds 85°C
- GPU memory usage exceeds 90%
- Any monitored service is down for >2m

To add email/Slack alert channels, configure an Alertmanager instance (not included in Phase 10 — add to `compose.monitoring.yml` when needed).

---

## Step 8 — Validate

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase10.sh"
```

Expected: all automated checks pass. Manual checks include Grafana login and dashboard load.

---

## Quick Reference

```bash
# Prometheus — check all targets
ssh kasemo@10.10.10.2 "curl -s http://localhost:9091/api/v1/targets | python3 -m json.tool | grep -E '(job|health)'"

# DCGM — live GPU metrics snapshot
ssh kasemo@10.10.10.2 "curl -s http://localhost:9400/metrics | grep DCGM_FI_DEV_GPU_UTIL"

# Reload Prometheus config without restart
ssh kasemo@10.10.10.2 "curl -sX POST http://localhost:9091/-/reload"

# Restart just Grafana (e.g. after config change)
ssh kasemo@10.10.10.2 "docker compose -f ~/ai-workstation/docker/compose.monitoring.yml restart grafana"

# View DCGM logs (common issue: SYS_ADMIN capability missing)
ssh kasemo@10.10.10.2 "docker logs dcgm-exporter --tail 50"
```

---

## Troubleshooting

| Symptom | Check |
| ------- | ----- |
| DCGM Exporter exits immediately | Container needs `cap_add: [SYS_ADMIN]` — confirm it's in compose.monitoring.yml |
| Grafana blank after login | Provisioning path wrong — must be `../configs/grafana/provisioning` (not `./configs/`) |
| Prometheus target shows `DOWN` | Check if scraped container is running: `docker ps \| grep <name>` |
| DCGM shows `no metrics` for GPUs | nvidia-ctk runtime not configured: `nvidia-ctk runtime configure --runtime=docker` then `sudo systemctl restart docker` |
| Grafana shows no data | Prometheus datasource URL must be `http://prometheus:9090` (container name, not localhost) — auto-provisioned via `../configs/grafana/provisioning/datasources/` |
