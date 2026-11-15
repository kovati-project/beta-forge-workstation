"""
MCP Tool Bridge — exposes MCP servers to Open WebUI agents via pipe interface.
Install as a Pipe in Open WebUI Admin → Functions → Add Function

Usage: Select this pipe in chat to enable agent access to filesystem, fetch, code-exec, browser.

Preferred alternative: Open WebUI (0.6.31+) connects to MCP servers natively.
Admin Settings → External Tools → Add Server → type "MCP (Streamable HTTP)",
URL from MCP_ENDPOINTS below. This pipe remains for scripted / pipe-based use.

All four servers (docker/compose.agentic.yml) speak MCP streamable HTTP at
``/mcp``: every exchange starts with ``initialize``, which returns an
``Mcp-Session-Id`` header that later requests must echo. Replies are either
JSON or a short SSE stream, depending on the server.
"""

import json
from typing import Generator, Optional

import requests

# MCP server endpoints (container names on the ai-workstation network)
MCP_ENDPOINTS = {
    "filesystem": "http://mcp-filesystem:3100/mcp",
    "fetch":      "http://mcp-fetch:3103/mcp",
    "code_exec":  "http://mcp-code-exec:3102/mcp",
    "browser":    "http://mcp-browser:3101/mcp",
}

PROTOCOL_VERSION = "2025-03-26"


class MCPClient:
    """Minimal synchronous streamable-HTTP MCP client (one session)."""

    def __init__(self, url: str, timeout: int):
        self.url = url
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self._id = 0

    def _headers(self) -> dict:
        h = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    @staticmethod
    def _messages(resp: requests.Response) -> list:
        if resp.headers.get("content-type", "").startswith("text/event-stream"):
            return [json.loads(line[5:]) for line in resp.text.splitlines()
                    if line.startswith("data:") and line[5:].strip()]
        body = resp.json()
        return body if isinstance(body, list) else [body]

    def request(self, method: str, params: Optional[dict] = None) -> dict:
        self._id += 1
        payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}
        resp = requests.post(self.url, json=payload, headers=self._headers(), timeout=self.timeout)
        resp.raise_for_status()
        if method == "initialize":
            self.session_id = resp.headers.get("mcp-session-id")
        for msg in self._messages(resp):
            if msg.get("id") == self._id:
                if "error" in msg:
                    raise RuntimeError(f"MCP error {msg['error'].get('code')}: {msg['error'].get('message')}")
                return msg.get("result", {})
        raise RuntimeError(f"no response to {method}")

    def __enter__(self):
        self.request("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "open-webui-mcp-pipe", "version": "1.0"},
        })
        requests.post(self.url, json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                      headers=self._headers(), timeout=self.timeout)
        return self

    def __exit__(self, *exc):
        if self.session_id:
            try:
                requests.delete(self.url, headers=self._headers(), timeout=self.timeout)
            except requests.RequestException:
                pass


class Pipe:
    """MCP Tool Bridge pipe for Open WebUI."""

    class Valves:
        """Configuration for MCP pipe."""
        mcp_servers: dict = {"filesystem": True, "fetch": True, "code_exec": False, "browser": False}
        timeout_seconds: int = 30

    def __init__(self):
        self.valves = self.Valves()

    def _endpoint(self, server: str) -> str:
        if server not in self.valves.mcp_servers or not self.valves.mcp_servers[server]:
            raise ValueError(f"MCP server '{server}' not enabled")
        endpoint = MCP_ENDPOINTS.get(server)
        if not endpoint:
            raise ValueError(f"Unknown MCP server: {server}")
        return endpoint

    def list_mcp_tools(self, server: str) -> dict:
        """List the tools an MCP server offers."""
        try:
            with MCPClient(self._endpoint(server), self.valves.timeout_seconds) as client:
                return client.request("tools/list")
        except requests.Timeout:
            return {"error": f"MCP server '{server}' timeout after {self.valves.timeout_seconds}s"}
        except Exception as e:
            return {"error": f"MCP call failed: {str(e)}"}

    def call_mcp_tool(self, server: str, tool: str, params: dict) -> dict:
        """Call a tool on an MCP server (streamable HTTP, JSON-RPC tools/call)."""
        try:
            with MCPClient(self._endpoint(server), self.valves.timeout_seconds) as client:
                return client.request("tools/call", {"name": tool, "arguments": params})
        except requests.Timeout:
            return {"error": f"MCP server '{server}' timeout after {self.valves.timeout_seconds}s"}
        except Exception as e:
            return {"error": f"MCP call failed: {str(e)}"}

    def pipe(
        self,
        body: dict,
        __user__: dict,
        __model__: str = "",
        __messages__: list = [],
        __files__: list = [],
    ) -> dict | Generator:
        """
        Main pipe handler for Open WebUI.

        In Open WebUI, agents can request tool calls via:
        {
          "type": "function",
          "function": {
            "name": "mcp_call",
            "arguments": {
              "server": "filesystem",
              "tool": "read_text_file",
              "params": {"path": "/data/documents/file.txt"}
            }
          }
        }
        """

        # Pass through to LLM — tool execution handled by Open WebUI's tool calling mechanism
        # The MCP calls are invoked when LLM requests them

        return body
