"""MCP server management API endpoints."""

import asyncio
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
import httpx

router = APIRouter()

# MCP servers running via compose.agentic.yml
MCP_SERVERS = {
    "filesystem": {"port": 3100, "description": "Read/write access to /data (read-only mount)"},
    "browser":    {"port": 3101, "description": "Playwright-based browser automation"},
    "code-exec":  {"port": 3102, "description": "Sandboxed code execution"},
    "fetch":      {"port": 3103, "description": "HTTP fetch / web retrieval"},
}

MCP_HOST = "localhost"
_JSONRPC_TIMEOUT = 5.0


async def _probe_server(name: str, port: int) -> Dict:
    """Probe a single MCP server: TCP connect + JSON-RPC initialize."""
    base_url = f"http://{MCP_HOST}:{port}"
    result = {"name": name, "port": port, "status": "down", "capabilities": [], "error": None}

    try:
        async with httpx.AsyncClient(timeout=_JSONRPC_TIMEOUT) as client:
            # Send MCP initialize request
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "loadout-manager", "version": "1.0"},
                },
            }
            resp = await client.post(f"{base_url}/", json=payload)
            if resp.status_code == 200:
                data = resp.json()
                caps = data.get("result", {}).get("capabilities", {})
                result["status"] = "up"
                result["capabilities"] = list(caps.keys())
                result["server_info"] = data.get("result", {}).get("serverInfo", {})
            else:
                result["status"] = "error"
                result["error"] = f"HTTP {resp.status_code}"
    except httpx.ConnectError:
        result["error"] = "Connection refused — container not running"
    except httpx.TimeoutException:
        result["error"] = f"Timeout after {_JSONRPC_TIMEOUT}s"
    except Exception as e:
        result["error"] = str(e)

    return result


@router.get("/mcp/servers")
async def list_mcp_servers() -> Dict:
    """List all configured MCP servers with live health status."""
    tasks = [
        _probe_server(name, cfg["port"])
        for name, cfg in MCP_SERVERS.items()
    ]
    results = await asyncio.gather(*tasks)

    servers = []
    for i, (name, cfg) in enumerate(MCP_SERVERS.items()):
        probe = results[i]
        servers.append({
            **probe,
            "description": cfg["description"],
        })

    up = sum(1 for s in servers if s["status"] == "up")
    return {"servers": servers, "summary": {"total": len(servers), "up": up, "down": len(servers) - up}}


@router.post("/mcp/test")
async def test_mcp_server(name: str) -> Dict:
    """Test connection to a named MCP server and return capabilities."""
    if name not in MCP_SERVERS:
        raise HTTPException(status_code=404, detail=f"Unknown MCP server: {name}. Known: {list(MCP_SERVERS)}")

    result = await _probe_server(name, MCP_SERVERS[name]["port"])

    if result["status"] == "down":
        raise HTTPException(status_code=503, detail=result["error"] or "Server unreachable")

    return result


@router.get("/mcp/servers/{name}/tools")
async def list_server_tools(name: str) -> Dict:
    """Retrieve the tool list from a running MCP server."""
    if name not in MCP_SERVERS:
        raise HTTPException(status_code=404, detail=f"Unknown MCP server: {name}")

    port = MCP_SERVERS[name]["port"]
    base_url = f"http://{MCP_HOST}:{port}"

    try:
        async with httpx.AsyncClient(timeout=_JSONRPC_TIMEOUT) as client:
            payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
            resp = await client.post(f"{base_url}/", json=payload)
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"MCP server returned HTTP {resp.status_code}")
            data = resp.json()
            tools = data.get("result", {}).get("tools", [])
            return {"server": name, "tools": tools, "count": len(tools)}
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail=f"MCP server '{name}' not reachable on port {port}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail=f"MCP server '{name}' timed out")
