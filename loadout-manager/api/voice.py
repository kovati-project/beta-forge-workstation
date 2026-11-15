"""
Voice API — Whisper STT & Piper TTS integration
Endpoints for speech-to-text and text-to-speech

Backends (docker/compose.voice.yml):
  WHISPER_URL  faster-whisper-server, OpenAI-compatible HTTP (host port 9099)
  PIPER_URL    piper-openai, an OpenAI-compatible /v1/audio/speech adapter in
               front of the Wyoming-only piper container (host port 5000)
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
import httpx
import os

router = APIRouter(tags=["voice"])

WHISPER_URL = os.getenv("WHISPER_URL", "http://localhost:9099").rstrip("/")
PIPER_URL = os.getenv("PIPER_URL", "http://localhost:5000").rstrip("/")

# "whisper-1" makes faster-whisper-server use its configured WHISPER__MODEL,
# so the model is chosen in one place (WHISPER_MODEL in docker/.env).
WHISPER_MODEL_ALIAS = "whisper-1"
DEFAULT_VOICE = os.getenv("PIPER_VOICE", "en_US-lessac-high")


class SynthesizeRequest(BaseModel):
    text: str
    voice: Optional[str] = None


def _upstream_detail(name: str, resp: httpx.Response) -> str:
    return f"{name} returned HTTP {resp.status_code}: {resp.text[:200]}"


def _unreachable(name: str, e: Exception) -> HTTPException:
    return HTTPException(status_code=502, detail=f"{name} unreachable: {str(e) or type(e).__name__}")


@router.get("/voice/status")
async def get_voice_status():
    """Check Whisper and Piper availability."""
    results = {
        "whisper": None,
        "piper": None,
    }

    async with httpx.AsyncClient(timeout=3.0) as client:
        # /health is local to the server; /v1/models queries the Hugging Face
        # Hub in faster-whisper-server and can exceed the 3s timeout.
        # piper-openai's /health is 200 only when the Wyoming port answers.
        for name, url in (("whisper", WHISPER_URL), ("piper", PIPER_URL)):
            try:
                resp = await client.get(f"{url}/health")
                results[name] = "ready" if resp.status_code == 200 else f"error: HTTP {resp.status_code}"
            except Exception as e:
                results[name] = f"error: {str(e) or type(e).__name__}"

    if results["whisper"] != "ready" or results["piper"] != "ready":
        raise HTTPException(status_code=503, detail={"message": "Voice services not ready", **results})

    return results


@router.post("/voice/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe audio file using Whisper."""
    audio_data = await file.read()
    files = {"file": (file.filename or "audio.wav", audio_data,
                      file.content_type or "application/octet-stream")}
    data = {"model": WHISPER_MODEL_ALIAS}
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{WHISPER_URL}/v1/audio/transcriptions", files=files, data=data)
    except httpx.HTTPError as e:
        raise _unreachable("Whisper", e)

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=_upstream_detail("Whisper", resp))
    return resp.json()


@router.post("/voice/synthesize")
async def synthesize_speech(req: SynthesizeRequest):
    """Synthesize speech (WAV) using Piper via the OpenAI-compatible adapter.

    Body: {"text": str, "voice"?: str} (what ui/src/utils/voiceAPI.js sends).
    """
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")
    payload = {
        "model": "piper",
        "input": req.text,
        "voice": req.voice or DEFAULT_VOICE,
        "response_format": "wav",
    }
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{PIPER_URL}/v1/audio/speech", json=payload)
    except httpx.HTTPError as e:
        raise _unreachable("Piper", e)

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=_upstream_detail("Piper", resp))
    return Response(
        content=resp.content,
        media_type=resp.headers.get("content-type", "audio/wav"),
        headers={"Content-Disposition": "attachment; filename=speech.wav"},
    )


@router.get("/voice/voices")
async def list_voices():
    """List Piper voices as {name: {languages, description}}.

    The configured default voice comes first, then English voices, then the
    rest, so a UI that shows the first few keys shows useful ones.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{PIPER_URL}/v1/audio/voices")
    except httpx.HTTPError as e:
        raise _unreachable("Piper", e)
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=_upstream_detail("Piper", resp))

    body = resp.json()
    default = body.get("default") or DEFAULT_VOICE
    voices = [v for v in body.get("voices", []) if v.get("name")]

    def rank(v):
        name = v["name"]
        return (name != default, not name.startswith("en_"), name)

    return {
        v["name"]: {"languages": v.get("languages", []), "description": v.get("description", "")}
        for v in sorted(voices, key=rank)
    }


@router.get("/voice/models")
async def list_models():
    """Whisper models currently loaded on the GPU.

    Uses /api/ps, not /v1/models: in faster-whisper-server /v1/models lists
    Hugging Face Hub models by download count, which is not what is running.
    A model loads on first request and unloads after WHISPER__TTL (300 s).
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{WHISPER_URL}/api/ps")
    except httpx.HTTPError as e:
        raise _unreachable("Whisper", e)
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=_upstream_detail("Whisper", resp))
    return {"default": WHISPER_MODEL_ALIAS, "loaded": resp.json().get("models", [])}
