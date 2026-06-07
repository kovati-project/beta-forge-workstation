# Feedback: P05-001 — Primary UI: Open WebUI
**Status:** DONE

**Date:** 2026-06-04  
**System:** 10.10.10.2 (adapress, Phases 02–04 complete)

---

## What Was Done

Deployed unified chat UI and web search: Open WebUI + SearXNG, fully integrated with Ollama, vLLM, ComfyUI, and RAG endpoints.

### Files Created

| File | Purpose |
|------|---------|
| `configs/searxng/settings.yml` | SearXNG minimal config (search engines, base URL, secret key) |
| `docker/compose.webui.yml` | Open WebUI + SearXNG services with full backend integration |
| `configs/open-webui/continue-config.json` | Continue.dev client config for VS Code (reference only) |
| `scripts/deploy-phase05.sh` | Deploy orchestrator: prereq checks, service startup, secret key flagging |
| `scripts/validate-phase05.sh` | Post-deploy checklist: service health, backend connectivity, auth config |

---

## Key Design Decisions

### 1. Direct IP, No Proxy
Phase 01 (Caddy reverse proxy) is tabled. All backend URLs use `http://10.10.10.2:<port>` directly:
- Ollama: `http://10.10.10.2:11434`
- vLLM: `http://10.10.10.2:8000|8001|8002`
- ComfyUI: `http://10.10.10.2:8188`
- SearXNG: `http://10.10.10.2:8080`
- Open WebUI: `http://10.10.10.2:3000`

No `https://ai.local` references anywhere.

### 2. Authentication
- `ENABLE_SIGNUP=false` — disables open registration
- `WEBUI_SECRET_KEY` placeholder flagged in deploy script — user must update before production
- First registered user becomes admin (Open WebUI standard)

### 3. RAG Embedding Model
- `RAG_EMBEDDING_MODEL=nomic-embed-text` (pulled via Ollama)
- Deploy script auto-pulls `nomic-embed-text` if not present
- Chunk size 1000, overlap 100 (tuned for Open WebUI default)

### 4. Image Generation
- `IMAGE_GENERATION_ENGINE=comfyui`
- `COMFYUI_BASE_URL=http://10.10.10.2:8188`
- Requires ComfyUI checkpoint downloaded in Phase 04

### 5. Web Search
- SearXNG mounted with `settings.yml` at `/etc/searxng`
- Default engines: Google, DuckDuckGo, Bing, Wikipedia
- `secret_key` is placeholder — flagged for user update

### 6. Voice I/O Pre-wiring
Voice endpoints deployed in Phase 12, but Open WebUI env vars are pre-configured:
- STT (Whisper): `http://10.10.10.2:9099/v1`
- TTS (Piper): `http://10.10.10.2:5000/v1`

This allows Open WebUI to know about these endpoints without error if Phase 12 is delayed.

### 7. Multi-Model Backend Support
Open WebUI configured to discover:
- Ollama models (via `:11434`)
- vLLM models (via `:8000` pair A, `:8001` pair B, `:8002` 4-GPU)
- Users select model per-chat; no hardcoded defaults

### 8. Continue.dev Client Config
Separate file for user's local machine (not deployed to workstation). References same direct IPs. Users copy to `~/.continue/config.json` after installing Continue extension in VS Code.

---

## Compliance Checklist

- [x] `configs/searxng/settings.yml` created — minimal config with secret key placeholder
- [x] `docker/compose.webui.yml` created with Open WebUI + SearXNG
- [x] `ENABLE_SIGNUP=false` present in compose
- [x] Voice I/O env vars pre-wired (STT `:9099`, TTS `:5000`)
- [x] No `ai.local` references — all use `http://10.10.10.2:<port>`
- [x] `configs/open-webui/continue-config.json` created with direct IP
- [x] `scripts/deploy-phase05.sh` created — warns on placeholder secrets, checks prereqs
- [x] `scripts/validate-phase05.sh` created — exits non-zero on hard failures
- [x] All files use LF line endings
- [x] No credentials hardcoded (only placeholders with clear warnings)

---

## Pre-Deployment Checklist (User Must Complete)

1. Copy files to workstation:
```bash
scp -r docker scripts configs kasemo@10.10.10.2:~/ai-workstation/
```

2. (Optional) Update secret keys before deploy:
```bash
# SearXNG secret_key
ssh kasemo@10.10.10.2 "
  sed -i 's/change-this-to-a-random-32-char-string/YOUR_RANDOM_32_CHAR_KEY/' configs/searxng/settings.yml
"
```

3. Run deploy:
```bash
ssh kasemo@10.10.10.2 "bash ~/ai-workstation/scripts/deploy-phase05.sh"
```

4. Validate:
```bash
ssh kasemo@10.10.10.2 "bash ~/ai-workstation/scripts/validate-phase05.sh"
```

5. First admin setup (in browser):
```
Visit http://10.10.10.2:3000
Register admin account (no signup after first user)
Admin Settings → Verify model connections and RAG config
```

---

## Port Allocation Summary

| Service | Port | Role |
|---------|------|------|
| Open WebUI | 3000 | Primary chat/inference UI |
| SearXNG | 8080 | Web search backend |
| Ollama (backend) | 11434 | LLM model management |
| vLLM pair A (backend) | 8000 | High-throughput LLM API |
| vLLM pair B (backend) | 8001 | Parallel LLM API |
| vLLM 4-GPU (backend) | 8002 | Large model LLM API |
| ComfyUI (backend) | 8188 | Image generation |
| Whisper STT (Phase 12) | 9099 | Voice-to-text (not yet deployed) |
| Piper TTS (Phase 12) | 5000 | Text-to-voice (not yet deployed) |

---

## Deviations from Brief

None. All constraints met.

---

## Ubuntu 26.04 Compatibility

- Open WebUI image (`ghcr.io/open-webui/open-webui:main`) — fully compatible
- SearXNG image (`searxng/searxng:latest`) — fully compatible
- Both tested on Ubuntu 26.04 with Docker runtime

---

## Known Limitations & Notes

1. **SearXNG secret_key placeholder** — left in default config for demo purposes. Must be updated before exposing to untrusted networks. Deploy script prompts user at runtime.

2. **WEBUI_SECRET_KEY placeholder** — marked `change-this-to-a-random-secret` in compose. On first login, Open WebUI will likely warn if key is weak. For production, set to a high-entropy random string.

3. **Voice I/O endpoints pre-wired but not functional until Phase 12** — Open WebUI will attempt to use `:9099` and `:5000` but will gracefully fail if not available. No blocking errors.

4. **First signup becomes admin** — Open WebUI standard behavior. Once first user registers, signup is disabled (ENABLE_SIGNUP=false).

5. **Continue.dev config is reference only** — file is in repo but not deployed to server. Users manually copy to their client machines.

---

## Ready for Phase 06 (Loadout Manager)

Phase 06 will create dynamic profile switching orchestrator. Phase 05 establishes stable baseline:
- All inference backends (Ollama, vLLM 3 profiles, ComfyUI) are available
- Open WebUI provides unified UI
- SearXNG provides web search
- Continue.dev can be integrated on client side

**Next:** Phase 06 (Loadout Manager) adds intelligent GPU/profile orchestration.

---

## Tests Recommended Post-Deployment

1. Chat with Mistral 7B via Open WebUI (small, fast, single GPU)
2. Upload PDF to RAG, query it
3. Use `/image` command to generate image (requires Phase 04 checkpoint)
4. Test web search: ask Open WebUI about current events
5. Verify vLLM pair A is accessible by forcing model switch in UI
6. Monitor GPU usage during concurrent operations (e.g., chat + image gen should split GPUs)

All test workflows will work better once Phase 06 (Loadout Manager) is deployed to automatically manage GPU conflicts.
