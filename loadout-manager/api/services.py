"""Service management API endpoints."""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict
from pathlib import Path
import docker
from fastapi import APIRouter, BackgroundTasks, HTTPException

logger = logging.getLogger(__name__)

try:
    from config import SERVICE_MAP, PORT_MAP, COMPOSE_FILES, SERVICE_PROFILES, COMPOSE_SERVICE_NAME, GPU_ASSIGNMENT
except ImportError:
    from ..config import SERVICE_MAP, PORT_MAP, COMPOSE_FILES, SERVICE_PROFILES, COMPOSE_SERVICE_NAME, GPU_ASSIGNMENT

router = APIRouter()

# Compose files are mounted at /compose inside the container (docker/ dir).
# Fall back to the sibling docker/ dir when running outside a container.
_COMPOSE_DIR = Path(os.getenv("COMPOSE_DIR", "/compose"))
if not _COMPOSE_DIR.exists():
    _COMPOSE_DIR = Path(__file__).parent.parent.parent / "docker"

# HOST_COMPOSE_DIR is the real host-filesystem path to the docker/ directory.
# Without it, relative paths in compose files (e.g. ../configs/nccl/nccl.conf)
# resolve to /configs/... on the host instead of <repo>/configs/..., causing
# bind mount failures and silent container start failures.
_HOST_COMPOSE_DIR = os.getenv("HOST_COMPOSE_DIR", "")

try:
    docker_client = docker.from_env()
except Exception as e:
    docker_client = None
    print(f"Warning: Docker client not available: {e}")


async def _compose(compose_file: str, subcommand: str, *args: str, profile: str = None) -> int:
    """Run: docker compose [--project-directory <dir>] [--profile <name>] -f <file> <subcommand> [args...]"""
    cmd = ["docker", "compose"]
    if _HOST_COMPOSE_DIR:
        cmd += ["--project-directory", _HOST_COMPOSE_DIR]
    if profile:
        cmd += ["--profile", profile]
    cmd += ["-f", str(_COMPOSE_DIR / compose_file), subcommand, *args]
    logger.info("compose cmd: %s", " ".join(cmd))
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    if stdout:
        for line in stdout.decode(errors="replace").splitlines():
            logger.info("compose[%s]: %s", subcommand, line)
    if proc.returncode != 0:
        logger.error("compose %s %s exited %d", subcommand, compose_file, proc.returncode)
    return proc.returncode


def _get_container(name: str):
    """Get Docker container by service name."""
    if not docker_client:
        raise HTTPException(status_code=503, detail="Docker not available")
    
    docker_name = SERVICE_MAP.get(name)
    if not docker_name:
        raise HTTPException(status_code=404, detail=f"Service {name} not found")
    
    containers = docker_client.containers.list(all=True)
    container = next((c for c in containers if docker_name in c.name), None)
    
    if not container:
        raise HTTPException(status_code=404, detail=f"Container for {name} not found")
    
    return container


def _get_uptime(container) -> int:
    """Calculate container uptime in seconds."""
    if container.status != 'running':
        return 0
    try:
        started = datetime.fromisoformat(
            container.attrs['State']['StartedAt'].replace('Z', '+00:00')
        )
        return int((datetime.now(started.tzinfo) - started).total_seconds())
    except:
        return 0


@router.get("/services")
async def list_services() -> Dict:
    """List all managed services with their status."""
    result = {}
    
    if not docker_client:
        return result
    
    containers = docker_client.containers.list(all=True)
    
    _status_map = {"exited": "stopped", "created": "stopped", "dead": "error", "removing": "stopping"}

    for svc_name, docker_name in SERVICE_MAP.items():
        container = next((c for c in containers if docker_name in c.name), None)
        raw_status = container.status if container else "exited"

        result[svc_name] = {
            "status": _status_map.get(raw_status, raw_status),
            "port": PORT_MAP.get(svc_name),
            "image": container.image.tags[0] if container and container.image.tags else None,
            "uptime_seconds": _get_uptime(container) if container else 0,
            "compose_file": COMPOSE_FILES.get(svc_name),
            "gpus": GPU_ASSIGNMENT.get(svc_name, []),
        }
    
    return result


@router.get("/services/{name}")
async def get_service(name: str) -> Dict:
    """Get details for a specific service."""
    if name not in SERVICE_MAP:
        raise HTTPException(status_code=404, detail=f"Service {name} not found")
    
    container = _get_container(name)
    
    _status_map = {"exited": "stopped", "created": "stopped", "dead": "error", "removing": "stopping"}
    return {
        "name": name,
        "status": _status_map.get(container.status, container.status),
        "port": PORT_MAP.get(name),
        "image": container.image.tags[0] if container.image.tags else None,
        "image_id": container.image.id,
        "uptime_seconds": _get_uptime(container),
        "compose_file": COMPOSE_FILES.get(name),
        "gpus": GPU_ASSIGNMENT.get(name, []),
    }


@router.post("/services/{name}/start")
async def start_service(name: str, background_tasks: BackgroundTasks) -> Dict:
    """Start a service."""
    if name not in SERVICE_MAP:
        raise HTTPException(status_code=404, detail=f"Service {name} not found")

    compose_file = COMPOSE_FILES.get(name)
    if not compose_file:
        raise HTTPException(status_code=400, detail=f"No compose file for {name}")

    svc = COMPOSE_SERVICE_NAME.get(name, name)
    profile = SERVICE_PROFILES.get(name)
    background_tasks.add_task(_compose, compose_file, "up", "-d", "--no-deps", svc, profile=profile)
    return {"status": "starting", "service": name}


@router.post("/services/{name}/stop")
async def stop_service(name: str, background_tasks: BackgroundTasks) -> Dict:
    """Stop a service."""
    if name not in SERVICE_MAP:
        raise HTTPException(status_code=404, detail=f"Service {name} not found")

    compose_file = COMPOSE_FILES.get(name)
    if not compose_file:
        raise HTTPException(status_code=400, detail=f"No compose file for {name}")

    svc = COMPOSE_SERVICE_NAME.get(name, name)
    background_tasks.add_task(_compose, compose_file, "stop", svc)
    return {"status": "stopping", "service": name}


@router.get("/services/{name}/logs")
async def get_logs(name: str, n: int = 200) -> Dict:
    """Get last N log lines for a service."""
    container = _get_container(name)
    
    try:
        logs = container.logs(tail=n, timestamps=True).decode('utf-8', errors='ignore')
        return {"logs": logs.splitlines()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/services/{name}/logs/stream")
async def stream_logs(name: str):
    """Stream logs for a service (SSE)."""
    from fastapi.responses import StreamingResponse
    
    container = _get_container(name)
    
    async def event_generator():
        try:
            for line in container.logs(stream=True, follow=True, timestamps=True):
                decoded = line.decode('utf-8', errors='ignore').strip()
                if decoded:
                    yield f"data: {decoded}\n\n"
        except Exception as e:
            yield f"data: Error: {e}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
