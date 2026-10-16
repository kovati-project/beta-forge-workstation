#!/usr/bin/env python3
"""
Loadout Manager — GPU profile orchestrator for AI workstation.
Manages Docker Compose stack switching with GPU exclusivity and VRAM awareness.
Extends with Kovati OS backend API for all frontend operations.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import subprocess
import yaml
import asyncio
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
import pynvml
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import API routers
from api import create_router

app = FastAPI(title="Loadout Manager", version="1.0.0")

# ── Middleware ───────────────────────────────────────────────────────────────

# CORS for local/LAN usage
app.add_middleware(CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
)

# Auth middleware for appliance mode
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Validate auth in appliance mode."""
    appliance_mode = os.getenv("KOVATI_OS_MODE", "workstation") == "appliance"
    
    # Allow health checks and setup endpoints without auth
    if request.url.path.startswith("/health") or request.url.path.startswith("/api/setup"):
        response = await call_next(request)
        return response
    
    if appliance_mode:
        # Check for Authentik forward-auth headers
        user = request.headers.get("X-Authentik-Username")
        if not user:
            return HTMLResponse(content="Unauthorized", status_code=401)
        request.state.user = user
        request.state.role = request.headers.get("X-Authentik-Groups", "user")
    
    response = await call_next(request)
    return response

# ── Include API Routers ──────────────────────────────────────────────────────
api_router = create_router()
app.include_router(api_router)

# ── Configuration ────────────────────────────────────────────────────────────
CONFIG_PATH = Path(__file__).parent / "profiles.yaml"
COMPOSE_BASE = Path(__file__).parent.parent / "docker"
REPO_ROOT = Path(__file__).parent

# ── State ────────────────────────────────────────────────────────────────────
STATE_PATH = Path(os.environ.get("LOADOUT_STATE_PATH", "/data/loadout-manager/state.json"))

state = {
    "active_profile": None,
    "switching": False,
    "last_switched": None,
    "running_services": []
}

_PERSISTED_KEYS = ("active_profile", "last_switched", "running_services")


def save_state() -> None:
    """Persist state to disk. Never fatal — a failed write must not break a switch."""
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {k: state[k] for k in _PERSISTED_KEYS}
        # Write via a temp file in the same directory so a crash mid-write
        # cannot leave a truncated state.json behind.
        tmp = STATE_PATH.with_suffix(".json.tmp")
        with open(tmp, "w") as f:
            json.dump(payload, f)
        os.replace(tmp, STATE_PATH)
    except Exception as e:
        logger.warning(f"Could not persist state to {STATE_PATH}: {e}")


def load_state() -> None:
    """Restore state from disk at startup. Absent or corrupt file is not an error."""
    if not STATE_PATH.exists():
        logger.info(f"No persisted state at {STATE_PATH}; starting cold")
        return
    try:
        with open(STATE_PATH) as f:
            saved = json.load(f)
        if not isinstance(saved, dict):
            raise ValueError("state file is not an object")
        for k in _PERSISTED_KEYS:
            if k in saved:
                state[k] = saved[k]
        # "switching" is deliberately not restored. A switch that was in flight
        # when the process died is not in flight now, and persisting True would
        # wedge every subsequent activate/stop behind the 409 guard.
        state["switching"] = False
        logger.info(f"Restored state: active_profile={state['active_profile']}")
    except Exception as e:
        logger.warning(f"Ignoring unreadable state file {STATE_PATH}: {e}")


load_state()

def load_profiles() -> Dict:
    """Load and parse profiles.yaml."""
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)["profiles"]

# ── GPU telemetry ────────────────────────────────────────────────────────────
# NVML failure used to be swallowed and reported as an empty GPU list, which the
# UI could not tell apart from "no GPUs" (TASK-010 / #5). The reader below returns
# an explicit availability flag and error string instead. `gpus` is still always a
# list, so consumers written against the old shape keep working.

# Workload kind per service name; drives the colour of the per-GPU service tag.
# Services not listed here render with the neutral tag colour.
SERVICE_TYPES = {
    "ollama": "inference",
    "vllm-pair-a": "inference",
    "vllm-pair-b": "inference",
    "vllm-4gpu": "inference",
    "axolotl": "training",
    "kohya": "training",
    "unsloth": "training",
    "comfyui": "image",
    "invokeai": "image",
    "realesrgan": "image",
    "real-esrgan": "image",
    "rembg": "image",
}

# NVLink bridges are derived from the `inference-pair-<letter>` profiles: each
# one's two exclusive GPUs are the GPUs joined by that bridge. This matches the
# physical topology (`nvidia-smi topo -m` shows NV4 only between 0-3 and 1-2).
_PAIR_PROFILE_RE = re.compile(r"^inference-pair-([a-z])$")

# Repeated polls must not flood the log with an identical failure every 3s.
_GPU_ERROR_RELOG_SECS = 300
_gpu_last_error: Optional[str] = None
_gpu_last_error_logged = 0.0


def _log_gpu_telemetry(error: Optional[str], exc: Optional[BaseException] = None) -> None:
    """Log availability transitions; re-log a persisting failure only occasionally."""
    global _gpu_last_error, _gpu_last_error_logged
    if error is None:
        if _gpu_last_error is not None:
            logger.info(f"GPU telemetry recovered (was: {_gpu_last_error})")
            _gpu_last_error = None
        return
    now = time.monotonic()
    if error != _gpu_last_error or now - _gpu_last_error_logged >= _GPU_ERROR_RELOG_SECS:
        logger.error(f"GPU telemetry unavailable: {error}", exc_info=exc)
        _gpu_last_error = error
        _gpu_last_error_logged = now


def _gpu_unavailable(stage: str, exc: Optional[BaseException] = None,
                     message: Optional[str] = None) -> Dict:
    if message is None:
        message = f"{type(exc).__name__}: {exc}"
    error = f"{stage}: {message}"[:300]
    _log_gpu_telemetry(error, exc)
    return {"available": False, "gpus": [], "error": error}


def read_gpu_telemetry() -> Dict:
    """Read raw per-GPU metrics from NVML.

    Returns {"available": bool, "gpus": [...], "error": str | None}. When NVML
    cannot be initialised, enumerated or queried, `available` is False, `gpus`
    is [] and `error` says why. Zero visible devices is also reported as
    unavailable: on this workstation it means the container cannot see the GPUs.
    """
    try:
        pynvml.nvmlInit()
    except Exception as e:
        return _gpu_unavailable("nvmlInit", e)

    stage = "enumerate devices"
    try:
        count = pynvml.nvmlDeviceGetCount()
        if count == 0:
            return _gpu_unavailable(
                stage, message="NVML initialised but reports 0 GPU devices "
                               "(check NVIDIA_VISIBLE_DEVICES and the device reservation)")
        gpus = []
        for i in range(count):
            stage = f"query GPU {i}"
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            try:
                power_w = round(pynvml.nvmlDeviceGetPowerUsage(handle) / 1000, 1)
            except Exception:
                power_w = 0
            try:
                _pci = pynvml.nvmlDeviceGetPciInfo(handle)
                bus_id = _pci.busId.decode() if isinstance(_pci.busId, bytes) else _pci.busId
            except Exception:
                bus_id = None
            gpus.append({
                "index": i,
                "vram_used_gb": round(mem.used / 1024**3, 1),
                "vram_total_gb": round(mem.total / 1024**3, 1),
                "vram_free_gb": round(mem.free / 1024**3, 1),
                "utilization_pct": util.gpu,
                "temp_c": temp,
                "power_w": power_w,
                "bus_id": bus_id,
            })
    except Exception as e:
        return _gpu_unavailable(stage, e)
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass

    _log_gpu_telemetry(None)
    return {"available": True, "gpus": gpus, "error": None}


def _nvlink_bridge_labels(profiles: Dict) -> Dict[int, str]:
    """Map GPU index -> "Bridge X" from the inference-pair-X profiles."""
    labels: Dict[int, str] = {}
    for name, p in profiles.items():
        m = _PAIR_PROFILE_RE.match(name)
        if not m:
            continue
        try:
            pair = sorted({int(g) for g in (p.get("exclusive_gpus") or [])})
        except (TypeError, ValueError):
            continue
        if len(pair) != 2:
            continue
        for idx in pair:
            labels[idx] = f"Bridge {m.group(1).upper()}"
    return labels


def _annotate_gpus(gpus: List[Dict]) -> None:
    """Add topology and profile-claim fields to each GPU dict, in place.

    nvlink_bridge        "Bridge A" / "Bridge B" / None
    claimed_by_profile   active profile name if it assigns or reserves this GPU
    active_service       service(s) the active profile runs on this GPU
    service_type         inference / training / image / None

    Claims reflect the manager's own profile state, not an observed process
    list: VRAM held by something the manager did not start shows no claim.
    While a switch is in flight the previous profile is being torn down, so no
    claim is asserted. Never raises; /status must not 500 on a bad profiles.yaml.
    """
    for g in gpus:
        g.update(nvlink_bridge=None, claimed_by_profile=None,
                 active_service=None, service_type=None)
    if not gpus:
        return
    try:
        profiles = load_profiles()
    except Exception as e:
        logger.warning(f"Could not load profiles for GPU annotation: {e}")
        return

    bridges = _nvlink_bridge_labels(profiles)
    active = state["active_profile"]
    profile = None if state["switching"] else profiles.get(active)

    claimed = set()
    services_by_gpu: Dict[int, List[str]] = {}
    if profile:
        try:
            for idx in profile.get("exclusive_gpus") or []:
                claimed.add(int(idx))
            for svc, idxs in (profile.get("gpu_assignment") or {}).items():
                for idx in idxs or []:
                    claimed.add(int(idx))
                    services_by_gpu.setdefault(int(idx), []).append(svc)
        except (TypeError, ValueError) as e:
            logger.warning(f"Malformed GPU assignment in profile {active}: {e}")
            claimed, services_by_gpu = set(), {}

    for g in gpus:
        idx = g["index"]
        g["nvlink_bridge"] = bridges.get(idx)
        if idx not in claimed:
            continue
        g["claimed_by_profile"] = active
        svcs = services_by_gpu.get(idx, [])
        if svcs:
            g["active_service"] = " + ".join(svcs)
            types = {SERVICE_TYPES.get(s) for s in svcs}
            g["service_type"] = types.pop() if len(types) == 1 else None


def get_gpu_telemetry() -> Dict:
    """read_gpu_telemetry() plus topology/claim annotations on each GPU."""
    telemetry = read_gpu_telemetry()
    _annotate_gpus(telemetry["gpus"])
    return telemetry


def _telemetry_summary(telemetry: Dict) -> Dict:
    return {"available": telemetry["available"], "error": telemetry["error"]}


def get_gpu_info() -> List[Dict]:
    """GPU list only, for callers that do not need the availability signal.

    An empty list means telemetry is unavailable (or zero devices); use
    get_gpu_telemetry() when the reason matters."""
    return get_gpu_telemetry()["gpus"]

def _claim_switch() -> bool:
    """Atomically take the single switch slot. Callers must not await between
    checking and claiming, so the flag is raised the moment a request is
    accepted rather than when its background task happens to start; a second
    request arriving meanwhile then sees it and is refused."""
    if state["switching"]:
        return False
    state["switching"] = True
    return True


async def _run_blocking(*args, **kwargs):
    """subprocess.run in a worker thread. docker compose calls take up to
    minutes; on the event loop they would stall /status, /health and /ws."""
    return await asyncio.to_thread(subprocess.run, *args, **kwargs)


async def stop_all_services():
    """Stop all managed Docker Compose stacks."""
    compose_files = ["compose.inference.yml", "compose.training.yml", "compose.studio.yml"]
    for cf in compose_files:
        try:
            await _run_blocking(
                ["docker", "compose", "-f", str(COMPOSE_BASE / cf), "down"],
                capture_output=True,
                timeout=60
            )
            logger.info(f"Stopped {cf}")
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout stopping {cf}")
        except Exception as e:
            logger.error(f"Error stopping {cf}: {e}")

async def do_switch(profile_name: str):
    """Background task: switch to new profile. The caller has already claimed
    the switch slot with _claim_switch(); this releases it when done."""
    state["switching"] = True
    await broadcast_state()
    try:
        profile = load_profiles()[profile_name]
        logger.info(f"Switching to profile: {profile_name}")

        # Stop all existing services
        await stop_all_services()
        await asyncio.sleep(3)  # Allow GPU memory to release

        # Build docker compose command
        cmd = ["docker", "compose"]
        for cf in profile["compose_files"]:
            cf_name = cf.split("/")[-1]
            cmd += ["-f", str(COMPOSE_BASE / cf_name)]

        cmd += ["up", "-d", "--remove-orphans"] + profile["services"]

        # Execute
        result = await _run_blocking(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"Docker compose failed: {result.stderr}")
        
        state["active_profile"] = profile_name
        state["running_services"] = profile["services"]
        state["last_switched"] = time.time()
        save_state()
        logger.info(f"Successfully activated profile: {profile_name}")
        
    except Exception as e:
        logger.error(f"Profile switch failed: {e}")
        state["active_profile"] = None
        state["running_services"] = []
        save_state()
    finally:
        state["switching"] = False
        await broadcast_state()

# ── WebSocket event stream ───────────────────────────────────────────────────
# The UI polls /status every 3s (1s while switching). That is the whole reason a
# switch feels laggy: a state change is invisible for up to a full interval. This
# pushes transitions instead. Polling still works and is left in place as a
# fallback for clients that cannot hold a socket open.

_ws_clients = set()


def _state_event() -> Dict:
    return {
        "type": "state",
        "active_profile": state["active_profile"],
        "switching": state["switching"],
        "last_switched": state["last_switched"],
        "running_services": state["running_services"],
    }


async def broadcast_state() -> None:
    """Push current state to every connected client, dropping any that fail."""
    if not _ws_clients:
        return
    event = _state_event()
    for ws in list(_ws_clients):
        try:
            await ws.send_json(event)
        except Exception:
            # A send failure means the peer is gone; discard rather than retry.
            _ws_clients.discard(ws)


@app.websocket("/ws")
async def ws_events(websocket: WebSocket):
    """Event stream. Sends current state on connect, then on every transition."""
    await websocket.accept()
    _ws_clients.add(websocket)
    try:
        await websocket.send_json(_state_event())
        while True:
            # There is no client->server protocol yet. Receiving parks the
            # coroutine and gives us a disconnect signal without a poll loop.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"WebSocket closed: {e}")
    finally:
        _ws_clients.discard(websocket)


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/loadouts")
def list_loadouts():
    """List all available loadout profiles."""
    profiles = load_profiles()
    return {
        name: {
            "description": p.get("description", ""),
            "services": p.get("services", []),
            "exclusive_gpus": p.get("exclusive_gpus", []),
            "vram_required_gb": p.get("vram_required_gb"),
            "compatible_with": p.get("compatible_with", []),
            "incompatible_with": p.get("incompatible_with", []),
            "active": name == state["active_profile"]
        }
        for name, p in profiles.items()
    }

@app.get("/status")
def get_status():
    """Get current system and profile status.

    `gpus` is always a list. `gpu_telemetry.available` is false (with `error`)
    when NVML could not be read; `gpus` is then [] because there is no data,
    not because the hardware is idle.
    """
    telemetry = get_gpu_telemetry()
    return {
        "active_profile": state["active_profile"],
        "switching": state["switching"],
        "last_switched": state["last_switched"],
        "running_services": state["running_services"],
        "gpus": telemetry["gpus"],
        "gpu_telemetry": _telemetry_summary(telemetry),
    }

@app.post("/activate/{profile_name}")
async def activate_profile(profile_name: str, background_tasks: BackgroundTasks):
    """Activate a profile (background task)."""
    profiles = load_profiles()
    
    if profile_name not in profiles:
        raise HTTPException(404, f"Profile '{profile_name}' not found")
    if state["switching"]:
        raise HTTPException(409, "Profile switch already in progress")
    
    profile = profiles[profile_name]
    
    # Check VRAM requirement. A requirement of 0 (e.g. idle) needs no telemetry,
    # so it must stay reachable while NVML is down.
    if (profile.get("vram_required_gb") or 0) > 0:
        telemetry = get_gpu_telemetry()
        if not telemetry["available"]:
            # Fail closed, but say why: "0.0GB free" would be a false reading.
            raise HTTPException(
                409,
                f"Cannot verify VRAM requirement: GPU telemetry unavailable ({telemetry['error']})"
            )
        total_free = sum(g["vram_free_gb"] for g in telemetry["gpus"])
        if total_free < profile["vram_required_gb"]:
            raise HTTPException(
                409,
                f"Insufficient VRAM: {total_free:.1f}GB free, {profile['vram_required_gb']}GB required"
            )
    
    # Every check above ran without awaiting, so nothing can have claimed the
    # slot since the `switching` test at the top.
    if not _claim_switch():
        raise HTTPException(409, "Profile switch already in progress")
    background_tasks.add_task(do_switch, profile_name)
    return {"message": f"Switching to '{profile_name}'", "status": "switching"}

@app.post("/stop")
async def stop_all():
    """Stop all managed services."""
    # Hold the switch slot while stopping so an activation cannot start its
    # `up` underneath our `down`.
    if not _claim_switch():
        raise HTTPException(409, "Profile switch in progress")
    try:
        await stop_all_services()
        state["active_profile"] = None
        state["running_services"] = []
        save_state()
    finally:
        state["switching"] = False
    await broadcast_state()
    return {"message": "All services stopped"}

@app.get("/health")
def health():
    """Health check with GPU info. `status` reflects the API process only;
    GPU availability is reported separately in `gpu_telemetry`."""
    telemetry = get_gpu_telemetry()
    return {"status": "ok", "gpus": telemetry["gpus"],
            "gpu_telemetry": _telemetry_summary(telemetry)}

# ── Static Files (React Build) ───────────────────────────────────────────────

STATIC_DIR = Path(__file__).parent / "static"
if (STATIC_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    logger.info(f"Serving React UI from {STATIC_DIR}")
else:
    # React build not present — serve a minimal redirect page
    logger.warning(f"React build not found at {STATIC_DIR} — run: bash scripts/deploy-ui.sh")

    @app.get("/", response_class=HTMLResponse)
    def ui_fallback():
        return """<!DOCTYPE html><html><head><title>Kovati OS</title>
<style>body{font-family:monospace;background:#0a0e27;color:#e0e0e0;display:flex;
align-items:center;justify-content:center;height:100vh;margin:0;flex-direction:column;}
h1{color:#00d9ff;}code{background:#1a1f3a;padding:.4rem .8rem;border-radius:4px;}
</style></head><body>
<h1>⚡ Kovati OS</h1>
<p>React UI not built yet.</p>
<p>On the workstation, run:</p>
<code>bash scripts/deploy-ui.sh</code>
</body></html>"""

# ── Scheduler ────────────────────────────────────────────────────────────────
# Time-based profile switching: run training overnight, drop back to inference
# in the morning, without anyone being at the keyboard.

SCHEDULE_PATH = Path(os.environ.get("LOADOUT_SCHEDULE_PATH",
                                    str(STATE_PATH.parent / "schedule.json")))

schedule: List[Dict] = []
_scheduler_task = None
_last_fired: Dict[str, str] = {}


def load_schedule() -> None:
    global schedule
    if not SCHEDULE_PATH.exists():
        return
    try:
        with open(SCHEDULE_PATH) as f:
            loaded = json.load(f)
        schedule = loaded if isinstance(loaded, list) else []
        logger.info(f"Loaded {len(schedule)} schedule entries")
    except Exception as e:
        logger.warning(f"Ignoring unreadable schedule {SCHEDULE_PATH}: {e}")
        schedule = []


def save_schedule() -> None:
    try:
        SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = SCHEDULE_PATH.with_suffix(".json.tmp")
        with open(tmp, "w") as f:
            json.dump(schedule, f)
        os.replace(tmp, SCHEDULE_PATH)
    except Exception as e:
        logger.warning(f"Could not persist schedule: {e}")


def _entry_due(entry: Dict, now) -> bool:
    """True if entry should fire at `now` and has not already fired this minute."""
    if not entry.get("enabled", True):
        return False
    if entry.get("time") != now.strftime("%H:%M"):
        return False
    days = entry.get("days")
    if days and now.weekday() not in days:
        return False
    # Guard against firing twice inside the same minute if the loop runs fast.
    stamp = now.strftime("%Y-%m-%d %H:%M")
    if _last_fired.get(entry["id"]) == stamp:
        return False
    _last_fired[entry["id"]] = stamp
    return True


async def scheduler_loop() -> None:
    """Check every 30s for entries due to fire."""
    while True:
        try:
            now = datetime.now()
            for entry in list(schedule):
                if not _entry_due(entry, now):
                    continue
                profile = entry.get("profile")
                profiles = load_profiles()
                if profile not in profiles:
                    logger.error(f"Schedule {entry['id']}: unknown profile {profile}")
                    continue
                if not _claim_switch():
                    logger.warning(f"Schedule {entry['id']}: switch already in "
                                   f"progress, skipping {profile}")
                    continue
                logger.info(f"Schedule {entry['id']} firing: activating {profile}")
                asyncio.create_task(do_switch(profile))
        except Exception as e:
            # A bad entry must never kill the loop.
            logger.error(f"Scheduler iteration failed: {e}")
        await asyncio.sleep(30)


@app.get("/schedule")
async def list_schedule():
    return {"schedule": schedule}


@app.post("/schedule")
async def add_schedule(entry: Dict):
    profile = entry.get("profile")
    at = entry.get("time")
    if not profile or not at:
        raise HTTPException(400, "profile and time are required")
    if profile not in load_profiles():
        raise HTTPException(404, f"Unknown profile '{profile}'")
    try:
        datetime.strptime(at, "%H:%M")
    except ValueError:
        raise HTTPException(400, "time must be HH:MM (24h)")
    days = entry.get("days")
    if days is not None:
        if not isinstance(days, list) or any(
                not isinstance(d, int) or d < 0 or d > 6 for d in days):
            raise HTTPException(400, "days must be a list of ints 0-6 (Mon=0)")

    new = {
        "id": f"sch-{int(time.time() * 1000)}",
        "profile": profile,
        "time": at,
        "days": days,
        "enabled": bool(entry.get("enabled", True)),
    }
    schedule.append(new)
    save_schedule()
    return new


@app.delete("/schedule/{entry_id}")
async def delete_schedule(entry_id: str):
    global schedule
    remaining = [e for e in schedule if e["id"] != entry_id]
    if len(remaining) == len(schedule):
        raise HTTPException(404, f"No schedule entry '{entry_id}'")
    schedule = remaining
    _last_fired.pop(entry_id, None)
    save_schedule()
    return {"message": f"Deleted {entry_id}"}


@app.on_event("startup")
async def _start_scheduler():
    global _scheduler_task
    load_schedule()
    _scheduler_task = asyncio.create_task(scheduler_loop())
    logger.info("Scheduler started")


# ── Startup ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8800,
        log_level="info",
        reload=False
    )
