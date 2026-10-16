"""Secrets management API endpoints.

Only the platform-managed secrets in config.MANAGED_SECRETS are listed or
rotated; third-party credentials in docker/.env are left alone. Rotation follows
docs/runbooks/rotate-postgres-passwords.md: change the live credential first
(ALTER ROLE for database passwords), then docker/.env, then RECREATE the
consumers that are running (`docker compose restart` does not re-read .env).
"""

import asyncio
import logging
import os
import secrets
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException

try:
    from config import MANAGED_SECRETS
except ImportError:
    from ..config import MANAGED_SECRETS
from .envfile import read_env, set_env_values

logger = logging.getLogger(__name__)
router = APIRouter()

# docker/.env, bind-mounted read-write at /compose/.env (docker/compose.loadout.yml).
ENV_FILE = Path(os.getenv("ENV_FILE", "/compose/.env"))
COMPOSE_DIR = Path(os.getenv("COMPOSE_DIR", "/compose"))
if not COMPOSE_DIR.exists():
    COMPOSE_DIR = Path(__file__).parent.parent.parent / "docker"
# Real host path of docker/, so relative paths in compose files resolve on the host.
HOST_COMPOSE_DIR = os.getenv("HOST_COMPOSE_DIR", "")

COMMAND_TIMEOUT = 180  # seconds; `up --force-recreate` of one service
_rotation_lock = asyncio.Lock()


class RotationError(Exception):
    pass


async def _run(argv: List[str], stdin: Optional[str] = None) -> Tuple[int, str]:
    """Run a command, return (exit code, combined output). Never raises."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE if stdin is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except OSError as e:
        return 127, str(e)
    try:
        out, _ = await asyncio.wait_for(
            proc.communicate(stdin.encode() if stdin is not None else None), COMMAND_TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, f"timed out after {COMMAND_TIMEOUT}s"
    return proc.returncode, (out or b"").decode(errors="replace").strip()


async def _set_role_password(container: str, user: str, db: str, role: str, value: str):
    """ALTER ROLE inside the database container. The statement goes in on stdin
    so the password never appears in argv (`ps`, docker events, logs)."""
    literal = value.replace("'", "''")
    sql = f"ALTER ROLE \"{role}\" WITH PASSWORD '{literal}';\n"
    return await _run(
        ["docker", "exec", "-i", container, "psql", "-U", user, "-d", db,
         "-v", "ON_ERROR_STOP=1", "-q"],
        stdin=sql)


def _compose(compose_file: str) -> List[str]:
    cmd = ["docker", "compose", "--ansi", "never"]
    if HOST_COMPOSE_DIR:
        cmd += ["--project-directory", HOST_COMPOSE_DIR]
    return cmd + ["--env-file", str(ENV_FILE), "-f", str(COMPOSE_DIR / compose_file)]


async def _recreate_if_running(compose_file: str, service: str) -> Dict:
    """Recreate a running consumer so it picks up the new value. A stopped one is
    left stopped; it reads the new value whenever it is next started."""
    rc, out = await _run(_compose(compose_file) + ["ps", "-q", "--status", "running", service])
    if rc != 0:
        return {"service": service, "status": "error", "detail": out[-500:]}
    if not out:
        return {"service": service, "status": "not running"}
    rc, out = await _run(_compose(compose_file) + ["up", "-d", "--no-deps", "--force-recreate", service])
    if rc != 0:
        logger.error("recreate %s failed: %s", service, out[-500:])
        return {"service": service, "status": "error", "detail": out[-500:]}
    return {"service": service, "status": "recreated"}


async def _db_container_state(container: str) -> str:
    """'running', 'stopped', or 'absent' (never created on this host)."""
    rc, out = await _run(["docker", "container", "inspect", "-f", "{{.State.Running}}", container])
    if rc != 0:
        return "absent"
    return "running" if out.strip() == "true" else "stopped"


async def _rotate_value(key: str, env: Dict[str, str]) -> List[str]:
    """Change the live credential(s), then docker/.env. On failure everything
    already changed is put back, so docker/.env stays the source of truth.

    A database container that does not exist holds no copy of the password and
    is skipped (it is created from docker/.env when first deployed). A stopped
    one does hold a copy, so rotation refuses rather than leave it behind.
    Returns the skipped containers."""
    spec = MANAGED_SECRETS[key]
    old = env.get(key) or None
    new = secrets.token_urlsafe(32)
    roles, skipped = [], []
    for role in spec["db_roles"]:
        container_state = await _db_container_state(role[0])
        if container_state == "absent":
            skipped.append(role[0])
        elif container_state == "stopped":
            raise RotationError(f"{role[0]} is stopped; start it so its {role[3]} role can "
                                f"be changed, then rotate again")
        else:
            roles.append(role)
    changed = []
    for role in roles:
        rc, out = await _set_role_password(*role, new)
        if rc != 0:
            msg = f"ALTER ROLE {role[3]} in {role[0]} failed: {out[-300:]}"
            for done in changed:
                if old is None or (await _set_role_password(*done, old))[0] != 0:
                    msg += (f"; could NOT restore role {done[3]} in {done[0]}, its password "
                            f"no longer matches docker/.env (see "
                            f"docs/runbooks/rotate-postgres-passwords.md, Rollback)")
            raise RotationError(msg)
        changed.append(role)
    set_env_values(ENV_FILE, {key: new})
    return skipped


def _consumers(keys: List[str]) -> List[Tuple[str, str]]:
    seen = []
    for k in keys:
        for pair in MANAGED_SECRETS[k]["recreate"]:
            if pair not in seen:
                seen.append(pair)
    return seen


def _require_env_file():
    if not ENV_FILE.exists():
        raise HTTPException(status_code=503, detail=f"{ENV_FILE} not found")


@router.get("/secrets")
async def list_secrets() -> Dict:
    """Platform-managed secrets present in docker/.env (names only, never values)."""
    env = read_env(ENV_FILE)
    return {"secrets": [
        {
            "key": key,
            "last_rotated": None,  # not tracked
            "affects": [svc for _, svc in spec["recreate"]],
            "rotatable": spec["rotate"] is None,
            "note": spec["rotate"],
        }
        for key, spec in MANAGED_SECRETS.items() if key in env
    ]}


@router.post("/secrets/{key}/rotate")
async def rotate_secret(key: str) -> Dict:
    """Rotate one platform-managed secret and recreate its running consumers."""
    spec = MANAGED_SECRETS.get(key)
    if spec is None:
        raise HTTPException(status_code=400, detail=f"{key} is not a platform-managed secret")
    if spec["rotate"] is not None:
        raise HTTPException(status_code=409, detail=f"{key} cannot be rotated: {spec['rotate']}")
    _require_env_file()

    async with _rotation_lock:
        try:
            not_deployed = await _rotate_value(key, read_env(ENV_FILE))
        except RotationError as e:
            raise HTTPException(status_code=502, detail=str(e))
        services = [await _recreate_if_running(f, s) for f, s in _consumers([key])]

    ok = all(s["status"] != "error" for s in services)
    return {
        "status": "rotated" if ok else "partial",
        "key": key,
        "affects": [s["service"] for s in services],
        "services": services,
        "not_deployed": not_deployed,
    }


@router.post("/secrets/rotate-all")
async def rotate_all_secrets() -> Dict:
    """Rotate every rotatable platform-managed secret present in docker/.env."""
    _require_env_file()
    async with _rotation_lock:
        env = read_env(ENV_FILE)
        rotated, failed, skipped, not_deployed = [], [], [], []
        for key, spec in MANAGED_SECRETS.items():
            if key not in env:
                continue
            if spec["rotate"] is not None:
                skipped.append({"key": key, "reason": spec["rotate"]})
                continue
            try:
                for container in await _rotate_value(key, env):
                    if container not in not_deployed:
                        not_deployed.append(container)
                rotated.append(key)
            except RotationError as e:
                failed.append({"key": key, "detail": str(e)})
        services = [await _recreate_if_running(f, s) for f, s in _consumers(rotated)]

    ok = not failed and all(s["status"] != "error" for s in services)
    return {
        "status": "rotated" if ok else "partial",
        "total": len(rotated),
        "rotated": rotated,
        "failed": failed,
        "skipped": skipped,
        "affects": [s["service"] for s in services],
        "services": services,
        "not_deployed": not_deployed,
    }
