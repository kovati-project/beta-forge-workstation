#!/bin/bash
# Phase 12 deployment: Voice I/O Stack
# Deploys Whisper STT and Piper TTS with OpenAI-compatible APIs

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/container-helpers.sh
source "$REPO_ROOT/scripts/lib/container-helpers.sh"

echo "=== Phase 12: Voice I/O ==="
echo ""

# Verify Phase 03 (vLLM) and Phase 05 (Open WebUI) for context
echo "Checking dependencies..."

if ! curl -sf http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "WARNING: Ollama not running (optional, but recommended for voice agent)"
else
    echo "✓ Ollama running"
fi

if ! curl -sf http://localhost:3000 > /dev/null 2>&1; then
    echo "WARNING: Open WebUI not running (needed for voice integration)"
else
    echo "✓ Open WebUI running"
fi
echo ""

# Verify docker compose file
if [ ! -f "docker/compose.voice.yml" ]; then
    echo "ERROR: docker/compose.voice.yml not found"
    exit 1
fi

# Create storage directories
echo "Creating storage directories..."
sudo mkdir -p /data/models/whisper
sudo mkdir -p /data/models/piper/voices
sudo mkdir -p /data/audio
sudo chmod -R 755 /data/audio
echo "✓ Directories created"
echo ""

# Check if models are available
if [ ! -d "/data/models/whisper/Systran" ]; then
    echo "WARNING: Whisper model not found"
    echo "Pull models first: bash scripts/pull-voice-models.sh"
fi

if [ ! -f "/data/models/piper/voices/en_US-lessac-high.onnx" ]; then
    echo "WARNING: Piper voice not found"
    echo "Pull models first: bash scripts/pull-voice-models.sh"
fi
echo ""

# Validate docker compose
echo "Validating compose file..."
if docker compose -f docker/compose.voice.yml config > /dev/null 2>&1; then
    echo "✓ docker/compose.voice.yml valid"
else
    echo "✗ docker/compose.voice.yml has errors"
    exit 1
fi
echo ""

# Start voice services
echo "Starting voice services..."
remove_orphan whisper ai-voice
remove_orphan piper ai-voice
docker compose -f docker/compose.voice.yml up -d
echo "✓ Voice services starting"
echo ""

# Wait for services to initialize
echo "Waiting for services to initialize..."
for i in {1..30}; do
    if curl -sf http://localhost:9099/v1/models > /dev/null 2>&1; then
        break
    fi
    if [ $i -eq 30 ]; then
        echo "WARNING: Whisper still initializing"
    fi
    sleep 1
done

echo ""
echo "Waiting for Piper..."
for i in {1..20}; do
    if curl -sf http://localhost:5000/docs > /dev/null 2>&1; then
        break
    fi
    if [ $i -eq 20 ]; then
        echo "WARNING: Piper still initializing"
    fi
    sleep 1
done

echo ""
echo "Verifying services..."
if curl -sf http://localhost:9099/v1/models > /dev/null 2>&1; then
    echo "✓ Whisper STT responding on :9099"
else
    echo "⊘ Whisper STT initializing (might need more time)"
fi

if curl -sf http://localhost:5000/docs > /dev/null 2>&1; then
    echo "✓ Piper TTS responding on :5000"
else
    echo "⊘ Piper TTS initializing (might need more time)"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Voice I/O services ready:"
echo ""
echo "  Whisper STT (transcription):  http://10.10.10.2:9099"
echo "  Piper TTS (synthesis):        http://10.10.10.2:5000"
echo ""
echo "Next steps:"
echo ""
echo "1. Test Whisper (speech-to-text):"
echo "   curl http://localhost:9099/v1/models"
echo ""
echo "2. Test Piper (text-to-speech):"
echo "   curl http://localhost:5000/docs"
echo ""
echo "3. Configure Open WebUI voice:"
echo "   Settings → Audio:"
echo "     Speech to Text → OpenAI (compatible)"
echo "       API Base: http://10.10.10.2:9099/v1"
echo "       API Key: EMPTY"
echo "       Model: whisper-1"
echo "     Text to Speech → OpenAI (compatible)"
echo "       API Base: http://10.10.10.2:5000/v1"
echo "       API Key: EMPTY"
echo "       Model: piper"
echo ""
echo "4. Test voice in Open WebUI:"
echo "   Click microphone icon → speak → verify transcription"
echo "   Enable voice response to hear TTS"
echo ""
echo "5. Run validation:"
echo "   bash scripts/validate-phase12.sh"
