# Authentik + Caddy Debug Handoff

**Date:** 2026-06-29  
**Author:** Kasem Omary  
**Status:** Authentik resolved ✅ — Caddy resolved ✅ — `dcgm-exporter` pending 🔲

---

## What Was Broken

The entire auth stack (`authentik`, `caddy`) was down, blocking all user-facing services that use Authentik SSO via Caddy forward-auth.

---

## Root Causes Found & Fixed

### 1. Authentik server crash-loop — `command: server` missing
**File:** `docker/compose.auth.yml`

The `authentik` container (web server) was restarting with exit code 0 every ~10 seconds. The `authentik-worker` was healthy. The logs showed only Django management command help text — not an error.

**Cause:** The Authentik Docker image (`ghcr.io/goauthentik/server:latest`) no longer ships a default `CMD`. The entrypoint is `dumb-init -- ak` with no argument, which prints help and exits 0. The `authentik-worker` service works because it has `command: worker` explicitly set. The `authentik` server service was missing `command: server`.

**Fix applied:**
```yaml
# docker/compose.auth.yml — added line 45
authentik:
  image: ghcr.io/goauthentik/server:latest
  command: server          # ← this line was missing
  ...
```

---

### 2. Caddyfile syntax errors — two invalid directives
**File:** `configs/caddy/Caddyfile.security` (deployed to `/data/caddy/Caddyfile`)

Caddy was crash-looping with exit code 1. Two distinct syntax errors:

**Error A:** `header_uri` is not a valid Caddy v2 directive (lines 38, 63, 79, 108).  
**Fix:** Replaced all 4 occurrences with `header_up` (the correct directive for manipulating upstream request headers in a `reverse_proxy` block).

```
# Before (invalid)
header_uri -Upgrade
# After (correct)
header_up -Upgrade
```

**Error B:** `abort` takes no arguments in Caddy v2 (line 137).  
**Fix:** Changed `abort 404` to `respond 404`.

```
# Before (invalid)
handle {
    abort 404
}
# After (correct)
handle {
    respond 404
}
```

---

### 3. `/data/caddy/Caddyfile` was never created
**Script:** `scripts/deploy-phase13.sh`

The deploy script creates `/data/authentik/` directories but never copies `configs/caddy/Caddyfile.security` to `/data/caddy/Caddyfile`. Caddy's volume mount expects the file to exist at runtime.

**Manual fix applied on server:**
```bash
sudo mkdir -p /data/caddy/certs /data/caddy/config /var/log/caddy
sudo cp configs/caddy/Caddyfile.security /data/caddy/Caddyfile
```

**Permanent fix needed:** Add these lines to `scripts/deploy-phase13.sh` after the `/data/authentik/` directory creation block.

---

## Current Status

| Service | Status | Notes |
|---------|--------|-------|
| `authentik` (server) | ✅ Running | Fixed with `command: server` |
| `authentik-worker` | ✅ Running (healthy) | Was already running |
| `authentik-postgres` | ✅ Running (healthy) | Was already running |
| `authentik-redis` | ✅ Running (healthy) | Was already running |
| `caddy` | ✅ Running | TLS cert issued for `ai.local` via local CA |
| `dcgm-exporter` | 🔲 Unknown | Mentioned at end of session — not investigated |

---

## Remaining Work

### High priority

**1. Investigate `dcgm-exporter`**
Mentioned but not looked at. Check:
```bash
docker ps --filter "name=dcgm" --format "table {{.Names}}\t{{.Status}}"
docker logs dcgm-exporter --tail 30 2>&1
```

**2. Fix `scripts/deploy-phase13.sh` — missing Caddyfile copy**
Add after the `mkdir -p /data/authentik/...` block:
```bash
sudo mkdir -p /data/caddy/certs /data/caddy/config /var/log/caddy
sudo cp configs/caddy/Caddyfile.security /data/caddy/Caddyfile
```

**3. Fix `scripts/start-all.sh` — no health-wait after Authentik starts**  
Line 102-103 currently just sleeps 5 seconds. If Authentik isn't ready (takes ~60s), downstream services fail auth. Replace with:
```bash
# After: start_service "Authentication (Authentik, Caddy)" "compose.auth.yml"
for i in $(seq 1 18); do
  curl -sf http://localhost:9080/-/health/live/ && break
  echo "Waiting for Authentik... ($i/18)"; sleep 5
done
```

### Medium priority

**4. Network warning on compose up**
Every `docker compose ... -f docker/compose.auth.yml up` emits:
```
WARN: a network with name ai-auth exists but was not created for project "ai-auth-stack"
Set `external: true` to use an existing network
```
Fix by changing the network definition in `docker/compose.auth.yml` (and `docker/compose.caddy.yml`) to mark `ai-auth` as external if it was created outside the stack, or ensure it's always created by the stack.

---

## How to Verify Everything Is Working

```bash
# All four Authentik containers healthy
docker ps --filter "name=authentik" --format "table {{.Names}}\t{{.Status}}"

# Authentik health endpoint
curl -sf http://localhost:9080/-/health/live/ && echo "Authentik OK"

# Caddy can reach Authentik through the ai-auth network
docker exec caddy curl -sf http://authentik:9000/-/health/live/ && echo "Caddy→Authentik OK"

# Caddy is up
docker ps --filter "name=caddy" --format "table {{.Names}}\t{{.Status}}"

# Run built-in validation
bash scripts/validate-phase13.sh
```

If Authentik needs initial admin setup:
```
http://10.10.10.2:9080/if/flow/initial-setup/
```

---

## Files Changed

| File | What Changed |
|------|-------------|
| `docker/compose.auth.yml` | Added `command: server` to the `authentik` service |
| `configs/caddy/Caddyfile.security` | `header_uri` → `header_up` (×4); `abort 404` → `respond 404` (×1) |
| `scripts/deploy-phase13.sh` | **TODO** — add Caddyfile copy step |
| `scripts/start-all.sh` | **TODO** — add health-wait loop after auth stack start |

---

## Restart Commands (for reference)

```bash
# Restart just the authentik server (after any compose.auth.yml changes)
docker compose --env-file docker/.env -f docker/compose.auth.yml up -d authentik

# Restart Caddy (after Caddyfile changes)
sudo cp configs/caddy/Caddyfile.security /data/caddy/Caddyfile
docker compose --env-file docker/.env -f docker/compose.caddy.yml restart caddy

# Full auth stack restart from scratch
docker compose --env-file docker/.env -f docker/compose.auth.yml down --remove-orphans
docker compose --env-file docker/.env -f docker/compose.auth.yml up -d authentik-postgres authentik-redis
sleep 15
docker compose --env-file docker/.env -f docker/compose.auth.yml up -d
```
