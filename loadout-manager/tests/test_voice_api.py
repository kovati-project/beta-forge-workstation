"""
/api/voice/* request shapes against Whisper (faster-whisper-server) and the
piper-openai adapter. httpx.AsyncClient is swapped for one on a MockTransport,
so nothing leaves the process; each test asserts what voice.py sends upstream.
"""

import json

import httpx
import pytest

WAV = b"RIFF\x24\x00\x00\x00WAVEfmt fake"


@pytest.fixture
def upstream(main_module, monkeypatch):
    """Route voice.py's outbound HTTP to a handler; record every request."""
    # Imported here, not at module level: importing the `api` package pulls in
    # api/gpu.py (the shared NVML reader), which must see conftest's pynvml stub
    # that main_module installs. A collection-time import binds the real pynvml
    # for the whole session and breaks the GPU gate tests.
    from api import voice
    seen = []
    routes = {}
    real = httpx.AsyncClient

    def handler(request):
        seen.append(request)
        key = (request.method, str(request.url))
        if key not in routes:
            return httpx.Response(404, text=f"no fake for {key}")
        r = routes[key]
        return r(request) if callable(r) else r

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(voice, "WHISPER_URL", "http://whisper.test")
    monkeypatch.setattr(voice, "PIPER_URL", "http://piper.test")
    monkeypatch.setattr(voice.httpx, "AsyncClient", factory)

    class U:
        pass
    u = U()
    u.seen = seen
    u.routes = routes
    u.voice = voice
    return u


def test_transcribe_posts_multipart_with_whisper1(api, upstream):
    upstream.routes[("POST", "http://whisper.test/v1/audio/transcriptions")] = \
        httpx.Response(200, json={"text": "hello world"})

    r = api.client.post("/api/voice/transcribe",
                        files={"file": ("clip.wav", WAV, "audio/wav")})

    assert r.status_code == 200, r.text
    assert r.json() == {"text": "hello world"}
    (req,) = upstream.seen
    body = req.content
    assert req.headers["content-type"].startswith("multipart/form-data")
    # whisper-1 resolves to the server's WHISPER__MODEL: the single source of truth.
    assert b'name="model"\r\n\r\nwhisper-1' in body
    assert b'name="file"; filename="clip.wav"' in body
    assert WAV in body


def test_transcribe_upstream_error_is_502(api, upstream):
    upstream.routes[("POST", "http://whisper.test/v1/audio/transcriptions")] = \
        httpx.Response(500, text="cuda oom")
    r = api.client.post("/api/voice/transcribe",
                        files={"file": ("clip.wav", WAV, "audio/wav")})
    assert r.status_code == 502
    assert "cuda oom" in r.json()["detail"]


def test_synthesize_accepts_ui_json_body_and_calls_openai_speech(api, upstream):
    upstream.routes[("POST", "http://piper.test/v1/audio/speech")] = \
        httpx.Response(200, content=WAV, headers={"content-type": "audio/wav"})

    # Exactly what ui/src/utils/voiceAPI.js sends.
    r = api.client.post("/api/voice/synthesize",
                        json={"text": "Hi there", "voice": "en_US-ryan-high"})

    assert r.status_code == 200, r.text
    assert r.content == WAV
    assert r.headers["content-type"].startswith("audio/wav")
    (req,) = upstream.seen
    assert json.loads(req.content) == {
        "model": "piper", "input": "Hi there",
        "voice": "en_US-ryan-high", "response_format": "wav",
    }


def test_synthesize_defaults_voice(api, upstream):
    upstream.routes[("POST", "http://piper.test/v1/audio/speech")] = \
        httpx.Response(200, content=WAV, headers={"content-type": "audio/wav"})
    r = api.client.post("/api/voice/synthesize", json={"text": "Hi"})
    assert r.status_code == 200
    assert json.loads(upstream.seen[0].content)["voice"] == upstream.voice.DEFAULT_VOICE


def test_synthesize_rejects_empty_text_without_calling_piper(api, upstream):
    r = api.client.post("/api/voice/synthesize", json={"text": "   "})
    assert r.status_code == 400
    assert upstream.seen == []


def test_synthesize_upstream_error_is_502(api, upstream):
    upstream.routes[("POST", "http://piper.test/v1/audio/speech")] = \
        httpx.Response(502, json={"error": {"message": "piper synthesis failed"}})
    r = api.client.post("/api/voice/synthesize", json={"text": "Hi"})
    assert r.status_code == 502


def test_status_probes_health_on_both(api, upstream):
    upstream.routes[("GET", "http://whisper.test/health")] = httpx.Response(200, text="OK")
    upstream.routes[("GET", "http://piper.test/health")] = httpx.Response(200, json={"status": "ok"})
    r = api.client.get("/api/voice/status")
    assert r.status_code == 200
    assert r.json() == {"whisper": "ready", "piper": "ready"}
    assert [str(q.url) for q in upstream.seen] == [
        "http://whisper.test/health", "http://piper.test/health"]


def test_status_503_names_the_failing_service(api, upstream):
    upstream.routes[("GET", "http://whisper.test/health")] = httpx.Response(200, text="OK")
    upstream.routes[("GET", "http://piper.test/health")] = httpx.Response(503)
    r = api.client.get("/api/voice/status")
    assert r.status_code == 503
    detail = r.json()["detail"]
    assert detail["whisper"] == "ready"
    assert detail["piper"] == "error: HTTP 503"


def test_voices_default_first_then_english(api, upstream):
    upstream.routes[("GET", "http://piper.test/v1/audio/voices")] = httpx.Response(200, json={
        "default": "en_US-lessac-high",
        "voices": [
            {"name": "ar_JO-kareem-low", "languages": ["ar_JO"], "description": ""},
            {"name": "en_US-ryan-high", "languages": ["en_US"], "description": ""},
            {"name": "en_US-lessac-high", "languages": ["en_US"], "description": ""},
        ],
    })
    r = api.client.get("/api/voice/voices")
    assert r.status_code == 200
    assert list(r.json()) == ["en_US-lessac-high", "en_US-ryan-high", "ar_JO-kareem-low"]


def test_models_reports_loaded_not_hub_listing(api, upstream):
    upstream.routes[("GET", "http://whisper.test/api/ps")] = \
        httpx.Response(200, json={"models": ["Systran/faster-whisper-large-v3"]})
    r = api.client.get("/api/voice/models")
    assert r.status_code == 200
    assert r.json() == {"default": "whisper-1", "loaded": ["Systran/faster-whisper-large-v3"]}
    assert [str(q.url) for q in upstream.seen] == ["http://whisper.test/api/ps"]
