# Phase 11 — Code Generation

**Services:** OpenHands autonomous coding agent (`:3003`)  
**IDE integration:** Continue.dev (local plugin on dev machine — no server-side deploy)  
**Compose file:** `docker/compose.codegen.yml`  
**Scripts:** `deploy-phase11.sh`, `validate-phase11.sh`

---

## Prerequisites

- [ ] Phase 03 deployed — vLLM running at `:8000` (required — deploy-phase11.sh will exit if absent)
- [ ] Phase 03 deployed — Ollama running at `:11434` (required)
- [ ] Phase 06 deployed — Loadout Manager running (recommended — not required)

---

## Step 1 — Pull Code Models

Do this before deploying to avoid timeouts. Models are large; pull takes 5–30 minutes.

```bash
# Primary: Qwen2.5-Coder 32B (autocomplete + chat — large, best quality)
ssh kasemo@10.10.10.2 "docker exec ollama ollama pull qwen2.5-coder:32b"

# Secondary: fast models for autocomplete and quick edits
ssh kasemo@10.10.10.2 "docker exec ollama ollama pull qwen2.5-coder:14b"
ssh kasemo@10.10.10.2 "docker exec ollama ollama pull qwen2.5-coder:7b"
ssh kasemo@10.10.10.2 "docker exec ollama ollama pull deepseek-coder-v2:16b"
```

Verify they loaded:
```bash
ssh kasemo@10.10.10.2 "docker exec ollama ollama list"
```

---

## Step 2 — Deploy OpenHands

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/deploy-phase11.sh"
```

The script:
1. Checks vLLM (`:8000`) and Ollama (`:11434`) are running
2. Creates `/data/openhands/` and `/data/code-cache/`
3. Starts the OpenHands container
4. Polls `:3003` for up to 30s

OpenHands connects to vLLM pair A (GPU0+3) at `http://10.10.10.2:8000/v1`. The model name `current-model` is resolved by vLLM to whatever is currently loaded.

---

## Step 3 — Configure Continue.dev (Dev Machine)

Continue.dev runs locally in your IDE and connects to the workstation over the network. No server-side deploy needed.

**Install the extension:**
```
VS Code:   Extensions → search "Continue" → Install
# or
code --install-extension Continue.continue
```

**Copy the config:**

From this repo on Windows, copy `configs/continue/config.json` to `~/.continue/config.json`:
```powershell
Copy-Item "d:\src\ai-workstation-project\configs\continue\config.json" "$env:USERPROFILE\.continue\config.json"
```

The config sets up 4 models:

| Model | Provider | Endpoint | Use |
| ----- | -------- | -------- | --- |
| Qwen2.5-Coder 32B [Primary] | openai | `10.10.10.2:8000/v1` | Chat, complex edits |
| DeepSeek Coder 16B [Debug] | ollama | `10.10.10.2:11434` | Debugging, explanation |
| Codellama 70B [Architect] | openai | `10.10.10.2:8002/v1` | Architecture, full-file refactor |
| Qwen2.5-Coder 14B [Fast] | ollama | `10.10.10.2:11434` | Quick edits |

Tab autocomplete uses `qwen2.5-coder:7b` via Ollama.  
Embeddings use `nomic-embed-text` via Ollama (codebase context indexing).

**Verify the connection:**

In VS Code, open the Continue panel (sidebar icon or `Ctrl+L`) and send a test message. You should get a response within a few seconds.

---

## Step 4 — Test OpenHands

Open `http://10.10.10.2:3003` in a browser.

1. Create a new workspace (mapped to `/data/openhands/` on the workstation)
2. Give it a task, e.g.: `"Create a Python FastAPI endpoint /health that returns {"status": "ok"} and write a pytest test for it"`
3. OpenHands will write files, run tests inside a sandboxed container, and iterate until the task succeeds

OpenHands uses vLLM pair A (GPU0+3) for reasoning. For larger refactors, switch the `OPENAI_API_BASE` env var to `http://10.10.10.2:8002/v1` (4-GPU endpoint) and restart:
```bash
ssh kasemo@10.10.10.2 "docker compose -f ~/ai-workstation/docker/compose.codegen.yml restart openhands"
```

---

## Step 5 — Test Continue.dev Features

**Chat (`Ctrl+L`):**
Select code in editor → `Ctrl+L` → type a question or edit instruction.

**Inline edit (`Ctrl+I`):**
Select a block → `Ctrl+I` → describe the change → Accept/Reject diff.

**Custom slash commands:**
- `/security-review` — checks for OWASP top 10, injection flaws, auth bypasses
- `/optimize` — algorithmic complexity + CUDA-specific analysis
- `/cuda-review` — GPU kernel review: coalescing, occupancy, bank conflicts
- `/document` — generates docstrings + usage examples

**Tab autocomplete:**
Just start typing — Continue uses `qwen2.5-coder:7b` to complete in real time. Should feel instant for short completions.

---

## Step 6 — Validate

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase11.sh"
```

---

## Quick Reference

```bash
# Check OpenHands status
ssh kasemo@10.10.10.2 "docker inspect -f '{{.State.Running}}' openhands"

# OpenHands logs (watch model calls and sandbox exec)
ssh kasemo@10.10.10.2 "docker logs -f openhands"

# Workspace files (browsable from dev machine)
ssh kasemo@10.10.10.2 "ls /data/openhands/"

# Switch OpenHands to 4-GPU endpoint for large tasks
ssh kasemo@10.10.10.2 "docker compose -f ~/ai-workstation/docker/compose.codegen.yml \
  stop openhands && \
  OPENAI_API_BASE=http://10.10.10.2:8002/v1 \
  docker compose -f ~/ai-workstation/docker/compose.codegen.yml up -d openhands"
```

---

## Troubleshooting

| Symptom | Check |
| ------- | ----- |
| Continue.dev shows "Connection refused" | Check `apiBase` values in `~/.continue/config.json` — Ollama must NOT have `/v1` suffix; OpenAI provider must have it |
| Tab autocomplete doesn't fire | `qwen2.5-coder:7b` not pulled — `docker exec ollama ollama list` |
| OpenHands sandbox errors | Docker socket mount `:ro` is correct for Unix sockets — check `docker logs openhands` |
| vLLM model name mismatch | Continue.dev sends `"model": "current-model"` — vLLM ignores this and serves whatever is loaded; it's intentional |
| Codellama 70B endpoint (`:8002`) times out | 4-GPU loadout not active — run `curl -X POST http://10.10.10.2:8800/activate/large-model` |
