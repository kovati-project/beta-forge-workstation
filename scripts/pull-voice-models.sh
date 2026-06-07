#!/bin/bash
# Download voice models: Whisper STT and Piper TTS models
# Run before deploying Phase 12

set -e

echo "=== Downloading Voice Models ==="
echo ""

# Create model directories
sudo mkdir -p /data/models/whisper
sudo mkdir -p /data/models/piper/voices
sudo mkdir -p /data/audio
echo "✓ Model directories created"
echo ""

# ========== WHISPER STT MODELS ==========
echo "Whisper STT Models:"
echo "Large-v3 (recommended): 6GB VRAM, best accuracy"
echo "Medium: 3GB VRAM, good accuracy, faster"
echo "Base: 1GB VRAM, acceptable accuracy"
echo ""

# Check if huggingface_hub is installed
if ! python3 -c "import huggingface_hub" 2>/dev/null; then
    echo "Installing huggingface_hub..."
    pip3 install -q huggingface_hub
fi

echo "Downloading Whisper large-v3 model..."
huggingface-cli download Systran/faster-whisper-large-v3 \
  --local-dir /data/models/whisper/Systran/faster-whisper-large-v3 \
  --quiet
echo "✓ Whisper large-v3 downloaded (6GB)"
echo ""

# ========== PIPER TTS MODELS ==========
echo "Downloading Piper TTS voices..."
echo ""

# High quality primary voice
echo "Downloading en_US-lessac-high (recommended, female)..."
wget -q -P /data/models/piper/voices \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/high/en_US-lessac-high.onnx
wget -q -P /data/models/piper/voices \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/high/en_US-lessac-high.onnx.json
echo "✓ en_US-lessac-high downloaded"

# Alternative male voice
echo "Downloading en_US-ryan-high (male alternative)..."
wget -q -P /data/models/piper/voices \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high/en_US-ryan-high.onnx
wget -q -P /data/models/piper/voices \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ryan/high/en_US-ryan-high.onnx.json
echo "✓ en_US-ryan-high downloaded"

# Medium quality but faster
echo "Downloading en_US-lessac-medium (faster)..."
wget -q -P /data/models/piper/voices \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
wget -q -P /data/models/piper/voices \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
echo "✓ en_US-lessac-medium downloaded"

echo ""
echo "=== Voice Models Ready ==="
echo ""
echo "Downloaded models:"
echo "  Whisper: /data/models/whisper/"
echo "  Piper voices: /data/models/piper/voices/"
echo ""
echo "Next: bash scripts/deploy-phase12.sh"
