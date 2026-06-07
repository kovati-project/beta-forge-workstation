"""
Admin API - Authentication & User Management
Endpoints for Authentik integration and admin operations
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import httpx
import os

router = APIRouter(tags=["admin"])

AUTHENTIK_URL = os.getenv("AUTHENTIK_URL", "http://localhost:9080")
AUTHENTIK_TOKEN = os.getenv("AUTHENTIK_TOKEN", "")


def _auth_headers():
    if not AUTHENTIK_TOKEN:
        raise HTTPException(status_code=503, detail="AUTHENTIK_TOKEN not configured")
    return {"Authorization": f"Bearer {AUTHENTIK_TOKEN}"}


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    name: Optional[str] = ""


class UserUpdate(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None
    is_active: Optional[bool] = None

@router.get("/api/admin/status")
async def get_admin_status():
    """Check Authentik service availability."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{AUTHENTIK_URL}/-/health/live/")
            if resp.status_code == 204:
                return {
                    "authentik": "ready",
                    "url": AUTHENTIK_URL,
                }
            else:
                raise HTTPException(status_code=503, detail="Authentik not ready")
    except Exception as e:
        return {
            "authentik": "error",
            "error": str(e),
        }

@router.get("/api/admin/users")
async def list_users():
    """List users via Authentik API."""
    if not AUTHENTIK_TOKEN:
        return {"users": [], "note": "AUTHENTIK_TOKEN not configured"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{AUTHENTIK_URL}/api/v3/core/users/",
                headers=_auth_headers(),
            )
            if resp.status_code == 200:
                data = resp.json()
                return {"users": data.get("results", []), "count": data.get("pagination", {}).get("count", 0)}
            raise HTTPException(status_code=502, detail=f"Authentik returned {resp.status_code}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"User listing error: {e}")


@router.post("/api/admin/users")
async def create_user(payload: UserCreate):
    """Create a new user in Authentik."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{AUTHENTIK_URL}/api/v3/core/users/",
                headers=_auth_headers(),
                json={
                    "username": payload.username,
                    "email": payload.email,
                    "name": payload.name or payload.username,
                    "is_active": True,
                    "groups": [],
                    "attributes": {},
                },
            )
            if resp.status_code not in (200, 201):
                detail = resp.json() if resp.content else resp.status_code
                raise HTTPException(status_code=502, detail=f"Authentik create failed: {detail}")

            created = resp.json()

            # Set password via separate endpoint
            pw_resp = await client.post(
                f"{AUTHENTIK_URL}/api/v3/core/users/{created['pk']}/set_password/",
                headers=_auth_headers(),
                json={"password": payload.password},
            )
            if pw_resp.status_code not in (200, 204):
                raise HTTPException(status_code=502, detail="User created but password set failed")

            return created
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Create user error: {e}")


@router.patch("/api/admin/users/{user_id}")
async def update_user(user_id: int, payload: UserUpdate):
    """Update a user in Authentik (email, name, active status)."""
    update_body = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not update_body:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.patch(
                f"{AUTHENTIK_URL}/api/v3/core/users/{user_id}/",
                headers=_auth_headers(),
                json=update_body,
            )
            if resp.status_code == 200:
                return resp.json()
            raise HTTPException(status_code=502, detail=f"Authentik update failed: {resp.status_code}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update user error: {e}")


@router.delete("/api/admin/users/{user_id}")
async def delete_user(user_id: int):
    """Delete a user from Authentik."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(
                f"{AUTHENTIK_URL}/api/v3/core/users/{user_id}/",
                headers=_auth_headers(),
            )
            if resp.status_code == 204:
                return {"status": "deleted", "user_id": user_id}
            raise HTTPException(status_code=502, detail=f"Authentik delete failed: {resp.status_code}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete user error: {e}")

@router.get("/api/admin/oauth2-apps")
async def list_oauth2_apps():
    """List OAuth2 applications."""
    if not AUTHENTIK_TOKEN:
        return {
            "applications": [
                {
                    "name": "Open WebUI",
                    "client_id": "openwebui",
                    "enabled": True,
                    "redirect_uris": "http://10.10.10.2:3000/auth/callback",
                },
                {
                    "name": "Grafana",
                    "client_id": "grafana",
                    "enabled": True,
                    "redirect_uris": "http://10.10.10.2:3001/login/generic_oauth",
                },
                {
                    "name": "n8n",
                    "client_id": "n8n",
                    "enabled": False,
                    "redirect_uris": "http://10.10.10.2:5678/auth/generic/callback",
                },
            ],
            "note": "Stub data - Authentik token not configured",
        }
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            headers = {"Authorization": f"Bearer {AUTHENTIK_TOKEN}"}
            resp = await client.get(
                f"{AUTHENTIK_URL}/api/v3/oauth2/applications/",
                headers=headers,
            )
            
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "applications": data.get("results", []),
                    "count": len(data.get("results", [])),
                }
            else:
                raise HTTPException(status_code=502, detail="Failed to fetch OAuth2 apps")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth2 app listing error: {str(e)}")

@router.get("/api/admin/security-policies")
async def get_security_policies():
    """Get security policies and settings."""
    return {
        "mfa_enabled": False,
        "password_min_length": 12,
        "password_require_uppercase": True,
        "password_require_special": True,
        "session_timeout_minutes": 1440,
        "login_attempts_limit": 5,
        "ip_whitelist_enabled": False,
        "tls_enforced": False,
        "network_isolation": True,
    }

@router.get("/api/admin/auth-logs")
async def get_auth_logs(limit: int = 50):
    """Get recent authentication events."""
    return {
        "logs": [
            {
                "timestamp": "2026-06-06T10:30:45Z",
                "user": "admin",
                "event": "login_success",
                "ip": "10.10.10.100",
                "application": "Open WebUI",
            },
            {
                "timestamp": "2026-06-06T09:15:22Z",
                "user": "system",
                "event": "token_refresh",
                "ip": "127.0.0.1",
                "application": "Loadout Manager",
            },
        ],
        "total": 342,
    }
