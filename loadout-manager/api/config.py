"""User-configurable settings API endpoints."""

import asyncio
import os
from pathlib import Path
from typing import Dict, List

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

try:
    from config import CONFIG_SCHEMA, CONFIG_SCHEMA_MAP
except ImportError:
    from ..config import CONFIG_SCHEMA, CONFIG_SCHEMA_MAP

try:
    from api.secrets import _read_env_file, _write_env_file
except ImportError:
    from .secrets import _read_env_file, _write_env_file

router = APIRouter()

MASKED = "••••••"


class UpdateConfigRequest(BaseModel):
    value: str


async def _restart_services(service_names: List[str]):
    for svc in service_names:
        try:
            await asyncio.create_subprocess_exec(
                "docker", "compose", "restart", svc,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except Exception as e:
            print(f"Failed to restart {svc}: {e}")


@router.get("/config")
async def get_config() -> Dict:
    """Return all user-configurable settings (sensitive values masked)."""
    env_vars = _read_env_file()
    result = []
    for category, key, description, sensitive, affects in CONFIG_SCHEMA:
        raw = env_vars.get(key, "")
        result.append({
            "key": key,
            "category": category,
            "description": description,
            "sensitive": sensitive,
            "value_set": bool(raw),
            "current_value": MASKED if (sensitive and raw) else (raw if not sensitive else ""),
            "affects": affects,
        })
    return {"config": result}


@router.patch("/config/{key}")
async def update_config(
    key: str,
    body: UpdateConfigRequest,
    background_tasks: BackgroundTasks,
) -> Dict:
    """Update a single user-configurable setting."""
    if key not in CONFIG_SCHEMA_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown config key: {key}")

    _write_env_file(key, body.value)

    affects = CONFIG_SCHEMA_MAP[key]["affects"]
    if affects:
        background_tasks.add_task(_restart_services, affects)

    return {"status": "updated", "key": key, "affects": affects}
