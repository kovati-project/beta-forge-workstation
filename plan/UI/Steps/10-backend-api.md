# KOVATI OS — Component Spec 10
## Backend API
*FastAPI extension · all routes · SSE streaming · Docker integration · auth middleware*

---

## 1. Purpose

The backend is a FastAPI application extending the existing Loadout Manager (`loadout-manager/main.py`). The existing GPU profile logic, pynvml integration, and Docker Compose orchestration are preserved unchanged. This spec covers all **new** endpoints added to support the full UI.

The backend is the only component that touches Docker, pynvml, Prometheus, Langfuse, MinIO, and Qdrant directly. The frontend never calls third-party services; all data flows through this API layer.

---

## 2. Architecture

```
Frontend (React)
    │ HTTP / SSE
    ▼
FastAPI (:8800)
    ├── /status, /loadouts, /activate, /stop, /health  (existing)
    ├── /api/services        → Docker Engine API (unix:///var/run/docker.sock)
    ├── /api/metrics         → Prometheus HTTP API (:9091)
    ├── /api/traces          → Langfuse REST API (:3002)
    ├── /api/models          → Ollama API (:11434) + vLLM (:8000, :8001, :8002)
    ├── /api/storage         → MinIO S3 API (:9000) + disk stats
    ├── /api/vectors         → Qdrant REST API (:6333)
    ├── /api/training        → Axolotl/Kohya container + log streaming
    ├── /api/mcp             → MCP server test connections
    ├── /api/keys            → In-memory/SQLite token store
    ├── /api/network         → WireGuard + Caddy management
    ├── /api/auth            → Authentik API (:9080)
    ├── /api/secrets         → docker/.env read/write
    ├── /api/stack           → Docker pull + restart + rollback
    ├── /api/backup          → backup.sh wrapper
    └── /                    → Static files (React build)
```

---

## 3. Module Structure

Split `main.py` into a package:

```
loadout-manager/
├── main.py              # App factory, mount routers, serve static
├── config.py            # Environment, paths, service catalog, port map
├── profiles.py          # Existing profile logic (unchanged)
├── gpu.py               # Existing pynvml wrapper (unchanged)
├── api/
│   ├── __init__.py
│   ├── services.py      # Docker container management
│   ├── metrics.py       # Prometheus + system stats
│   ├── traces.py        # Langfuse integration
│   ├── models.py        # Ollama + vLLM model management
│   ├── storage.py       # MinIO + disk + PostgreSQL sizes
│   ├── vectors.py       # Qdrant operations
│   ├── training.py      # Training job launch + log streaming
│   ├── mcp.py           # MCP server test
│   ├── keys.py          # API key management
│   ├── network.py       # WireGuard + Caddy + network config
│   ├── auth.py          # Authentik user management
│   ├── secrets.py       # .env read/write/rotate
│   ├── stack.py         # Docker image updates + rollback
│   ├── backup.py        # Backup job management
│   └── activity.py      # Event log
└── static/              # Built React frontend (gitignored, built by CI)
```

---

## 4. Existing Endpoints (Unchanged)

```
GET  /status           → GPU status, active profile, switching state
GET  /loadouts         → All profiles from profiles.yaml
POST /activate/{name}  → Switch loadout (async background task)
POST /stop             → Stop all managed services
GET  /health           → Basic health check
```

These are not modified. The v1.1 addition to `/status` is a new optional field `nvlink_bridge` (A or B) on each GPU object — backward compatible.

---

## 5. Service Management (`/api/services`)

```python
# api/services.py
import docker
client = docker.from_env()  # via unix socket

# Service catalog: maps UI name → Docker compose service name
SERVICE_MAP = {
    'vllm-pair-a': 'vllm-pair-a',
    'ollama': 'ollama',
    # ...
}

COMPOSE_FILES = {
    'vllm-pair-a': 'compose.inference.yml',
    'ollama': 'compose.inference.yml',
    # ...
}
```

### `GET /api/services`

Returns all services with status from Docker API.

```python
@router.get("/api/services")
async def list_services():
    containers = client.containers.list(all=True)
    result = {}
    for svc_name, docker_name in SERVICE_MAP.items():
        container = next((c for c in containers if docker_name in c.name), None)
        result[svc_name] = {
            "status": container.status if container else "stopped",
            "port": PORT_MAP[svc_name],
            "gpus": GPU_ASSIGNMENT.get(svc_name, []),
            "image": container.image.tags[0] if container else None,
            "uptime_seconds": int((datetime.now() - container.attrs['State']['StartedAt']).total_seconds()) if container and container.status == 'running' else 0,
            "cpu_pct": 0,  # from cAdvisor, populated separately
            "mem_gb": 0,
            "managed_by_loadout": _get_managing_loadout(svc_name),
            "compose_file": COMPOSE_FILES[svc_name]
        }
    return result
```

### `GET /api/services/{name}`

Returns detailed info for one service (includes image digest, full uptime, resource stats).

### `POST /api/services/{name}/start`

```python
@router.post("/api/services/{name}/start")
async def start_service(name: str, background_tasks: BackgroundTasks):
    compose_file = COMPOSE_FILES[name]
    background_tasks.add_task(
        run_compose, "up", "-d", "--no-deps", name,
        f=compose_file
    )
    return {"status": "starting", "service": name}
```

### `POST /api/services/{name}/stop`

Similar pattern with `compose down --no-deps {name}`.

### `GET /api/services/{name}/logs`

```python
@router.get("/api/services/{name}/logs")
async def get_logs(name: str, n: int = 200):
    container = _get_container(name)
    logs = container.logs(tail=n, timestamps=True).decode('utf-8')
    return {"lines": logs.splitlines()}
```

### `GET /api/services/{name}/logs/stream` (SSE)

```python
@router.get("/api/services/{name}/logs/stream")
async def stream_logs(name: str, request: Request):
    async def event_generator():
        container = _get_container(name)
        for line in container.logs(stream=True, follow=True, timestamps=True):
            if await request.is_disconnected():
                break
            yield f"data: {line.decode('utf-8').strip()}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

---

## 6. Metrics (`/api/metrics`)

### `GET /api/metrics/gpu`

Returns 30 min of GPU VRAM history at 3s resolution.

```python
# In-memory circular buffer: 600 samples per GPU (30min × 3s)
gpu_history = {i: deque(maxlen=600) for i in range(4)}

# Background task appends every 3s from pynvml
async def poll_gpu_metrics():
    while True:
        for i in range(4):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            gpu_history[i].append(mem.used / 1e9)
        await asyncio.sleep(3)

@router.get("/api/metrics/gpu")
async def gpu_history_endpoint():
    return {str(i): list(gpu_history[i]) for i in range(4)}
```

### `GET /api/metrics/system`

Proxies Prometheus queries:

```python
PROMETHEUS_BASE = "http://localhost:9091/api/v1"

@router.get("/api/metrics/system")
async def system_metrics():
    async with httpx.AsyncClient() as client:
        ram = await query_prometheus(client, 'node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes')
        cpu = await query_prometheus(client, '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)')
        disk_read = await query_prometheus(client, 'rate(node_disk_read_bytes_total[1m])')
        net_rx = await query_prometheus(client, 'rate(node_network_receive_bytes_total{device="eth0"}[1m])')
    return {"ram_used_bytes": ram, "cpu_pct": cpu, "disk_read_bps": disk_read, "net_rx_bps": net_rx}
```

### `GET /api/metrics/containers`

Queries cAdvisor-sourced metrics from Prometheus:

```python
queries = {
    "mem": 'container_memory_usage_bytes{name!=""}',
    "cpu": 'rate(container_cpu_usage_seconds_total{name!=""}[1m]) * 100',
    "restarts": 'container_restart_count',
}
```

---

## 7. Training (`/api/training`)

### `POST /api/training/start`

```python
@dataclass
class TrainingConfig:
    engine: str  # "axolotl" | "unsloth" | "kohya"
    model: str
    dataset_path: str
    lora_config: dict

@router.post("/api/training/start")
async def start_training(cfg: TrainingConfig, background_tasks: BackgroundTasks):
    # 1. Validate profile switch if needed
    # 2. Generate config file from template
    # 3. Start container with config volume-mounted
    config_path = _write_training_config(cfg)
    background_tasks.add_task(_launch_training_container, cfg.engine, config_path)
    return {"status": "starting", "run_id": run_id}
```

### Config Generation

For Axolotl, generate `axolotl-config.yml` from Jinja2 template:

```yaml
# templates/axolotl-config.yml.j2
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

output_dir: /data/checkpoints/text/{{ run_name }}/
```

### `GET /api/training/status`

Returns whether a training job is active, its run metadata, and parsed metrics (step, loss, ETA).

### `POST /api/training/stop`

Sends `SIGTERM` to the training container, waits for graceful shutdown.

### `POST /api/training/export`

Copies the latest checkpoint to the canonical MinIO path.

---

## 8. Storage (`/api/storage`)

### MinIO Integration

```python
from minio import Minio
minio_client = Minio("localhost:9000",
    access_key=os.getenv("MINIO_ACCESS_KEY"),
    secret_key=os.getenv("MINIO_SECRET_KEY"),
    secure=False
)

@router.get("/api/storage/buckets/{bucket}")
async def list_bucket(bucket: str, prefix: str = ""):
    objects = minio_client.list_objects(bucket, prefix=prefix, recursive=False)
    return [{"name": o.object_name, "size": o.size, "modified": o.last_modified} for o in objects]
```

### `POST /api/storage/upload`

Multipart upload via `python-multipart`. Streams directly to MinIO using `put_object`.

### `GET /api/storage/preview`

Fetches first N bytes of a file from MinIO, parses JSONL, returns first N records.

### `GET /api/storage/summary`

Aggregates MinIO bucket sizes, PostgreSQL database sizes (via `pg_database_size()`), and disk usage (`shutil.disk_usage('/data')`).

---

## 9. Secrets (`/api/secrets`)

```python
ENV_FILE = Path("/home/kasemo/ai-workstation/docker/.env")

@router.get("/api/secrets")
async def list_secrets():
    lines = ENV_FILE.read_text().splitlines()
    keys = [l.split('=')[0] for l in lines if '=' in l and not l.startswith('#')]
    return {"keys": keys}  # Never return values

@router.post("/api/secrets/{key}/rotate")
async def rotate_secret(key: str, background_tasks: BackgroundTasks):
    new_value = secrets.token_urlsafe(32)
    _update_env_file(key, new_value)
    affected = AFFECTS_MAP[key]  # static map of key → service names
    background_tasks.add_task(_restart_services, affected)
    return {"key": key, "affects": affected, "status": "rotating"}
```

`_update_env_file` uses a line-by-line replace preserving comments and ordering.

---

## 10. Stack Management (`/api/stack`)

### `POST /api/stack/update`

Returns an SSE stream:

```python
@router.post("/api/stack/update")
async def update_stack(request: Request):
    async def event_gen():
        for svc, compose_file in COMPOSE_FILES.items():
            yield f"data: Pulling {svc}...\n\n"
            proc = await asyncio.create_subprocess_exec(
                "docker", "compose", "-f", compose_file, "pull", svc,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )
            async for line in proc.stdout:
                yield f"data: {line.decode().strip()}\n\n"
            # Record new digest
            _store_image_digest(svc)
            # Restart
            yield f"data: Restarting {svc}...\n\n"
            await _restart_service(svc)
            yield f"data: ✓ {svc} updated\n\n"
    return StreamingResponse(event_gen(), media_type="text/event-stream")
```

### Image Digest Store

SQLite table (simple, no ORM):

```sql
CREATE TABLE image_history (
    service TEXT,
    digest TEXT,
    pulled_at TIMESTAMP,
    is_current BOOLEAN
);
```

Rollback: queries previous digest → `docker pull {image}@{digest}` → restart.

---

## 11. Network & Caddy (`/api/network`)

### `GET /api/network`

```python
@router.get("/api/network")
async def get_network():
    wg_status = _get_wireguard_status()  # parse `wg show` output
    caddy_routes = _parse_caddyfile()
    return {
        "jumpbox_ip": os.getenv("JUMPBOX_IP"),
        "wireguard": wg_status,
        "caddy_running": _is_container_running("caddy"),
        "routes": caddy_routes,
        "interfaces": _get_network_interfaces(),  # ip addr show
        "mode": os.getenv("KOVATI_OS_MODE", "workstation")
    }
```

### `PATCH /api/network/routes/{service}`

Rewrites the Caddyfile entry for a service and sends `docker exec caddy caddy reload`.

---

## 12. Activity Log (`/api/activity`)

In-memory deque (last 100 events). Persisted to SQLite on write.

```python
activity_log = deque(maxlen=100)

def log_event(event_type: str, detail: str):
    event = {"ts": time.time(), "type": event_type, "detail": detail}
    activity_log.appendleft(event)
    db_insert_event(event)

# Called from: activate(), stop(), training/start, training/stop, backup/run, stack/update
```

`GET /api/activity` returns the last 10 (configurable with `?n=` param).

---

## 13. Auth Middleware

### JWT / Session Validation

In workstation mode: No auth by default. Optional: enable API key check via `X-API-Key` header.

In appliance mode: Authentik forward-auth. The Caddy reverse proxy sends `X-Authentik-*` headers. The FastAPI middleware validates these:

```python
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    if APPLIANCE_MODE:
        user = request.headers.get("X-Authentik-Username")
        if not user and not request.url.path.startswith("/health"):
            return Response(status_code=401)
        request.state.user = user
        request.state.role = request.headers.get("X-Authentik-Groups", "user")
    return await call_next(request)
```

### Role Gating

Settings panel destructive actions check role:

```python
def require_admin(request: Request):
    if APPLIANCE_MODE and request.state.role != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
```

Applied via FastAPI `Depends()` on sensitive routes.

---

## 14. CORS & Static Files

```python
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app.add_middleware(CORSMiddleware,
    allow_origins=["*"],  # LAN tool — no cross-origin threat model
    allow_methods=["*"],
    allow_headers=["*"]
)

# Serve React build last (catch-all)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

React Router uses hash routing (`/#/...`) so all routes resolve to `index.html` without server-side config.

---

## 15. Error Handling

All API routes return consistent error envelopes:

```python
class APIError(BaseModel):
    error: str
    detail: str | None = None
    service: str | None = None

# FastAPI exception handler
@app.exception_handler(Exception)
async def generic_handler(request, exc):
    return JSONResponse(status_code=500,
        content={"error": type(exc).__name__, "detail": str(exc)})
```

Docker-related errors (container not found, daemon unreachable) are caught and returned as `503 Service Unavailable` with a human-readable message — not raw Docker SDK stack traces.

---

## 16. Dependencies

```toml
# pyproject.toml additions to existing Loadout Manager deps
[tool.poetry.dependencies]
fastapi = ">=0.111"
uvicorn = {extras = ["standard"]}
docker = ">=7.0"         # Docker SDK for Python
httpx = ">=0.27"         # Async HTTP for Prometheus/Langfuse/Ollama
minio = ">=7.2"          # MinIO S3 client
jinja2 = ">=3.1"         # Training config templating
pynvml = ">=11.5"        # Existing
python-multipart = ">=0.0.9"  # File uploads
```
