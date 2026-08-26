"""Model management API endpoints."""

import os
import threading
from pathlib import Path
from typing import Dict, List, Optional
import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

router = APIRouter()

OLLAMA_URL = "http://localhost:11434"
VLLM_URLS = {
    "vllm-pair-a": "http://localhost:8000",
    "vllm-pair-b": "http://localhost:8001",
    "vllm-4gpu": "http://localhost:8002",
}

VLLM_MODEL_DIR = Path("/data/models/vllm")
VLLM_SLOTS = {
    "pair-a": "current",
    "pair-b": "current-b",
    "4gpu": "large",
}
SLOT_TO_SERVICE = {
    "pair-a": "vllm-pair-a",
    "pair-b": "vllm-pair-b",
    "4gpu": "vllm-4gpu",
}

_download_state: dict = {}


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


HF_API = "https://huggingface.co/api/models"


@router.get("/models/hf/search")
async def search_huggingface(q: str, limit: int = 20, task: Optional[str] = None) -> Dict:
    """Search the Hugging Face Hub so a repo id does not have to be known up front.

    Proxied through the backend rather than called from the browser: the host has
    outbound access and the UI may not, and it keeps one place to add a token later
    for gated repos.
    """
    q = (q or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="q is required")
    limit = max(1, min(limit, 50))

    params = {"search": q, "limit": limit, "sort": "downloads", "direction": -1}
    if task:
        params["filter"] = task

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(HF_API, params=params)
            r.raise_for_status()
            raw = r.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Hugging Face Hub timed out")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Hugging Face Hub unreachable: {e}")

    results = []
    for m in raw if isinstance(raw, list) else []:
        repo_id = m.get("modelId") or m.get("id")
        if not repo_id:
            continue
        results.append({
            "repo_id": repo_id,
            "downloads": m.get("downloads", 0),
            "likes": m.get("likes", 0),
            "pipeline_tag": m.get("pipeline_tag"),
            "gated": bool(m.get("gated")),
            "updated": m.get("lastModified"),
            # Suggested local name, so the download form can be prefilled.
            "suggested_name": repo_id.split("/")[-1].lower(),
        })
    return {"query": q, "count": len(results), "results": results}


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


@router.get("/models/vllm/local")
async def list_vllm_local() -> Dict:
    """List model directories in /data/models/vllm and current slot assignments."""
    skip = set(VLLM_SLOTS.values())  # {"current", "current-b", "large"}
    models = []

    if VLLM_MODEL_DIR.exists():
        for entry in sorted(VLLM_MODEL_DIR.iterdir()):
            if entry.name in skip or not entry.is_dir() or entry.is_symlink():
                continue
            size_bytes = sum(
                f.stat().st_size for f in entry.rglob("*") if f.is_file()
            )
            models.append({"name": entry.name, "size_gb": round(size_bytes / 1e9, 1)})

    slots = {}
    for slot, link_name in VLLM_SLOTS.items():
        link = VLLM_MODEL_DIR / link_name
        try:
            target = link.resolve()
            slots[slot] = target.name if target.exists() else None
        except Exception:
            slots[slot] = None

    return {"models": models, "slots": slots}


class ActivateRequest(BaseModel):
    slot: str
    model: str


@router.post("/models/vllm/activate")
async def activate_vllm_model(req: ActivateRequest) -> Dict:
    """Point a vLLM slot symlink at a local model directory."""
    if req.slot not in VLLM_SLOTS:
        raise HTTPException(status_code=400, detail=f"Unknown slot: {req.slot}")

    target = VLLM_MODEL_DIR / req.model
    if not target.is_dir() or target.is_symlink():
        raise HTTPException(status_code=404, detail=f"Model directory not found: {req.model}")

    link = VLLM_MODEL_DIR / VLLM_SLOTS[req.slot]
    tmp = link.parent / f".{link.name}.tmp"
    try:
        if tmp.exists() or tmp.is_symlink():
            tmp.unlink()
        # Relative target (basename only): the symlink lives in the same dir as the
        # model, so it resolves both on the host AND inside the vLLM container, which
        # mounts this dir at /models. An absolute target breaks inside the container.
        tmp.symlink_to(target.name)
        os.replace(tmp, link)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Symlink update failed: {e}")

    return {"slot": req.slot, "model": req.model, "status": "active"}


class DownloadRequest(BaseModel):
    repo_id: str
    local_name: str


@router.post("/models/vllm/download")
async def download_vllm_model(req: DownloadRequest) -> Dict:
    """Download a HuggingFace model into /data/models/vllm/<local_name>."""
    if _download_state.get("status") == "running":
        raise HTTPException(status_code=409, detail="A download is already in progress")

    if "/" in req.local_name or ".." in req.local_name or not req.local_name.strip():
        raise HTTPException(status_code=400, detail="Invalid local_name")

    dest = VLLM_MODEL_DIR / req.local_name
    _download_state.clear()
    _download_state.update({
        "status": "running",
        "repo_id": req.repo_id,
        "local_name": req.local_name,
    })

    def _run():
        try:
            from huggingface_hub import snapshot_download
            snapshot_download(
                repo_id=req.repo_id,
                local_dir=str(dest),
                ignore_patterns=["*.gguf"],
            )
            _download_state["status"] = "done"
        except Exception as e:
            _download_state["status"] = "error"
            _download_state["error"] = str(e)

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "started", "repo_id": req.repo_id, "local_name": req.local_name}


@router.get("/models/vllm/download/status")
async def vllm_download_status() -> Dict:
    """Return the current download state."""
    return dict(_download_state)
