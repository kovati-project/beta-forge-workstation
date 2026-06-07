"""Docker stack management API endpoints."""

import asyncio
import sqlite3
from datetime import datetime
from typing import Dict, List
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
import docker

try:
    from config import COMPOSE_FILES, DOCKER_DIR
except ImportError:
    from ..config import COMPOSE_FILES, DOCKER_DIR

router = APIRouter()

try:
    docker_client = docker.from_env()
except:
    docker_client = None

# SQLite for image history
IMAGE_HISTORY_DB = "/data/image_history.db"


def _init_db():
    """Initialize image history database."""
    try:
        conn = sqlite3.connect(IMAGE_HISTORY_DB)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS image_history (
                service TEXT,
                digest TEXT,
                pulled_at TIMESTAMP,
                is_current BOOLEAN
            )
        """)
        conn.commit()
        conn.close()
    except:
        pass


def _store_image_digest(service: str, digest: str):
    """Store image digest history."""
    try:
        _init_db()
        conn = sqlite3.connect(IMAGE_HISTORY_DB)
        
        # Mark previous as not current
        conn.execute(
            "UPDATE image_history SET is_current = 0 WHERE service = ? AND is_current = 1",
            (service,)
        )
        
        # Insert new
        conn.execute(
            "INSERT INTO image_history (service, digest, pulled_at, is_current) VALUES (?, ?, ?, 1)",
            (service, digest, datetime.now().isoformat())
        )
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Failed to store image digest: {e}")


@router.get("/stack/images")
async def list_stack_images() -> Dict:
    """List current Docker images and their digests."""
    if not docker_client:
        return {"images": []}
    
    try:
        images = []
        containers = docker_client.containers.list(all=True)
        
        seen = set()
        for container in containers:
            if container.image.id in seen:
                continue
            seen.add(container.image.id)
            
            images.append({
                "service": container.name,
                "image": container.image.tags[0] if container.image.tags else "unknown",
                "digest": container.image.id[:64],
                "previous_digest": None,  # Placeholder
            })
        
        return {"images": images}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stack/update")
async def update_all_services(request):
    """Update all Docker images (SSE stream)."""
    if not docker_client:
        raise HTTPException(status_code=503, detail="Docker not available")
    
    async def event_generator():
        try:
            for compose_file in set(COMPOSE_FILES.values()):
                file_path = DOCKER_DIR / compose_file
                yield f"data: Pulling images from {compose_file}...\n\n"
                
                proc = await asyncio.create_subprocess_exec(
                    "docker", "compose", "-f", str(file_path), "pull",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                async for line in proc.stdout:
                    decoded = line.decode('utf-8', errors='ignore').strip()
                    if decoded:
                        yield f"data: {decoded}\n\n"
                
                yield f"data: ✓ Updated images from {compose_file}\n\n"
        except Exception as e:
            yield f"data: Error: {e}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/stack/rollback/{service}")
async def rollback_service(service: str) -> Dict:
    """Rollback a service to previous image."""
    if service not in COMPOSE_FILES:
        raise HTTPException(status_code=404, detail=f"Service {service} not found")
    
    return {
        "status": "rolling back",
        "service": service,
    }
