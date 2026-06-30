#!/usr/bin/env python3
"""
Loadout Manager — GPU profile orchestrator for AI workstation.
Manages Docker Compose stack switching with GPU exclusivity and VRAM awareness.
Extends with Kovati OS backend API for all frontend operations.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import subprocess
import yaml
import asyncio
import time
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
state = {
    "active_profile": None,
    "switching": False,
    "last_switched": None,
    "running_services": []
}

def load_profiles() -> Dict:
    """Load and parse profiles.yaml."""
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)["profiles"]

def get_gpu_info() -> List[Dict]:
    """Get current GPU VRAM, utilization, and temperature."""
    try:
        pynvml.nvmlInit()
        gpus = []
        for i in range(pynvml.nvmlDeviceGetCount()):
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
        pynvml.nvmlShutdown()
        return gpus
    except Exception as e:
        logger.error(f"GPU info fetch failed: {e}")
        return []

def stop_all_services():
    """Stop all managed Docker Compose stacks."""
    compose_files = ["compose.inference.yml", "compose.training.yml", "compose.studio.yml"]
    for cf in compose_files:
        try:
            subprocess.run(
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
    """Background task: switch to new profile."""
    profiles = load_profiles()
    profile = profiles[profile_name]
    
    state["switching"] = True
    try:
        logger.info(f"Switching to profile: {profile_name}")
        
        # Stop all existing services
        stop_all_services()
        await asyncio.sleep(3)  # Allow GPU memory to release
        
        # Build docker compose command
        cmd = ["docker", "compose"]
        for cf in profile["compose_files"]:
            cf_name = cf.split("/")[-1]
            cmd += ["-f", str(COMPOSE_BASE / cf_name)]
        
        cmd += ["up", "-d", "--remove-orphans"] + profile["services"]
        
        # Execute
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"Docker compose failed: {result.stderr}")
        
        state["active_profile"] = profile_name
        state["running_services"] = profile["services"]
        state["last_switched"] = time.time()
        logger.info(f"Successfully activated profile: {profile_name}")
        
    except Exception as e:
        logger.error(f"Profile switch failed: {e}")
        state["active_profile"] = None
        state["running_services"] = []
    finally:
        state["switching"] = False

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
    """Get current system and profile status."""
    return {
        "active_profile": state["active_profile"],
        "switching": state["switching"],
        "last_switched": state["last_switched"],
        "running_services": state["running_services"],
        "gpus": get_gpu_info()
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
    
    # Check VRAM requirement
    if "vram_required_gb" in profile:
        gpus = get_gpu_info()
        total_free = sum(g["vram_free_gb"] for g in gpus)
        if total_free < profile["vram_required_gb"]:
            raise HTTPException(
                409,
                f"Insufficient VRAM: {total_free:.1f}GB free, {profile['vram_required_gb']}GB required"
            )
    
    background_tasks.add_task(do_switch, profile_name)
    return {"message": f"Switching to '{profile_name}'", "status": "switching"}

@app.post("/stop")
async def stop_all():
    """Stop all managed services."""
    if state["switching"]:
        raise HTTPException(409, "Profile switch in progress")
    stop_all_services()
    state["active_profile"] = None
    state["running_services"] = []
    return {"message": "All services stopped"}

@app.get("/health")
def health():
    """Health check with GPU info."""
    return {"status": "ok", "gpus": get_gpu_info()}

# ── Static Files (React Build) ───────────────────────────────────────────────

STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
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
