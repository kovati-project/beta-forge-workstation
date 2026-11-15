"""
Admin API - Authentication & User Management
Endpoints for Authentik integration and admin operations
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional
import httpx
import os
from pathlib import Path

from .envfile import read_env

router = APIRouter(tags=["admin"])

AUTHENTIK_URL = os.getenv("AUTHENTIK_URL", "http://host.docker.internal:9080")
AUTHENTIK_TOKEN = os.getenv("AUTHENTIK_TOKEN", "")


def _token() -> str:
    """The Authentik API token: the environment, else docker/.env.

    Read on every call so a token saved on the Settings page applies without
    recreating loadout-manager.
    """
    if AUTHENTIK_TOKEN:
        return AUTHENTIK_TOKEN
    env_file = Path(os.getenv("ENV_FILE", "/compose/.env"))
    return read_env(env_file).get("AUTHENTIK_TOKEN", "")

# Upper bound on pages followed when listing every group (Authentik pages at 100).
_MAX_PAGES = 50


def _auth_headers():
    token = _token()
    if not token:
        raise HTTPException(status_code=503, detail="AUTHENTIK_TOKEN not configured")
    return {"Authorization": f"Bearer {token}"}


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    name: Optional[str] = ""
    # Authentik groups to put the user in, by name ("Developer") or pk (UUID).
    groups: Optional[List[str]] = None


class UserUpdate(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None
    is_active: Optional[bool] = None
    # Replaces the user's group membership (names or pks); [] removes every
    # group, None leaves membership untouched.
    groups: Optional[List[str]] = None


# ── Authentik group helpers ─────────────────────────────────────────────────

async def _fetch_groups(client: httpx.AsyncClient) -> List[Dict]:
    """Every Authentik group (all pages), without the member lists."""
    groups: List[Dict] = []
    page = 1
    for _ in range(_MAX_PAGES):
        resp = await client.get(
            f"{AUTHENTIK_URL}/api/v3/core/groups/",
            headers=_auth_headers(),
            params={"include_users": "false", "ordering": "name", "page": page},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Authentik group listing failed: {resp.status_code}")
        data = resp.json()
        groups.extend(data.get("results", []))
        page = (data.get("pagination") or {}).get("next") or 0
        if not page:
            break
    return groups


async def _resolve_groups(client: httpx.AsyncClient, refs: List[str]) -> List[str]:
    """Map group names or pks to pks. Unknown references are a 400."""
    groups = await _fetch_groups(client)
    by_pk = {str(g["pk"]): str(g["pk"]) for g in groups}
    by_name = {g["name"]: str(g["pk"]) for g in groups}
    pks: List[str] = []
    unknown: List[str] = []
    for ref in refs:
        pk = by_pk.get(str(ref)) or by_name.get(ref)
        if pk is None:
            unknown.append(ref)
        elif pk not in pks:
            pks.append(pk)
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown Authentik group(s): {', '.join(unknown)}")
    return pks


async def _get_user(client: httpx.AsyncClient, user_id: int) -> Dict:
    resp = await client.get(
        f"{AUTHENTIK_URL}/api/v3/core/users/{user_id}/",
        headers=_auth_headers(),
        params={"include_groups": "true"},
    )
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Authentik user lookup failed: {resp.status_code}")
    return resp.json()


async def _set_user_groups(client: httpx.AsyncClient, user_id: int, current: List[str], wanted: List[str]):
    """Move a user from ``current`` to ``wanted`` group pks via add_user/remove_user."""
    current_set = {str(pk) for pk in current}
    changes = [("add_user", pk) for pk in wanted if pk not in current_set]
    changes += [("remove_user", pk) for pk in sorted(current_set - set(wanted))]
    for action, pk in changes:
        resp = await client.post(
            f"{AUTHENTIK_URL}/api/v3/core/groups/{pk}/{action}/",
            headers=_auth_headers(),
            json={"pk": user_id},
        )
        if resp.status_code not in (200, 204):
            raise HTTPException(
                status_code=502,
                detail=f"Authentik {action} failed for group {pk}: {resp.status_code}",
            )


def _with_group_names(user: Dict, names_by_pk: Optional[Dict[str, str]] = None) -> Dict:
    """Add ``group_names`` to an Authentik user (from groups_obj, else the pk map)."""
    groups_obj = user.get("groups_obj")
    if groups_obj is not None:
        names = [g.get("name") for g in groups_obj if g.get("name")]
    else:
        lookup = names_by_pk or {}
        names = [lookup.get(str(pk), str(pk)) for pk in user.get("groups") or []]
    return {**user, "group_names": sorted(names)}


async def _annotate_users(client: httpx.AsyncClient, users: List[Dict]) -> List[Dict]:
    """``_with_group_names`` for each user; fetches the group list only if some
    user came back without ``groups_obj``."""
    names_by_pk = None
    if any(u.get("groups_obj") is None and u.get("groups") for u in users):
        names_by_pk = {str(g["pk"]): g["name"] for g in await _fetch_groups(client)}
    return [_with_group_names(u, names_by_pk) for u in users]


def _group_summary(group: Dict) -> Dict:
    return {
        "pk": group.get("pk"),
        "name": group.get("name"),
        "is_superuser": bool(group.get("is_superuser")),
        "parent_name": group.get("parent_name"),
    }

@router.get("/admin/status")
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

@router.get("/admin/groups")
async def list_groups():
    """List Authentik groups (the roles that can be assigned to users)."""
    if not _token():
        return {"groups": [], "note": "AUTHENTIK_TOKEN not configured"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            groups = [_group_summary(g) for g in await _fetch_groups(client)]
            return {"groups": groups, "count": len(groups)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Group listing error: {e}")


@router.get("/admin/users")
async def list_users():
    """List users via Authentik API, each with its group names."""
    if not _token():
        return {"users": [], "note": "AUTHENTIK_TOKEN not configured"}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{AUTHENTIK_URL}/api/v3/core/users/",
                headers=_auth_headers(),
                params={"include_groups": "true"},
            )
            if resp.status_code == 200:
                data = resp.json()
                users = await _annotate_users(client, data.get("results", []))
                return {"users": users, "count": data.get("pagination", {}).get("count", 0)}
            raise HTTPException(status_code=502, detail=f"Authentik returned {resp.status_code}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"User listing error: {e}")


@router.get("/admin/users/{user_id}")
async def get_user(user_id: int):
    """Get one Authentik user, with its group names."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            user = await _get_user(client, user_id)
            return (await _annotate_users(client, [user]))[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Get user error: {e}")


@router.post("/admin/users")
async def create_user(payload: UserCreate):
    """Create a new user in Authentik, optionally in some groups."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Resolve groups first so an unknown name fails before anything is created.
            group_pks = await _resolve_groups(client, payload.groups) if payload.groups else []

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

            if not group_pks:
                return _with_group_names(created)

            try:
                await _set_user_groups(client, created["pk"], [], group_pks)
            except HTTPException as e:
                raise HTTPException(status_code=502, detail=f"User created but group assignment failed: {e.detail}")
            user = await _get_user(client, created["pk"])
            return (await _annotate_users(client, [user]))[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Create user error: {e}")


@router.patch("/admin/users/{user_id}")
async def update_user(user_id: int, payload: UserUpdate):
    """Update a user in Authentik (email, name, active status, group membership).

    ``groups`` replaces the membership: missing groups are added with
    add_user/, extra ones removed with remove_user/.
    """
    update_body = {k: v for k, v in payload.model_dump(exclude={"groups"}).items() if v is not None}
    if not update_body and payload.groups is None:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Resolve before writing anything, so an unknown group changes nothing.
            group_pks = await _resolve_groups(client, payload.groups) if payload.groups else []

            if update_body:
                resp = await client.patch(
                    f"{AUTHENTIK_URL}/api/v3/core/users/{user_id}/",
                    headers=_auth_headers(),
                    json=update_body,
                )
                if resp.status_code != 200:
                    raise HTTPException(status_code=502, detail=f"Authentik update failed: {resp.status_code}")
                user = resp.json()
            else:
                user = await _get_user(client, user_id)

            if payload.groups is not None:
                await _set_user_groups(client, user_id, user.get("groups") or [], group_pks)
                user = await _get_user(client, user_id)

            return (await _annotate_users(client, [user]))[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Update user error: {e}")


@router.delete("/admin/users/{user_id}")
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

@router.get("/admin/oauth2-apps")
async def list_oauth2_apps():
    """List OAuth2 applications."""
    if not _token():
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
            headers = _auth_headers()
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

@router.get("/admin/security-policies")
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

@router.get("/admin/auth-logs")
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
