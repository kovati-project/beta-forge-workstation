"""
docker/piper-openai/piper_openai.py: the OpenAI /v1/audio/speech adapter in
front of the Wyoming-only piper container.

A fake Wyoming server (real TCP, real framing: header line, then data_length
bytes of JSON, then payload_length bytes) stands in for piper, and the adapter's
real HTTP server is driven with urllib. Also checks that the compose wiring
(Open WebUI -> piper-openai -> piper) points at ports that exist.
"""

import importlib.util
import io
import json
import socket
import threading
import urllib.error
import urllib.request
import wave
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
ADAPTER = REPO / "docker" / "piper-openai" / "piper_openai.py"

PCM = b"\x01\x00\x02\x00" * 100   # 200 frames of s16le mono
RATE = 22050


def _load_adapter():
    spec = importlib.util.spec_from_file_location("piper_openai", ADAPTER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeWyoming:
    """Minimal Wyoming piper: answers describe and synthesize."""

    def __init__(self):
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen()
        self.port = self.sock.getsockname()[1]
        self.requests = []
        self.fail_with = None
        threading.Thread(target=self._serve, daemon=True).start()

    @staticmethod
    def _event(conn, etype, data=None, payload=b""):
        header = {"type": etype}
        body = json.dumps(data).encode() if data is not None else b""
        if body:
            header["data_length"] = len(body)
        if payload:
            header["payload_length"] = len(payload)
        conn.sendall(json.dumps(header).encode() + b"\n" + body + payload)

    def _serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                line = conn.makefile("rb").readline()
                if not line:
                    continue        # health probe: connect and close
                req = json.loads(line)
                self.requests.append(req)
                if req["type"] == "describe":
                    self._event(conn, "info", {"tts": [{"name": "piper", "voices": [
                        {"name": "en_US-lessac-high", "languages": ["en_US"],
                         "description": "lessac (high)"},
                    ]}]})
                elif req["type"] == "synthesize":
                    if self.fail_with:
                        self._event(conn, "error", {"text": self.fail_with})
                        continue
                    fmt = {"rate": RATE, "width": 2, "channels": 1}
                    self._event(conn, "audio-start", fmt)
                    self._event(conn, "audio-chunk", fmt, PCM[:200])
                    self._event(conn, "audio-chunk", fmt, PCM[200:])
                    self._event(conn, "audio-stop")

    def close(self):
        self.sock.close()


@pytest.fixture
def adapter(monkeypatch):
    mod = _load_adapter()
    wy = FakeWyoming()
    monkeypatch.setattr(mod, "PIPER_HOST", "127.0.0.1")
    monkeypatch.setattr(mod, "PIPER_PORT", wy.port)
    monkeypatch.setattr(mod, "TIMEOUT", 5.0)
    httpd = mod.ThreadingHTTPServer(("127.0.0.1", 0), mod.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"

    def call(method, path, body=None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.headers.get("Content-Type"), r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("Content-Type"), e.read()

    yield mod, wy, call
    httpd.shutdown()
    httpd.server_close()
    wy.close()


def test_speech_returns_wav_from_wyoming_audio(adapter):
    _, wy, call = adapter
    # What Open WebUI's "openai" TTS engine sends.
    status, ctype, body = call("POST", "/v1/audio/speech",
                               {"model": "piper", "input": "Hello there", "voice": "alloy"})
    assert status == 200, body
    assert ctype == "audio/wav"
    with wave.open(io.BytesIO(body)) as w:
        assert (w.getframerate(), w.getsampwidth(), w.getnchannels()) == (RATE, 2, 1)
        assert w.readframes(w.getnframes()) == PCM
    # OpenAI voice names fall back to piper's own default: no voice sent.
    assert wy.requests == [{"type": "synthesize", "data": {"text": "Hello there"}}]


def test_speech_passes_piper_voice_names_through(adapter):
    _, wy, call = adapter
    status, _, _ = call("POST", "/v1/audio/speech",
                        {"input": "Hi", "voice": "en_US-ryan-high"})
    assert status == 200
    assert wy.requests[0]["data"]["voice"] == {"name": "en_US-ryan-high"}


def test_speech_pcm_format_carries_rate(adapter):
    _, _, call = adapter
    status, ctype, body = call("POST", "/v1/audio/speech",
                               {"input": "Hi", "response_format": "pcm"})
    assert status == 200
    # Open WebUI parses rate/channels from this to transcode raw PCM.
    assert ctype == f"audio/pcm;rate={RATE};channels=1"
    assert body == PCM


@pytest.mark.parametrize("body", [{}, {"input": ""}, {"input": 5},
                                  {"input": "x", "voice": "../../etc/passwd"}])
def test_speech_rejects_bad_requests(adapter, body):
    _, wy, call = adapter
    status, _, resp = call("POST", "/v1/audio/speech", body)
    assert status == 400
    assert "error" in json.loads(resp)
    assert wy.requests == []


def test_speech_piper_error_is_502(adapter):
    _, wy, call = adapter
    wy.fail_with = "voice not found"
    status, _, resp = call("POST", "/v1/audio/speech", {"input": "Hi", "voice": "xx_XX-nope-low"})
    assert status == 502
    assert "voice not found" in json.loads(resp)["error"]["message"]


def test_voices_and_models(adapter):
    mod, _, call = adapter
    status, _, body = call("GET", "/v1/audio/voices")
    assert status == 200
    assert json.loads(body) == {"default": mod.PIPER_VOICE, "voices": [
        {"name": "en_US-lessac-high", "languages": ["en_US"], "description": "lessac (high)"}]}
    status, _, body = call("GET", "/v1/models")
    assert status == 200
    assert [m["id"] for m in json.loads(body)["data"]] == ["piper"]


def test_health_follows_wyoming_port(adapter):
    mod, wy, call = adapter
    assert call("GET", "/health")[0] == 200
    wy.close()
    assert call("GET", "/health")[0] == 503


# ── compose wiring ───────────────────────────────────────────────────────────

def _compose(name):
    return yaml.safe_load((REPO / "docker" / name).read_text(encoding="utf-8"))


def _env(service):
    return dict(e.split("=", 1) for e in service.get("environment", []))


def test_open_webui_audio_points_at_voice_services():
    voice = _compose("compose.voice.yml")["services"]
    webui = _env(_compose("compose.webui.yml")["services"]["open-webui"])

    assert webui["AUDIO_TTS_ENGINE"] == "openai"
    assert webui["AUDIO_TTS_OPENAI_API_BASE_URL"] == "http://piper-openai:8000/v1"
    adapter = voice["piper-openai"]
    assert _env(adapter)["PORT"] == "8000"
    assert _env(adapter)["PIPER_HOST"] == "piper" and _env(adapter)["PIPER_PORT"] == "10200"
    assert "5000:8000" in adapter["ports"]
    assert any(v.endswith("/app/piper_openai.py:ro") and v.startswith("./piper-openai/")
               for v in adapter["volumes"])

    assert webui["AUDIO_STT_ENGINE"] == "openai"
    assert webui["AUDIO_STT_OPENAI_API_BASE_URL"] == "http://whisper:8000/v1"
    assert webui["AUDIO_STT_MODEL"] == "whisper-1"
    assert "9099:8000" in voice["whisper"]["ports"]


def test_whisper_model_has_one_source_of_truth():
    whisper = _env(_compose("compose.voice.yml")["services"]["whisper"])
    assert whisper["WHISPER__MODEL"] == "${WHISPER_MODEL:-Systran/faster-whisper-large-v3}"
    # single-underscore names are ignored by faster-whisper-server
    assert not any(k.startswith("WHISPER_") and not k.startswith("WHISPER__") for k in whisper)
    pull = (REPO / "scripts" / "pull-voice-models.sh").read_text(encoding="utf-8")
    assert "env_value WHISPER_MODEL Systran/faster-whisper-large-v3" in pull
