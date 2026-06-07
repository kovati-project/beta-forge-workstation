# Phase 08 — Agentic Workflows & MCP
[← Training Pipeline](07-training-pipeline.md) | [Next: Storage & RAG →](09-storage-rag.md)

---

## Objective
Deploy n8n for visual workflow automation, Dify for LLM chain orchestration, and MCP (Model Context Protocol) sidecars that give agents access to filesystem, browser, code execution, and external APIs. Wire everything into Open WebUI's pipe system.

---

## Services Deployed

| Service | Port | Role |
|---------|------|------|
| n8n | 5678 | Visual workflow builder, 400+ integrations |
| Dify | 80 | LLM pipeline orchestration UI |
| MCP filesystem | 3100 | File read/write/search for agents |
| MCP browser | 3101 | Playwright headless browser |
| MCP code-exec | 3102 | Sandboxed code execution |
| MCP fetch | 3103 | HTTP fetch / web scraping |

---

## Step 1 — Docker Compose: Agentic Stack

```bash
cat <<'EOF' > ~/ai-workstation/docker/compose.agentic.yml
version: '3.8'

services:

  # ── n8n: visual workflow automation ───────────────────────────────────────
  n8n:
    image: n8nio/n8n:latest
    container_name: n8n
    restart: unless-stopped
    ports:
      - "5678:5678"
    volumes:
      - n8n-data:/home/node/.n8n
      - /data/n8n-files:/files
    environment:
      - N8N_HOST=0.0.0.0
      - N8N_PORT=5678
      - N8N_PROTOCOL=https
      - WEBHOOK_URL=https://ai.local/n8n/
      - N8N_ENCRYPTION_KEY=change-this-random-key-32chars
      - DB_TYPE=sqlite
      - EXECUTIONS_PROCESS=main
      # LLM integration via OpenAI-compatible endpoint
      - N8N_AI_ENABLED=true
      - N8N_AI_PROVIDER=openai
      - N8N_AI_OPENAI_API_KEY=EMPTY
      - N8N_AI_OPENAI_BASE_URL=http://10.10.10.2:11434/v1

  # ── Dify: LLM app development platform ────────────────────────────────────
  dify-api:
    image: langgenius/dify-api:latest
    container_name: dify-api
    restart: unless-stopped
    environment:
      - MODE=api
      - SECRET_KEY=change-this-secret
      - DB_USERNAME=dify
      - DB_PASSWORD=difypassword
      - DB_HOST=dify-db
      - DB_DATABASE=dify
      - REDIS_HOST=dify-redis
      - STORAGE_TYPE=local
      - OPENAI_API_BASE=http://10.10.10.2:11434/v1
    depends_on:
      - dify-db
      - dify-redis
    volumes:
      - dify-storage:/app/api/storage

  dify-web:
    image: langgenius/dify-web:latest
    container_name: dify-web
    restart: unless-stopped
    ports:
      - "3010:3000"
    environment:
      - NEXT_PUBLIC_API_PREFIX=http://10.10.10.2:5001/v1
      - NEXT_PUBLIC_APP_API_PREFIX=http://10.10.10.2:5001/api

  dify-db:
    image: postgres:15-alpine
    container_name: dify-db
    restart: unless-stopped
    environment:
      - POSTGRES_USER=dify
      - POSTGRES_PASSWORD=difypassword
      - POSTGRES_DB=dify
    volumes:
      - dify-db-data:/var/lib/postgresql/data

  dify-redis:
    image: redis:7-alpine
    container_name: dify-redis
    restart: unless-stopped
    volumes:
      - dify-redis-data:/data

  # ── MCP Servers ───────────────────────────────────────────────────────────

  mcp-filesystem:
    image: node:20-alpine
    container_name: mcp-filesystem
    restart: unless-stopped
    ports:
      - "3100:3100"
    volumes:
      - /data:/data:ro          # read-only by default
      - /home/$USER:/home/user  # user home for read/write
    command: >
      sh -c "npx -y @modelcontextprotocol/server-filesystem
             --port 3100 /data /home/user"

  mcp-fetch:
    image: node:20-alpine
    container_name: mcp-fetch
    restart: unless-stopped
    ports:
      - "3103:3103"
    command: >
      sh -c "npx -y @modelcontextprotocol/server-fetch --port 3103"

  mcp-code-exec:
    image: ghcr.io/e2b-dev/mcp-server:latest
    container_name: mcp-code-exec
    restart: unless-stopped
    ports:
      - "3102:3102"
    environment:
      - PORT=3102
      # Uses E2B cloud sandboxes OR local Docker sandboxes
      # For fully local: replace with custom sandbox image

  mcp-browser:
    image: mcr.microsoft.com/playwright:v1.48.0-jammy
    container_name: mcp-browser
    restart: unless-stopped
    ports:
      - "3101:3101"
    command: >
      sh -c "npx -y @playwright/mcp --port 3101 --headless"

volumes:
  n8n-data:
  dify-storage:
  dify-db-data:
  dify-redis-data:

EOF

docker compose -f ~/ai-workstation/docker/compose.agentic.yml up -d \
  n8n mcp-filesystem mcp-fetch mcp-browser
```

---

## Step 2 — n8n Initial Configuration

```bash
# Access at https://ai.local/n8n or http://10.10.10.2:5678
# Create owner account on first launch
```

**Key credentials to configure in n8n (Settings → Credentials):**

| Credential | Purpose |
|-----------|---------|
| OpenAI API (Ollama endpoint) | LLM node, AI Agent node |
| HTTP Header Auth | Loadout Manager API |
| SSH | Workstation remote commands |
| Postgres | Database automation |
| GitHub | Code repository automation |

**Core workflows to build:**

1. **Model health monitor** — every 5 min, check `/status` on Loadout Manager, alert if GPU temp >85°C
2. **Training pipeline** — webhook trigger → validate dataset → activate training loadout → run Axolotl → notify completion
3. **Content pipeline** — text prompt → Ollama → image prompt refinement → ComfyUI API → save to output
4. **RAG ingestion** — watch `/data/documents/inbox/` → chunk → embed via Ollama → upsert to Qdrant

---

## Step 3 — Open WebUI Pipe: MCP Integration

Open WebUI pipes allow agents to call MCP tools mid-conversation. Add this as a Function in Open WebUI Admin → Functions:

```python
"""
MCP Tool Bridge — exposes filesystem, fetch, and code-exec to Open WebUI agents.
Add as a Pipe in Admin → Functions → Add Function
"""
import requests
import json
from typing import Generator

MCP_ENDPOINTS = {
    "filesystem": "http://10.10.10.2:3100",
    "fetch":      "http://10.10.10.2:3103",
    "code_exec":  "http://10.10.10.2:3102",
}

class Pipe:
    class Valves:
        pass

    def __init__(self):
        self.valves = self.Valves()

    def call_mcp(self, server: str, tool: str, params: dict) -> dict:
        endpoint = MCP_ENDPOINTS.get(server)
        if not endpoint:
            return {"error": f"Unknown MCP server: {server}"}
        try:
            resp = requests.post(
                f"{endpoint}/call",
                json={"tool": tool, "params": params},
                timeout=30
            )
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def pipe(self, body: dict, __user__: dict) -> dict | Generator:
        # Parse tool calls from the last assistant message
        messages = body.get("messages", [])
        # Pass through to model — tool execution handled by Open WebUI
        return body
```

---

## Step 4 — n8n LLM Agent Workflow Example

The following n8n workflow structure implements a research agent:

```json
{
  "name": "Research Agent",
  "nodes": [
    {
      "name": "Webhook Trigger",
      "type": "n8n-nodes-base.webhook",
      "parameters": {"path": "research", "method": "POST"}
    },
    {
      "name": "AI Agent",
      "type": "@n8n/n8n-nodes-langchain.agent",
      "parameters": {
        "model": "ollama",
        "prompt": "{{ $json.query }}",
        "tools": ["web_search", "read_file", "http_request"]
      }
    },
    {
      "name": "Web Search",
      "type": "@n8n/n8n-nodes-langchain.toolSerpApi",
      "parameters": {}
    },
    {
      "name": "Save Result",
      "type": "n8n-nodes-base.writeFile",
      "parameters": {
        "path": "/files/research/{{ $now }}.md",
        "content": "{{ $json.output }}"
      }
    }
  ]
}
```

---

## Step 5 — Agentic Workflow Patterns

### Pattern 1: Overnight Research Pipeline
```
Schedule (11pm) → Activate inference-pair-a → 
Fetch URLs from reading list → Summarize via vLLM → 
Save to /data/outputs/research/ → Notify via webhook
```

### Pattern 2: Code Review Agent
```
Webhook (GitHub PR) → Fetch PR diff via MCP-fetch → 
Code review via vLLM → Post review comment → 
Log result to Langfuse
```

### Pattern 3: Image Generation Pipeline
```
Webhook (prompt) → Text enhancement via Ollama → 
Queue to ComfyUI API → Poll for completion → 
Upscale via Real-ESRGAN → Save + notify
```

### Pattern 4: Training Data Curation
```
Watch /data/datasets/raw/ → Filter quality via Ollama → 
Auto-tag via Label Studio ML backend → 
Move to /data/datasets/formatted/ → Notify training ready
```

---

## Step 6 — Dify Setup (Optional — Advanced Pipelines)

```bash
docker compose -f ~/ai-workstation/docker/compose.agentic.yml up -d \
  dify-api dify-web dify-db dify-redis

# Access at http://10.10.10.2:3010
# Create admin account on first launch
```

Configure Dify to use local Ollama:
- Settings → Model Providers → OpenAI Compatible
- Base URL: `http://10.10.10.2:11434/v1`
- API Key: `EMPTY`
- Model: `qwen2.5-coder:32b` (or any Ollama model)

Use Dify for:
- Multi-step RAG pipelines with conditional logic
- Document Q&A apps with custom UI
- Chatbot apps with tool use built via visual editor

---

## Validation Checklist

- [ ] n8n accessible at `:5678`, owner account created
- [ ] n8n can call Ollama via AI node (test with simple text completion)
- [ ] MCP filesystem server responding at `:3100`
- [ ] MCP fetch server responding at `:3103`
- [ ] MCP browser server responding at `:3101`
- [ ] At least one n8n workflow running end-to-end (health monitor recommended)
- [ ] Open WebUI pipe registered and visible in model selection

---

## Notes
- n8n stores credentials encrypted — the `N8N_ENCRYPTION_KEY` must be backed up; losing it means reconfiguring all credentials
- MCP filesystem is read-only to `/data/` by default — adjust mounts carefully before granting write access to agent workflows
- The browser MCP runs headless Playwright — it can execute JavaScript on pages, which is powerful but should be sandboxed from production credentials
- Dify is heavier than n8n and requires more RAM — start with n8n and add Dify only if you need its visual pipeline builder for multi-step RAG
