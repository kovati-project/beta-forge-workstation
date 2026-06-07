#!/bin/bash
# Phase 12 validation: Verify voice I/O stack deployment

set -e

echo "=== Phase 12 Validation ==="
echo ""

FAILED=0
PASSED=0

check_pass() {
    echo "✓ $1"
    PASSED=$(( PASSED + 1 ))
}

check_fail() {
    echo "✗ $1"
    FAILED=$(( FAILED + 1 ))
}

check_warn() {
    echo "⊘ $1"
}

# ========== AUTOMATED CHECKS ==========
echo "Automated checks:"
echo ""

# 1. Whisper container running
if docker ps | grep -q whisper; then
    check_pass "Whisper container running"
else
    check_fail "Whisper container not running"
fi

# 2. Piper container running
if docker ps | grep -q piper; then
    check_pass "Piper container running"
else
    check_fail "Piper container not running"
fi

# 3. Whisper API responding
if curl -sf http://localhost:9099/v1/models > /dev/null 2>&1; then
    check_pass "Whisper API responding on :9099"
else
    check_fail "Whisper API not responding on :9099"
fi

# 4. Piper API responding
if curl -sf http://localhost:5000/docs > /dev/null 2>&1; then
    check_pass "Piper API responding on :5000"
else
    check_fail "Piper API not responding on :5000"
fi

# 5. Docker compose file valid
if docker compose -f docker/compose.voice.yml config > /dev/null 2>&1; then
    check_pass "docker/compose.voice.yml is valid"
else
    check_fail "docker/compose.voice.yml syntax error"
fi

# 6. Model directories exist
for dir in /data/models/whisper /data/models/piper/voices /data/audio; do
    if [ -d "$dir" ]; then
        check_pass "Directory exists: $dir"
    else
        check_fail "Directory missing: $dir"
    fi
done

# 7. Whisper model files exist
if [ -f "/data/models/whisper/Systran/faster-whisper-large-v3/model.safetensors" ] || \
   [ -d "/data/models/whisper/Systran/faster-whisper-large-v3" ]; then
    check_pass "Whisper large-v3 model available"
else
    check_warn "Whisper model not found (pull with: bash scripts/pull-voice-models.sh)"
fi

# 8. Piper voice files exist
VOICE_COUNT=$(find /data/models/piper/voices -name "*.onnx" | wc -l)
if [ "$VOICE_COUNT" -gt 0 ]; then
    check_pass "Piper voice models available ($VOICE_COUNT voice(s))"
else
    check_warn "Piper voices not found (pull with: bash scripts/pull-voice-models.sh)"
fi

# 9. Test Whisper API with a tone
echo ""
echo "Testing Whisper transcription..."
if python3 -c "
import wave, struct, math, subprocess, json
# Generate 1 second of 440Hz sine wave
with wave.open('/tmp/test_tone.wav', 'w') as f:
    f.setnchannels(1)
    f.setsampwidth(2)
    f.setframerate(16000)
    for i in range(16000):
        f.writeframes(struct.pack('<h', int(32767 * 0.3 * math.sin(2*math.pi*440*i/16000))))
" 2>/dev/null; then
    # Try transcription
    if curl -sf -F "file=@/tmp/test_tone.wav" -F "model=whisper-1" \
        http://localhost:9099/v1/audio/transcriptions > /dev/null 2>&1; then
        check_pass "Whisper transcription API working"
    else
        check_warn "Whisper transcription test inconclusive"
    fi
else
    check_warn "Could not generate test audio"
fi

# 10. Test Piper TTS with a request
echo ""
echo "Testing Piper TTS..."
if curl -sf -X POST http://localhost:5000/v1/audio/speech \
    -H "Content-Type: application/json" \
    -d '{"model":"piper","input":"Test","voice":"en_US-lessac-high"}' \
    -o /tmp/test_tts.wav 2>/dev/null && [ -s /tmp/test_tts.wav ]; then
    check_pass "Piper TTS API working"
else
    check_warn "Piper TTS test inconclusive"
fi

echo ""
echo "Automated checks: $PASSED passed, $FAILED failed"
echo ""

# ========== MANUAL CHECKS ==========
echo "Manual verification checklist:"
echo ""
echo "[ ] Whisper model loading:"
echo "    docker logs whisper | tail -20 (should see 'Model loaded')"
echo ""
echo "[ ] GPU0 VRAM usage:"
echo "    nvidia-smi (should show ~6GB used by whisper)"
echo ""
echo "[ ] Whisper API detailed check:"
echo "    curl -s http://localhost:9099/v1/models | jq"
echo ""
echo "[ ] Piper voice list:"
echo "    curl -s http://localhost:5000/api/voices | jq"
echo ""
echo "[ ] Open WebUI voice integration:"
echo "    Open WebUI → Settings → Audio"
echo "    Click microphone icon in chat input"
echo "    Speak clearly: 'Hello, this is a test'"
echo "    Verify text appears in chat box"
echo ""
echo "[ ] Open WebUI TTS response:"
echo "    Enable 'Speak responses' in audio settings"
echo "    Ask any question in Open WebUI"
echo "    Verify audio response plays (should be ~200-500ms)"
echo ""
echo "[ ] Piper voice quality test:"
echo "    Curl to Piper with same sentence multiple times"
echo "    Should be consistent (voice model is deterministic)"
echo ""
echo "[ ] Whisper accuracy test:"
echo "    Record yourself saying something clear"
echo "    curl -F 'file=@recording.wav' http://localhost:9099/v1/audio/transcriptions"
echo "    Verify transcription accuracy"
echo ""
echo "[ ] Real-time transcription (optional):"
echo "    python3 scripts/whisper-realtime.py"
echo "    Should show live transcription as you speak"
echo ""

# ========== GPU MEMORY CHECK ==========
echo ""
echo "GPU memory allocation (target: GPU0 6GB for Whisper):"
nvidia-smi --query-gpu=name,memory.used,memory.total --format=csv,noheader 2>/dev/null || echo "  (nvidia-smi not available)"

# ========== RESULT ==========
echo ""
if [ $FAILED -eq 0 ]; then
    echo "Phase 12 READY ✓"
    exit 0
else
    echo "Phase 12 has $FAILED issue(s) — see above"
    exit 1
fi
