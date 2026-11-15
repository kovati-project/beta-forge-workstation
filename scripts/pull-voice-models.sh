#!/bin/bash
[ -n "${BASH_VERSION:-}" ] || { echo "ERROR: this script needs bash - run: bash $0" >&2; exit 1; }
# Pre-download voice models: the Whisper STT model and Piper TTS voices.
# Optional: both containers download on first use. Pre-seeding avoids a
# multi-GB download on the first transcription request.
# Run before deploying Phase 12.
#
# The Whisper model comes from WHISPER_MODEL in docker/.env (default
# Systran/faster-whisper-large-v3), the same variable compose.voice.yml passes
# to the server, so the cached model is always the one that gets loaded.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$REPO_ROOT/docker/.env"

env_value() {  # env_value NAME DEFAULT: process env, then docker/.env, then DEFAULT
    local name=$1 default=$2 val="${!1:-}"
    if [ -z "$val" ] && [ -f "$ENV_FILE" ]; then
        val=$(sed -n "s/^${name}=//p" "$ENV_FILE" | tail -1 | tr -d '"'"'"'\r')
    fi
    echo "${val:-$default}"
}

WHISPER_MODEL=$(env_value WHISPER_MODEL Systran/faster-whisper-large-v3)
PIPER_VOICE=$(env_value PIPER_VOICE en_US-lessac-high)

# The whisper container mounts /data/models/whisper at /root/.cache/huggingface,
# so the Hugging Face hub cache it reads is /data/models/whisper/hub.
WHISPER_HUB=/data/models/whisper/hub
# linuxserver/piper uses /config (= /data/models/piper) as --data-dir and
# --download-dir and looks for <voice>.onnx directly in it.
PIPER_DIR=/data/models/piper

echo "=== Downloading Voice Models ==="
echo ""

sudo mkdir -p "$WHISPER_HUB" "$PIPER_DIR" /data/audio
# The download below runs as the current user; the container runs as root and
# can still read and write the cache.
sudo chown "$(id -u):$(id -g)" "$WHISPER_HUB"
echo "✓ Model directories ready"
echo ""

# ========== WHISPER STT MODEL ==========
if ! python3 -c "import huggingface_hub" 2>/dev/null; then
    echo "Installing huggingface_hub..."
    pip3 install -q huggingface_hub
fi

echo "Downloading Whisper model $WHISPER_MODEL into $WHISPER_HUB ..."
HF_HUB_CACHE="$WHISPER_HUB" python3 - "$WHISPER_MODEL" <<'PY'
import sys
from huggingface_hub import snapshot_download
path = snapshot_download(repo_id=sys.argv[1])
print(f"  cached at {path}")
PY
echo "✓ Whisper $WHISPER_MODEL cached (large-v3 is about 3 GB)"
echo ""

# ========== PIPER TTS VOICES ==========
download_voice() {  # download_voice en_US-lessac-high
    local voice=$1 lang region name quality base
    IFS=- read -r lang name quality <<< "$voice"
    region=${lang%%_*}
    base="https://huggingface.co/rhasspy/piper-voices/resolve/main/${region}/${lang}/${name}/${quality}/${voice}"
    for ext in onnx onnx.json; do
        if [ -s "$PIPER_DIR/$voice.$ext" ]; then
            continue
        fi
        sudo wget -q -O "$PIPER_DIR/$voice.$ext" "$base.$ext"
    done
    echo "✓ $voice"
}

echo "Downloading Piper voices into $PIPER_DIR ..."
for v in "$PIPER_VOICE" en_US-ryan-high en_US-lessac-medium; do
    download_voice "$v"
done
# linuxserver/piper runs as abc (uid 911) and writes into /config.
sudo chown -R 911:911 "$PIPER_DIR"

echo ""
echo "=== Voice Models Ready ==="
echo ""
echo "  Whisper: $WHISPER_HUB (model $WHISPER_MODEL)"
echo "  Piper voices: $PIPER_DIR"
echo ""
echo "Next: bash scripts/deploy-phase12.sh"
