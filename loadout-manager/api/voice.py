"""
Voice API — Whisper STT & Piper TTS integration
Endpoints for speech-to-text and text-to-speech
"""

from fastapi import APIRouter, HTTPException, File, UploadFile
from fastapi.responses import StreamingResponse
import httpx
import os

router = APIRouter(tags=["voice"])

WHISPER_URL = os.getenv("WHISPER_URL", "http://localhost:9099")
PIPER_URL = os.getenv("PIPER_URL", "http://localhost:5000")

@router.get("/voice/status")
async def get_voice_status():
    """Check Whisper and Piper availability."""
    results = {
        "whisper": None,
        "piper": None,
    }
    
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{WHISPER_URL}/v1/models")
            if resp.status_code == 200:
                results["whisper"] = "ready"
    except Exception as e:
        results["whisper"] = f"error: {str(e)}"
    
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{PIPER_URL}/api/voices")
            if resp.status_code == 200:
                results["piper"] = "ready"
    except Exception as e:
        results["piper"] = f"error: {str(e)}"
    
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
    """Synthesize speech using Piper TTS."""
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
    """List available Piper voices."""
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
