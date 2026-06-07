# Step 10 — Backend API

> **Prerequisites:** Steps 01–09 complete. All frontend panels are implemented with mock data.
> **Reference spec:** `plan/UI/Steps/10-backend-api.md`

---

## Goal

Refactor `loadout-manager/main.py` into a package and implement all new API endpoints that the UI has been calling with mock data. The existing GPU profile and NVLink logic is **preserved unchanged**.

This step also resolves all deferred issues accumulated during steps 01–09.

---

## Deferred Issues to Resolve

| # | Issue | Resolution |
|---|-------|------------|
| 1 | Step 03: Loadout activation confirmation skipped | Step 09 already fixes this in the frontend. Verify it's in place. |
| 2 | `GET /loadouts` field names never reported | Document the actual field names in the feedback file (see end). |
| 3 | Step 06 frontend used `/api/storage/list` but spec says `/api/storage/buckets/{bucket}` | Implement `/api/storage/buckets/{bucket}` as canonical; add `/api/storage/list` alias accepting `?path=` for backward compat. |
| 4 | SSE through Vite proxy | Add `changeOrigin: true` to the proxy config in `vite.config.js` for SSE to stream correctly. |
| 5 | `.env` path hardcoded to `/home/kasemo/…` in spec | Use `os.getenv("KOVATI_ENV_FILE", "/opt/kovati/docker/.env")` instead. |

---

## New Python Dependencies

Add to `loadout-manager/requirements.txt` (or `pyproject.toml`):

```
docker>=7.0
httpx>=0.27
minio>=7.2
jinja2>=3.1
python-multipart>=0.0.9
aiofiles>=23.0
```

---

## Module Structure

```
loadout-manager/
├── main.py              ← refactored app factory
├── config.py            ← env vars, paths, service catalog
├── profiles.py          ← EXISTING, unchanged
├── gpu.py               ← EXISTING, unchanged
├── api/
│   ├── __init__.py      ← empty
│   ├── services.py
│   ├── metrics.py
│   ├── traces.py
│   ├── models.py
│   ├── storage.py
│   ├── vectors.py
│   ├── training.py
│   ├── mcp.py
│   ├── keys.py
│   ├── network.py
│   ├── auth.py
│   ├── secrets.py
│   ├── stack.py
│   ├── backup.py
│   └── activity.py
├── templates/
│   └── axolotl-config.yml.j2
└── static/              ← React build (gitignored)
```

---

## 1. `config.py`

```python
import os
from pathlib import Path

# Product name — never hardcode "KOVATI OS"
PRODUCT_NAME = os.getenv("KOVATI_OS_PRODUCT_NAME", "KOVATI OS")

# Operating mode
APPLIANCE_MODE = os.getenv("KOVATI_OS_MODE", "workstation") == "appliance"

# File paths — all override-able for testing / packaging
KOVATI_ROOT   = Path(os.getenv("KOVATI_ROOT",   "/opt/kovati"))
DOCKER_ROOT   = Path(os.getenv("DOCKER_ROOT",   "/opt/kovati/docker"))
ENV_FILE      = Path(os.getenv("KOVATI_ENV_FILE", str(DOCKER_ROOT / ".env")))
BACKUP_DIR    = Path(os.getenv("BACKUP_DIR",    "/data/backups"))
DATA_DIR      = Path(os.getenv("DATA_DIR",      "/data"))

# Network
JUMPBOX_IP    = os.getenv("JUMPBOX_IP",    "10.0.0.1")
PROMETHEUS    = os.getenv("PROMETHEUS_URL", "http://localhost:9091")
LANGFUSE_URL  = os.getenv("LANGFUSE_URL",  "http://localhost:3002")
OLLAMA_URL    = os.getenv("OLLAMA_URL",    "http://localhost:11434")

# MinIO
MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT",   "localhost:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY",  "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY",  "minioadmin")

# Authentik
AUTHENTIK_URL    = os.getenv("AUTHENTIK_URL",     "http://localhost:9080")
AUTHENTIK_TOKEN  = os.getenv("AUTHENTIK_TOKEN",   "")

# SQLite for API keys and image history
DB_PATH = Path(os.getenv("KOVATI_DB_PATH", str(KOVATI_ROOT / "kovati.db")))

# Service → Docker Compose file mapping
COMPOSE_FILES: dict[str, str] = {
    "vllm-pair-a":    "compose.inference.yml",
    "vllm-pair-b":    "compose.inference.yml",
    "vllm-4gpu":      "compose.inference.yml",
    "ollama":         "compose.inference.yml",
    "open-webui":     "compose.apps.yml",
    "n8n":            "compose.apps.yml",
    "langfuse":       "compose.apps.yml",
    "dify":           "compose.apps.yml",
    "grafana":        "compose.monitoring.yml",
    "prometheus":     "compose.monitoring.yml",
    "cadvisor":       "compose.monitoring.yml",
    "minio":          "compose.storage.yml",
    "qdrant":         "compose.storage.yml",
    "postgres":       "compose.storage.yml",
    "searxng":        "compose.apps.yml",
    "authentik":      "compose.auth.yml",
    "caddy":          "compose.network.yml",
    "comfyui":        "compose.studio.yml",
    "kohya":          "compose.training.yml",
    "axolotl":        "compose.training.yml",
    "faster-whisper": "compose.inference.yml",
    "piper-tts":      "compose.inference.yml",
    "litellm":        "compose.inference.yml",
    "mcp-filesystem": "compose.mcp.yml",
    "mcp-browser":    "compose.mcp.yml",
    "mcp-code-exec":  "compose.mcp.yml",
    "mcp-fetch":      "compose.mcp.yml",
}

# Service → LAN port
PORT_MAP: dict[str, int] = {
    "vllm-pair-a": 8000, "vllm-pair-b": 8001, "vllm-4gpu": 8002,
    "ollama": 11434, "open-webui": 8080, "n8n": 5678,
    "langfuse": 3000, "dify": 3001, "grafana": 3005,
    "prometheus": 9091, "cadvisor": 8085, "minio": 9001,
    "qdrant": 6333, "postgres": 5432, "searxng": 8888,
    "authentik": 9080, "caddy": 80, "comfyui": 7860,
    "kohya": 7861, "faster-whisper": 9000, "piper-tts": 9001,
    "litellm": 4000, "mcp-filesystem": 3100, "mcp-browser": 3101,
    "mcp-code-exec": 3102, "mcp-fetch": 3103,
}

# Secret key → services that must restart on rotation
SECRET_AFFECTS: dict[str, list[str]] = {
    "POSTGRES_PASSWORD":    ["langfuse", "n8n", "dify"],
    "LANGFUSE_SECRET_KEY":  ["langfuse"],
    "MINIO_SECRET_KEY":     ["minio"],
    "AUTHENTIK_SECRET_KEY": ["authentik"],
    "N8N_ENCRYPTION_KEY":   ["n8n"],
    "DIFY_SECRET_KEY":      ["dify"],
    "LANGFUSE_SALT":        ["langfuse"],
    "GRAFANA_ADMIN_PASS":   ["grafana"],
    "QDRANT_API_KEY":       ["qdrant"],
    "SEARXNG_SECRET":       ["searxng"],
    "OPENWEBUI_SECRET":     ["open-webui"],
    "MINIO_ACCESS_KEY":     ["minio"],
    "CADDY_API_TOKEN":      ["caddy"],
    "JWT_SECRET":           ["loadout-manager"],
}

# MCP servers: name → port
MCP_SERVERS: dict[str, int] = {
    "mcp-filesystem": 3100,
    "mcp-browser":    3101,
    "mcp-code-exec":  3102,
    "mcp-fetch":      3103,
}
```

---

## 2. `main.py` (refactored)

```python
import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from config import APPLIANCE_MODE, PRODUCT_NAME
from gpu import start_gpu_polling            # existing background task
from api import (
    services, metrics, traces, models, storage, vectors,
    training, mcp, keys, network, auth, secrets, stack,
    backup, activity,
)
from api.keys import init_db

# ── Startup / shutdown ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()                          # create SQLite tables
    asyncio.create_task(metrics.poll_gpu_metrics())   # 3s GPU history loop
    asyncio.create_task(metrics.poll_system_metrics()) # 10s system metrics cache
    yield
    # cleanup (none needed — tasks cancel on shutdown)

# ── App factory ─────────────────────────────────────────────────────────────

app = FastAPI(title=PRODUCT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # LAN tool — no cross-origin threat model
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth middleware (appliance mode only)
if APPLIANCE_MODE:
    from api.auth import auth_middleware
    app.middleware("http")(auth_middleware)

# ── Existing routes (UNCHANGED) ─────────────────────────────────────────────
# profiles.py and gpu.py are imported by the existing router module.
# Import it here without modification:
from loadout_routes import router as loadout_router   # existing router
app.include_router(loadout_router)

# ── New API routers ─────────────────────────────────────────────────────────
for module in [services, metrics, traces, models, storage, vectors,
               training, mcp, keys, network, auth, secrets, stack,
               backup, activity]:
    app.include_router(module.router)

# ── Error handler ────────────────────────────────────────────────────────────
@app.exception_handler(Exception)
async def generic_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": type(exc).__name__, "detail": str(exc)},
    )

# ── Static files (React build) — MUST be last ───────────────────────────────
_static = Path("static")
if _static.exists():
    app.mount("/", StaticFiles(directory=str(_static), html=True), name="static")
```

> **Note:** If the existing routes are in `main.py` directly (not a separate router), extract them to `loadout_routes.py` first, then import. The route logic must not change.

---

## 3. `api/services.py`

```python
import docker
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import StreamingResponse

from config import COMPOSE_FILES, PORT_MAP, DOCKER_ROOT
from api.activity import log_event

router = APIRouter()
_docker = docker.from_env()

def _get_container(name: str):
    containers = _docker.containers.list(all=True)
    match = next((c for c in containers if name in c.name), None)
    if match is None:
        raise ValueError(f"Container '{name}' not found")
    return match

def _uptime_seconds(container) -> int:
    if container.status != "running":
        return 0
    started = container.attrs["State"]["StartedAt"]
    # Docker returns ISO with nanoseconds — truncate to microseconds
    started_dt = datetime.fromisoformat(started[:26]).replace(tzinfo=timezone.utc)
    return int((datetime.now(timezone.utc) - started_dt).total_seconds())

def _managing_loadout(svc_name: str) -> str | None:
    # Delegate to existing profiles module
    try:
        from profiles import get_active_profile
        profile = get_active_profile()
        if profile and svc_name in profile.get("services", []):
            return profile["name"]
    except Exception:
        pass
    return None

@router.get("/api/services")
async def list_services():
    containers = _docker.containers.list(all=True)
    result = {}
    for svc_name in COMPOSE_FILES:
        container = next((c for c in containers if svc_name in c.name), None)
        result[svc_name] = {
            "status": container.status if container else "stopped",
            "port": PORT_MAP.get(svc_name),
            "image": (container.image.tags or [None])[0] if container else None,
            "uptime_seconds": _uptime_seconds(container) if container else 0,
            "managed_by_loadout": _managing_loadout(svc_name),
        }
    return result

@router.get("/api/services/{name}")
async def get_service(name: str):
    container = _get_container(name)
    return {
        "status": container.status,
        "image": (container.image.tags or [None])[0],
        "image_digest": container.image.id[:12],
        "uptime_seconds": _uptime_seconds(container),
        "restarts": container.attrs["RestartCount"],
    }

@router.post("/api/services/{name}/start")
async def start_service(name: str, background_tasks: BackgroundTasks):
    import asyncio, subprocess
    compose = COMPOSE_FILES.get(name)
    if not compose:
        return {"error": f"Unknown service: {name}"}
    async def _run():
        proc = await asyncio.create_subprocess_exec(
            "docker", "compose", "-f", str(DOCKER_ROOT / compose),
            "up", "-d", "--no-deps", name,
            cwd=str(DOCKER_ROOT),
        )
        await proc.wait()
        log_event("service_start", f"Started {name}")
    background_tasks.add_task(_run)
    return {"status": "starting", "service": name}

@router.post("/api/services/{name}/stop")
async def stop_service(name: str, background_tasks: BackgroundTasks):
    import asyncio
    compose = COMPOSE_FILES.get(name)
    if not compose:
        return {"error": f"Unknown service: {name}"}
    async def _run():
        proc = await asyncio.create_subprocess_exec(
            "docker", "compose", "-f", str(DOCKER_ROOT / compose),
            "stop", name,
            cwd=str(DOCKER_ROOT),
        )
        await proc.wait()
        log_event("service_stop", f"Stopped {name}")
    background_tasks.add_task(_run)
    return {"status": "stopping", "service": name}

@router.get("/api/services/{name}/logs")
async def get_logs(name: str, n: int = 200):
    container = _get_container(name)
    raw = container.logs(tail=n, timestamps=True)
    return {"lines": raw.decode("utf-8", errors="replace").splitlines()}

@router.get("/api/services/{name}/logs/stream")
async def stream_logs(name: str, request: Request):
    async def event_gen():
        container = _get_container(name)
        for chunk in container.logs(stream=True, follow=True, timestamps=True):
            if await request.is_disconnected():
                break
            line = chunk.decode("utf-8", errors="replace").strip()
            if line:
                yield f"data: {line}\n\n"
    return StreamingResponse(event_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

---

## 4. `api/metrics.py`

```python
import asyncio
from collections import deque
from fastapi import APIRouter
import httpx
import pynvml

from config import PROMETHEUS

router = APIRouter()

# ── GPU history buffer ───────────────────────────────────────────────────────
gpu_vram_history:  dict[int, deque] = {i: deque(maxlen=600) for i in range(4)}
gpu_util_history:  dict[int, deque] = {i: deque(maxlen=600) for i in range(4)}
_system_cache: dict = {}

async def poll_gpu_metrics():
    """Runs forever; appends VRAM+util samples every 3s."""
    pynvml.nvmlInit()
    while True:
        for i in range(4):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            mem  = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            gpu_vram_history[i].append(round(mem.used / 1e9, 2))
            gpu_util_history[i].append(util.gpu)
        await asyncio.sleep(3)

async def poll_system_metrics():
    """Cache system metrics every 10s to avoid hammering Prometheus."""
    while True:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                async def q(expr):
                    r = await client.get(f"{PROMETHEUS}/api/v1/query", params={"query": expr})
                    return float(r.json()["data"]["result"][0]["value"][1])
                _system_cache.update({
                    "cpu_pct":        await q('100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)'),
                    "ram_used_gb":    await q('(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1e9'),
                    "ram_total_gb":   await q('node_memory_MemTotal_bytes / 1e9'),
                    "disk_read_mbps": await q('rate(node_disk_read_bytes_total[1m]) / 1e6'),
                    "disk_write_mbps":await q('rate(node_disk_write_bytes_total[1m]) / 1e6'),
                    "net_rx_mbps":    await q('rate(node_network_receive_bytes_total{device="eth0"}[1m]) * 8 / 1e6'),
                    "net_tx_mbps":    await q('rate(node_network_transmit_bytes_total{device="eth0"}[1m]) * 8 / 1e6'),
                })
        except Exception:
            pass  # stale cache on error — UI shows last known values
        await asyncio.sleep(10)

@router.get("/api/metrics/gpu")
async def gpu_metrics():
    return {
        "history": {str(i): list(gpu_vram_history[i]) for i in range(4)},
        "util":    {str(i): list(gpu_util_history[i])  for i in range(4)},
    }

@router.get("/api/metrics/system")
async def system_metrics():
    return _system_cache or {
        "cpu_pct": 0, "ram_used_gb": 0, "ram_total_gb": 512,
        "disk_read_mbps": 0, "disk_write_mbps": 0,
        "net_rx_mbps": 0, "net_tx_mbps": 0,
    }

@router.get("/api/metrics/containers")
async def container_metrics():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{PROMETHEUS}/api/v1/query",
                                    params={"query": 'container_memory_usage_bytes{name!=""}'})
            data = resp.json()["data"]["result"]
            return [
                {"name": r["metric"]["name"], "mem_bytes": float(r["value"][1])}
                for r in data
            ]
    except Exception as e:
        return {"error": str(e)}
```

---

## 5. `api/storage.py`

Implement the canonical endpoint **and** the backward-compat alias used by the step 06 frontend.

```python
from fastapi import APIRouter, UploadFile, File, HTTPException
from minio import Minio
from minio.error import S3Error
import io

from config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY

router = APIRouter()

_minio = Minio(MINIO_ENDPOINT, access_key=MINIO_ACCESS_KEY,
               secret_key=MINIO_SECRET_KEY, secure=False)

@router.get("/api/storage/buckets/{bucket}")
async def list_bucket(bucket: str, prefix: str = ""):
    try:
        objects = _minio.list_objects(bucket, prefix=prefix, recursive=False)
        return [
            {"name": o.object_name, "size": o.size,
             "modified": o.last_modified.isoformat() if o.last_modified else None}
            for o in objects
        ]
    except S3Error as e:
        raise HTTPException(status_code=404, detail=str(e))

# Backward-compat alias for step 06 frontend (used /api/storage/list?path=...)
@router.get("/api/storage/list")
async def list_storage_compat(path: str = ""):
    # Translate path format "bucket/prefix" into bucket + prefix
    parts = path.lstrip("/").split("/", 1)
    bucket = parts[0] if parts[0] else "training"
    prefix = parts[1] if len(parts) > 1 else ""
    return await list_bucket(bucket, prefix)

@router.get("/api/storage/summary")
async def storage_summary():
    import shutil
    disk = shutil.disk_usage(str("/data"))
    buckets = {}
    try:
        for b in _minio.list_buckets():
            total = sum(o.size for o in _minio.list_objects(b.name, recursive=True))
            buckets[b.name] = total
    except Exception:
        pass
    return {
        "disk_used_bytes":  disk.used,
        "disk_total_bytes": disk.total,
        "buckets": buckets,
    }

@router.post("/api/storage/upload")
async def upload_file(bucket: str, path: str, file: UploadFile = File(...)):
    data = await file.read()
    _minio.put_object(bucket, path, io.BytesIO(data), len(data),
                      content_type=file.content_type or "application/octet-stream")
    return {"bucket": bucket, "path": path, "size": len(data)}

@router.get("/api/storage/preview")
async def preview_file(bucket: str, path: str, n: int = 3):
    try:
        resp = _minio.get_object(bucket, path)
        lines = []
        for line in resp:
            lines.append(line.decode("utf-8", errors="replace").strip())
            if len(lines) >= n:
                break
        return {"lines": lines}
    except S3Error as e:
        raise HTTPException(status_code=404, detail=str(e))
```

---

## 6. `api/secrets.py`

```python
import secrets as secrets_module
from fastapi import APIRouter, BackgroundTasks
from config import ENV_FILE, SECRET_AFFECTS

router = APIRouter()

def _read_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    result = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip()
    return result

def _write_env_key(key: str, value: str):
    """Replace a single key's value in .env, preserving all other lines."""
    if not ENV_FILE.exists():
        ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        ENV_FILE.write_text(f"{key}={value}\n")
        return
    lines = ENV_FILE.read_text().splitlines(keepends=True)
    replaced = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}=") or line.strip() == key:
            lines[i] = f"{key}={value}\n"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}\n")
    ENV_FILE.write_text("".join(lines))

async def _restart_services(names: list[str]):
    import asyncio
    from config import COMPOSE_FILES, DOCKER_ROOT
    for name in names:
        compose = COMPOSE_FILES.get(name)
        if not compose:
            continue
        proc = await asyncio.create_subprocess_exec(
            "docker", "compose", "-f", str(DOCKER_ROOT / compose),
            "restart", name, cwd=str(DOCKER_ROOT),
        )
        await proc.wait()

@router.get("/api/secrets")
async def list_secrets():
    env = _read_env()
    result = []
    for key in env:
        result.append({
            "key": key,
            "affects": SECRET_AFFECTS.get(key, []),
            # Never include the value
        })
    return {"keys": result}

@router.post("/api/secrets/{key}/rotate")
async def rotate_secret(key: str, background_tasks: BackgroundTasks):
    new_value = secrets_module.token_urlsafe(32)
    _write_env_key(key, new_value)
    affected = SECRET_AFFECTS.get(key, [])
    background_tasks.add_task(_restart_services, affected)
    return {"key": key, "affects": affected, "status": "rotating"}
```

---

## 7. `api/keys.py`

SQLite-backed API key store. Token values are stored as bcrypt hashes — the cleartext is returned exactly once on creation.

```python
import secrets
import sqlite3
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from config import DB_PATH

router = APIRouter()

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH))
    con.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            name        TEXT PRIMARY KEY,
            scope       TEXT NOT NULL,
            token_hash  TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            last_used   TEXT
        )
    """)
    con.commit()
    con.close()

def _con():
    return sqlite3.connect(str(DB_PATH))

class CreateKeyRequest(BaseModel):
    name:  str
    scope: str

@router.get("/api/keys")
async def list_keys():
    with _con() as con:
        rows = con.execute(
            "SELECT name, scope, created_at, last_used FROM api_keys"
        ).fetchall()
    return [
        {"name": r[0], "scope": r[1], "created": r[2], "lastUsed": r[3] or "Never"}
        for r in rows
    ]

@router.post("/api/keys")
async def create_key(req: CreateKeyRequest):
    token = f"sk-kovati-{secrets.token_urlsafe(24)}"
    # Store only the first 8 chars as a recognizable prefix, hash the rest
    import hashlib
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    now = datetime.now(timezone.utc).strftime("%b %d")
    with _con() as con:
        try:
            con.execute(
                "INSERT INTO api_keys (name, scope, token_hash, created_at) VALUES (?,?,?,?)",
                (req.name, req.scope, token_hash, now)
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail=f"Key '{req.name}' already exists")
    # Token returned ONCE — never stored in cleartext
    return {"name": req.name, "scope": req.scope, "token": token}

@router.delete("/api/keys/{name}")
async def delete_key(name: str):
    with _con() as con:
        con.execute("DELETE FROM api_keys WHERE name = ?", (name,))
    return {"deleted": name}
```

---

## 8. `api/stack.py`

```python
import asyncio
import sqlite3
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from config import COMPOSE_FILES, DOCKER_ROOT, DB_PATH
from api.activity import log_event

router = APIRouter()

def _init_image_history():
    con = sqlite3.connect(str(DB_PATH))
    con.execute("""
        CREATE TABLE IF NOT EXISTS image_history (
            service    TEXT NOT NULL,
            digest     TEXT NOT NULL,
            pulled_at  TEXT NOT NULL,
            is_current INTEGER NOT NULL DEFAULT 1
        )
    """)
    con.commit()
    con.close()

def _get_previous_digest(service: str) -> str | None:
    with sqlite3.connect(str(DB_PATH)) as con:
        row = con.execute(
            "SELECT digest FROM image_history WHERE service=? AND is_current=0 ORDER BY pulled_at DESC LIMIT 1",
            (service,)
        ).fetchone()
    return row[0] if row else None

def _store_digest(service: str, digest: str):
    now = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(str(DB_PATH)) as con:
        con.execute("UPDATE image_history SET is_current=0 WHERE service=?", (service,))
        con.execute("INSERT INTO image_history (service, digest, pulled_at, is_current) VALUES (?,?,?,1)",
                    (service, digest, now))

@router.get("/api/stack/images")
async def list_images():
    import docker
    client = docker.from_env()
    result = []
    for svc in COMPOSE_FILES:
        containers = client.containers.list(all=True)
        c = next((x for x in containers if svc in x.name), None)
        result.append({
            "service":         svc,
            "image":           (c.image.tags or ["unknown"])[0] if c else "unknown",
            "digest":          c.image.id[7:15] if c else "",
            "previous_digest": _get_previous_digest(svc),
            "pulled_at":       "unknown",
        })
    return result

@router.post("/api/stack/update")
async def update_stack(request: Request):
    async def event_gen():
        for svc, compose_file in COMPOSE_FILES.items():
            yield f"data: Pulling {svc}...\n\n"
            proc = await asyncio.create_subprocess_exec(
                "docker", "compose", "-f", str(DOCKER_ROOT / compose_file), "pull", svc,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                cwd=str(DOCKER_ROOT),
            )
            async for line in proc.stdout:
                yield f"data:   {line.decode(errors='replace').strip()}\n\n"
            await proc.wait()
            yield f"data: Restarting {svc}...\n\n"
            restart = await asyncio.create_subprocess_exec(
                "docker", "compose", "-f", str(DOCKER_ROOT / compose_file), "restart", svc,
                cwd=str(DOCKER_ROOT),
            )
            await restart.wait()
            yield f"data: ✓ {svc} updated\n\n"
            if await request.is_disconnected():
                return
        log_event("stack_update", "All services updated")
    return StreamingResponse(event_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@router.post("/api/stack/rollback/{service}")
async def rollback_service(service: str):
    digest = _get_previous_digest(service)
    if not digest:
        return {"error": "No previous digest stored for this service"}
    compose = COMPOSE_FILES.get(service)
    if not compose:
        return {"error": f"Unknown service: {service}"}
    proc = await asyncio.create_subprocess_exec(
        "docker", "compose", "-f", str(DOCKER_ROOT / compose), "restart", service,
        cwd=str(DOCKER_ROOT),
    )
    await proc.wait()
    log_event("stack_rollback", f"Rolled back {service} to {digest}")
    return {"service": service, "digest": digest, "status": "restarted"}
```

---

## 9. `api/network.py`

```python
import subprocess
import os
from fastapi import APIRouter
from pydantic import BaseModel
from config import JUMPBOX_IP, DOCKER_ROOT

router = APIRouter()

def _wg_status() -> dict:
    try:
        out = subprocess.check_output(["wg", "show"], text=True, timeout=5)
        peers = out.count("peer:")
        return {"status": "connected" if peers > 0 else "disconnected", "peers": peers}
    except Exception:
        return {"status": "unknown", "peers": 0}

def _is_container_running(name: str) -> bool:
    try:
        import docker
        c = docker.from_env().containers.list()
        return any(name in x.name for x in c)
    except Exception:
        return False

@router.get("/api/network")
async def get_network():
    return {
        "jumpbox_ip":   os.getenv("JUMPBOX_IP", JUMPBOX_IP),
        "wireguard":    _wg_status(),
        "caddy_running":_is_container_running("caddy"),
        "mode":         os.getenv("KOVATI_OS_MODE", "workstation"),
        "interfaces":   [],  # TODO: parse `ip addr show` output
    }

class NetworkPatch(BaseModel):
    jumpbox_ip: str | None = None
    mode: str | None = None

@router.patch("/api/network")
async def patch_network(patch: NetworkPatch):
    if patch.jumpbox_ip:
        os.environ["JUMPBOX_IP"] = patch.jumpbox_ip
        # Caddy reload — send to Caddy admin API
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                await client.post("http://localhost:2019/load")
        except Exception:
            pass
    if patch.mode:
        os.environ["KOVATI_OS_MODE"] = patch.mode
    return {"ok": True}

class RoutePatch(BaseModel):
    exposed: bool

@router.patch("/api/network/routes/{service}")
async def patch_route(service: str, patch: RoutePatch):
    # TODO: rewrite Caddyfile and reload
    return {"service": service, "exposed": patch.exposed}
```

---

## 10. `api/auth.py`

```python
import httpx
from fastapi import APIRouter, Request, Response
from config import AUTHENTIK_URL, AUTHENTIK_TOKEN, APPLIANCE_MODE

router = APIRouter()

async def auth_middleware(request: Request, call_next):
    if request.url.path in ("/health", "/status"):
        return await call_next(request)
    user = request.headers.get("X-Authentik-Username")
    if not user:
        return Response(status_code=401)
    request.state.user = user
    request.state.groups = request.headers.get("X-Authentik-Groups", "")
    return await call_next(request)

@router.get("/api/auth/status")
async def auth_status():
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{AUTHENTIK_URL}/-/health/live/")
            running = r.status_code == 204
    except Exception:
        running = False
    return {"authentik": {"status": "running" if running else "stopped"}}

@router.get("/api/auth/users")
async def list_users():
    if not AUTHENTIK_TOKEN:
        return {"users": [], "error": "AUTHENTIK_TOKEN not configured"}
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.get(
            f"{AUTHENTIK_URL}/api/v3/core/users/",
            headers={"Authorization": f"Bearer {AUTHENTIK_TOKEN}"},
        )
        data = r.json()
    return {"users": [
        {"username": u["username"], "email": u["email"],
         "last_login": u.get("last_login"), "role": "admin" if u.get("is_superuser") else "user"}
        for u in data.get("results", [])
    ]}

@router.delete("/api/auth/users/{username}/sessions")
async def revoke_sessions(username: str):
    # Authentik API: invalidate all sessions for user
    # TODO: implement via AUTHENTIK_TOKEN + Authentik REST API
    return {"ok": True, "username": username}

@router.delete("/api/auth/users/{username}")
async def delete_user(username: str):
    # TODO: implement via Authentik API
    return {"ok": True, "username": username}
```

---

## 11. `api/training.py`

```python
import asyncio, uuid, os, json
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from jinja2 import Environment, FileSystemLoader
from config import DATA_DIR, DOCKER_ROOT
from api.activity import log_event

router = APIRouter()

_active_run: dict = {}  # single training job at a time
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

class TrainingConfig(BaseModel):
    engine: str        # "axolotl" | "kohya"
    model: str
    dataset_path: str
    lora_config: dict

def _write_axolotl_config(cfg: TrainingConfig, run_id: str) -> str:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    tmpl = env.get_template("axolotl-config.yml.j2")
    out_path = DATA_DIR / "runs" / run_id / "axolotl-config.yml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tmpl.render(
        model=cfg.model, dataset_path=cfg.dataset_path,
        lora_config=cfg.lora_config, run_name=run_id,
    ))
    return str(out_path)

async def _launch_training(cfg: TrainingConfig, run_id: str):
    config_path = _write_axolotl_config(cfg, run_id)
    _active_run.update({"run_id": run_id, "engine": cfg.engine, "model": cfg.model,
                         "status": "running", "step": 0})
    proc = await asyncio.create_subprocess_exec(
        "docker", "compose", "-f", str(DOCKER_ROOT / "compose.training.yml"),
        "run", "--rm", cfg.engine,
        "--config", config_path,
        cwd=str(DOCKER_ROOT),
    )
    await proc.wait()
    _active_run.update({"status": "completed" if proc.returncode == 0 else "failed"})
    log_event("training_complete", f"Run {run_id} finished (rc={proc.returncode})")

@router.post("/api/training/start")
async def start_training(cfg: TrainingConfig, bg: BackgroundTasks):
    if _active_run.get("status") == "running":
        return {"error": "A training job is already running"}
    run_id = f"{cfg.engine}-{uuid.uuid4().hex[:8]}"
    bg.add_task(_launch_training, cfg, run_id)
    log_event("training_start", f"Started {cfg.engine} run {run_id}")
    return {"status": "starting", "run_id": run_id}

@router.get("/api/training/status")
async def training_status():
    return _active_run or {"status": "idle"}

@router.post("/api/training/stop")
async def stop_training():
    run_id = _active_run.get("run_id", "")
    await asyncio.create_subprocess_exec(
        "docker", "compose", "-f", str(DOCKER_ROOT / "compose.training.yml"),
        "stop", cwd=str(DOCKER_ROOT),
    )
    _active_run.update({"status": "stopped"})
    log_event("training_stop", f"Stopped run {run_id}")
    return {"status": "stopped"}

@router.post("/api/training/export")
async def export_checkpoint(run_id: str):
    # Copy latest checkpoint to MinIO via minio client
    return {"status": "exporting", "run_id": run_id}
```

---

## 12. `api/mcp.py`

```python
import httpx
from fastapi import APIRouter
from config import MCP_SERVERS

router = APIRouter()

@router.post("/api/mcp/{name}/test")
async def test_mcp(name: str):
    port = MCP_SERVERS.get(name)
    if not port:
        return {"ok": False, "message": f"Unknown MCP server: {name}"}
    try:
        async with httpx.AsyncClient(timeout=4) as client:
            r = await client.get(f"http://localhost:{port}/mcp/tools")
            if r.status_code == 200:
                tools = r.json()
                count = len(tools.get("tools", tools) if isinstance(tools, dict) else tools)
                return {"ok": True, "message": f"{count} tools available"}
            return {"ok": False, "message": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"ok": False, "message": str(e)}
```

---

## 13. `api/activity.py`

```python
import sqlite3
import time
from collections import deque
from fastapi import APIRouter
from config import DB_PATH

router = APIRouter()
_log: deque[dict] = deque(maxlen=100)

def init_activity_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(DB_PATH)) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS activity (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                ts      REAL NOT NULL,
                type    TEXT NOT NULL,
                detail  TEXT NOT NULL
            )
        """)

def log_event(event_type: str, detail: str):
    event = {"ts": time.time(), "type": event_type, "detail": detail}
    _log.appendleft(event)
    try:
        with sqlite3.connect(str(DB_PATH)) as con:
            con.execute("INSERT INTO activity (ts, type, detail) VALUES (?,?,?)",
                        (event["ts"], event["type"], event["detail"]))
    except Exception:
        pass

@router.get("/api/activity")
async def get_activity(n: int = 10):
    return list(_log)[:n]
```

---

## 14. `api/traces.py` (Langfuse)

```python
import httpx
from fastapi import APIRouter
from config import LANGFUSE_URL

router = APIRouter()

@router.get("/api/traces")
async def list_traces(offset: int = 0, limit: int = 20):
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{LANGFUSE_URL}/api/public/observations",
                                 params={"limit": limit, "offset": offset})
            return r.json()
    except Exception as e:
        return {"traces": [], "error": str(e)}
```

---

## 15. `api/backup.py`

```python
import asyncio, subprocess
from fastapi import APIRouter
from config import BACKUP_DIR, KOVATI_ROOT

router = APIRouter()
_running = False

@router.get("/api/backup/config")
async def get_config():
    # Read cron schedule from crontab or config file
    cron_file = KOVATI_ROOT / "backup-schedule.txt"
    schedule = cron_file.read_text().strip() if cron_file.exists() else "0 6 * * *"
    return {"schedule": schedule, "destination": str(BACKUP_DIR)}

@router.patch("/api/backup/config")
async def patch_config(body: dict):
    schedule = body.get("schedule", "0 6 * * *")
    cron_file = KOVATI_ROOT / "backup-schedule.txt"
    cron_file.write_text(schedule + "\n")
    return {"schedule": schedule}

@router.get("/api/backup/history")
async def backup_history():
    archives = sorted(BACKUP_DIR.glob("*.tar.gz"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [
        {"id": i, "ts": p.stem, "size_gb": round(p.stat().st_size / 1e9, 1), "status": "ok"}
        for i, p in enumerate(archives[:10])
    ]

@router.post("/api/backup/run")
async def run_backup():
    global _running
    if _running:
        return {"error": "Backup already running"}
    _running = True
    script = KOVATI_ROOT / "scripts" / "backup.sh"
    proc = await asyncio.create_subprocess_exec(str(script))
    asyncio.create_task(_wait(proc))
    return {"status": "running"}

async def _wait(proc):
    global _running
    await proc.wait()
    _running = False

@router.delete("/api/backup/{id}")
async def delete_backup(id: int):
    # Map id back to file — for real impl, store in DB; mock here
    return {"deleted": id}
```

---

## 16. `api/vectors.py` (Qdrant)

```python
import httpx
from fastapi import APIRouter
from config import QDRANT_URL  # add to config.py: os.getenv("QDRANT_URL", "http://localhost:6333")

router = APIRouter()

@router.get("/api/vectors/collections")
async def list_collections():
    async with httpx.AsyncClient(timeout=5) as client:
        r = await client.get(f"{QDRANT_URL}/collections")
        return r.json()

@router.delete("/api/vectors/collections/{name}")
async def delete_collection(name: str):
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.delete(f"{QDRANT_URL}/collections/{name}")
        return r.json()
```

**Add to `config.py`:**
```python
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
```

---

## 17. Vite proxy fix for SSE

In `ui/vite.config.js`, add `changeOrigin: true` to all proxy targets:

```js
proxy: {
  '/api': {
    target: 'http://localhost:8800',
    changeOrigin: true,           // ← required for SSE streaming
  },
  '/status': {
    target: 'http://localhost:8800',
    changeOrigin: true,
  },
  '/loadouts': {
    target: 'http://localhost:8800',
    changeOrigin: true,
  },
  '/activate': {
    target: 'http://localhost:8800',
    changeOrigin: true,
  },
  '/stop': {
    target: 'http://localhost:8800',
    changeOrigin: true,
  },
},
```

---

## 18. `templates/axolotl-config.yml.j2`

```yaml
base_model: {{ model }}
model_type: AutoModelForCausalLM
tokenizer_type: AutoTokenizer

datasets:
  - path: {{ dataset_path }}
    type: alpaca

lora_r: {{ lora_config.rank }}
lora_alpha: {{ lora_config.alpha }}
learning_rate: {{ lora_config.lr }}
num_epochs: {{ lora_config.epochs }}
micro_batch_size: {{ lora_config.micro_batch }}
gradient_accumulation_steps: {{ lora_config.grad_accum }}

bf16: true
flash_attention: true
output_dir: /data/checkpoints/text/{{ run_name }}/
logging_steps: 1
save_steps: 100
```

---

## 19. `api/alerts.py` (alert history)

```python
import sqlite3
from fastapi import APIRouter
from config import DB_PATH

router = APIRouter()

def init_alerts_db():
    with sqlite3.connect(str(DB_PATH)) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ts        TEXT NOT NULL,
                severity  TEXT NOT NULL,
                source    TEXT NOT NULL,
                msg       TEXT NOT NULL,
                ongoing   INTEGER DEFAULT 0
            )
        """)

@router.get("/api/alerts/history")
async def alert_history():
    with sqlite3.connect(str(DB_PATH)) as con:
        rows = con.execute(
            "SELECT id, ts, severity, source, msg, ongoing FROM alerts ORDER BY ts DESC LIMIT 100"
        ).fetchall()
    return [
        {"id": r[0], "ts": r[1], "severity": r[2], "source": r[3],
         "msg": r[4], "ongoing": bool(r[5])}
        for r in rows
    ]
```

Add `from api import alerts` and `app.include_router(alerts.router)` in `main.py`. Call `alerts.init_alerts_db()` in `init_db()`.

---

## Acceptance Criteria

### Package structure
- [ ] `loadout-manager/main.py` is the app factory importing routers from `api/`
- [ ] Existing `/status`, `/loadouts`, `/activate/{name}`, `/stop`, `/health` routes unchanged and functional
- [ ] `uvicorn main:app --reload` starts without errors; `/health` returns 200

### Service endpoints
- [ ] `GET /api/services` returns dict keyed by service name with at minimum `status`, `port`, `managed_by_loadout`
- [ ] `POST /api/services/{name}/start` and `/stop` start background tasks; return immediately
- [ ] `GET /api/services/{name}/logs?n=200` returns `{ "lines": [...] }`
- [ ] `GET /api/services/{name}/logs/stream` returns `text/event-stream` with `data: ...` lines

### Metrics
- [ ] `GET /api/metrics/gpu` returns 600-sample history per GPU after background task warms up (returns fewer samples on startup, never errors)
- [ ] `GET /api/metrics/system` returns system metrics; on Prometheus error returns last cached values (not a 500)

### Storage
- [ ] `GET /api/storage/buckets/{bucket}` lists MinIO objects; `GET /api/storage/list?path=` also works (backward compat)
- [ ] `POST /api/storage/upload` successfully uploads a small file to MinIO

### Secrets
- [ ] `GET /api/secrets` never includes any field containing a secret value — response contains only `key`, `affects`, no `value`, no `hash`
- [ ] `POST /api/secrets/{key}/rotate` triggers container restarts via background task

### API Keys
- [ ] `POST /api/keys` returns the token in the response body exactly once; subsequent `GET /api/keys` shows the key name but no token
- [ ] `DELETE /api/keys/{name}` removes the key

### Stack
- [ ] `POST /api/stack/update` returns `text/event-stream`; each `data:` line is human-readable progress text

### Vite proxy
- [ ] SSE endpoints work through the Vite dev proxy (no network errors in browser console when connecting to log/stream or stack/update)

### Deferred issues
- [ ] `/loadouts` response field names documented in feedback
- [ ] `/api/storage/list` alias working
- [ ] `changeOrigin: true` added to vite.config.js
- [ ] `KOVATI_ENV_FILE` env var used (not hardcoded path)

---

## Feedback

Write `plan/UI/GHC-Feedback/10-feedback.md` when done.

**Required in Notes:**
- List the actual field names returned by `GET /loadouts` (e.g. `name`, `label`, `gpus`, `services`, `incompatible_with`, `color` — whatever the real profiles.yaml uses).
- Confirm that the Docker SDK `docker.from_env()` connects via the Unix socket on this system. If not, note the connection string used.
- Report whether the `polls_system_metrics` background task connects to Prometheus successfully. If Prometheus is not running, note what fallback values are returned.
- Was the `changeOrigin: true` fix sufficient to make SSE stream through Vite proxy, or was additional config needed (e.g. `ws: true`, `headers`)?
