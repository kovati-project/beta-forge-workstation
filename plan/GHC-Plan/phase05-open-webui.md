# GHC Task: Phase 05 — Primary UI: Open WebUI
**Brief ID:** P05-001  
**Source doc:** `/plan/steps/05-open-webui.md`  
**Write feedback to:** `/plan/ghc-feedback/phase05-open-webui.md`

---

## Context

Phases 01–04 are complete. The workstation (`adapress`, 10.10.10.2) has:
- Ubuntu 26.04 LTS, driver 595.71.05, CUDA 13.3
- Ollama running at `:11434` (GPU0)
- vLLM pair A available at `:8000` (GPU0+GPU3, not always active)
- vLLM pair B available at `:8001` (GPU1+GPU2, not always active)
- vLLM 4-GPU available at `:8002` (all GPUs, profile-gated)
- ComfyUI running at `:8188` (GPU0)
- Rembg at `:8190`, Real-ESRGAN at `:8189`

**Phase 01 (Caddy reverse proxy) is tabled.** There is no `https://ai.local` reverse proxy in place. All services are accessed directly by IP. Any config referencing `https://ai.local` must use `http://10.10.10.2:<port>` instead.

This phase deploys Open WebUI as the unified chat/inference UI and SearXNG for web search.

---

## Scope

Create:
1. **`docker/compose.webui.yml`** — Open WebUI + SearXNG
2. **`configs/searxng/settings.yml`** — SearXNG minimal config
3. **`configs/open-webui/continue-config.json`** — Continue.dev client config
4. **`scripts/deploy-phase05.sh`** — start services, print post-deploy setup steps
5. **`scripts/validate-phase05.sh`** — post-deploy checklist, exits non-zero on failure

**Not in scope:** Open WebUI admin UI configuration (user does this in browser), voice I/O endpoints (Phase 12), pipes/agent integration (Phase 08).

---

## Step 1 — SearXNG Config

SearXNG requires a minimal settings file before it will start.

Create `configs/searxng/settings.yml`:

```yaml
use_default_settings: true

server:
  secret_key: "change-this-to-a-random-32-char-string"
  bind_address: "0.0.0.0:8080"
  base_url: "http://10.10.10.2:8080/"

search:
  safe_search: 0
  default_lang: "en"

engines:
  - name: google
    engine: google
    disabled: false
  - name: duckduckgo
    engine: duckduckgo
    disabled: false
  - name: bing
    engine: bing
    disabled: false
  - name: wikipedia
    engine: wikipedia
    disabled: false

ui:
  default_theme: simple
  infinite_scroll: true
```

---

## Step 2 — Docker Compose: Open WebUI + SearXNG

Create `docker/compose.webui.yml`:

```yaml
services:

  # ── Open WebUI: unified chat and inference UI ───────────────────────────────
  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    container_name: open-webui
    restart: unless-stopped
    ports:
      - "3000:8080"
    volumes:
      - open-webui-data:/app/backend/data
      - /data/models/ollama:/root/.ollama
    environment:
      # Ollama backend (primary)
      - OLLAMA_BASE_URL=http://10.10.10.2:11434

      # vLLM backends (OpenAI-compatible)
      - OPENAI_API_BASE_URLS=http://10.10.10.2:8000;http://10.10.10.2:8001;http://10.10.10.2:8002
      - OPENAI_API_KEYS=EMPTY;EMPTY;EMPTY

      # Image generation via ComfyUI
      - ENABLE_IMAGE_GENERATION=true
      - IMAGE_GENERATION_ENGINE=comfyui
      - COMFYUI_BASE_URL=http://10.10.10.2:8188

      # RAG
      - RAG_EMBEDDING_MODEL=nomic-embed-text
      - RAG_EMBEDDING_ENGINE=ollama
      - CHUNK_SIZE=1000
      - CHUNK_OVERLAP=100

      # Web search via SearXNG
      - ENABLE_WEB_SEARCH=true
      - WEB_SEARCH_ENGINE=searxng
      - SEARXNG_QUERY_URL=http://10.10.10.2:8080/search?q=<query>&format=json

      # Auth
      - WEBUI_SECRET_KEY=change-this-to-a-random-secret
      - ENABLE_SIGNUP=false
      - DEFAULT_USER_ROLE=user

      # Voice I/O pre-wiring (endpoints deployed in Phase 12)
      - AUDIO_STT_ENGINE=openai
      - AUDIO_STT_OPENAI_API_BASE_URL=http://10.10.10.2:9099/v1
      - AUDIO_STT_OPENAI_API_KEY=EMPTY
      - AUDIO_TTS_ENGINE=openai
      - AUDIO_TTS_OPENAI_API_BASE_URL=http://10.10.10.2:5000/v1
      - AUDIO_TTS_OPENAI_API_KEY=EMPTY

      # Features
      - ENABLE_CODE_EXECUTION=true
      - ENABLE_COMMUNITY_SHARING=false

    extra_hosts:
      - "host.docker.internal:host-gateway"

  # ── SearXNG: self-hosted web search ────────────────────────────────────────
  searxng:
    image: searxng/searxng:latest
    container_name: searxng
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./configs/searxng:/etc/searxng

volumes:
  open-webui-data:
```

---

## Step 3 — Continue.dev Client Config

This file is for the user to copy to their client machine (laptop/desktop), not deployed to the workstation.

Create `configs/open-webui/continue-config.json`:

```json
{
  "models": [
    {
      "title": "Qwen2.5-Coder 32B (NVLink-A)",
      "provider": "openai",
      "model": "current-model",
      "apiBase": "http://10.10.10.2:8000/v1/",
      "apiKey": "EMPTY"
    },
    {
      "title": "Llama 3.3 70B (4-GPU)",
      "provider": "openai",
      "model": "large-model",
      "apiBase": "http://10.10.10.2:8002/v1/",
      "apiKey": "EMPTY"
    },
    {
      "title": "Mistral 7B (fast)",
      "provider": "ollama",
      "model": "mistral:7b",
      "apiBase": "http://10.10.10.2:11434"
    }
  ],
  "tabAutocompleteModel": {
    "title": "Qwen2.5-Coder 14B",
    "provider": "ollama",
    "model": "qwen2.5-coder:14b",
    "apiBase": "http://10.10.10.2:11434"
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

## Step 4 — Deploy Script

Create `scripts/deploy-phase05.sh`:

```bash
#!/usr/bin/env bash
# Deploy Phase 05: Open WebUI + SearXNG
# Run on the workstation as kasemo.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== Phase 05: Open WebUI Deploy ==="
echo ""

# ── 1. Prereq checks ──────────────────────────────────────────────────────────
echo "[1/3] Checking prerequisites..."
if ! docker ps --filter name=ollama --filter status=running | grep -q ollama; then
    echo "  ✗ Ollama is not running — start Phase 03 services first"
    exit 1
fi
echo "  ✓ Ollama running"

if ! curl -sf http://localhost:11434/v1/models | grep -q nomic-embed-text; then
    echo "  ⚠  nomic-embed-text not found in Ollama — pulling now..."
    docker exec ollama ollama pull nomic-embed-text
fi
echo "  ✓ nomic-embed-text present (required for RAG)"

# ── 2. Check SearXNG config ───────────────────────────────────────────────────
echo "[2/3] Checking SearXNG config..."
if [[ ! -f "$REPO_ROOT/configs/searxng/settings.yml" ]]; then
    echo "  ✗ configs/searxng/settings.yml not found"
    exit 1
fi
if grep -q "change-this-to-a-random-32-char-string" "$REPO_ROOT/configs/searxng/settings.yml"; then
    echo "  ⚠  SearXNG secret_key is still the placeholder value."
    echo "     Update configs/searxng/settings.yml before proceeding? (y/N)"
    read -r confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || echo "  Continuing with placeholder — update before production use."
fi

# ── 3. Start services ─────────────────────────────────────────────────────────
echo "[3/3] Starting Open WebUI and SearXNG..."
docker compose -f "$REPO_ROOT/docker/compose.webui.yml" up -d
echo "  Waiting for Open WebUI startup (20s)..."
sleep 20

if curl -sf http://localhost:3000/ &>/dev/null; then
    echo "  ✓ Open WebUI running at http://10.10.10.2:3000"
else
    echo "  ✗ Open WebUI not responding — check: docker logs open-webui"
    exit 1
fi

echo ""
echo "=== Deploy complete ==="
echo ""
echo "Next steps (in browser at http://10.10.10.2:3000):"
echo "  1. Register your admin account (first signup = admin)"
echo "  2. Admin → Settings → General: set WEBUI_SECRET_KEY equivalent in UI if prompted"
echo "  3. Verify models visible: Admin → Settings → Connections"
echo "  4. Test chat with a small model (mistral:7b recommended for first test)"
echo "  5. Test image generation: type /image a red cat in the chat"
echo "  6. Settings → Documents: verify chunk size 1000, overlap 100"
echo ""
echo "Continue.dev config for client machines:"
echo "  Copy configs/open-webui/continue-config.json to ~/.continue/config.json"
echo "  Install VS Code extension: code --install-extension Continue.continue"
```

---

## Step 5 — Validate Script

Create `scripts/validate-phase05.sh`:

```bash
#!/usr/bin/env bash
# Run on the workstation after deploy-phase05.sh completes.
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
PASS=0; FAIL=0; WARN=0

check() {
    local desc="$1"; shift
    if eval "$@" &>/dev/null; then
        echo -e "${GREEN}✓${NC} $desc"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} $desc"
        ((FAIL++))
    fi
}

warn() {
    echo -e "${YELLOW}?${NC} $1 — check manually"
    ((WARN++))
}

echo "=== Phase 05 Validation ==="
echo ""

# Services
check "Open WebUI container running"  "docker ps --filter name=open-webui --filter status=running | grep -q open-webui"
check "Open WebUI HTTP responding"    "curl -sf http://localhost:3000/"
check "SearXNG container running"     "docker ps --filter name=searxng --filter status=running | grep -q searxng"
check "SearXNG API responding"        "curl -sf 'http://localhost:8080/search?q=test&format=json'"

# Backends reachable from Open WebUI's perspective
echo ""
check "Ollama reachable at :11434"    "curl -sf http://localhost:11434/v1/models"
check "nomic-embed-text in Ollama"    "curl -sf http://localhost:11434/v1/models | grep -q nomic-embed-text"
check "ComfyUI reachable at :8188"    "curl -sf http://localhost:8188/system_stats"

# Config
echo ""
check "WEBUI_SECRET_KEY not default"  "docker inspect open-webui | grep WEBUI_SECRET_KEY | grep -v 'change-this'"
check "ENABLE_SIGNUP=false set"       "docker inspect open-webui | grep -q 'ENABLE_SIGNUP=false'"
check "SearXNG secret not placeholder" "grep -v 'change-this-to-a-random' configs/searxng/settings.yml | grep -q secret_key"

# Manual checks
echo ""
warn "Admin account created and signup disabled — verify in browser"
warn "Ollama models visible in model selector — check http://10.10.10.2:3000"
warn "Chat response from mistral:7b works end-to-end"
warn "/image command produces output via ComfyUI (requires checkpoint downloaded)"
warn "Web search returns results in chat"
warn "RAG document upload works — try uploading a PDF and querying it"

echo ""
echo "Result: ${PASS} passed, ${FAIL} failed, ${WARN} manual checks"
[[ $FAIL -eq 0 ]] && echo -e "${GREEN}Phase 05 READY${NC}" || echo -e "${RED}Phase 05 NOT READY — fix failures above${NC}"
exit $FAIL
```

---

## Constraints

- **Phase 01 (Caddy) is tabled.** All URLs in config files must use `http://10.10.10.2:<port>` directly — no `https://ai.local` references anywhere.
- **`ENABLE_SIGNUP=false` is required** in the compose file. Open WebUI must not allow open registration.
- **`WEBUI_SECRET_KEY` placeholder must be clearly flagged** — the deploy script prompts the user; the default placeholder value must never be left silently in production.
- **SearXNG must have its own `settings.yml`** mounted at `/etc/searxng` — it will not start without it.
- **Voice I/O endpoints (`:9099`, `:5000`) are pre-wired but not yet deployed** — they come in Phase 12. The compose env vars are set so Open WebUI knows where to find them; the services simply won't respond until Phase 12. Do not omit these env vars.
- **Do not pin Open WebUI or SearXNG image versions** — version pinning is Phase 14.
- **Continue.dev config uses direct IP, not `ai.local`** — Phase 01 proxy is tabled.

---

## Done When

- [ ] `configs/searxng/settings.yml` created
- [ ] `docker/compose.webui.yml` created — Open WebUI + SearXNG
- [ ] `ENABLE_SIGNUP=false` present in compose env
- [ ] Voice I/O env vars pre-wired in compose (STT `:9099`, TTS `:5000`)
- [ ] No `https://ai.local` URLs anywhere (all use `http://10.10.10.2:<port>`)
- [ ] `configs/open-webui/continue-config.json` created using direct IP
- [ ] `scripts/deploy-phase05.sh` created — warns on placeholder secrets
- [ ] `scripts/validate-phase05.sh` created — exits non-zero on hard failures
- [ ] All files use Unix line endings (LF)

---

## Return to Claude

In your feedback file, include:
1. List of all files created with their paths
2. Confirm no `ai.local` references exist in any created file
3. Confirm `ENABLE_SIGNUP=false` is present
4. Confirm voice I/O env vars are pre-wired
5. Any deviations from the spec and why
6. Any blockers before Phase 06 can start
