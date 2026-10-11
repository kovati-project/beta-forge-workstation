"""
Voice API — Whisper STT & Piper TTS integration
Endpoints for speech-to-text and text-to-speech
"""

from fastapi import APIRouter, HTTPException, File, UploadFile
from fastapi.responses import StreamingResponse
import asyncio
import httpx
import os
from urllib.parse import urlparse

router = APIRouter(tags=["voice"])

WHISPER_URL = os.getenv("WHISPER_URL", "http://localhost:9099")
PIPER_URL = os.getenv("PIPER_URL", "http://localhost:5000")

# Piper (ghcr.io/linuxserver/piper) serves the Wyoming protocol over raw TCP,
# not HTTP. Liveness is a TCP connect to host:port. Host/port default to the
# ones in PIPER_URL so existing deployments keep working; override with
# PIPER_HOST / PIPER_PORT if needed.
_piper_parsed = urlparse(PIPER_URL if "//" in PIPER_URL else f"//{PIPER_URL}")
PIPER_HOST = os.getenv("PIPER_HOST") or _piper_parsed.hostname or "localhost"
PIPER_PORT = int(os.getenv("PIPER_PORT") or _piper_parsed.port or 5000)


async def _tcp_alive(host: str, port: int, timeout: float = 3.0) -> None:
    """Open and immediately close a TCP connection; raise on failure/timeout."""
    _, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port), timeout=timeout
    )
    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


@router.get("/voice/status")
async def get_voice_status():
    """Check Whisper and Piper availability."""
    results = {
        "whisper": None,
        "piper": None,
    }

    try:
        # /health is local to the server; /v1/models queries the Hugging Face
        # Hub in faster-whisper-server and can exceed the 3s timeout.
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{WHISPER_URL}/health")
            if resp.status_code == 200:
                results["whisper"] = "ready"
    except Exception as e:
        results["whisper"] = f"error: {str(e) or type(e).__name__}"

    try:
        await _tcp_alive(PIPER_HOST, PIPER_PORT)
        results["piper"] = "ready"
    except Exception as e:
        results["piper"] = f"error: {str(e) or type(e).__name__}"

    if results["whisper"] != "ready" or results["piper"] != "ready":
        raise HTTPException(status_code=503, detail="Voice services not ready")
    
    return results

@router.post("/voice/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe audio file using Whisper."""
    try:
        audio_data = await file.read()
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            files = {"file": (file.filename, audio_data, file.content_type)}
            data = {"model": "whisper-1"}
            
            resp = await client.post(
                f"{WHISPER_URL}/v1/audio/transcriptions",
                files=files,
                data=data
            )
            
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Whisper transcription failed")
            
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")

@router.post("/voice/synthesize")
async def synthesize_speech(text: str, voice: str = "en_US-lessac-high"):
    """Synthesize speech using Piper TTS.

    NOTE: known broken. Piper speaks Wyoming (raw TCP), so this HTTP call to
    /api/tts cannot succeed. Needs a Wyoming client or a different TTS backend
    (see issue #38).
    """
    try:
        payload = {
            "text": text,
            "voice": voice,
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{PIPER_URL}/api/tts",
                json=payload,
            )
            
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Piper synthesis failed")
            
            return StreamingResponse(
                iter([resp.content]),
                media_type="audio/wav",
                headers={"Content-Disposition": "attachment; filename=speech.wav"}
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Synthesis error: {str(e)}")

@router.get("/voice/voices")
async def list_voices():
    """List available Piper voices.

    NOTE: known broken for the same reason as /voice/synthesize: Piper has no
    HTTP /api/voices endpoint (Wyoming `describe` returns the voice list).
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{PIPER_URL}/api/voices")
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Failed to fetch voices")
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice listing error: {str(e)}")

@router.get("/voice/models")
async def list_models():
    """List available Whisper models."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{WHISPER_URL}/v1/models")
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail="Failed to fetch models")
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model listing error: {str(e)}")
