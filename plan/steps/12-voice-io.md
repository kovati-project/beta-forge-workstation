# Phase 12 — Voice I/O
[← Code Generation](11-code-generation.md) | [Next: Security Hardening →](13-security-hardening.md)

---

## Objective
Deploy fully local speech-to-text (Whisper.cpp via faster-whisper) and text-to-speech (Piper TTS) with OpenAI-compatible API endpoints that Open WebUI consumes natively. Zero cloud audio leakage.

---

## Step 1 — Docker Compose: Voice Stack

```bash
cat <<'EOF' > ~/ai-workstation/docker/compose.voice.yml
version: '3.8'

services:

  # ── faster-whisper: STT with OpenAI-compatible API ────────────────────────
  whisper:
    image: fedirz/faster-whisper-server:latest-cuda
    container_name: whisper
    restart: unless-stopped
    ports:
      - "9099:8000"
    volumes:
      - /data/models/whisper:/root/.cache/huggingface
    environment:
      - NVIDIA_VISIBLE_DEVICES=0
      - WHISPER__MODEL=large-v3
      - WHISPER__INFERENCE_DEVICE=cuda
      - WHISPER__COMPUTE_TYPE=float16
      - WHISPER__BEAM_SIZE=5
      - WHISPER__LANGUAGE=en          # set to null for auto-detect
      - WHISPER__VAD_FILTER=true      # silence detection
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']
              capabilities: [gpu]

  # ── Piper TTS: fast local text-to-speech ─────────────────────────────────
  piper:
    image: ghcr.io/linuxserver/piper:latest
    container_name: piper
    restart: unless-stopped
    ports:
      - "5000:10200"
    volumes:
      - /data/models/piper:/config
    environment:
      - PIPER_VOICE=en_US-lessac-high    # see voice list below
      - PIPER_LENGTH_SCALE=1.0           # speech rate (1.0 = normal)
      - PIPER_NOISE_SCALE=0.667
      - PIPER_NOISE_W=0.8

volumes: {}

EOF

docker compose -f ~/ai-workstation/docker/compose.voice.yml up -d
```

---

## Step 2 — Whisper Model Download

faster-whisper downloads the model on first start. To pre-download:

```bash
pip3 install huggingface_hub
huggingface-cli download Systran/faster-whisper-large-v3 \
  --local-dir /data/models/whisper/Systran/faster-whisper-large-v3
```

**Model size vs accuracy trade-off:**

| Model | VRAM | WER (English) | Speed |
|-------|------|---------------|-------|
| tiny | 1GB | High | Very fast |
| base | 1GB | Medium-high | Fast |
| medium | 3GB | Medium | Fast |
| large-v3 | 6GB | Low | ~1.5x realtime on A5500 |

`large-v3` is recommended — it fits in 6GB leaving 18GB for concurrent LLM inference on GPU0.

---

## Step 3 — Piper TTS Voice Selection

```bash
# Download voices to local storage
mkdir -p /data/models/piper/voices

# High quality English voices
wget -P /data/models/piper/voices \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/high/en_US-lessac-high.onnx
wget -P /data/models/piper/voices \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/high/en_US-lessac-high.onnx.json

# Alternative voices
wget -P /data/models/piper/voices \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high/en_US-ryan-high.onnx
wget -P /data/models/piper/voices \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high/en_US-ryan-high.onnx.json
```

Available voice catalog: https://huggingface.co/rhasspy/piper-voices/tree/main

---

## Step 4 — API Validation

```bash
# Test Whisper STT (OpenAI-compatible)
curl http://localhost:9099/v1/audio/transcriptions \
  -F file=@/path/to/test.wav \
  -F model=whisper-1

# Test with a generated WAV file
python3 -c "
import wave, struct, math
with wave.open('/tmp/test.wav', 'w') as f:
    f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000)
    for i in range(16000):
        f.writeframes(struct.pack('<h', int(32767 * math.sin(2*math.pi*440*i/16000))))
"
curl http://localhost:9099/v1/audio/transcriptions \
  -F file=@/tmp/test.wav -F model=whisper-1

# Test Piper TTS
curl http://localhost:5000/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"piper","input":"Hello, this is a test of the local text to speech system.","voice":"en_US-lessac-high"}' \
  --output /tmp/test_output.wav
aplay /tmp/test_output.wav   # or use any audio player
```

---

## Step 5 — Open WebUI Voice Integration

In Open WebUI Settings → Audio:

```
Speech to Text:
  Engine: OpenAI (compatible)
  API Base URL: http://10.10.10.2:9099/v1
  API Key: EMPTY
  Model: whisper-1

Text to Speech:
  Engine: OpenAI (compatible)
  API Base URL: http://10.10.10.2:5000/v1
  API Key: EMPTY
  Model: piper
  Voice: en_US-lessac-high
```

Test in Open WebUI:
- Click the microphone icon in the chat input
- Speak a sentence
- Verify transcription appears in the text box
- Enable voice response in settings
- Verify TTS plays back the model's response

---

## Step 6 — n8n Voice Workflow

```
Webhook (audio file upload)
  → HTTP Request to Whisper API (transcribe)
  → Extract transcript text
  → AI Agent (Ollama) with transcript as input
  → HTTP Request to Piper TTS (synthesize response)
  → Return audio file
```

This creates a fully local voice agent accessible via webhook.

---

## Step 7 — Whisper Real-Time Streaming (Optional)

For lower-latency real-time transcription using the WebSocket API:

```python
# ~/ai-workstation/scripts/whisper-realtime.py
"""Real-time transcription via faster-whisper WebSocket."""
import asyncio
import websockets
import pyaudio
import json

WHISPER_WS = "ws://localhost:9000/v1/audio/transcriptions/realtime"
SAMPLE_RATE = 16000
CHUNK_SIZE = 1024

async def transcribe_realtime():
    async with websockets.connect(WHISPER_WS) as ws:
        audio = pyaudio.PyAudio()
        stream = audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=SAMPLE_RATE,
            input=True,
            frames_per_buffer=CHUNK_SIZE
        )
        
        print("Listening... (Ctrl+C to stop)")
        try:
            while True:
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                await ws.send(data)
                
                try:
                    result = await asyncio.wait_for(ws.recv(), timeout=0.1)
                    parsed = json.loads(result)
                    if parsed.get("text"):
                        print(f"\r{parsed['text']}", end="", flush=True)
                except asyncio.TimeoutError:
                    pass
        except KeyboardInterrupt:
            pass
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()

asyncio.run(transcribe_realtime())
```

---

## Validation Checklist

- [ ] Whisper container running, model loaded (check logs for "Model loaded")
- [ ] `GET http://localhost:9099/v1/models` returns whisper model
- [ ] Audio transcription test returns correct text
- [ ] Piper TTS container running, voice model downloaded
- [ ] TTS test produces audible WAV output
- [ ] Open WebUI microphone button activates and transcribes correctly
- [ ] Open WebUI TTS plays model responses aloud
- [ ] GPU0 VRAM shows Whisper model (~6GB) loaded alongside other services

---

## Notes
- Whisper large-v3 uses ~6GB VRAM — confirm GPU0 has headroom alongside ComfyUI (which needs 8-12GB). Use medium (3GB) if running both simultaneously
- Piper TTS runs on CPU — it's fast enough (150-300ms for typical responses) without needing GPU
- VAD (Voice Activity Detection) is enabled by default in the config — it strips silence from audio before transcription, improving accuracy
- For multilingual use: set `WHISPER__LANGUAGE=null` for auto-detection; this adds ~200ms latency for language identification
- Piper voices are `.onnx` format — trained models, not synthesized. Quality is significantly better than classic TTS but varies by voice; test several before committing to one
