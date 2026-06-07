# GHC Task: Phase 12 — Voice I/O
**Brief ID:** P12-001  
**Source doc:** `/plan/steps/12-voice-io.md`  
**Write feedback to:** `/plan/ghc-feedback/phase12-voice-io.md`

---

## Context

Phases 01–11 are complete. The workstation has:
- Ollama at `:11434`, Open WebUI at `:3000`
- GPU0 is currently used by Ollama and optionally ComfyUI

The voice I/O endpoints (`:9099` for STT, `:5000` for TTS) were pre-wired in Open WebUI's Phase 05 config but the services have not been deployed until now. This phase deploys faster-whisper (STT) and Piper TTS, connects them to Open WebUI's Audio settings, and provides a real-time streaming script.

**GPU0 VRAM note:** Whisper large-v3 uses ~6GB VRAM on GPU0. Ollama also uses GPU0. They can coexist because Ollama loads/unloads models dynamically, but running ComfyUI simultaneously on GPU0 would exceed VRAM. Use the Loadout Manager `image-studio` profile (which moves LLM inference off GPU0) before running ComfyUI + Whisper simultaneously.

---

## Scope

Create:
1. **`docker/compose.voice.yml`** — faster-whisper (STT) and Piper TTS services
2. **`scripts/deploy-phase12.sh`** — create model directories, pre-download Whisper model and Piper voices, start services, validate endpoints
3. **`scripts/validate-phase12.sh`** — container status and API endpoint checks; exits non-zero on failure
4. **`scripts/whisper-realtime.py`** — real-time WebSocket transcription client (reference script, runs on client machine)

**Not in scope:** Open WebUI audio settings configuration (done in browser by user), n8n voice workflow (user builds in n8n UI).

---

## Step 1 — `docker/compose.voice.yml`

**whisper service:**
- Image: `fedirz/faster-whisper-server:latest-cuda`
- Port: `9099:8000`
- `restart: unless-stopped`
- Volume: `/data/models/whisper:/root/.cache/huggingface`
- GPU: `device_ids: ['0']`
- Environment:
  - `NVIDIA_VISIBLE_DEVICES=0`
  - `WHISPER__MODEL=large-v3`
  - `WHISPER__INFERENCE_DEVICE=cuda`
  - `WHISPER__COMPUTE_TYPE=float16`
  - `WHISPER__BEAM_SIZE=5`
  - `WHISPER__LANGUAGE=en`
  - `WHISPER__VAD_FILTER=true`

**piper service:**
- Image: `ghcr.io/linuxserver/piper:latest`
- Port: `5000:10200`
- `restart: unless-stopped`
- Volume: `/data/models/piper:/config`
- Environment:
  - `PIPER_VOICE=en_US-lessac-high`
  - `PIPER_LENGTH_SCALE=1.0`
  - `PIPER_NOISE_SCALE=0.667`
  - `PIPER_NOISE_W=0.8`
- No GPU reservation — Piper runs on CPU only

**Do not include `version: '3.8'`** and **do not include a `volumes:` key** — there are no named volumes in this compose file (both mounts are bind mounts).

---

## Step 2 — `scripts/deploy-phase12.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Phase 12: Voice I/O ==="

# Create model directories
sudo mkdir -p /data/models/whisper
sudo mkdir -p /data/models/piper/voices
sudo chown -R "$USER:$USER" /data/models/whisper /data/models/piper

# Pre-download Whisper large-v3 model (avoids slow first-start)
if [[ ! -d /data/models/whisper/Systran ]]; then
    echo "Downloading Whisper large-v3 model (~3GB)..."
    pip3 install -q huggingface_hub
    huggingface-cli download Systran/faster-whisper-large-v3 \
        --local-dir /data/models/whisper/Systran/faster-whisper-large-v3
else
    echo "Whisper model already present, skipping download."
fi

# Pre-download Piper voices
VOICES_DIR=/data/models/piper/voices
PIPER_HF="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US"
for VOICE in "lessac/high/en_US-lessac-high" "ryan/high/en_US-ryan-high"; do
    NAME=$(basename "$VOICE")
    if [[ ! -f "$VOICES_DIR/${NAME}.onnx" ]]; then
        echo "Downloading Piper voice: $NAME"
        wget -q -P "$VOICES_DIR" "$PIPER_HF/$VOICE.onnx"
        wget -q -P "$VOICES_DIR" "$PIPER_HF/$VOICE.onnx.json"
    fi
done

# Start services
docker compose -f "$REPO_ROOT/docker/compose.voice.yml" up -d

# Wait for Whisper (model load takes 30-60s on first start)
echo "Waiting for Whisper STT (model load may take up to 60s)..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:9099/v1/models >/dev/null 2>&1; then
        echo "Whisper ready at http://10.10.10.2:9099"
        break
    fi
    sleep 3
done

# Wait for Piper
echo "Waiting for Piper TTS..."
for i in $(seq 1 15); do
    if curl -sf http://localhost:5000/ >/dev/null 2>&1; then
        echo "Piper ready at http://10.10.10.2:5000"
        break
    fi
    sleep 2
done

echo ""
echo "Voice services running:"
echo "  STT (Whisper)  → http://10.10.10.2:9099  (OpenAI-compatible)"
echo "  TTS (Piper)    → http://10.10.10.2:5000   (OpenAI-compatible)"
echo ""
echo "Configure Open WebUI: Settings → Audio"
echo "  STT: http://10.10.10.2:9099/v1  key=EMPTY  model=whisper-1"
echo "  TTS: http://10.10.10.2:5000/v1  key=EMPTY  model=piper  voice=en_US-lessac-high"
```

---

## Step 3 — `scripts/validate-phase12.sh`

Automated checks:

| Check | Command |
|-------|---------|
| Whisper container running | `docker ps --filter name=whisper --filter status=running \| grep -q whisper` |
| Whisper models endpoint | `curl -sf http://localhost:9099/v1/models` |
| Whisper model loaded | `curl -sf http://localhost:9099/v1/models \| grep -q 'whisper'` |
| Piper container running | `docker ps --filter name=piper --filter status=running \| grep -q piper` |
| Piper HTTP responding | `curl -sf http://localhost:5000/` |
| Whisper model dir exists | `test -d /data/models/whisper` |
| Piper voices dir exists | `test -d /data/models/piper/voices` |
| Lessac voice downloaded | `test -f /data/models/piper/voices/en_US-lessac-high.onnx` |
| whisper-realtime.py exists | `test -f scripts/whisper-realtime.py` |

Manual checks (warn only):
- Test STT: upload a WAV and confirm transcription (see test command in quick reference)
- Test TTS: send a speech synthesis request and confirm WAV output
- Configure Open WebUI: Settings → Audio → set STT and TTS endpoints
- In Open WebUI, click the microphone and speak a sentence — verify transcript appears
- Enable voice response, confirm TTS plays the model's reply

Use the same `check()` / `warn()` pattern as prior validate scripts. Exit with `$FAIL` count.

---

## Step 4 — `scripts/whisper-realtime.py`

Real-time transcription client for use on a client machine (not the workstation). Use the exact implementation from the source doc with one fix:

**Bug in source doc:** The WebSocket URL is `ws://localhost:9000/...` but Whisper is on port `9099`. Fix the constant:

```python
WHISPER_WS = "ws://10.10.10.2:9099/v1/audio/transcriptions/realtime"
```

Also change `SAMPLE_RATE` and all audio logic to match the corrected URL. Keep the rest of the implementation identical to the source doc.

Add a comment at the top: `# Run on client machine: pip install websockets pyaudio`

---

## Constraints

1. **No `volumes:` key in compose file** — both mounts in this compose file are bind mounts (host paths). A `volumes: {}` entry is unnecessary and may confuse tooling. Omit it entirely.
2. **Piper runs CPU-only** — do not add a `deploy.resources.reservations.devices` block to the Piper service. Adding GPU reservation would cause it to fail on systems where GPU0 is already fully allocated.
3. **Whisper model load time** — the deploy script must wait up to 90 seconds for Whisper to be ready. The model loads from disk into GPU memory on startup; the container starts before the model is ready, so a health check loop is required.
4. **`whisper-realtime.py` WebSocket port fix** — source doc has `ws://localhost:9000/...` but the service is exposed on `9099`. Use `ws://10.10.10.2:9099/...` (the workstation IP, not localhost, since this script runs on a client machine).
5. **VRAM coexistence** — Whisper large-v3 uses ~6GB of GPU0 VRAM alongside Ollama. Do NOT add a note suggesting users should run this on a different GPU — Whisper's CUDA support is tied to the image and `NVIDIA_VISIBLE_DEVICES=0` is intentional.
6. **Voice endpoint pre-wiring** — Open WebUI was configured in Phase 05 to point at `:9099` and `:5000` for STT/TTS. Now that the services are live, the user only needs to navigate to Settings → Audio to verify or update those values — no compose changes needed for Open WebUI.

---

## Feedback Template

Write to `/plan/ghc-feedback/phase12-voice-io.md`:

```markdown
# GHC Feedback: Phase 12 — Voice I/O
**Brief:** P12-001 | **Status:** Complete / Partial / Blocked

## Files Created
- [ ] docker/compose.voice.yml
- [ ] scripts/deploy-phase12.sh
- [ ] scripts/validate-phase12.sh
- [ ] scripts/whisper-realtime.py

## Deviations from Brief
| Item | Plan | Actual | Reason |

## Validation Results
[paste validate-phase12.sh output]

## Notes
```
