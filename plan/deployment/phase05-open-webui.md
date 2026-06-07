# Phase 05 — Open WebUI

**Services:** Open WebUI (`:3000`), SearXNG (`:8080`)  
**Compose file:** `docker/compose.webui.yml`  
**Scripts:** `deploy-phase05.sh`, `validate-phase05.sh`

---

## Prerequisites

- [ ] Phase 03 deployed — Ollama running at `:11434`
- [ ] `nomic-embed-text` pulled in Ollama (required for RAG)
- [ ] Phase 04 deployed — ComfyUI running at `:8188` (required for `/image` command)
- [ ] Files on workstation: `scp -r docker scripts configs kasemo@10.10.10.2:~/ai-workstation/`

The deploy script checks for Ollama at startup and exits if it's not running.

---

## Step 1 — Update Secrets

Do this before deploying. Both secrets ship as placeholders.

```bash
# Generate a random key
openssl rand -hex 32

# Update SearXNG secret (replace YOUR_KEY with output above)
ssh kasemo@10.10.10.2 "sed -i 's/change-this-to-a-random-32-char-string/YOUR_KEY/' \
  ~/ai-workstation/configs/searxng/settings.yml"

# Update Open WebUI secret key
# Edit compose.webui.yml on the workstation and replace:
#   WEBUI_SECRET_KEY=change-this-to-a-random-secret
ssh kasemo@10.10.10.2 "nano ~/ai-workstation/docker/compose.webui.yml"
```

---

## Step 2 — Deploy

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/deploy-phase05.sh"
```

The script:
1. Confirms Ollama is running
2. Pulls `nomic-embed-text` if not already present
3. Warns if SearXNG secret is still a placeholder
4. Starts Open WebUI and SearXNG
5. Confirms Open WebUI is responding at `:3000`

---

## Step 3 — Create Admin Account

Open `http://10.10.10.2:3000` in a browser.

The first user to register becomes admin. **Register immediately** — `ENABLE_SIGNUP=false` prevents any further accounts without admin action.

---

## Step 4 — Verify Model Connections (Admin UI)

Navigate to **Admin Panel → Settings → Connections**:

| Connection | URL | Key |
|------------|-----|-----|
| Ollama | `http://10.10.10.2:11434` | — |
| vLLM pair A | `http://10.10.10.2:8000` | `EMPTY` |
| vLLM pair B | `http://10.10.10.2:8001` | `EMPTY` |
| vLLM 4-GPU | `http://10.10.10.2:8002` | `EMPTY` |

vLLM connections show offline if those services aren't active — expected until a model is loaded.

---

## Step 5 — Verify RAG

Navigate to **Admin Panel → Settings → Documents**:
- Chunk size: `1000`
- Overlap: `100`
- Embedding model: `nomic-embed-text` via Ollama

Test: create a Knowledge Base, upload a PDF, ask a question in chat using `#knowledge-base-name`.

---

## Step 6 — Verify Image Generation

Requires ComfyUI running (Phase 04) and at least one checkpoint downloaded.

In chat:
```
/image a red cat sitting on a wooden table, photorealistic
```

First generation may be slow as the model loads into VRAM.

---

## Step 7 — Validate

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase05.sh"
```

The `WEBUI_SECRET_KEY not default` check will fail if you haven't replaced the placeholder — that's intentional.

---

## Step 8 — Configure Continue.dev (Client Machine)

Run this on your local machine (laptop/desktop), not the workstation:

```bash
cp configs/open-webui/continue-config.json ~/.continue/config.json
code --install-extension Continue.continue
```

The config connects directly to `http://10.10.10.2:<port>` — no proxy required.

---

## Quick Reference

```bash
# Restart Open WebUI (after changing env vars)
ssh kasemo@10.10.10.2 "docker compose -f ~/ai-workstation/docker/compose.webui.yml up -d"

# View logs
ssh kasemo@10.10.10.2 "docker logs -f open-webui"
ssh kasemo@10.10.10.2 "docker logs -f searxng"

# Test SearXNG
ssh kasemo@10.10.10.2 "curl -sf 'http://localhost:8080/search?q=test&format=json' \
  | python3 -m json.tool | head -20"
```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Open WebUI shows no models | Verify Ollama is running: `docker ps \| grep ollama`; check connections in Admin panel |
| `/image` fails | Confirm ComfyUI running at `:8188` and a checkpoint is downloaded |
| Web search returns nothing | `docker logs searxng`; verify `settings.yml` is mounted correctly |
| RAG returns irrelevant results | Confirm `nomic-embed-text` pulled and selected as embedding model in Documents settings |
| Session expires immediately | `WEBUI_SECRET_KEY` may be empty or too short — update and restart |
