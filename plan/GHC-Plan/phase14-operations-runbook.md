# GHC Task: Phase 14 — Operations Runbook
**Brief ID:** P14-001  
**Source doc:** `/plan/steps/14-operations-runbook.md`  
**Write feedback to:** `/plan/ghc-feedback/phase14-operations-runbook.md`

---

## Context

Phases 01–13 are complete. The full stack is deployed. This phase creates the operational scripts that tie everything together: a full-stack startup script, a health check dashboard, a backup script, and a systemd service for auto-start on boot. These are day-to-day operational tools, not one-time setup scripts.

**Phase 01 (Caddy) is still tabled.** The `start-all.sh` source doc prints `Open WebUI: https://ai.local` — change to `http://10.10.10.2:3000`.

**Systemd variable expansion:** The source doc uses `$USER` and `$HOME` in the systemd unit file. Systemd does not expand these shell variables in `ExecStart`/`ExecStop` lines. Use literal values: `/home/kasemo` and `kasemo`.

---

## Scope

Create:
1. **`scripts/start-all.sh`** — ordered full-stack startup; activates default inference profile
2. **`scripts/healthcheck.sh`** — per-service HTTP health checks + GPU status + active loadout
3. **`scripts/backup.sh`** — snapshot all Docker volumes, configs, LoRAs; sync to MinIO; prune old
4. **`configs/systemd/ai-workstation.service`** — systemd unit for auto-start on boot
5. **`scripts/validate-phase14.sh`** — verifies all operational scripts exist, are executable, and pass a dry-run check

**Not in scope:** Automated restore procedures (document in comments), SIEM log forwarding (Phase 13), Prometheus alerting wiring to n8n (Phase 08 workflow).

---

## Step 1 — `scripts/start-all.sh`

Use the source doc implementation with these fixes:
- Replace `echo "Open WebUI: https://ai.local"` with `echo "Open WebUI: http://10.10.10.2:3000"`
- The script should also start `compose.training.yml` for always-on training services (Label Studio, JupyterLab) — add after step 6
- Add `compose.monitoring.yml` to the stop comment at the bottom

```bash
#!/usr/bin/env bash
set -euo pipefail

COMPOSE="docker compose"
BASE="$HOME/ai-workstation/docker"

echo "=== Starting AI Workstation ==="

# 1. Storage (everything depends on this)
echo "[1/7] Storage stack..."
$COMPOSE -f "$BASE/compose.storage.yml" up -d
sleep 5

# 2. Monitoring (start early to catch startup metrics)
echo "[2/7] Monitoring stack..."
$COMPOSE -f "$BASE/compose.monitoring.yml" up -d
sleep 3

# 3. Auth (before any user-facing services)
echo "[3/7] Auth (Authentik)..."
$COMPOSE -f "$BASE/compose.auth.yml" \
    --env-file "$HOME/ai-workstation/configs/authentik/.env" up -d
sleep 5

# 4. Loadout manager
echo "[4/7] Loadout manager..."
$COMPOSE -f "$BASE/compose.loadout.yml" up -d
sleep 3

# 5. Default inference profile
echo "[5/7] Activating inference-small profile..."
curl -sX POST http://localhost:8800/activate/inference-small
sleep 10

# 6. UI and agentic services
echo "[6/7] UI and agentic services..."
$COMPOSE -f "$BASE/compose.webui.yml" up -d
$COMPOSE -f "$BASE/compose.agentic.yml" up -d \
    n8n mcp-filesystem mcp-fetch mcp-browser
$COMPOSE -f "$BASE/compose.voice.yml" up -d

# 7. Always-on training services (no GPU)
echo "[7/7] Training support services..."
$COMPOSE -f "$BASE/compose.training.yml" up -d \
    label-studio jupyterlab

echo ""
echo "=== Startup complete ==="
echo "Open WebUI:      http://10.10.10.2:3000"
echo "Loadout Manager: http://10.10.10.2:8800"
echo "Grafana:         http://10.10.10.2:3001"
echo ""
echo "Run healthcheck: bash ~/ai-workstation/scripts/healthcheck.sh"
```

---

## Step 2 — `scripts/healthcheck.sh`

Use the exact source doc implementation. Two additions:
- Add `Grafana` and `Prometheus` health checks (already in source)
- Add a note comment: `# Some services (vLLM, ComfyUI) may not be running depending on active loadout — failures are expected if profile is not active`

The `check()` function uses HTTP status code comparison — keep this pattern (it's different from the `check()` in validate scripts which uses `eval`).

---

## Step 3 — `scripts/backup.sh`

Use the exact source doc implementation. Two fixes:

1. **MinIO `mc` alias assumed configured.** Add a guard at the top:
```bash
if ! mc alias list | grep -q '^local'; then
    echo "ERROR: MinIO 'local' alias not configured. Run: mc alias set local http://localhost:9000 admin <password>"
    exit 1
fi
```

2. **Replace `$USER` with `kasemo`** in paths so the script works when run via systemd or cron (where `$USER` may not be set). Use `SCRIPT_USER=kasemo` at the top and substitute.

The crontab line from the source doc goes in a comment at the bottom of the script:
```bash
# To schedule: run `crontab -e` and add:
# 0 2 * * * /home/kasemo/ai-workstation/scripts/backup.sh >> /var/log/ai-backup.log 2>&1
```

---

## Step 4 — `configs/systemd/ai-workstation.service`

Use the source doc structure with these fixes:
- Replace `$USER` with `kasemo` (literal)
- Replace `$HOME` with `/home/kasemo` (literal — systemd does not expand shell vars in `ExecStart`)
- `ExecStop` must be a single command, not a compound shell expression — use `ExecStop=/bin/bash -c '...'` syntax or split into multiple `ExecStop=` lines

```ini
[Unit]
Description=AI Workstation Services
After=docker.service network-online.target
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=kasemo
WorkingDirectory=/home/kasemo/ai-workstation
ExecStart=/home/kasemo/ai-workstation/scripts/start-all.sh
ExecStop=/bin/bash -c 'docker compose \
    -f /home/kasemo/ai-workstation/docker/compose.webui.yml \
    -f /home/kasemo/ai-workstation/docker/compose.agentic.yml \
    -f /home/kasem/ai-workstation/docker/compose.voice.yml \
    -f /home/kasemo/ai-workstation/docker/compose.storage.yml \
    -f /home/kasemo/ai-workstation/docker/compose.monitoring.yml \
    -f /home/kasemo/ai-workstation/docker/compose.training.yml \
    down'
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Note: `ExecStop` paths use `/home/kasemo` not `/home/kasem` — fix the typo in the source doc.

Also create a brief install note as a comment at the top of the file:
```
# Install: sudo cp this file /etc/systemd/system/ai-workstation.service
#          sudo systemctl daemon-reload && sudo systemctl enable ai-workstation
```

---

## Step 5 — `scripts/validate-phase14.sh`

Automated checks:

| Check | Command |
|-------|---------|
| start-all.sh exists | `test -f scripts/start-all.sh` |
| start-all.sh executable | `test -x scripts/start-all.sh` |
| healthcheck.sh exists | `test -f scripts/healthcheck.sh` |
| healthcheck.sh executable | `test -x scripts/healthcheck.sh` |
| backup.sh exists | `test -f scripts/backup.sh` |
| backup.sh executable | `test -x scripts/backup.sh` |
| systemd unit exists | `test -f configs/systemd/ai-workstation.service` |
| systemd unit valid syntax | `systemd-analyze verify configs/systemd/ai-workstation.service 2>/dev/null \|\| true` |
| start-all.sh no ai.local refs | `! grep -q 'ai.local' scripts/start-all.sh` |
| backup dirs exist | `test -d /data/backups` |
| crontab comment in backup.sh | `grep -q 'crontab' scripts/backup.sh` |
| mc guard in backup.sh | `grep -q 'mc alias' scripts/backup.sh` |

Manual checks (warn only):
- Run `bash scripts/healthcheck.sh` and review output
- Run `bash scripts/backup.sh` and verify backup appears in `/data/backups/`
- Verify backup synced to MinIO: `mc ls local/backups/`
- Install systemd unit and confirm `systemctl status ai-workstation` shows loaded
- Set up daily crontab for backup.sh

Use the same `check()` / `warn()` pattern as prior validate scripts. Exit with `$FAIL` count.

---

## Constraints

1. **`$USER` and `$HOME` in systemd unit** — systemd does not perform shell variable expansion in `ExecStart`/`ExecStop` lines. All paths must be literal: `/home/kasemo/ai-workstation/...`. Using `%h` (systemd specifier for home dir) is acceptable as an alternative to hardcoding.

2. **`ExecStop` is a single directive** — systemd `ExecStop=` must be a single executable with arguments, not a shell pipeline or multi-command string. Use `/bin/bash -c '...'` to wrap multiple compose commands, or use an `ExecStop` script instead.

3. **`start-all.sh` activates `inference-small`** — not `inference-pair-a` as in the source doc. `inference-small` is safer as a default because it only uses GPU0 and allows ComfyUI to start independently on the same GPU later. The user can manually switch to a larger profile.

4. **`backup.sh` MinIO dependency** — backup syncs to MinIO, so MinIO must be running. Add a MinIO health check before the sync step and skip (with warning) if MinIO is not reachable, rather than exiting with an error.

5. **Weekly maintenance checklist** — include as a commented block at the bottom of `healthcheck.sh` for reference, not as a separate file.

---

## Feedback Template

Write to `/plan/ghc-feedback/phase14-operations-runbook.md`:

```markdown
# GHC Feedback: Phase 14 — Operations Runbook
**Brief:** P14-001 | **Status:** Complete / Partial / Blocked

## Files Created
- [ ] scripts/start-all.sh
- [ ] scripts/healthcheck.sh
- [ ] scripts/backup.sh
- [ ] configs/systemd/ai-workstation.service
- [ ] scripts/validate-phase14.sh

## Deviations from Brief
| Item | Plan | Actual | Reason |

## Validation Results
[paste validate-phase14.sh output]

## Notes
```
