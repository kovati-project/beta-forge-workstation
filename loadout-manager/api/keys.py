"""API key management endpoints.

Keys are shown once, at generation. Only a SHA-256 hash and a short display
prefix are stored, in a JSON file under the persisted /data/loadout-manager
mount (mode 0600, written atomically). Older stores holding the raw key are
upgraded to hashes the first time they are read.

verify_api_key() checks a presented key and records its use. Nothing calls it
yet: no endpoint enforces API keys today (see the follow-up issue to #61).
"""

import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
import threading
from datetime import datetime, timezone
from typing import Dict, Optional
from fastapi import APIRouter, HTTPException

router = APIRouter()

# /data/loadout-manager is the volume compose.loadout.yml persists; the old
# default (/data/config) was inside the container and lost on every recreate.
KEYS_FILE = os.getenv("API_KEYS_FILE", "/data/loadout-manager/api_keys.json")

KEY_PREFIX = "nk_"
DISPLAY_PREFIX_LEN = 10          # "nk_" + 7 characters, enough to tell keys apart
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")

# The store is one JSON file that every operation reads, changes and replaces
# whole. Without mutual exclusion two overlapping operations (a generate and a
# touch, or a delete and a touch) each start from the same snapshot and the
# later write silently discards the earlier one: a new key vanishes, or a
# deleted (revoked) key comes back. Hold this lock across every
# load-modify-save, including the legacy upgrade write inside _load_keys.
# It is a plain Lock, so _load_keys/_save_keys must never take it themselves:
# callers do, once, around the whole read-modify-write.
_STORE_LOCK = threading.Lock()


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def _load_keys() -> Dict:
    """Read the store, upgrading legacy entries. The caller holds _STORE_LOCK."""
    if not os.path.exists(KEYS_FILE):
        return {}
    try:
        with open(KEYS_FILE, "r") as f:
            store = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(store, dict):
        return {}
    # Upgrade entries written by the old version, which stored the raw key.
    upgraded = False
    for meta in store.values():
        if isinstance(meta, dict) and "key" in meta:
            raw = meta.pop("key") or ""
            meta.setdefault("hash", _hash(raw))
            meta.setdefault("prefix", raw[:DISPLAY_PREFIX_LEN])
            upgraded = True
    if upgraded:
        _save_keys(store)
    return store


def _save_keys(store: Dict) -> None:
    """Write atomically with mode 0600: the file is a credential store.

    The caller holds _STORE_LOCK."""
    directory = os.path.dirname(KEYS_FILE) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".api_keys.", dir=directory)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(store, f, indent=2)
        os.chmod(tmp, 0o600)
        os.replace(tmp, KEYS_FILE)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def verify_api_key(presented: str, touch: bool = True) -> Optional[str]:
    """Name of the key matching ``presented``, or None. Updates last_used."""
    if not presented or not presented.startswith(KEY_PREFIX):
        return None
    digest = _hash(presented)
    with _STORE_LOCK:
        store = _load_keys()
        for name, meta in store.items():
            if hmac.compare_digest(meta.get("hash", ""), digest):
                if touch:
                    meta["last_used"] = _now_iso()
                    _save_keys(store)
                return name
    return None


@router.get("/keys")
async def list_api_keys() -> Dict:
    """List all API keys (metadata only; the key itself is never returned)."""
    with _STORE_LOCK:       # reading can write: legacy entries are upgraded
        store = _load_keys()
    keys = [
        {
            "name": name,
            "created": meta.get("created", "unknown"),
            "last_used": meta.get("last_used"),
            "prefix": meta.get("prefix", "") + "...",
        }
        for name, meta in store.items()
    ]
    return {"keys": keys, "count": len(keys)}


@router.post("/keys/generate")
async def generate_api_key(name: str) -> Dict:
    """Generate and persist a new API key. Returns the full key once — store it safely."""
    if not NAME_RE.match(name):
        raise HTTPException(
            status_code=400,
            detail="Key name must be 1-64 characters: letters, digits, '.', '_' or '-'")
    key = f"{KEY_PREFIX}{secrets.token_urlsafe(32)}"
    created = _now_iso()
    with _STORE_LOCK:
        store = _load_keys()
        if name in store:
            raise HTTPException(status_code=409, detail=f"Key name '{name}' already exists")
        store[name] = {"hash": _hash(key), "prefix": key[:DISPLAY_PREFIX_LEN],
                       "created": created, "last_used": None}
        _save_keys(store)

    return {"name": name, "key": key, "created": created}


@router.post("/keys/{name}/touch")
async def touch_api_key(name: str) -> Dict:
    """Update the last_used timestamp for a key."""
    with _STORE_LOCK:
        store = _load_keys()
        if name not in store:
            raise HTTPException(status_code=404, detail="Key not found")
        last_used = store[name]["last_used"] = _now_iso()
        _save_keys(store)
    return {"status": "ok", "name": name, "last_used": last_used}


@router.delete("/keys/{name}")
async def delete_api_key(name: str) -> Dict:
    """Delete an API key permanently."""
    with _STORE_LOCK:
        store = _load_keys()
        if name not in store:
            raise HTTPException(status_code=404, detail="Key not found")
        del store[name]
        _save_keys(store)
    return {"status": "deleted", "name": name}
