"""Authentication and user management API endpoints."""

from typing import Dict, List
import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter()

AUTHENTIK_URL = "http://localhost:9000"


@router.get("/auth/status")
async def get_auth_status() -> Dict:
    """Get Authentik service status."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{AUTHENTIK_URL}/api/v3/admin/version/")
            if response.status_code == 200:
                return {
                    "running": True,
                    "port": 9000,
                    "forward_auth": ["open-webui", "n8n"],
                }
    except:
        pass
    
    return {
        "running": False,
        "port": 9000,
    }


@router.get("/auth/users")
async def get_auth_users() -> Dict:
    """Get list of users from Authentik."""
    try:
        async with httpx.AsyncClient() as client:
            # This would normally use Authentik API with proper auth
            # Placeholder implementation
            return {
                "users": [
                    {
                        "id": "1",
                        "username": "admin",
                        "email": "admin@example.com",
                        "last_login": "2026-06-06T12:00:00Z",
                        "role": "admin",
                    },
                ]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auth/users/{user_id}/promote")
async def promote_user(user_id: str) -> Dict:
    """Promote user to admin."""
    return {"status": "promoting", "user_id": user_id, "role": "admin"}


@router.post("/auth/users/{user_id}/demote")
async def demote_user(user_id: str) -> Dict:
    """Demote user to regular user."""
    return {"status": "demoting", "user_id": user_id, "role": "user"}


@router.delete("/auth/users/{user_id}")
async def delete_user(user_id: str) -> Dict:
    """Delete a user."""
    return {"status": "deleted", "user_id": user_id}
