# Phase 05 — Primary UI: Open WebUI
[← Image Inference](04-inference-image.md) | [Next: Loadout Manager →](06-loadout-manager.md)

---

## Objective
Deploy Open WebUI as the unified chat/inference UI. Connect it to Ollama and vLLM, enable image generation via ComfyUI, configure RAG, and set up user management. This is the primary daily-use interface for all AI interactions.

---

## Step 1 — Docker Compose

```bash
cat <<'EOF' > ~/ai-workstation/docker/compose.webui.yml
version: '3.8'

services:

  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: open-webui
    restart: unless-stopped
    ports:
      - "3000:8080"
    volumes:
      - open-webui-data:/app/backend/data
      - /data/models/ollama:/root/.ollama   # shared model cache
    environment:
      # Primary backend: Ollama (local)
      - OLLAMA_BASE_URL=http://10.10.10.2:11434

      # Additional OpenAI-compatible backends (vLLM)
      - OPENAI_API_BASE_URLS=http://10.10.10.2:8000;http://10.10.10.2:8001;http://10.10.10.2:8002
      - OPENAI_API_KEYS=EMPTY;EMPTY;EMPTY   # vLLM needs a key value but ignores it

      # Image generation via ComfyUI
      - ENABLE_IMAGE_GENERATION=true
      - IMAGE_GENERATION_ENGINE=comfyui
      - COMFYUI_BASE_URL=http://10.10.10.2:8188

      # RAG configuration
      - RAG_EMBEDDING_MODEL=nomic-embed-text  # via Ollama
      - RAG_EMBEDDING_ENGINE=ollama
      - CHUNK_SIZE=1000
      - CHUNK_OVERLAP=100

      # Auth and security
      - WEBUI_SECRET_KEY=change-this-to-a-random-secret
      - ENABLE_SIGNUP=false          # disable open registration
      - DEFAULT_USER_ROLE=user

      # Features
      - ENABLE_CODE_EXECUTION=true
      - ENABLE_WEB_SEARCH=true
      - ENABLE_COMMUNITY_SHARING=false

    extra_hosts:
      - "host.docker.internal:host-gateway"

volumes:
  open-webui-data:

EOF

docker compose -f ~/ai-workstation/docker/compose.webui.yml up -d
```

---

## Step 2 — Initial Setup

```bash
# Wait for startup
docker logs -f open-webui

# Access at http://10.10.10.2:3000 (or via Caddy: https://ai.local)
# First user to register becomes admin
# Sign up with your primary account immediately
```

---

## Step 3 — Model Configuration

In the Open WebUI admin panel:

**Settings → Connections:**
- Ollama: `http://10.10.10.2:11434` — verify models load
- OpenAI (vLLM pair A): `http://10.10.10.2:8000`, key: `EMPTY`
- OpenAI (vLLM pair B): `http://10.10.10.2:8001`, key: `EMPTY`
- OpenAI (vLLM 4GPU): `http://10.10.10.2:8002`, key: `EMPTY`

**Settings → Models:**
- Set display names per model (e.g. `Qwen2.5-32B [NVLink-A]`, `Llama3.3-70B [4GPU]`)
- Set default system prompts per model if desired
- Hide models not relevant to non-admin users

---

## Step 4 — RAG Pipeline Setup

```bash
# Ensure nomic-embed-text is pulled in Ollama
docker exec ollama ollama pull nomic-embed-text

# Verify embedding endpoint
curl http://localhost:11434/api/embed \
  -d '{"model":"nomic-embed-text","input":"test embedding"}'
```

In Open WebUI:
- **Settings → Documents:** set chunk size 1000, overlap 100
- **Workspace → Knowledge:** create knowledge bases (e.g. "Security Research", "Codebase", "Personal Notes")
- Upload documents — PDFs, markdown, code files all supported
- Enable `#knowledge-base-name` syntax in chat to query specific collections

---

## Step 5 — Image Generation Setup

```bash
# Ensure ComfyUI is running (Phase 04)
curl http://localhost:8188/system_stats
```

In Open WebUI:
- **Settings → Images → ComfyUI**
- URL: `http://10.10.10.2:8188`
- Upload a default workflow JSON (export from ComfyUI UI)
- Set default resolution: 1024×1024 for SDXL, 1360×768 for FLUX

Test in chat:
```
/image a cyberpunk cityscape at night, neon lights reflecting in rain
```

---

## Step 6 — Pipes and Functions (Agent Integration)

Open WebUI supports "Pipes" — Python functions that intercept messages and route them to custom logic. This is the integration point for agentic workflows (Phase 08).

```python
# Example pipe: route to vLLM based on model size keyword
# Save as a Pipe in Open WebUI Admin → Functions

def pipe(body: dict, __user__: dict) -> dict:
    model = body.get("model", "")
    if "70b" in model.lower():
        # Route to 4-GPU vLLM endpoint
        body["model"] = "large-model"
        # Override base URL in pipe
    return body
```

---

## Step 7 — Web Search Integration

```bash
# Option 1: SearXNG (fully self-hosted)
cat <<'EOF' >> ~/ai-workstation/docker/compose.webui.yml
  searxng:
    image: searxng/searxng:latest
    container_name: searxng
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./configs/searxng:/etc/searxng
    environment:
      - SEARXNG_BASE_URL=http://10.10.10.2:8080
EOF

docker compose -f ~/ai-workstation/docker/compose.webui.yml up -d searxng
```

In Open WebUI:
- **Settings → Web Search:** SearXNG URL: `http://10.10.10.2:8080`

---

## Step 8 — Voice I/O Pre-wiring

Open WebUI has built-in STT/TTS support. Pre-configure endpoints that will be deployed in Phase 12:

```
Settings → Audio:
  STT Engine: OpenAI (compatible)
  STT URL: http://10.10.10.2:9099/v1
  STT API Key: EMPTY
  TTS Engine: OpenAI (compatible)
  TTS URL: http://10.10.10.2:5000/v1
  TTS Voice: [configure after Phase 12]
```

---

## Step 9 — Continue.dev for Code Copilot

Install Continue.dev in VS Code on any client machine:

```bash
# VS Code extension
code --install-extension Continue.continue
```

Configure `~/.continue/config.json` on the client:

```json
{
  "models": [
    {
      "title": "Qwen2.5-Coder 32B (NVLink-A)",
      "provider": "openai",
      "model": "current-model",
      "apiBase": "https://ai.local/api/v1/",
      "apiKey": "your-basic-auth-token"
    },
    {
      "title": "Mistral 7B (fast)",
      "provider": "ollama",
      "model": "mistral:7b",
      "apiBase": "https://ai.local/ollama/"
    }
  ],
  "tabAutocompleteModel": {
    "title": "Qwen2.5-Coder 14B",
    "provider": "ollama",
    "model": "qwen2.5-coder:14b",
    "apiBase": "https://ai.local/ollama/"
  },
  "contextProviders": [
    {"name": "code"},
    {"name": "docs"},
    {"name": "diff"},
    {"name": "terminal"},
    {"name": "problems"}
  ],
  "slashCommands": [
    {"name": "edit", "description": "Edit selected code"},
    {"name": "comment", "description": "Add comments"},
    {"name": "tests", "description": "Write tests"}
  ]
}
```

---

## Validation Checklist

- [ ] Open WebUI accessible via browser at `:3000` and via Caddy at `https://ai.local`
- [ ] Admin account created, signup disabled
- [ ] Ollama models visible and responding in chat
- [ ] vLLM endpoints connected (may show offline if vLLM not started — expected)
- [ ] RAG: document upload works, query returns relevant chunks
- [ ] Image generation: `/image` command produces output via ComfyUI
- [ ] Web search working via SearXNG
- [ ] Continue.dev connecting to Ollama via Caddy reverse proxy

---

## Notes
- Open WebUI updates frequently — pin to a specific image tag in production (`ghcr.io/open-webui/open-webui:v0.4.x`)
- The `WEBUI_SECRET_KEY` must be a strong random value — it signs session tokens
- Multi-user: create accounts for each user in Admin → Users; set model access per user group
- All conversations are stored in the Docker volume — back this up regularly (Phase 14)
