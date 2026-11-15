"""Opt-in API access control (#102).

With LOADOUT_REQUIRE_AUTH=true, state-changing and sensitive requests must
prove who sent them. A request passes when it carries either

  * a valid API key (``Authorization: Bearer nk_...`` or ``X-API-Key: nk_...``),
    checked with keys.verify_api_key (which also records last_used), or
  * the Authentik forward-auth identity header (X-Authentik-Username) AND comes
    from a trusted proxy address (LOADOUT_TRUSTED_PROXIES). Caddy sets that
    header only after Authentik has authenticated the user; from any other
    source it is trivially forged, so it is ignored there.

Protected: every POST/PUT/PATCH/DELETE, plus GET/HEAD on the sensitive prefixes
below. Everything else (/status, /loadouts, /health, the UI, /ws) stays open,
as do the monitoring endpoints Prometheus and Alertmanager call unattended.

Settings are read from the process environment first, then from docker/.env
(ENV_FILE), so the Settings page can toggle them without a recreate. The
default is off: with the switch off this module changes nothing.
"""

import ipaddress
import logging
import os
from pathlib import Path
from typing import List, Optional, Tuple, Union

from fastapi import Request
from fastapi.responses import JSONResponse

from .envfile import read_env
from .keys import KEY_PREFIX, verify_api_key

logger = logging.getLogger(__name__)

ENV_FILE = Path(os.getenv("ENV_FILE", "/compose/.env"))

REQUIRE_AUTH_SETTING = "LOADOUT_REQUIRE_AUTH"
TRUSTED_PROXIES_SETTING = "LOADOUT_TRUSTED_PROXIES"

# Caddy and loadout-manager share the ai-loadout bridge network
# (docker/compose.caddy.yml, docker/compose.loadout.yml). Its subnet comes from
# Docker's default address pool, 172.16.0.0/12, unless the operator pins one.
DEFAULT_TRUSTED_PROXIES = "172.16.0.0/12"

# configs/caddy/Caddyfile.security: forward_auth ... copy_headers X-Authentik-Username
IDENTITY_HEADER = "X-Authentik-Username"

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
SENSITIVE_PREFIXES = ("/api/secrets", "/api/keys", "/api/admin", "/api/backup", "/api/config")
# Unattended callers that cannot present a key. Matched exactly.
OPEN_PATHS = {"/health", "/metrics", "/api/alerts/webhook"}

_TRUE = {"1", "true", "yes", "on"}

Network = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]


def _setting(key: str, default: str) -> str:
    value = os.environ.get(key)
    if value is None:
        try:
            value = read_env(ENV_FILE).get(key)
        except OSError:
            value = None
    value = (value or "").strip().strip('"').strip("'")
    return value or default


def require_auth_enabled() -> bool:
    return _setting(REQUIRE_AUTH_SETTING, "false").lower() in _TRUE


def trusted_proxies() -> List[Network]:
    nets = []
    for part in _setting(TRUSTED_PROXIES_SETTING, DEFAULT_TRUSTED_PROXIES).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            nets.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid %s entry: %r", TRUSTED_PROXIES_SETTING, part)
    return nets


def is_protected(method: str, path: str) -> bool:
    """Whether (method, path) needs credentials when enforcement is on."""
    method = method.upper()
    if method == "OPTIONS" or path in OPEN_PATHS:
        return False
    if method in WRITE_METHODS:
        return True
    return path.startswith(SENSITIVE_PREFIXES)


def _from_trusted_proxy(request: Request) -> bool:
    host = request.client.host if request.client else None
    if not host:
        return False
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(addr.version == net.version and addr in net for net in trusted_proxies())


def _presented_key(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()
    key = request.headers.get("x-api-key", "").strip()
    return key or None


def authenticate(request: Request) -> Optional[Tuple[str, str]]:
    """(method, principal) for a request that proves who sent it, else None."""
    key = _presented_key(request)
    if key and key.startswith(KEY_PREFIX):
        name = verify_api_key(key)
        if name:
            return "api_key", name
    user = request.headers.get(IDENTITY_HEADER, "").strip()
    if user and _from_trusted_proxy(request):
        return "forward_auth", user
    return None


def check_request(request: Request) -> Optional[JSONResponse]:
    """None when the request may proceed; a 401 response otherwise."""
    if not require_auth_enabled() or not is_protected(request.method, request.url.path):
        return None
    who = authenticate(request)
    if who is not None:
        request.state.auth_method, request.state.user = who
        return None
    client = request.client.host if request.client else "?"
    logger.info("401 %s %s from %s: no valid credentials", request.method, request.url.path, client)
    return JSONResponse(
        status_code=401,
        content={"detail": "Authentication required: send an API key "
                           "(Authorization: Bearer nk_... or X-API-Key) "
                           "or sign in through https://ai.local/loadout/"},
        headers={"WWW-Authenticate": "Bearer"},
    )
