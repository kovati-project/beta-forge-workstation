# KOVATI OS — Component Spec 09
## Settings Panel
*Secrets · Network · Auth · Stack Management · Backups · Mode*

---

## 1. Purpose

The Settings panel is where the operator configures and maintains the platform infrastructure itself — not individual service behavior. It covers:

- Rotating secrets stored in `docker/.env`
- Network and WireGuard configuration
- Authentik SSO user management
- Docker image updates and rollback
- Backup scheduling and execution

In **appliance mode**, most of this panel is read-only. Controls that are restricted show a lock icon and "Managed by administrator" tooltip.

---

## 2. Layout

```
┌────────────────────────────────┐ ┌────────────────────────────┐
│ Secrets                        │ │ Network                    │
│ 14 keys · docker/.env          │ │ Jumpbox · WireGuard · Caddy│
├────────────────────────────────┤ └────────────────────────────┘
│                                │ ┌────────────────────────────┐
│                                │ │ Auth                       │
│                                │ │ Authentik SSO · Users      │
└────────────────────────────────┘ └────────────────────────────┘
┌─────────────────────────────────────────────────────────────────┐
│ Stack Management                                                │
│ Container images · updates · rollback                          │
├─────────────────────────────────────────────────────────────────┤
│ Backups                                                         │
│ Schedule · history · run now                                    │
├─────────────────────────────────────────────────────────────────┤
│ Mode & Platform (shown only in relevant contexts)               │
└─────────────────────────────────────────────────────────────────┘
```

Two-column top row (Secrets left, Network + Auth stacked right). Single-column below.

---

## 3. Secrets

Source: `GET /api/secrets` — returns key **names only**, never values.

```
┌──────────────────────────────────────────────────────────────┐
│ Secrets                                    14 keys · .env    │
│                                                              │
│ Key Name             │ Last Rotated │ Affects               │ Rotate │
├──────────────────────────────────────────────────────────────┤
│ POSTGRES_PASSWORD     │ 60d ago      │ langfuse, n8n, dify  │ [Rotate]│
│ LANGFUSE_SECRET_KEY   │ 60d ago      │ langfuse             │ [Rotate]│
│ MINIO_SECRET_KEY      │ 60d ago      │ minio                │ [Rotate]│
│ AUTHENTIK_SECRET_KEY  │ 60d ago      │ authentik            │ [Rotate]│
│ N8N_ENCRYPTION_KEY    │ 60d ago      │ n8n                  │ [Rotate]│
│ DIFY_SECRET_KEY       │ 60d ago      │ dify                 │ [Rotate]│
│ LANGFUSE_SALT         │ 60d ago      │ langfuse             │ [Rotate]│
│ GRAFANA_ADMIN_PASS    │ 60d ago      │ grafana              │ [Rotate]│
│ ...                   │ ...          │ ...                  │ ...     │
└──────────────────────────────────────────────────────────────┘
│ + 6 more                    [Show All]                        │
└──────────────────────────────────────────────────────────────┘
```

**Value column:** Never shown. No "reveal" button exists. The backend never sends secret values to the frontend.

**Rotate action:**
1. Confirmation dialog: `"Rotate POSTGRES_PASSWORD? This will restart: langfuse, n8n, dify. These services will be briefly unavailable."`
2. `POST /api/secrets/{key}/rotate`
3. Backend: generates new value → writes to `docker/.env` → restarts affected containers
4. Show progress: which containers are restarting (inline list with spinners)
5. On completion: "Last Rotated" updates to "just now"

**Rotate All button** (at bottom, requires explicit confirmation with two-step dialog):
- Step 1: `"Rotate all 14 secrets? All services will restart."`
- Step 2: type "rotate all" in text input to confirm

**Appliance mode:** Rotate buttons hidden (not just disabled). "Secrets managed by administrator" label in place of the table.

---

## 4. Network

Source: `GET /api/network`.

```
┌──────────────────────────────────────────────────────────────┐
│ Network                                                      │
│                                                              │
│ Jumpbox IP      10.0.0.1                          [Edit]     │
│ WireGuard       ● connected · 2 peers             [Config ↗] │
│ Caddy Proxy     ● running                         [Config ↗] │
│ Management IF   eth1 · 192.168.1.100 (1GbE)                 │
│ Data IF         eth0 · 10.0.0.5 (10GbE)                     │
│ Mode            [workstation]                                │
└──────────────────────────────────────────────────────────────┘
```

**Jumpbox IP edit:**
- Click "Edit" → field becomes editable (text input, pre-filled with current value)
- Shows: "Save" + "Cancel" buttons
- `PATCH /api/network {jumpbox_ip: "10.0.0.1"}`
- Caddy restarts automatically after save

**WireGuard status:**
- `● connected · N peers` → green dot
- `○ disconnected` → red dot
- "Config ↗" opens WireGuard admin (if a web UI is available) or shows the peer config in a modal

**Mode field:**
- `[workstation]` — editable toggle in workstation mode
- `[appliance]` — read-only if set by boot configuration

---

## 5. Auth

Source: `GET /api/auth/status` + `GET /api/auth/users`.

```
┌──────────────────────────────────────────────────────────────┐
│ Auth                                                         │
│                                                              │
│ Authentik SSO   ● running :9080 / :9443           [Open ↗]  │
│ Forward Auth    enabled: open-webui, n8n                     │
│                                                              │
│ Users                                  [+ Add User]         │
│ Username     │ Email              │ Last Login │ Role │ Act  │
│ kasemo       │ k@example.com      │ 2h ago     │ admin│ [▼]  │
│ devuser      │ dev@example.com    │ 3d ago     │ user │ [▼]  │
└──────────────────────────────────────────────────────────────┘
```

**"Open ↗"** → opens Authentik admin UI (`:9080`) in new tab.

**"+ Add User"** → opens Authentik admin in new tab to the user creation flow. (The full Authentik admin is the source of truth for user management; KOVATI OS does not replicate its entire interface.)

**User row actions dropdown `[▼]`:**
- Promote to admin / Demote to user
- Reset password (opens Authentik admin to that user)
- Revoke all sessions
- Delete user

**Forward Auth toggle** (per service): not shown here — managed in Expose panel (external access) and Authentik directly.

---

## 6. Stack Management

Source: `GET /api/stack/images` — returns current image digest per container.

```
┌──────────────────────────────────────────────────────────────┐
│ Stack Management                                             │
│                                                              │
│ [Update All Services]           Last update: 3d ago · all ✓ │
│                                                              │
│ Service       │ Image                    │ Digest     │ Act  │
├──────────────────────────────────────────────────────────────┤
│ vllm-pair-a   │ vllm/vllm-openai:v0.9.1  │ a1b2...f3d4│[RB] │
│ ollama        │ ollama/ollama:0.6.8       │ c5d6...e7f8│[RB] │
│ open-webui    │ ghcr.io/open-webui:main   │ 9a0b...1c2d│[RB] │
│ n8n           │ n8nio/n8n:1.42.0          │ 3e4f...5a6b│[RB] │
│ ...           │ ...                       │ ...        │ [RB]│
└──────────────────────────────────────────────────────────────┘
```

**"Update All Services" button:**
1. Confirmation: `"Pull latest images and restart all services? Brief downtime per service."`
2. `POST /api/stack/update`
3. Backend runs `docker compose pull` then rolling restart
4. Live progress per service shown in a log panel below the button (SSE stream from update script)

**Update progress display:**
```
Updating: vllm-pair-a...
  Pulling image: 2.1 GB / 4.3 GB [████████░░░░░░░░░]
  ✓ Pulled new image sha256:a1b2...
  Restarting container... ✓ Running (2.1s)
Updating: ollama...
```

**Rollback `[RB]` button:**
- Shown only if a previous image digest is stored
- `POST /api/stack/rollback/{service}` — re-pulls the previous pinned digest and restarts
- Confirmation: `"Roll back {service} to {previous_digest}?"`

**Image digest display:** Truncated to first 8 chars + last 4. Full digest on hover tooltip.

**Appliance mode:** "Update All" button replaced with: "Updates managed via validated stack snapshots. Contact your administrator." Rollback button hidden.

---

## 7. Backups

Source: `GET /api/backup/history` + `GET /api/backup/config`.

```
┌──────────────────────────────────────────────────────────────┐
│ Backups                                                      │
│                                                              │
│ Last backup: 2026-06-05 06:00 · 42 GB · ✓ success           │
│ Schedule:    0 6 * * *                    [Edit Schedule]    │
│ Destination: /data/backups/               [Browse ↗]        │
│                                                              │
│ [Run Backup Now]                                             │
│                                                              │
│ History:                                                     │
│ Date                │ Size   │ Status  │ Act                  │
│ 2026-06-05 06:00    │ 42 GB  │ ✓ ok    │ [Delete]            │
│ 2026-06-04 06:00    │ 41 GB  │ ✓ ok    │ [Delete]            │
│ 2026-06-03 06:00    │ 43 GB  │ ✗ fail  │ [Delete] [Retry]    │
│ ...                 │ ...    │ ...     │ [Delete]            │
│ (Last 10 entries)                                            │
└──────────────────────────────────────────────────────────────┘
```

**"Edit Schedule":** Opens an inline cron editor:
```
[0] [6] [*] [*] [*]  → daily at 06:00
min  hr  dom  mon  dow
[Save Schedule]
```
`PATCH /api/backup/config {schedule: "0 6 * * *"}`.

**"Run Backup Now":**
1. `POST /api/backup/run`
2. Button becomes "Backup running… [spinner]"
3. Progress shown inline: `Archiving /data/models/ (10.1 TB)… ████░░░░░░`
4. On completion: history table updates, button reverts

**Failed backup row:** Shows `✗ fail` in `--red`, with optional "[Retry]" button.

**Delete backup:** Removes the archive from `/data/backups/`. Confirmation required.

---

## 8. Mode & Platform Section

Shown only in specific conditions.

**First-Boot Wizard (distro / appliance mode only):**

```
┌──────────────────────────────────────────────────────────────┐
│ Platform Setup                                               │
│                                                              │
│ First-boot wizard: ✓ Completed 2026-06-01 14:22             │
│                                                              │
│ Hardware detected: 4× RTX A5500 · NVLink A(0↔3) B(1↔2)     │
│ Profile assigned: dual-stack                                 │
│ Secrets: generated                                           │
│ Network: configured                                          │
│ Stack: provisioned                                           │
│                                                              │
│ [Re-run First-Boot Wizard]  ← requires admin confirmation    │
└──────────────────────────────────────────────────────────────┘
```

**Appliance mode:** "Re-run" button hidden.

---

## 9. API Dependencies

| Data | Endpoint | Method | Notes |
|------|----------|--------|-------|
| Secret key names | `GET /api/secrets` | GET | Names only |
| Rotate secret | `POST /api/secrets/{key}/rotate` | POST | Restarts affected containers |
| Network config | `GET /api/network` | GET | IPs, WireGuard, Caddy |
| Update jumpbox IP | `PATCH /api/network` | PATCH | Triggers Caddy reload |
| Auth status | `GET /api/auth/status` | GET | Authentik running/stopped |
| User list | `GET /api/auth/users` | GET | From Authentik API |
| Stack images | `GET /api/stack/images` | GET | Current + previous digests |
| Update all | `POST /api/stack/update` | POST | SSE progress stream |
| Rollback service | `POST /api/stack/rollback/{name}` | POST | |
| Backup config | `GET /api/backup/config` | GET | Schedule + destination |
| Update schedule | `PATCH /api/backup/config` | PATCH | |
| Backup history | `GET /api/backup/history` | GET | Last 10 |
| Run backup | `POST /api/backup/run` | POST | |
| Delete backup | `DELETE /api/backup/{id}` | DELETE | |

---

## 10. Appliance Mode Restrictions Summary

| Feature | Workstation | Appliance |
|---------|------------|---------|
| Rotate secrets | ✓ | ✗ hidden |
| Edit jumpbox IP | ✓ | ✗ read-only |
| Update all services | ✓ | ✗ locked to validated snapshots |
| Rollback individual service | ✓ | ✗ hidden |
| Edit backup schedule | ✓ | ✗ read-only |
| Re-run first-boot wizard | ✓ (with confirm) | ✗ hidden |
| View user list | ✓ | ✓ (read-only) |
| Add/remove users | ✓ (via Authentik ↗) | ✗ |
