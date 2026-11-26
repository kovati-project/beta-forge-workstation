"""MCP server management API endpoints.

The four MCP servers in docker/compose.agentic.yml all speak MCP streamable
HTTP at ``http://<host>:<port>/mcp``. A probe is a real MCP handshake:
``initialize`` (which returns the session id), ``notifications/initialized``,
then optionally ``tools/list``, then the session is closed with DELETE.

loadout-manager runs on its own Docker network, so it reaches the servers
through their published ports on the host (``MCP_HOST``, set to
``host.docker.internal`` in compose.loadout.yml).
"""

import asyncio
import json
import os
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter()

# MCP servers running via compose.agentic.yml
MCP_SERVERS = {
    "filesystem": {"port": 3100, "description": "Read-only access to /data (documents, datasets, outputs, notebooks)"},
    "browser":    {"port": 3101, "description": "Playwright headless Chromium browser automation"},
    "code-exec":  {"port": 3102, "description": "Sandboxed Python execution (no network, stdlib only)"},
    "fetch":      {"port": 3103, "description": "HTTP fetch / web retrieval as markdown"},
}

MCP_HOST = os.getenv("MCP_HOST", "localhost")
MCP_PATH = "/mcp"
PROTOCOL_VERSION = "2025-03-26"
_JSONRPC_TIMEOUT = 5.0
_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


class MCPError(Exception):
    """The server answered, but not with a usable MCP response."""


def _canonical(name: str) -> Optional[str]:
    """Accept both the API name ('filesystem') and the container name ('mcp-filesystem')."""
    if name in MCP_SERVERS:
        return name
    if name.startswith("mcp-") and name[4:] in MCP_SERVERS:
        return name[4:]
    return None


def _server_url(port: int) -> str:
    return f"http://{MCP_HOST}:{port}{MCP_PATH}"


def _parse_response(resp: httpx.Response, request_id: int) -> Dict[str, Any]:
    """Extract the JSON-RPC response for ``request_id`` from a JSON or SSE body."""
    ctype = resp.headers.get("content-type", "")
    if ctype.startswith("text/event-stream"):
        messages = []
        for line in resp.text.splitlines():
            if line.startswith("data:"):
                payload = line[5:].strip()
                if payload:
                    messages.append(json.loads(payload))
    else:
        body = resp.json()
        messages = body if isinstance(body, list) else [body]

    for msg in messages:
        if isinstance(msg, dict) and msg.get("id") == request_id:
            if "error" in msg:
                err = msg["error"]
                raise MCPError(f"JSON-RPC error {err.get('code')}: {err.get('message')}")
            return msg.get("result", {})
    raise MCPError("no JSON-RPC response in reply")


class MCPSession:
    """Minimal streamable-HTTP MCP client: enough to initialize and list tools."""

    def __init__(self, client: httpx.AsyncClient, url: str):
        self.client = client
        self.url = url
        self.session_id: Optional[str] = None
        self._next_id = 0

    def _headers(self) -> Dict[str, str]:
        headers = dict(_HEADERS)
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    async def request(self, method: str, params: Optional[dict] = None) -> Dict[str, Any]:
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params or {}}
        resp = await self.client.post(self.url, json=payload, headers=self._headers())
        if resp.status_code != 200:
            raise MCPError(f"HTTP {resp.status_code} on {method}")
        if method == "initialize":
            self.session_id = resp.headers.get("mcp-session-id")
        return _parse_response(resp, self._next_id)

    async def notify(self, method: str) -> None:
        payload = {"jsonrpc": "2.0", "method": method}
        await self.client.post(self.url, json=payload, headers=self._headers())

    async def initialize(self) -> Dict[str, Any]:
        result = await self.request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "loadout-manager", "version": "1.0"},
        })
        await self.notify("notifications/initialized")
        return result

    async def close(self) -> None:
        if self.session_id:
            try:
                await self.client.delete(self.url, headers=self._headers())
            except httpx.HTTPError:
                pass


async def _probe_server(name: str, port: int, list_tools: bool = False) -> Dict:
    """Probe a single MCP server with a real MCP handshake."""
    result: Dict[str, Any] = {
        "name": name, "port": port, "url": _server_url(port),
        "status": "down", "capabilities": [], "error": None,
    }

    try:
        async with httpx.AsyncClient(timeout=_JSONRPC_TIMEOUT) as client:
            session = MCPSession(client, _server_url(port))
            try:
                init = await session.initialize()
                result["status"] = "up"
                result["capabilities"] = list(init.get("capabilities", {}).keys())
                result["server_info"] = init.get("serverInfo", {})
                if list_tools:
                    result["tools"] = (await session.request("tools/list")).get("tools", [])
            finally:
                await session.close()
    except httpx.ConnectError:
        result["error"] = "Connection refused — container not running"
    except httpx.TimeoutException:
        result["error"] = f"Timeout after {_JSONRPC_TIMEOUT}s"
    except (MCPError, ValueError) as e:
        result["status"] = "error"
        result["error"] = str(e)
    except Exception as e:
        result["error"] = str(e)

    return result


@router.get("/mcp/servers")
async def list_mcp_servers() -> Dict:
    """List all configured MCP servers with live health status."""
    results = await asyncio.gather(*(
        _probe_server(name, cfg["port"]) for name, cfg in MCP_SERVERS.items()
    ))
    servers = [
        {**probe, "description": cfg["description"]}
        for probe, cfg in zip(results, MCP_SERVERS.values())
    ]
    up = sum(1 for s in servers if s["status"] == "up")
    return {"servers": servers, "summary": {"total": len(servers), "up": up, "down": len(servers) - up}}


async def _test(name: str) -> Dict:
    key = _canonical(name)
    if key is None:
        raise HTTPException(status_code=404, detail=f"Unknown MCP server: {name}. Known: {list(MCP_SERVERS)}")

    result = await _probe_server(key, MCP_SERVERS[key]["port"], list_tools=True)
    if result["status"] == "down":
        raise HTTPException(status_code=503, detail=result["error"] or "Server unreachable")
    if result["status"] == "error":
        raise HTTPException(status_code=502, detail=result["error"])

    info = result.get("server_info", {})
    label = f"{info.get('name', key)} {info.get('version', '')}".strip()
    result["message"] = f"{label}: {len(result.get('tools', []))} tools"
    return result


@router.post("/mcp/test")
async def test_mcp_server(name: str) -> Dict:
    """Test connection to a named MCP server and return capabilities (name as query param)."""
    return await _test(name)


@router.post("/mcp/{name}/test")
async def test_mcp_server_by_path(name: str) -> Dict:
    """Same as POST /mcp/test; the form the UI's Expose page calls (accepts 'mcp-<name>')."""
    return await _test(name)


@router.get("/mcp/servers/{name}/tools")
async def list_server_tools(name: str) -> Dict:
    """Retrieve the tool list from a running MCP server."""
    key = _canonical(name)
    if key is None:
        raise HTTPException(status_code=404, detail=f"Unknown MCP server: {name}")

    port = MCP_SERVERS[key]["port"]
    result = await _probe_server(key, port, list_tools=True)
    if result["status"] == "down":
        raise HTTPException(status_code=503, detail=f"MCP server '{key}' not reachable on port {port}: {result['error']}")
    if result["status"] == "error":
        raise HTTPException(status_code=502, detail=result["error"])
    tools = result.get("tools", [])
    return {"server": key, "tools": tools, "count": len(tools)}
