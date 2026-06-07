# Phase 08 — Agentic Workflows & MCP

**Services:** n8n (`:5678`), MCP filesystem (`:3100`), MCP browser (`:3101`), MCP code-exec (`:3102`), MCP fetch (`:3103`)  
**Optional:** Dify (`:3010`, profile: `dify`)  
**Compose file:** `docker/compose.agentic.yml`  
**Scripts:** `setup-phase08.sh`, `deploy-phase08.sh`, `validate-phase08.sh`

---

## Prerequisites

- [ ] Phase 05 deployed — Open WebUI running at `:3000`
- [ ] Phase 06 deployed — Loadout Manager running at `:8800`
- [ ] Files on workstation: `scp -r docker scripts configs kasemo@10.10.10.2:~/ai-workstation/`
- [ ] ≥5GB free disk space for n8n data volume

---

## Step 1 — Run Setup

Creates `/data/n8n-files/` and prints credential reference information.

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/setup-phase08.sh"
```

---

## Step 2 — Update n8n Encryption Key

The encryption key protects all stored n8n credentials. **Back this up.** If the container is recreated without the same key, all stored credentials become unreadable.

```bash
# Generate a key
openssl rand -hex 16

# Update the compose file on the workstation
ssh kasemo@10.10.10.2 "nano ~/ai-workstation/docker/compose.agentic.yml"
# Replace: N8N_ENCRYPTION_KEY=change-this-random-key-32chars-minimum-length
# with your generated key, then save.
```

---

## Step 3 — Deploy

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/deploy-phase08.sh"
```

Starts n8n and all four MCP servers. Dify is not started (optional — see Step 7). The script waits for n8n to respond before printing service URLs.

---

## Step 4 — Create n8n Owner Account

Open `http://10.10.10.2:5678` in a browser.

n8n requires an owner account on first launch. Create one — this is the admin account for all workflow management.

---

## Step 5 — Configure n8n AI Integration

In n8n: **Settings → AI**

| Field | Value |
|-------|-------|
| Provider | OpenAI |
| Base URL | `http://10.10.10.2:11434/v1` |
| API Key | `EMPTY` |

This wires the n8n AI Agent node to Ollama. Any model pulled in Ollama is available here.

---

## Step 6 — Add n8n Credentials

In n8n: **Settings → Credentials → Add Credential**

| Name | Type | Configuration |
|------|------|---------------|
| Ollama | OpenAI API | Base URL: `http://10.10.10.2:11434/v1`, Key: `EMPTY` |
| Loadout Manager | HTTP Header Auth | Base URL: `http://10.10.10.2:8800` |
| ComfyUI | HTTP Header Auth | Base URL: `http://10.10.10.2:8188` |
| Workstation SSH | SSH | Host: `10.10.10.2`, User: `kasemo`, key-pair auth |

Add GitHub, Slack, or other credentials as needed for your workflows.

---

## Step 7 — Build First Workflow: Health Monitor

In n8n: **Workflows → Create New**

Recommended first workflow to verify the full stack:

```
Cron Trigger (every 5 min)
  └─ HTTP Request → GET http://10.10.10.2:8800/status
       └─ IF node → gpus[0].temp_c > 85
            ├─ true  → Notification (Slack / email / write to file)
            └─ false → No-op
```

Test with **Execute Workflow** (manual trigger) before activating on schedule.

---

## Step 8 — Register MCP Pipe in Open WebUI (Optional)

This allows agents in Open WebUI chat to invoke MCP tools directly.

1. Open `http://10.10.10.2:3000`
2. **Admin Panel → Functions → Add Function**
3. Paste the contents of `configs/open-webui/mcp-pipe.py`
4. Save and enable

Once registered, select the MCP pipe as a model in chat to give the agent tool access.

---

## Step 9 — Validate

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase08.sh"
```

Expected: 11 automated checks pass, 5 manual checks listed.

---

## Deploy Dify (Optional)

Dify is heavier (4 containers: API, web, Postgres, Redis). Only deploy if you need its visual multi-step RAG pipeline builder.

```bash
ssh kasemo@10.10.10.2 "docker compose -f ~/ai-workstation/docker/compose.agentic.yml \
  --profile dify up -d"
```

Access at `http://10.10.10.2:3010`. On first launch, create an admin account, then configure a model provider:
- **Settings → Model Providers → OpenAI Compatible**
- Base URL: `http://10.10.10.2:11434/v1`, API Key: `EMPTY`

---

## Reference Workflow Patterns

| Pattern | Trigger | What It Does |
|---------|---------|--------------|
| Health Monitor | Cron (5 min) | Poll Loadout Manager `/status`, alert if GPU temp > 85°C |
| Training Pipeline | Webhook | Activate training profile → run Axolotl → notify on completion |
| Content Generation | Webhook | Enhance prompt via Ollama → queue ComfyUI → upscale → save |
| RAG Ingestion | File watcher | Watch `/data/documents/inbox/` → chunk → embed → Qdrant upsert |
| Dataset Curation | File watcher | Quality-score via LLM → auto-tag → move to formatted/ or rejected/ |

---

## Quick Reference

```bash
# Check service status
ssh kasemo@10.10.10.2 "docker ps --filter name=n8n --filter name=mcp"

# Restart n8n (after changing compose env vars)
ssh kasemo@10.10.10.2 "docker compose -f ~/ai-workstation/docker/compose.agentic.yml \
  up -d n8n"

# View n8n logs
ssh kasemo@10.10.10.2 "docker logs -f n8n"

# View MCP server logs
ssh kasemo@10.10.10.2 "docker logs -f mcp-filesystem"

# Test MCP filesystem endpoint
ssh kasemo@10.10.10.2 "curl -s http://localhost:3100/"

# Test MCP fetch endpoint
ssh kasemo@10.10.10.2 "curl -s http://localhost:3103/"

# Stop all agentic services
ssh kasemo@10.10.10.2 "docker compose -f ~/ai-workstation/docker/compose.agentic.yml down"
```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| n8n won't start | Check `docker logs n8n`; if encryption key changed on restart, volume may need reset: `docker volume rm n8n-data` (destroys all workflows/credentials) |
| n8n can't reach Ollama | Verify Ollama is running: `docker ps \| grep ollama`; test `curl http://localhost:11434/v1/models` |
| MCP server not responding | `docker logs mcp-filesystem` (or whichever); container may still be pulling the node image on first start |
| Webhook URL wrong in n8n UI | Verify `WEBHOOK_URL=http://10.10.10.2:5678/` in compose file |
| MCP filesystem permission denied | `/data` is mounted read-only by default; write access requires adjusting the volume mount |
| Dify fails to start | Ensure `dify-db` and `dify-redis` start before `dify-api`; check `docker logs dify-api` |
| n8n credentials lost after restart | `N8N_ENCRYPTION_KEY` changed or missing — must be identical to the key used when credentials were created |
