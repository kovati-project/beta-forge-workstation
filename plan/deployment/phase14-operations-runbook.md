# Phase 14 — Operations Runbook

**Purpose:** Auto-start on boot, scheduled backups, recurring health checks, operational tooling  
**No new services deployed.** This phase installs systemd units and validates the full stack.  
**Scripts:** `setup-systemd-service.sh`, `start-all.sh`, `healthcheck.sh`, `backup.sh`  
**Static unit:** `configs/systemd/ai-workstation.service`

---

## Prerequisites

- [ ] All previous phases deployed (03–13)
- [ ] Files synced to workstation: `scp -r scripts configs kasemo@10.10.10.2:~/ai-workstation/`
- [ ] Scripts are executable on workstation

Make scripts executable:
```bash
ssh kasemo@10.10.10.2 "chmod +x ~/ai-workstation/scripts/*.sh ~/ai-workstation/scripts/*.py"
```

---

## Step 1 — Install Systemd Units

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && sudo bash scripts/setup-systemd-service.sh"
```

The script installs 5 units into `/etc/systemd/system/`:

| Unit | Type | Purpose |
| ---- | ---- | ------- |
| `ai-workstation.service` | oneshot + RemainAfterExit | Starts all services on boot via `start-all.sh` |
| `ai-workstation-backup.service` | oneshot | Runs `backup.sh` |
| `ai-workstation-backup.timer` | timer | Fires backup daily at 02:00 |
| `ai-workstation-healthcheck.service` | oneshot | Runs `healthcheck.sh` |
| `ai-workstation-healthcheck.timer` | timer | Fires 5min after boot, then every 6h |

The service unit uses literal paths (`/home/kasemo/ai-workstation/`) — no shell variable expansion.

**ExecStop** shuts down all compose stacks:
```
compose.webui.yml, compose.agentic.yml, compose.codegen.yml,
compose.voice.yml, compose.training.yml, compose.inference.yml,
compose.loadout.yml, compose.auth.yml, compose.monitoring.yml, compose.storage.yml
```

---

## Step 2 — Enable Auto-Start on Boot

```bash
ssh kasemo@10.10.10.2 "sudo systemctl enable ai-workstation"
```

Verify it's enabled:
```bash
ssh kasemo@10.10.10.2 "sudo systemctl is-enabled ai-workstation"
# Expected: enabled
```

Enable the timers:
```bash
ssh kasemo@10.10.10.2 "sudo systemctl enable --now ai-workstation-backup.timer && \
  sudo systemctl enable --now ai-workstation-healthcheck.timer"
```

---

## Step 3 — Test Manual Startup

Stop all running services first, then test the service:
```bash
# Stop all services (optional — skip if testing on a fresh boot)
ssh kasemo@10.10.10.2 "sudo systemctl stop ai-workstation"

# Start via systemd
ssh kasemo@10.10.10.2 "sudo systemctl start ai-workstation"

# Follow the startup log
ssh kasemo@10.10.10.2 "journalctl -u ai-workstation -f"
```

`start-all.sh` starts services in dependency order:
1. Storage (MinIO, Qdrant, Postgres)
2. Monitoring (Prometheus, Grafana, DCGM, Node Exporter, cAdvisor)
3. Authentik
4. Loadout Manager → waits for `:8800/health`
5. Activates `inference-small` profile
6. Inference (Ollama, vLLM, ComfyUI)
7. Training services (if `compose.training.yml` present — optional)
8. Web UI (Open WebUI, SearXNG) + Agentic (n8n, MCP servers) + OpenHands
9. Voice (Whisper, Piper)

Full cold-start takes approximately 2–4 minutes. The timeout is `TimeoutStartSec=600`.

---

## Step 4 — Test Health Check

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/healthcheck.sh"
```

The script checks ~30 endpoints and prints a summary like:
```
✓ All services healthy (28/28 running)
```

It also prints GPU status (temperature, utilisation, memory), active Loadout profile, and `/data` disk usage.

Health check results are written to the systemd journal:
```bash
ssh kasemo@10.10.10.2 "journalctl -u ai-workstation-healthcheck.service --since '1 hour ago'"
```

---

## Step 5 — Test Backup

Run a manual backup to verify it works before the timer fires:
```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/backup.sh"
```

Backups are written to `/data/backups/YYYYMMDD-HHMMSS/`. Each run creates a timestamped subdirectory containing:
- Docker volume archives (`.tar.gz`) for persistent data volumes
- Config directory snapshots
- Metadata file with timestamps and sizes

Verify:
```bash
ssh kasemo@10.10.10.2 "ls -lh /data/backups/"
```

**Backup to MinIO** (after Phase 09 MinIO is running):
```bash
ssh kasemo@10.10.10.2 "mc cp --recursive /data/backups/ local/backups/"
```

---

## Step 6 — Verify Timer Schedules

```bash
ssh kasemo@10.10.10.2 "systemctl list-timers --all | grep ai-workstation"
```

Expected:
```
Sat 2026-06-06 02:00:00 UTC  ...  ai-workstation-backup.timer
Thu 2026-06-05 18:30:00 UTC  ...  ai-workstation-healthcheck.timer
```

---

## Step 7 — Full System Validate

Run all phase validate scripts to confirm nothing regressed:
```bash
ssh kasemo@10.10.10.2 "for phase in 03 04 05 06 07 08 09 10 11 12 13; do
  echo '=== Phase '$phase' ==='
  cd ~/ai-workstation && bash scripts/validate-phase${phase}.sh 2>&1 | tail -5
done"
```

---

## Quick Reference

```bash
# Start / stop all services
ssh kasemo@10.10.10.2 "sudo systemctl start ai-workstation"
ssh kasemo@10.10.10.2 "sudo systemctl stop ai-workstation"

# Service status
ssh kasemo@10.10.10.2 "sudo systemctl status ai-workstation"

# View startup log
ssh kasemo@10.10.10.2 "journalctl -u ai-workstation -b --no-pager"

# Run health check now
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/healthcheck.sh"

# Run backup now
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/backup.sh"

# Run backup for just configs (fast)
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/backup.sh configs"

# Timer status
ssh kasemo@10.10.10.2 "systemctl list-timers --all | grep ai-workstation"

# View backup journal
ssh kasemo@10.10.10.2 "journalctl -u ai-workstation-backup.service --since today"

# Reload systemd after unit file changes
ssh kasemo@10.10.10.2 "sudo systemctl daemon-reload"
```

---

## Systemd Unit Reference

The static reference unit is at `configs/systemd/ai-workstation.service`. The `setup-systemd-service.sh` generator produces the same unit with paths set at install time. Both should be kept in sync.

To install the static unit directly (alternative to the generator script):
```bash
scp configs/systemd/ai-workstation.service kasemo@10.10.10.2:/tmp/
ssh kasemo@10.10.10.2 "sudo cp /tmp/ai-workstation.service /etc/systemd/system/ && \
  sudo systemctl daemon-reload && \
  sudo systemctl enable ai-workstation"
```

---

## Troubleshooting

| Symptom | Check |
| ------- | ----- |
| `systemctl start` hangs > 10min | `start-all.sh` blocked on a health poll — check `journalctl -u ai-workstation -f` for which step |
| Loadout Manager health check fails | Container not running — `docker ps \| grep loadout`; check `docker logs loadout-manager` |
| `inference-small` profile activation fails | Loadout Manager started but profile not configured — `curl http://localhost:8800/profiles` to list available |
| `start-all.sh` exits with "Code generation services failed" | compose.codegen.yml error is non-fatal (`\|\| echo "…"`) — check `docker logs openhands` |
| Backup script fails | `/data/backups` not writable — `sudo chown kasemo:kasemo /data/backups` |
| Timers not firing | `systemctl list-timers` shows timers but `ACTIVATES` column empty — `sudo systemctl daemon-reload && sudo systemctl restart ai-workstation-backup.timer` |
| `$USER` not expanded in unit | Correct by design — systemd units use literal `kasemo`; `$USER` is not expanded in ExecStart/ExecStop |
