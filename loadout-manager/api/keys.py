"""API key management endpoints."""

import json
import os
import secrets
from datetime import datetime, timezone
from typing import Dict, Optional
from fastapi import APIRouter, HTTPException

router = APIRouter()

KEYS_FILE = os.getenv("API_KEYS_FILE", "/data/config/api_keys.json")


def _load_keys() -> Dict:
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_keys(store: Dict) -> None:
    os.makedirs(os.path.dirname(KEYS_FILE), exist_ok=True)
    with open(KEYS_FILE, "w") as f:
        json.dump(store, f, indent=2)


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@router.get("/keys")
async def list_api_keys() -> Dict:
    """List all API keys (values redacted)."""
    store = _load_keys()
    keys = [
        {
            "name": name,
            "created": meta.get("created", "unknown"),
            "last_used": meta.get("last_used"),
            "prefix": meta.get("key", "")[:10] + "...",
        }
        for name, meta in store.items()
    ]
    return {"keys": keys, "count": len(keys)}


@router.post("/keys/generate")
async def generate_api_key(name: str) -> Dict:
    """Generate and persist a new API key. Returns the full key once — store it safely."""
    store = _load_keys()
    if name in store:
        raise HTTPException(status_code=409, detail=f"Key name '{name}' already exists")

    key = f"nk_{secrets.token_urlsafe(32)}"
    store[name] = {"key": key, "created": _now_iso(), "last_used": None}
    _save_keys(store)

    return {"name": name, "key": key, "created": store[name]["created"]}


@router.post("/keys/{name}/touch")
async def touch_api_key(name: str) -> Dict:
    """Update the last_used timestamp for a key (called on each authenticated request)."""
    store = _load_keys()
    if name not in store:
        raise HTTPException(status_code=404, detail="Key not found")
    store[name]["last_used"] = _now_iso()
    _save_keys(store)
    return {"status": "ok", "name": name, "last_used": store[name]["last_used"]}


@router.delete("/keys/{name}")
async def delete_api_key(name: str) -> Dict:
    """Delete an API key permanently."""
    store = _load_keys()
    if name not in store:
        raise HTTPException(status_code=404, detail="Key not found")
    del store[name]
    _save_keys(store)
    return {"status": "deleted", "name": name}
