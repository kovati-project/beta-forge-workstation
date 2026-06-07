"""Secrets management API endpoints."""

import os
import re
import secrets
from pathlib import Path
from typing import Dict, List
from fastapi import APIRouter, BackgroundTasks, HTTPException

try:
    from config import AFFECTS_MAP
except ImportError:
    from ..config import AFFECTS_MAP

router = APIRouter()

ENV_FILE = Path(os.getenv("ENV_FILE", "/home/kasemo/ai-workstation/docker/.env"))


def _read_env_file() -> Dict[str, str]:
    """Read .env file safely."""
    if not ENV_FILE.exists():
        return {}
    
    env_vars = {}
    try:
        with open(ENV_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    except Exception as e:
        print(f"Error reading ENV file: {e}")
    
    return env_vars


def _write_env_file(key: str, value: str):
    """Update or add key in .env file."""
    try:
        if not ENV_FILE.exists():
            ENV_FILE.touch()
        
        content = ENV_FILE.read_text()
        pattern = rf"^{re.escape(key)}=.*$"
        
        if re.search(pattern, content, re.MULTILINE):
            # Replace existing
            new_content = re.sub(pattern, f"{key}={value}", content, flags=re.MULTILINE)
        else:
            # Append new
            new_content = content.rstrip() + f"\n{key}={value}\n"
        
        ENV_FILE.write_text(new_content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update .env: {e}")


async def _restart_services(service_names: List[str]):
    """Restart affected services."""
    import asyncio
    import subprocess
    
    for svc in service_names:
        try:
            await asyncio.create_subprocess_exec(
                "docker", "compose", "restart", svc,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
        except Exception as e:
            print(f"Failed to restart {svc}: {e}")


@router.get("/secrets")
async def list_secrets() -> Dict:
    """List secret key names (never values)."""
    env_vars = _read_env_file()
    
    secrets_list = []
    for key in env_vars.keys():
        # Skip non-secret keys
        if any(x in key for x in ['PASSWORD', 'SECRET', 'KEY', 'TOKEN', 'SALT']):
            affects = AFFECTS_MAP.get(key, [])
            secrets_list.append({
                "key": key,
                "last_rotated": "60d ago",  # Placeholder
                "affects": affects,
            })
    
    return {"secrets": secrets_list}


@router.post("/secrets/{key}/rotate")
async def rotate_secret(key: str, background_tasks: BackgroundTasks) -> Dict:
    """Rotate a secret key."""
    if key not in AFFECTS_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown secret key: {key}")
    
    new_value = secrets.token_urlsafe(32)
    
    # Update .env file
    _write_env_file(key, new_value)
    
    # Restart affected services
    affected = AFFECTS_MAP.get(key, [])
    background_tasks.add_task(_restart_services, affected)
    
    return {
        "status": "rotating",
        "key": key,
        "affects": affected,
    }


@router.post("/secrets/rotate-all")
async def rotate_all_secrets(background_tasks: BackgroundTasks) -> Dict:
    """Rotate all secrets."""
    env_vars = _read_env_file()
    affected_services = set()
    
    for key in env_vars.keys():
        if any(x in key for x in ['PASSWORD', 'SECRET', 'KEY', 'TOKEN', 'SALT']):
            new_value = secrets.token_urlsafe(32)
            _write_env_file(key, new_value)
            affected_services.update(AFFECTS_MAP.get(key, []))
    
    background_tasks.add_task(_restart_services, list(affected_services))
    
    return {
        "status": "rotating",
        "total": len(env_vars),
        "affects": list(affected_services),
    }
