# GHC Task: Phase 11 — Code Generation
**Brief ID:** P11-001  
**Source doc:** `/plan/steps/11-code-generation.md`  
**Write feedback to:** `/plan/ghc-feedback/phase11-code-generation.md`

---

## Context

Phases 01–10 are complete. The workstation has:
- Ollama at `:11434` with `qwen2.5-coder:14b` already pulled (Phase 03)
- vLLM pair A at `:8000` (GPU0+GPU3), 4-GPU at `:8002`
- `nomic-embed-text` pulled in Ollama (for codebase indexing)
- Phase 08 deployed `docker/compose.agentic.yml` with n8n and MCP servers

**Phase 01 (Caddy reverse proxy) is tabled.** The source doc's Continue.dev config uses `https://ai.local/vllm-a/v1/` and `https://ai.local/ollama/` — these must be replaced with direct IP endpoints. Phase 05 already shipped a basic `configs/open-webui/continue-config.json`; this phase replaces it with the full config.

This phase pulls additional code models, writes the full Continue.dev config, adds OpenHands to `compose.agentic.yml`, and creates deploy/validate scripts.

---

## Scope

Create or update:
1. **`configs/continue/config.json`** — full Continue.dev config with all models, tab autocomplete, embeddings, context providers, slash commands, and custom commands
2. **`docker/compose.agentic.yml`** — add the `openhands` service (file already exists from Phase 08; add the new service block, do not overwrite the file)
3. **`scripts/deploy-phase11.sh`** — pull code models via Ollama, start OpenHands, print setup instructions
4. **`scripts/validate-phase11.sh`** — model availability checks, OpenHands endpoint check; exits non-zero on failure

**Not in scope:** Codebase indexing (done in VS Code by user), system prompt configuration in Open WebUI (done in browser), language routing pipe (reference code only — not a deployed service).

---

## Step 1 — `configs/continue/config.json`

Full config replacing the stub written in Phase 05. All `apiBase` values must use direct IPs — no `https://ai.local` references.

```json
{
  "models": [
    {
      "title": "Qwen2.5-Coder 32B [Primary]",
      "provider": "openai",
      "model": "current-model",
      "apiBase": "http://10.10.10.2:8000/v1",
      "apiKey": "EMPTY",
      "contextLength": 32768,
      "completionOptions": {
        "temperature": 0.1,
        "maxTokens": 4096
      }
    },
    {
      "title": "DeepSeek Coder 16B [Debug]",
      "provider": "ollama",
      "model": "deepseek-coder-v2:16b",
      "apiBase": "http://10.10.10.2:11434",
      "contextLength": 16384
    },
    {
      "title": "Llama 3.3 70B [Architect]",
      "provider": "openai",
      "model": "large-model",
      "apiBase": "http://10.10.10.2:8002/v1",
      "apiKey": "EMPTY",
      "contextLength": 16384
    }
  ],

  "tabAutocompleteModel": {
    "title": "Qwen2.5-Coder 7B [Fast]",
    "provider": "ollama",
    "model": "qwen2.5-coder:7b",
    "apiBase": "http://10.10.10.2:11434",
    "contextLength": 4096
  },

  "embeddingsProvider": {
    "provider": "ollama",
    "model": "nomic-embed-text",
    "apiBase": "http://10.10.10.2:11434"
  },

  "contextProviders": [
    {"name": "code", "params": {}},
    {"name": "docs", "params": {}},
    {"name": "diff", "params": {}},
    {"name": "terminal", "params": {}},
    {"name": "problems", "params": {}},
    {"name": "folder", "params": {}},
    {
      "name": "codebase",
      "params": {
        "nRetrieve": 25,
        "nFinal": 5,
        "useReranking": true
      }
    }
  ],

  "slashCommands": [
    {"name": "edit",    "description": "Edit selected code"},
    {"name": "comment", "description": "Add inline documentation"},
    {"name": "tests",   "description": "Generate unit tests"},
    {"name": "refactor","description": "Refactor for clarity and performance"},
    {"name": "review",  "description": "Security and quality code review"},
    {"name": "explain", "description": "Explain this code in depth"}
  ],

  "customCommands": [
    {
      "name": "security-review",
      "prompt": "Review this code for security vulnerabilities. Check for: injection flaws, authentication bypasses, insecure deserialization, sensitive data exposure, SSRF, and privilege escalation. Provide specific remediation for each finding.",
      "description": "Security-focused code review"
    },
    {
      "name": "optimize",
      "prompt": "Analyze this code for performance issues. Identify algorithmic complexity problems, unnecessary allocations, blocking calls, and optimization opportunities. Provide concrete improvements.",
      "description": "Performance analysis and optimization"
    },
    {
      "name": "document",
      "prompt": "Write comprehensive documentation for this code: function signatures, parameter descriptions, return values, exceptions, usage examples, and architectural notes where relevant.",
      "description": "Generate full documentation"
    }
  ]
}
```

Key corrections vs source doc:
- `"apiBase": "http://10.10.10.2:8000/v1"` (not `https://ai.local/vllm-a/v1/`)
- `"apiBase": "http://10.10.10.2:11434"` for Ollama (not `https://ai.local/ollama/`)
- `"apiBase": "http://10.10.10.2:8002/v1"` for 4-GPU vLLM (not `https://ai.local/vllm-4gpu/v1/`)
- Ollama `apiBase` uses `http://10.10.10.2:11434` without a trailing `/v1` — the Continue.dev Ollama provider appends its own path

---

## Step 2 — Add OpenHands to `docker/compose.agentic.yml`

**Edit the existing file** — do not overwrite it. Add the `openhands` service to the `services:` block. Do not touch any existing services.

```yaml
  openhands:
    image: ghcr.io/all-hands-ai/openhands:latest
    container_name: openhands
    restart: unless-stopped
    ports:
      - "3003:3000"
    volumes:
      - /data/openhands:/opt/openhands/workspace
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - OPENAI_API_BASE=http://10.10.10.2:8000/v1
      - OPENAI_API_KEY=EMPTY
      - OPENAI_MODEL=current-model
      - SANDBOX_TYPE=local
      - WORKSPACE_MOUNT_PATH=/data/openhands
```

OpenHands requires the Docker socket to spin up sandbox containers for code execution — treat it as a privileged service. SANDBOX_TYPE=local means it uses the host Docker daemon, not an external sandbox.

---

## Step 3 — `scripts/deploy-phase11.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Phase 11: Code Generation ==="

# Pull code models into Ollama
echo "Pulling code models (this may take a while)..."
docker exec ollama ollama pull qwen2.5-coder:32b
docker exec ollama ollama pull qwen2.5-coder:7b
docker exec ollama ollama pull deepseek-coder-v2:16b

# Create OpenHands workspace
mkdir -p /data/openhands

# Start OpenHands
docker compose -f "$REPO_ROOT/docker/compose.agentic.yml" up -d openhands

# Wait for OpenHands
echo "Waiting for OpenHands..."
for i in $(seq 1 20); do
    if curl -sf http://localhost:3003/ >/dev/null 2>&1; then
        echo "OpenHands ready at http://10.10.10.2:3003"
        break
    fi
    sleep 3
done

echo ""
echo "Code models available in Ollama:"
docker exec ollama ollama list | grep -E "coder|deepseek"

echo ""
echo "Continue.dev config: copy to client machine:"
echo "  cp $REPO_ROOT/configs/continue/config.json ~/.continue/config.json"
echo ""
echo "OpenHands: http://10.10.10.2:3003"
echo "  Connected to vLLM pair A at :8000"
echo "  Workspace: /data/openhands/"
```

---

## Step 4 — `scripts/validate-phase11.sh`

Automated checks:

| Check | Command |
|-------|---------|
| Ollama running | `docker ps --filter name=ollama --filter status=running \| grep -q ollama` |
| qwen2.5-coder:7b pulled | `docker exec ollama ollama list \| grep -q 'qwen2.5-coder:7b'` |
| qwen2.5-coder:14b pulled | `docker exec ollama ollama list \| grep -q 'qwen2.5-coder:14b'` |
| nomic-embed-text pulled | `docker exec ollama ollama list \| grep -q 'nomic-embed-text'` |
| Ollama API responding | `curl -sf http://localhost:11434/v1/models` |
| vLLM pair A responding | `curl -sf http://localhost:8000/v1/models` |
| OpenHands running | `docker ps --filter name=openhands --filter status=running \| grep -q openhands` |
| OpenHands HTTP | `curl -sf http://localhost:3003/` |
| continue config exists | `test -f configs/continue/config.json` |
| continue config uses correct endpoint | `grep -q '10.10.10.2:8000' configs/continue/config.json` |
| continue config no ai.local refs | `! grep -q 'ai.local' configs/continue/config.json` |
| OpenHands workspace exists | `test -d /data/openhands` |

Manual checks (warn only):
- Install Continue.dev in VS Code: `code --install-extension Continue.continue`
- Copy config: `cp configs/continue/config.json ~/.continue/config.json`
- Tab autocomplete triggers on typing (test in a `.py` or `.ts` file)
- `/security-review` slash command works on selected code
- OpenHands at `:3003` can complete a simple task ("write a hello world function")

Use the same `check()` / `warn()` pattern as prior validate scripts. Exit with `$FAIL` count.

---

## Constraints

1. **All `apiBase` values use direct IPs** — `http://10.10.10.2:8000/v1`, `http://10.10.10.2:11434`, `http://10.10.10.2:8002/v1`. No `https://ai.local` references anywhere in `configs/continue/config.json`.
2. **Ollama `apiBase` does not include `/v1`** — the Continue.dev `ollama` provider type appends its own path. Using `http://10.10.10.2:11434/v1` with provider `ollama` will double the path and fail.
3. **OpenHands appended to existing `compose.agentic.yml`** — do not recreate or overwrite this file. It contains n8n, MCP servers, and Dify services from Phase 08. Add only the `openhands` service block.
4. **`qwen2.5-coder:32b` is large (~20GB)** — deploy script pulls it but this will take time on first run. The script should not time out — do not add a timeout to the pull command.
5. **OpenHands Docker socket mount** — same security note as Loadout Manager (Phase 06): treat as privileged, LAN-only.
6. **`deepseek-coder-v2:16b` pull** — this model may not be available in all Ollama registries; add error handling (or `|| true`) on the pull so the script doesn't fail if it's unavailable.

---

## Feedback Template

Write to `/plan/ghc-feedback/phase11-code-generation.md`:

```markdown
# GHC Feedback: Phase 11 — Code Generation
**Brief:** P11-001 | **Status:** Complete / Partial / Blocked

## Files Created / Modified
- [ ] configs/continue/config.json (created)
- [ ] docker/compose.agentic.yml (openhands service added)
- [ ] scripts/deploy-phase11.sh (created)
- [ ] scripts/validate-phase11.sh (created)

## Deviations from Brief
| Item | Plan | Actual | Reason |

## Validation Results
[paste validate-phase11.sh output]

## Notes
```
