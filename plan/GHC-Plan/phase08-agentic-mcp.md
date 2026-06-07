# GHC Task: Phase 08 — Agentic Workflows & MCP
**Brief ID:** P08-001  
**Source doc:** `/plan/steps/08-agentic-mcp.md`  
**Write feedback to:** `/plan/ghc-feedback/phase08-agentic-mcp.md`

---

## Context

Phases 01–07 are complete. The workstation (`adapress`, 10.10.10.2) has:
- Ubuntu 26.04 LTS, driver 595.71.05, CUDA 13.3
- Ollama at `:11434`, vLLM pair A at `:8000`
- Open WebUI at `:3000`, SearXNG at `:8080`
- Loadout Manager at `:8800`
- ComfyUI at `:8188`, Real-ESRGAN at `:8189`

**Phase 01 (Caddy reverse proxy) is tabled.** There is no `https://ai.local` proxy. All services are accessed directly by IP. Any URL in configs or environment variables that references `https://ai.local` must use `http://10.10.10.2:<port>` instead.

This phase deploys n8n for visual workflow automation, MCP servers for agent tool access (filesystem, browser, fetch, code execution), and optionally Dify. It also registers an MCP tool bridge as an Open WebUI pipe.

---

## Scope

Create:
1. **`docker/compose.agentic.yml`** — n8n, MCP servers (filesystem, fetch, browser, code-exec), and Dify services (behind `dify` profile)
2. **`configs/open-webui/mcp-pipe.py`** — MCP Tool Bridge pipe for Open WebUI (added manually via Admin UI)
3. **`scripts/deploy-phase08.sh`** — start n8n + MCP servers; print post-deploy instructions
4. **`scripts/validate-phase08.sh`** — endpoint checks; exits non-zero on failure

**Not in scope:** n8n workflow JSON definitions (user builds these in the UI), Dify model provider configuration (done in browser), Open WebUI pipe installation (manual — requires admin browser access).

---

## Step 1 — `docker/compose.agentic.yml`

**n8n service:**
- Image: `n8nio/n8n:latest`
- Port: `5678:5678`
- `restart: unless-stopped`
- Volumes: `n8n-data:/home/node/.n8n`, `/data/n8n-files:/files`
- Environment:
  - `N8N_HOST=0.0.0.0`
  - `N8N_PORT=5678`
  - `N8N_PROTOCOL=http` ← **must be `http`**, not `https` (Phase 01 Caddy is tabled)
  - `WEBHOOK_URL=http://10.10.10.2:5678/` ← **must use IP, not `https://ai.local/n8n/`**
  - `N8N_ENCRYPTION_KEY=change-this-to-a-random-32-char-key`
  - `DB_TYPE=sqlite`
  - `EXECUTIONS_PROCESS=main`
  - `N8N_AI_ENABLED=true`
  - `N8N_AI_PROVIDER=openai`
  - `N8N_AI_OPENAI_API_KEY=EMPTY`
  - `N8N_AI_OPENAI_BASE_URL=http://10.10.10.2:11434/v1`

**mcp-filesystem service:**
- Image: `node:20-alpine`
- Port: `3100:3100`
- `restart: unless-stopped`
- Volumes: `/data:/data:ro`, `/home/kasemo:/home/user` ← hardcode `kasemo`, do not use `$USER` (shell variable not expanded in compose env)
- Command: `sh -c "npx -y @modelcontextprotocol/server-filesystem --port 3100 /data /home/user"`

**mcp-fetch service:**
- Image: `node:20-alpine`
- Port: `3103:3103`
- `restart: unless-stopped`
- Command: `sh -c "npx -y @modelcontextprotocol/server-fetch --port 3103"`

**mcp-browser service:**
- Image: `mcr.microsoft.com/playwright:v1.48.0-jammy`
- Port: `3101:3101`
- `restart: unless-stopped`
- Command: `sh -c "npx -y @playwright/mcp --port 3101 --headless"`

**mcp-code-exec service:**
- Image: `ghcr.io/e2b-dev/mcp-server:latest`
- Port: `3102:3102`
- `restart: unless-stopped`
- Environment: `PORT=3102`
- Add comment: `# E2B cloud sandbox by default — requires E2B_API_KEY env var for cloud mode`
- Profile: `code-exec` ← gate behind profile; it requires external API key or custom sandbox config

**Dify services** (`dify-api`, `dify-web`, `dify-db`, `dify-redis`) — all behind `dify` profile:
- Use exact definitions from source doc with these changes:
  - `dify-web` port: `3010:3000`
  - `OPENAI_API_BASE=http://10.10.10.2:11434/v1`
  - `NEXT_PUBLIC_API_PREFIX=http://10.10.10.2:5001/v1`
  - `NEXT_PUBLIC_APP_API_PREFIX=http://10.10.10.2:5001/api`
  - `dify-api` `SECRET_KEY=change-this-to-a-random-secret`
  - Add `profiles: [dify]` to all four Dify services

**Volumes:** `n8n-data`, `dify-storage`, `dify-db-data`, `dify-redis-data`

**Do not include `version: '3.8'`** — deprecated in modern Compose.

---

## Step 2 — `configs/open-webui/mcp-pipe.py`

The MCP Tool Bridge — to be added manually as a Pipe function in Open WebUI (Admin → Functions → Add Function). This file is a reference copy, not auto-installed.

Use the exact implementation from the source doc. Key constants:

```python
MCP_ENDPOINTS = {
    "filesystem": "http://10.10.10.2:3100",
    "fetch":      "http://10.10.10.2:3103",
    "code_exec":  "http://10.10.10.2:3102",
}
```

Add a docstring at the top explaining how to install it: paste into Open WebUI Admin → Functions → Add Function.

---

## Step 3 — `scripts/deploy-phase08.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Phase 08: Agentic Workflows & MCP ==="

# Create n8n files directory if not present
mkdir -p /data/n8n-files

# Start n8n and MCP servers (excludes dify and code-exec profiles)
docker compose -f "$REPO_ROOT/docker/compose.agentic.yml" up -d \
  n8n mcp-filesystem mcp-fetch mcp-browser

# Wait for n8n
echo "Waiting for n8n..."
for i in $(seq 1 20); do
    if curl -sf http://localhost:5678/healthz >/dev/null 2>&1; then
        echo "n8n ready at http://10.10.10.2:5678"
        break
    fi
    sleep 3
done

echo ""
echo "Services started:"
echo "  n8n            → http://10.10.10.2:5678"
echo "  MCP filesystem → http://10.10.10.2:3100"
echo "  MCP fetch      → http://10.10.10.2:3103"
echo "  MCP browser    → http://10.10.10.2:3101"
echo ""
echo "Next steps:"
echo "  1. Open http://10.10.10.2:5678 and create owner account"
echo "  2. Update N8N_ENCRYPTION_KEY in compose.agentic.yml"
echo "  3. In Open WebUI Admin → Functions, paste configs/open-webui/mcp-pipe.py"
echo ""
echo "Optional Dify stack:"
echo "  docker compose -f docker/compose.agentic.yml --profile dify up -d"
```

---

## Step 4 — `scripts/validate-phase08.sh`

Automated checks:

| Check | Command |
|-------|---------|
| n8n running | `docker ps --filter name=n8n --filter status=running \| grep -q ' n8n'` |
| n8n HTTP | `curl -sf http://localhost:5678/healthz` |
| MCP filesystem running | `docker ps --filter name=mcp-filesystem --filter status=running \| grep -q mcp-filesystem` |
| MCP filesystem HTTP | `curl -sf http://localhost:3100/` |
| MCP fetch running | `docker ps --filter name=mcp-fetch --filter status=running \| grep -q mcp-fetch` |
| MCP fetch HTTP | `curl -sf http://localhost:3103/` |
| MCP browser running | `docker ps --filter name=mcp-browser --filter status=running \| grep -q mcp-browser` |
| MCP browser HTTP | `curl -sf http://localhost:3101/` |
| n8n encryption key not default | `docker inspect n8n \| grep N8N_ENCRYPTION_KEY \| grep -v 'change-this'` |
| n8n using Ollama endpoint | `docker inspect n8n \| grep -q '11434'` |
| n8n files directory exists | `test -d /data/n8n-files` |
| mcp-pipe.py reference exists | `test -f configs/open-webui/mcp-pipe.py` |

Manual checks (warn only):
- Open `http://10.10.10.2:5678`, confirm owner account creation page loads
- Confirm n8n AI node can reach Ollama (test with simple completion)
- Confirm `POST http://localhost:3100/` returns MCP server info

Use the same `check()` / `warn()` pattern as prior validate scripts. Exit with `$FAIL` count.

---

## Constraints

1. **`N8N_PROTOCOL=http`** — n8n is accessed directly by IP. Setting `https` without a TLS terminator will break webhook callbacks and the n8n UI itself. The source doc incorrectly sets `https` — fix it.
2. **`WEBHOOK_URL=http://10.10.10.2:5678/`** — n8n uses this to construct webhook URLs shown in the UI. If set to an unreachable host, triggered webhooks will never fire. Fix from source doc's `https://ai.local/n8n/`.
3. **`$USER` in mcp-filesystem volume** — Docker Compose does not expand shell variables in volume mount paths. Use literal `kasemo` for `/home/kasemo:/home/user`.
4. **Dify behind `dify` profile** — Dify (4 containers) is optional and heavier than n8n. Do not auto-start it. The deploy script only starts n8n and MCP servers.
5. **mcp-code-exec behind `code-exec` profile** — requires either an E2B API key (cloud) or a custom local sandbox setup. Do not auto-start it.
6. **n8n `N8N_ENCRYPTION_KEY`** — this must be backed up. If the container is recreated without the same key, all stored credentials are unreadable. Flag clearly in a comment in the compose file.
7. **mcp-pipe.py is a reference file, not auto-installed** — Open WebUI functions cannot be installed from the filesystem; they must be pasted via the admin UI. The deploy script must print instructions for this step.

---

## Feedback Template

Write to `/plan/ghc-feedback/phase08-agentic-mcp.md`:

```markdown
# GHC Feedback: Phase 08 — Agentic Workflows & MCP
**Brief:** P08-001 | **Status:** Complete / Partial / Blocked

## Files Created
- [ ] docker/compose.agentic.yml
- [ ] configs/open-webui/mcp-pipe.py
- [ ] scripts/deploy-phase08.sh
- [ ] scripts/validate-phase08.sh

## Deviations from Brief
| Item | Plan | Actual | Reason |

## Validation Results
[paste validate-phase08.sh output]

## Notes
```
