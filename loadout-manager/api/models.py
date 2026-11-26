"""Model management API endpoints."""

import os
import threading
from pathlib import Path
from typing import Dict, List, Optional
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .envfile import read_env

router = APIRouter()

VLLM_URLS = {
    "vllm-pair-a": "http://localhost:8000",
    "vllm-pair-b": "http://localhost:8001",
    "vllm-4gpu": "http://localhost:8002",
    "vllm-embed": "http://localhost:8003",
}

VLLM_MODEL_DIR = Path("/data/models/vllm")
# Roots scanned for models already on disk (custom, fine-tuned, copied in by hand).
# Compose mounts both into the loadout-manager AND the vLLM containers at these
# same paths, so a registered model's absolute symlink resolves everywhere.
MODELS_ROOT = Path(os.getenv("LOADOUT_MODELS_ROOT", "/data/models"))
CHECKPOINTS_ROOT = Path(os.getenv("LOADOUT_CHECKPOINTS_ROOT", "/data/checkpoints"))
ENV_FILE = Path(os.getenv("ENV_FILE", "/compose/.env"))
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


@router.post("/models/load-lora")
async def load_lora(name: str) -> Dict:
    """Load a LoRA checkpoint."""
    return {
        "status": "loading",
        "lora": name,
    }


HF_API = "https://huggingface.co/api/models"


def _hf_token() -> Optional[str]:
    """HF token from the environment, else HUGGINGFACE_TOKEN in docker/.env
    (the key the Settings page manages). None when neither is set."""
    for key in ("HF_TOKEN", "HUGGINGFACE_TOKEN"):
        if os.getenv(key):
            return os.environ[key]
    try:
        return read_env(ENV_FILE).get("HUGGINGFACE_TOKEN") or None
    except OSError:
        return None


@router.get("/models/hf/search")
async def search_huggingface(q: str = "", limit: int = 20, task: Optional[str] = None) -> Dict:
    """Search the Hugging Face Hub so a repo id does not have to be known up front.

    ``task`` is a pipeline tag (text-generation, automatic-speech-recognition, ...).
    Proxied through the backend rather than called from the browser: the host has
    outbound access and the UI may not, and the HF token stays server-side.
    """
    q = (q or "").strip()
    task = (task or "").strip() or None
    if not q and not task:
        raise HTTPException(status_code=400, detail="q or task is required")
    limit = max(1, min(limit, 50))

    params = {"limit": limit, "sort": "downloads", "direction": -1}
    if q:
        params["search"] = q
    if task:
        params["filter"] = task
    headers = {}
    token = _hf_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(HF_API, params=params, headers=headers)
            r.raise_for_status()
            raw = r.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Hugging Face Hub timed out")
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Hugging Face Hub returned HTTP {e.response.status_code}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Hugging Face Hub unreachable: {e}")

    results = []
    for m in raw if isinstance(raw, list) else []:
        repo_id = m.get("id") or m.get("modelId")
        if not repo_id:
            continue
        tags = m.get("tags") or []
        results.append({
            "id": repo_id,
            "repo_id": repo_id,
            "downloads": m.get("downloads", 0),
            "likes": m.get("likes", 0),
            "pipeline_tag": m.get("pipeline_tag"),
            "tags": tags,
            "lastModified": m.get("lastModified"),
            # HF returns false, "auto" or "manual".
            "gated": bool(m.get("gated")),
            # GGUF-only repos are flagged so the UI can say vLLM will not serve them.
            "gguf": "gguf" in tags,
            # Suggested local name, so the download form can be prefilled.
            "suggested_name": repo_id.split("/")[-1].lower(),
        })
    return {"query": q, "task": task, "count": len(results), "results": results}


# ── models already on disk ────────────────────────────────────────────────────

# Under MODELS_ROOT: vllm is listed by /models/vllm/local; the others are caches
# or blob stores whose layout is not a model directory.
_SKIP_UNDER_MODELS = {"vllm", "hf-cache", "ollama"}
_SCAN_DEPTH = 4


def _model_format(d: Path) -> Optional[str]:
    """'hf' (config.json; vLLM can serve it), 'adapter' (LoRA), 'gguf' or
    'safetensors'; None when the directory does not look like a model."""
    try:
        names = [f.name for f in d.iterdir() if f.is_file()]
    except OSError:
        return None
    if "config.json" in names:
        return "hf"
    if "adapter_config.json" in names:
        return "adapter"
    if any(n.endswith(".gguf") for n in names):
        return "gguf"
    if any(n.endswith(".safetensors") for n in names):
        return "safetensors"
    return None


def _dir_size_gb(d: Path) -> float:
    total = 0
    for f in d.rglob("*"):
        try:
            if f.is_file() and not f.is_symlink():
                total += f.stat().st_size
        except OSError:
            pass
    return round(total / 1e9, 1)


def discover_local_models(roots: List[Path]) -> List[Dict]:
    """Model directories under ``roots``. A directory that qualifies is not
    descended into, so the checkpoint-N subdirs of a training run do not each
    show up next to the run."""
    found = []

    def walk(d: Path, root: Path, depth: int):
        fmt = _model_format(d) if d != root else None
        if fmt:
            found.append({
                "name": d.relative_to(root).as_posix().replace("/", "-"),
                "path": str(d),
                "root": str(root),
                "format": fmt,
                "size_gb": _dir_size_gb(d),
                "registerable": fmt == "hf",
            })
            return
        if depth >= _SCAN_DEPTH:
            return
        try:
            children = sorted(c for c in d.iterdir() if c.is_dir() and not c.is_symlink())
        except OSError:
            return
        for c in children:
            if c.name.startswith("."):
                continue
            if d == MODELS_ROOT and c.name in _SKIP_UNDER_MODELS:
                continue
            walk(c, root, depth + 1)

    for root in roots:
        if root.is_dir():
            walk(root, root, 0)
    return found


def _registered_targets() -> Dict[str, str]:
    """{target path: entry name} for models registered into VLLM_MODEL_DIR."""
    out = {}
    if VLLM_MODEL_DIR.is_dir():
        skip = set(VLLM_SLOTS.values())
        for e in VLLM_MODEL_DIR.iterdir():
            if e.is_symlink() and e.name not in skip:
                out[str(e.resolve())] = e.name
    return out


@router.get("/models/local")
async def list_local_models() -> Dict:
    """Models already on disk under the models and checkpoints roots.

    Rescanned on every call, so models copied onto the host out of band show up
    without restarting anything. POST /models/local/register makes an HF-format
    one loadable into a vLLM slot without copying or re-downloading it.
    """
    registered = _registered_targets()
    models = discover_local_models([MODELS_ROOT, CHECKPOINTS_ROOT])
    for m in models:
        m["registered_as"] = registered.get(str(Path(m["path"]).resolve()))
    return {"roots": [str(MODELS_ROOT), str(CHECKPOINTS_ROOT)], "models": models}


class RegisterRequest(BaseModel):
    path: str
    name: str


def _valid_local_name(name: str) -> bool:
    return (bool(name.strip()) and "/" not in name and "\\" not in name
            and ".." not in name and not name.startswith("."))


@router.post("/models/local/register")
async def register_local_model(req: RegisterRequest) -> Dict:
    """Link an on-disk HF-format model into VLLM_MODEL_DIR as ``name``.

    The entry is an absolute symlink to the original directory: no copy, no
    download. It resolves inside the vLLM containers because compose mounts
    MODELS_ROOT and CHECKPOINTS_ROOT there at the same paths.
    """
    name = req.name.strip()
    if not _valid_local_name(name) or name in VLLM_SLOTS.values():
        raise HTTPException(status_code=400, detail="Invalid name")

    try:
        src = Path(req.path).resolve(strict=True)
    except (OSError, RuntimeError):
        raise HTTPException(status_code=404, detail=f"Not found: {req.path}")
    roots = [r.resolve() for r in (MODELS_ROOT, CHECKPOINTS_ROOT) if r.exists()]
    if not any(src.is_relative_to(r) and src != r for r in roots):
        raise HTTPException(status_code=400,
                            detail="Path must be under the models or checkpoints root")
    if VLLM_MODEL_DIR.exists() and src.is_relative_to(VLLM_MODEL_DIR.resolve()):
        raise HTTPException(status_code=400, detail="Already in the vLLM model directory")
    if not src.is_dir() or _model_format(src) != "hf":
        raise HTTPException(status_code=400,
                            detail="Not an HF-format model directory (no config.json)")

    link = VLLM_MODEL_DIR / name
    if link.exists() or link.is_symlink():
        raise HTTPException(status_code=409, detail=f"{name} already exists in {VLLM_MODEL_DIR}")
    try:
        VLLM_MODEL_DIR.mkdir(parents=True, exist_ok=True)
        link.symlink_to(src, target_is_directory=True)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Symlink failed: {e}")
    return {"status": "registered", "name": name, "path": str(src)}


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
            if entry.name in skip or entry.name.startswith(".") or not entry.is_dir():
                continue
            # A symlink here is a model registered from elsewhere on disk
            # (POST /models/local/register); size it at its target.
            registered = entry.is_symlink()
            target = entry.resolve() if registered else entry
            models.append({
                "name": entry.name,
                "size_gb": _dir_size_gb(target),
                "registered_from": str(target) if registered else None,
            })

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
    """Point a vLLM slot symlink at a local model directory (or a registered one)."""
    if req.slot not in VLLM_SLOTS:
        raise HTTPException(status_code=400, detail=f"Unknown slot: {req.slot}")

    target = VLLM_MODEL_DIR / req.model
    if (not _valid_local_name(req.model) or req.model in VLLM_SLOTS.values()
            or not target.is_dir()):
        raise HTTPException(status_code=404, detail=f"Model directory not found: {req.model}")

    link = VLLM_MODEL_DIR / VLLM_SLOTS[req.slot]
    tmp = link.parent / f".{link.name}.tmp"
    try:
        if tmp.exists() or tmp.is_symlink():
            tmp.unlink()
        # Relative target (basename only): the symlink lives in the same dir as the
        # model, so it resolves both on the host AND inside the vLLM container, which
        # mounts this dir at /models. An absolute target breaks inside the container.
        # (A registered model is itself an absolute symlink to a path the vLLM
        # containers mount at the same location, so the chain still resolves.)
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
                token=_hf_token(),
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
