#!/usr/bin/env python3
"""
Loadout Manager — GPU profile orchestrator for AI workstation.
Manages Docker Compose stack switching with GPU exclusivity and VRAM awareness.
Extends with Kovati OS backend API for all frontend operations.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, PlainTextResponse
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
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import API routers
from api import create_router
from api.gpu import read_gpu_telemetry

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
    
    # Allow health checks and setup endpoints without auth. The Alertmanager
    # webhook is called container-to-container, never through Authentik, so it
    # carries no forward-auth headers; it can only append to the alert history.
    # /metrics is the Prometheus scrape target, likewise container-to-container
    # (prometheus -> loadout-manager:8800 over ai-workstation) and read-only.
    if (request.url.path.startswith("/health") or request.url.path.startswith("/api/setup")
            or request.url.path in ("/api/alerts/webhook", "/metrics")):
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
    "running_services": [],
    # Why the last switch or stop did not complete, or None. Not persisted:
    # it describes this process's last attempt, not the stack's state.
    "last_error": None,
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
# The NVML reader itself lives in api/gpu.py (shared with api/metrics.py); this
# section adds topology and profile-claim annotations on top of it.

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


def _nvlink_pairs(profiles: Dict) -> List[List[int]]:
    """The NVLink-bridged GPU pairs, ordered by bridge letter ([[0, 3], [1, 2]])."""
    pairs: Dict[str, List[int]] = {}
    for idx, label in _nvlink_bridge_labels(profiles).items():
        pairs.setdefault(label, []).append(idx)
    return [sorted(pairs[label]) for label in sorted(pairs)]


# Card accent per workload kind on the Loadout page; inference is the default.
_ACCENT_BY_TYPE = {"training": "amber", "image": "purple"}


def _profile_accent(p: Dict) -> str:
    """`accent` from profiles.yaml if set, else from the profile's services:
    any training service -> amber, else any image service -> purple, else cyan."""
    if p.get("accent"):
        return p["accent"]
    types = {SERVICE_TYPES.get(s) for s in p.get("services") or []}
    for kind in ("training", "image"):
        if kind in types:
            return _ACCENT_BY_TYPE[kind]
    return "cyan"


def _profile_nvlink_pairs(p: Dict, pairs: List[List[int]]) -> List[List[int]]:
    """`nvlink_pairs` from profiles.yaml if set, else the bridged pairs whose
    GPUs are both claimed by the profile."""
    if "nvlink_pairs" in p:
        return p["nvlink_pairs"] or []
    try:
        gpus = {int(g) for g in p.get("exclusive_gpus") or []}
    except (TypeError, ValueError):
        return []
    return [pair for pair in pairs if set(pair) <= gpus]


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


# ── Activation gates ─────────────────────────────────────────────────────────
# Every path that starts a profile (POST /activate, the scheduler, and do_switch
# itself after teardown) goes through these checks. They fail closed: anything
# they cannot verify is refused.

def _vram_reserve_per_gpu() -> float:
    """GiB per GPU that NVML never reports as free on an otherwise empty card
    (driver and context reservation, typically 0.3-0.5 GiB on a 24 GB card)."""
    raw = os.environ.get("LOADOUT_VRAM_RESERVE_GB_PER_GPU", "0.5")
    try:
        return max(0.0, float(raw))
    except ValueError:
        logger.warning(f"Ignoring invalid LOADOUT_VRAM_RESERVE_GB_PER_GPU={raw!r}; using 0.5")
        return 0.5


VRAM_RESERVE_GB_PER_GPU = _vram_reserve_per_gpu()


def _incompatible(a: str, b: str, profiles: Dict) -> bool:
    """Symmetric: either side declaring the other is enough."""
    return (b in (profiles.get(a) or {}).get("incompatible_with", [])
            or a in (profiles.get(b) or {}).get("incompatible_with", []))


def _check_incompatibility(profile_name: str, profiles: Dict) -> Optional[str]:
    """Refuse a target the active profile is declared incompatible with. The
    operator has to /stop the active profile first. Re-activating the active
    profile (a restart) and switching to a profile with no services (idle, the
    way out of anything) are always allowed."""
    active = state["active_profile"]
    if not active or active == profile_name:
        return None
    if not (profiles[profile_name].get("services") or []):
        return None
    if active not in profiles:
        return (f"Active profile '{active}' is not defined in profiles.yaml, so "
                f"compatibility cannot be checked; stop it first")
    if _incompatible(active, profile_name, profiles):
        return (f"Profile '{profile_name}' is incompatible with the active "
                f"profile '{active}'; stop it first")
    return None


def _check_vram(profile_name: str, profile: Dict, telemetry: Dict,
                outgoing_running: bool) -> Optional[str]:
    """Free VRAM on the profile's own GPUs must cover vram_required_gb.

    A requirement of 0 (idle) needs no telemetry. A missing requirement is
    "unknown": telemetry must still be readable, but no amount is enforced.

    `outgoing_running`: a managed profile is still up and the switch will tear
    it (all three stacks) down before starting. Its VRAM is about to be freed,
    so current free memory says nothing; only check that the requirement can
    fit on these GPUs at all. do_switch re-checks free memory after teardown.

    Headroom: the requirements in profiles.yaml are whole-card figures (48 for
    two 24 GB cards, 96 for four), but an empty card never reports all of its
    memory as free. The free-memory check therefore credits
    VRAM_RESERVE_GB_PER_GPU per GPU. Without that credit those profiles pass
    the capacity check, get the running profile torn down, and then are always
    refused after teardown. With it, the two checks agree: a switch that passes
    the capacity check fails after teardown only if something unmanaged holds
    more than the reserve.
    """
    raw = profile.get("vram_required_gb")
    try:
        required = None if raw is None else float(raw)
    except (TypeError, ValueError):
        return f"Profile '{profile_name}' has an invalid vram_required_gb: {raw!r}"
    if required is not None and required <= 0:
        return None

    if not telemetry["available"]:
        # Fail closed, but say why: "0.0GB free" would be a false reading.
        return (f"Cannot verify VRAM for '{profile_name}': GPU telemetry "
                f"unavailable ({telemetry['error']})")
    if required is None:
        logger.warning(f"Profile {profile_name} declares no vram_required_gb; "
                       f"only GPU telemetry availability was checked")
        return None

    by_index = {g["index"]: g for g in telemetry["gpus"]}
    try:
        wanted = sorted({int(i) for i in profile.get("exclusive_gpus") or []})
    except (TypeError, ValueError):
        return f"Profile '{profile_name}' has malformed exclusive_gpus"
    if not wanted:
        wanted = sorted(by_index)
    missing = [i for i in wanted if i not in by_index]
    if missing:
        return f"GPU(s) {missing} required by '{profile_name}' are not visible"

    gpus = [by_index[i] for i in wanted]
    if outgoing_running:
        capacity = sum(g["vram_total_gb"] for g in gpus)
        if capacity < required:
            return (f"Insufficient VRAM: GPUs {wanted} hold {capacity:.1f}GB in "
                    f"total, {required:g}GB required")
        return None
    free = sum(g["vram_free_gb"] for g in gpus)
    reserve = VRAM_RESERVE_GB_PER_GPU * len(gpus)
    if free + reserve < required:
        return (f"Insufficient VRAM: {free:.1f}GB free on GPUs {wanted} "
                f"(+{reserve:g}GB driver reserve), {required:g}GB required")
    return None


def validate_activation(profile_name: str, profiles: Dict) -> Optional[str]:
    """Pre-switch gate shared by POST /activate and the scheduler. Returns the
    refusal reason, or None if the activation may proceed. Never awaits, so a
    caller can check and then _claim_switch() atomically."""
    reason = _check_incompatibility(profile_name, profiles)
    if reason:
        return reason
    return _check_vram(profile_name, profiles[profile_name], get_gpu_telemetry(),
                       outgoing_running=bool(state["running_services"]))


async def _run_blocking(*args, **kwargs):
    """subprocess.run in a worker thread. docker compose calls take up to
    minutes; on the event loop they would stall /status, /health and /ws."""
    return await asyncio.to_thread(subprocess.run, *args, **kwargs)


async def stop_all_services() -> List[str]:
    """Stop all managed Docker Compose stacks. Returns a description of each
    stack that could not be confirmed stopped (empty list = all stopped)."""
    compose_files = ["compose.inference.yml", "compose.training.yml", "compose.studio.yml"]
    failures = []
    for cf in compose_files:
        try:
            result = await _run_blocking(
                ["docker", "compose", "-f", str(COMPOSE_BASE / cf), "down"],
                capture_output=True,
                text=True,
                timeout=60
            )
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout stopping {cf}")
            failures.append(f"{cf}: timed out")
            continue
        except Exception as e:
            logger.error(f"Error stopping {cf}: {e}")
            failures.append(f"{cf}: {e}")
            continue
        if result.returncode != 0:
            err = (result.stderr or "").strip()[:200]
            logger.error(f"Stopping {cf} failed (exit {result.returncode}): {err}")
            failures.append(f"{cf}: exit {result.returncode}: {err}")
        else:
            logger.info(f"Stopped {cf}")
    return failures


class _SwitchAborted(Exception):
    """The switch stopped before anything new was started."""


async def do_switch(profile_name: str):
    """Background task: switch to new profile. The caller has already claimed
    the switch slot with _claim_switch(); this releases it when done."""
    state["switching"] = True
    await broadcast_state()
    try:
        try:
            profile = load_profiles()[profile_name]
        except Exception as e:
            # Nothing has been stopped yet, so the state still describes reality.
            raise _SwitchAborted(f"Cannot load profile '{profile_name}': "
                                 f"{type(e).__name__}: {e}")
        logger.info(f"Switching to profile: {profile_name}")

        # Stop all existing services. If any stack may still be running, do
        # not start another on top of it: that is the VRAM conflict the gates
        # exist to prevent. The old profile stays recorded as active (some of
        # it may still be up, so the gates keep treating it as running) and
        # last_error says which stacks did not stop.
        failures = await stop_all_services()
        if failures:
            raise _SwitchAborted(
                f"Teardown partly failed, not starting '{profile_name}'. "
                f"{3 - len(failures)} of 3 stacks stopped; possibly still running: "
                f"{'; '.join(failures)}. '{state['active_profile']}' is still "
                f"recorded as active until a /stop succeeds")

        # Everything managed is down from here on.
        state["active_profile"] = None
        state["running_services"] = []
        save_state()
        await asyncio.sleep(3)  # Allow GPU memory to release

        # The authoritative VRAM check: the pre-check could not see what the
        # outgoing profile was about to free, and the scheduler path may have
        # waited between checking and switching.
        reason = _check_vram(profile_name, profile, get_gpu_telemetry(),
                             outgoing_running=False)
        if reason:
            raise _SwitchAborted(reason)

        services = profile.get("services") or []
        if services:
            cmd = ["docker", "compose"]
            for cf in profile["compose_files"]:
                cf_name = cf.split("/")[-1]
                cmd += ["-f", str(COMPOSE_BASE / cf_name)]
            cmd += ["up", "-d", "--remove-orphans"] + services
            try:
                result = await _run_blocking(cmd, capture_output=True, text=True, timeout=120)
                if result.returncode != 0:
                    raise RuntimeError(f"Docker compose failed: {result.stderr}")
            except Exception as e:
                # `up` may have started some containers before failing (or the
                # CLI was killed mid-start). Take them down again so nothing
                # holds VRAM behind a state that says nothing is running.
                logger.error(f"Starting {profile_name} failed, cleaning up: {e}")
                leftover = await stop_all_services()
                if leftover:
                    # Some of the new profile may be running and holding VRAM.
                    # Record it as active so the gates keep treating it as
                    # running, rather than claiming nothing is up.
                    state["active_profile"] = profile_name
                    state["running_services"] = list(services)
                    save_state()
                    raise _SwitchAborted(
                        f"Starting '{profile_name}' failed ({e}) and cleanup also "
                        f"failed: {'; '.join(leftover)}. '{profile_name}' is recorded "
                        f"as active because some of it may be running; /stop it")
                raise
        # A profile with no services (idle) has nothing to start: no `up` at
        # all, since a bare `docker compose up` would pick up whatever compose
        # file happens to be in the working directory.

        state["active_profile"] = profile_name
        state["running_services"] = list(services)
        state["last_switched"] = time.time()
        state["last_error"] = None
        save_state()
        logger.info(f"Successfully activated profile: {profile_name}")

    except _SwitchAborted as e:
        logger.error(f"Profile switch aborted: {e}")
        state["last_error"] = str(e)
    except Exception as e:
        logger.error(f"Profile switch failed: {e}")
        state["active_profile"] = None
        state["running_services"] = []
        state["last_error"] = f"Switch to '{profile_name}' failed: {e}"
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
        "last_error": state["last_error"],
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
    pairs = _nvlink_pairs(profiles)
    return {
        name: {
            "description": p.get("description", ""),
            "services": p.get("services", []),
            "exclusive_gpus": p.get("exclusive_gpus", []),
            "vram_required_gb": p.get("vram_required_gb"),
            "compatible_with": p.get("compatible_with", []),
            "incompatible_with": p.get("incompatible_with", []),
            "accent": _profile_accent(p),
            "nvlink_pairs": _profile_nvlink_pairs(p, pairs),
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
        "last_error": state["last_error"],
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
    
    # Incompatibility and VRAM gates (shared with the scheduler). idle
    # (requirement 0) needs no telemetry, so it stays reachable with NVML down.
    reason = validate_activation(profile_name, profiles)
    if reason:
        raise HTTPException(409, reason)

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
        failures = await stop_all_services()
        if failures:
            # Something may still be running: do not claim otherwise.
            state["last_error"] = f"Stop failed: {'; '.join(failures)}"
        else:
            state["active_profile"] = None
            state["running_services"] = []
            state["last_error"] = None
            save_state()
    finally:
        state["switching"] = False
    await broadcast_state()
    if failures:
        raise HTTPException(502, state["last_error"])
    return {"message": "All services stopped"}

@app.get("/health")
def health():
    """Health check with GPU info. `status` reflects the API process only;
    GPU availability is reported separately in `gpu_telemetry`."""
    telemetry = get_gpu_telemetry()
    return {"status": "ok", "gpus": telemetry["gpus"],
            "gpu_telemetry": _telemetry_summary(telemetry)}

# ── Prometheus exposition ────────────────────────────────────────────────────
# Scraped by configs/prometheus/prometheus.yml (job loadout-manager). Hand-written
# text exposition format 0.0.4; prometheus_client is not a dependency.
#
# loadout_service_expected is what the ProfileServiceDown alert joins against:
# one series per service (= container name) the active profile runs, so a
# profile-gated scrape target alerts only while its profile is active. It is
# empty while a switch is in progress, because services are being stopped and
# started on purpose.

_METRICS_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def _label_value(v) -> str:
    return str(v).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def _labels(**labels) -> str:
    if not labels:
        return ""
    return "{" + ",".join(f'{k}="{_label_value(v)}"' for k, v in labels.items()) + "}"


def expected_services() -> List[str]:
    """Services (container names) the active profile should be running, from
    profiles.yaml. Empty with no active profile or while switching."""
    active = state["active_profile"]
    if not active or state["switching"]:
        return []
    try:
        profile = load_profiles().get(active)
    except Exception as e:
        logger.warning(f"/metrics: cannot read profiles: {e}")
        return []
    return list((profile or {}).get("services") or [])


def render_metrics() -> str:
    out: List[str] = []

    def metric(name: str, help_: str, samples) -> None:
        out.append(f"# HELP {name} {help_}")
        out.append(f"# TYPE {name} gauge")
        for labels, value in samples:
            out.append(f"{name}{_labels(**labels)} {value}")

    metric("loadout_manager_up", "1 while the loadout-manager API is serving.", [({}, 1)])
    metric("loadout_switching", "1 while a profile switch is in progress.",
           [({}, 1 if state["switching"] else 0)])
    active = state["active_profile"]
    metric("loadout_active_profile_info",
           "The active loadout profile (no series when none is active).",
           [({"profile": active}, 1)] if active else [])
    metric("loadout_service_expected",
           "1 for each service (container name) the active profile should be running.",
           [({"profile": active, "service": svc}, 1) for svc in expected_services()])

    telemetry = read_gpu_telemetry()
    gpus = telemetry["gpus"]
    metric("loadout_gpu_telemetry_available", "1 if NVML could be read.",
           [({}, 1 if telemetry["available"] else 0)])
    metric("loadout_gpu_vram_used_bytes", "VRAM in use per GPU, from NVML.",
           [({"gpu": g["index"]}, g["vram_used_bytes"]) for g in gpus])
    metric("loadout_gpu_vram_total_bytes", "Total VRAM per GPU, from NVML.",
           [({"gpu": g["index"]}, g["vram_total_bytes"]) for g in gpus])
    return "\n".join(out) + "\n"


@app.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics():
    """Prometheus scrape endpoint (text exposition format)."""
    return PlainTextResponse(render_metrics(), media_type=_METRICS_CONTENT_TYPE)

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
                # Same gates as POST /activate; no await between this and the claim.
                reason = validate_activation(profile, profiles)
                if reason:
                    logger.error(f"Schedule {entry['id']}: not activating {profile}: {reason}")
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
