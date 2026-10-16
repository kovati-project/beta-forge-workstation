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

from . import secrets as secrets_api  # owns ENV_FILE
from .envfile import read_env, set_env_values

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
    env_vars = read_env(secrets_api.ENV_FILE)
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

    if "\n" in body.value or "\r" in body.value:
        raise HTTPException(status_code=400, detail="Value must be a single line")
    try:
        set_env_values(secrets_api.ENV_FILE, {key: body.value})
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to update .env: {e}")

    affects = CONFIG_SCHEMA_MAP[key]["affects"]
    if affects:
        background_tasks.add_task(_restart_services, affects)

    return {"status": "updated", "key": key, "affects": affects}
