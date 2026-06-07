"""Model management API endpoints."""

from typing import Dict, List
import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException

router = APIRouter()

OLLAMA_URL = "http://localhost:11434"
VLLM_URLS = {
    "vllm-pair-a": "http://localhost:8000",
    "vllm-pair-b": "http://localhost:8001",
    "vllm-4gpu": "http://localhost:8002",
}


async def _ollama_request(endpoint: str, method: str = "GET", **kwargs):
    """Make async request to Ollama."""
    try:
        async with httpx.AsyncClient() as client:
            if method == "GET":
                return await client.get(f"{OLLAMA_URL}{endpoint}", **kwargs)
            elif method == "POST":
                return await client.post(f"{OLLAMA_URL}{endpoint}", **kwargs)
            elif method == "DELETE":
                return await client.delete(f"{OLLAMA_URL}{endpoint}", **kwargs)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ollama unavailable: {e}")


@router.get("/models")
async def list_models() -> Dict:
    """List all Ollama models."""
    try:
        response = await _ollama_request("/api/tags")
        data = response.json()
        
        models = []
        for model in data.get("models", []):
            models.append({
                "name": model["name"],
                "size": model.get("size", 0),
                "digest": model.get("digest", ""),
                "modified": model.get("modified_at", ""),
            })
        
        return {"models": models}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/pull")
async def pull_model(name: str, background_tasks: BackgroundTasks) -> Dict:
    """Pull a new model."""
    async def _pull():
        try:
            await _ollama_request(
                "/api/pull",
                method="POST",
                json={"name": name}
            )
        except Exception as e:
            print(f"Model pull failed: {e}")
    
    background_tasks.add_task(_pull)
    return {"status": "pulling", "model": name}


@router.delete("/models/{name}")
async def delete_model(name: str) -> Dict:
    """Delete a model."""
    try:
        response = await _ollama_request(
            "/api/delete",
            method="DELETE",
            json={"name": name}
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        
        return {"status": "deleted", "model": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/models/load-lora")
async def load_lora(name: str) -> Dict:
    """Load a LoRA checkpoint."""
    return {
        "status": "loading",
        "lora": name,
    }


@router.get("/models/vllm/models")
async def list_vllm_models(endpoint: str = "vllm-pair-a") -> Dict:
    """List models from vLLM endpoint."""
    try:
        url = VLLM_URLS.get(endpoint)
        if not url:
            raise HTTPException(status_code=400, detail=f"Unknown endpoint: {endpoint}")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{url}/v1/models")
            data = response.json()
            return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
