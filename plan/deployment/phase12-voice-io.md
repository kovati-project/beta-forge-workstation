# Phase 12 — Voice I/O

**Services:** Whisper STT (`:9099`), Piper TTS (`:5000`)  
**Compose file:** `docker/compose.voice.yml`  
**Scripts:** `deploy-phase12.sh`, `validate-phase12.sh`, `whisper-realtime.py`

---

## Prerequisites

- [ ] Phase 05 deployed — Open WebUI running at `:3000` (needed for voice integration)
- [ ] Phase 03 deployed — Ollama running (recommended: voice agent uses it for response generation)
- [ ] GPU 0 available — Whisper uses `NVIDIA_VISIBLE_DEVICES=0`; check Loadout Manager profile first

**GPU conflict:** Whisper takes GPU 0 exclusively while running. If Ollama (also on GPU 0) is loaded, start voice services after confirming GPU 0 is free or use a loadout profile that parks Ollama's heavy models:
```bash
curl -X POST http://localhost:8800/activate/voice
```

---

## Step 1 — Pre-Pull Whisper Model (Optional but Recommended)

The `whisper-large-v3` model is ~1.5GB and downloads on first start. Pre-pulling avoids a 90s timeout during deploy:

```bash
ssh kasemo@10.10.10.2 "mkdir -p /data/models/whisper"
# The model downloads automatically on container first start — no separate pull needed.
# It caches to /data/models/whisper so it persists across container restarts.
```

**Piper voice model** (`en_US-lessac-high.onnx`) also downloads automatically on first start to `/data/models/piper/voices/`. No pre-pull needed.

---

## Step 2 — Deploy

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/deploy-phase12.sh"
```

The script:
1. Creates `/data/models/whisper`, `/data/models/piper/voices`, `/data/audio`
2. Validates compose.voice.yml syntax
3. Starts Whisper and Piper
4. Polls `:9099` (Whisper) and `:5000` (Piper) until ready

**First start is slow.** Whisper downloads the large-v3 model and loads it to GPU 0 — allow 2–5 minutes before the health check passes. The deploy script warns if the poll times out; this is normal on first run.

---

## Step 3 — Verify Whisper STT

```bash
# List available models
ssh kasemo@10.10.10.2 "curl -s http://localhost:9099/v1/models | python3 -m json.tool"

# Transcribe a test audio file (WAV or MP3)
ssh kasemo@10.10.10.2 "curl -s -X POST http://localhost:9099/v1/audio/transcriptions \
  -H 'Content-Type: multipart/form-data' \
  -F 'file=@/data/audio/test.wav' \
  -F 'model=whisper-1'"
```

Expected: JSON with a `text` field containing the transcription.

---

## Step 4 — Verify Piper TTS

```bash
# List available voices
ssh kasemo@10.10.10.2 "curl -s http://localhost:5000/api/voices | python3 -m json.tool"

# Synthesize speech (saves to WAV file)
ssh kasemo@10.10.10.2 "curl -s -X POST http://localhost:5000/api/tts \
  -H 'Content-Type: application/json' \
  -d '{\"text\": \"Hello from the AI workstation.\"}' \
  --output /data/audio/test-tts.wav"

# Confirm file was created and has size
ssh kasemo@10.10.10.2 "ls -lh /data/audio/test-tts.wav"
```

---

## Step 5 — Configure Open WebUI Audio

In Open WebUI: **Admin Panel → Settings → Audio**

**Speech to Text (STT):**

| Setting | Value |
| ------- | ----- |
| Engine | OpenAI (compatible) |
| API Base URL | `http://10.10.10.2:9099/v1` |
| API Key | `EMPTY` |
| Model | `whisper-1` |

**Text to Speech (TTS):**

| Setting | Value |
| ------- | ----- |
| Engine | OpenAI (compatible) |
| API Base URL | `http://10.10.10.2:5000/v1` |
| API Key | `EMPTY` |
| Voice | `en_US-lessac-high` |

Test: click the microphone icon in a chat, speak a sentence, release — the transcription should appear in the input box within 2–3 seconds.

---

## Step 6 — Test Realtime Transcription (WebSocket)

`scripts/whisper-realtime.py` streams microphone audio to Whisper over WebSocket and prints live transcription.

Run from the workstation (requires PyAudio):
```bash
ssh kasemo@10.10.10.2 "pip3 install -q pyaudio websockets"
ssh kasemo@10.10.10.2 "python3 ~/ai-workstation/scripts/whisper-realtime.py"
```

Or run from a local machine that can reach the workstation — the WebSocket URL is:
```
ws://10.10.10.2:9099/v1/audio/transcriptions/realtime
```

Speak into the microphone; transcribed text prints in real time. `Ctrl+C` to stop.

---

## Step 7 — Validate

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase12.sh"
```

---

## Quick Reference

```bash
# Whisper model info
ssh kasemo@10.10.10.2 "curl -s http://localhost:9099/v1/models"

# Piper available voices
ssh kasemo@10.10.10.2 "curl -s http://localhost:5000/api/voices"

# Check GPU usage during transcription (should show GPU 0 active)
ssh kasemo@10.10.10.2 "watch -n 1 nvidia-smi"

# Restart voice services
ssh kasemo@10.10.10.2 "docker compose -f ~/ai-workstation/docker/compose.voice.yml restart"

# View Whisper logs (includes model load progress)
ssh kasemo@10.10.10.2 "docker logs -f whisper"

# Change Whisper language (default: en)
# Edit compose.voice.yml: WHISPER_LANGUAGE=fr then restart
```

---

## Troubleshooting

| Symptom | Check |
| ------- | ----- |
| Whisper health check times out on first deploy | Normal — `whisper-large-v3` loads to GPU in ~2min. Wait and retry: `curl http://localhost:9099/v1/models` |
| `CUDA out of memory` in Whisper logs | GPU 0 occupied by another container. Check `nvidia-smi` and switch to a voice-compatible loadout profile |
| Open WebUI microphone icon does nothing | STT API base must include `/v1` — check the Settings → Audio config |
| Piper TTS returns empty audio | Voice model not yet downloaded — `docker logs piper` will show download progress |
| WebSocket realtime disconnects immediately | Model still loading — wait for `curl http://localhost:9099/v1/models` to return successfully |
| Piper has no GPU reservation | Correct by design — Piper is CPU-only. TTS is fast enough on CPU; no GPU needed |
