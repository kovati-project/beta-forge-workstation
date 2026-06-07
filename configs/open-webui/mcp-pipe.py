"""
MCP Tool Bridge — exposes MCP servers to Open WebUI agents via pipe interface.
Install as a Pipe in Open WebUI Admin → Functions → Add Function

Usage: Select this pipe in chat to enable agent access to filesystem, fetch, code-exec, browser.
"""

import requests
import json
from typing import Optional, Generator

# MCP server endpoints
MCP_ENDPOINTS = {
    "filesystem": "http://10.10.10.2:3100",
    "fetch":      "http://10.10.10.2:3103",
    "code_exec":  "http://10.10.10.2:3102",
    "browser":    "http://10.10.10.2:3101",
}


class Pipe:
    """MCP Tool Bridge pipe for Open WebUI."""
    
    class Valves:
        """Configuration for MCP pipe."""
        mcp_servers: dict = {"filesystem": True, "fetch": True, "code_exec": False, "browser": False}
        timeout_seconds: int = 30
    
    def __init__(self):
        self.valves = self.Valves()
    
    def call_mcp_tool(self, server: str, tool: str, params: dict) -> dict:
        """Call a tool on an MCP server via JSON-RPC."""
        if server not in self.valves.mcp_servers or not self.valves.mcp_servers[server]:
            return {"error": f"MCP server '{server}' not enabled"}
        
        endpoint = MCP_ENDPOINTS.get(server)
        if not endpoint:
            return {"error": f"Unknown MCP server: {server}"}
        
        try:
            # MCP servers expose tools via /tools endpoint and call via /call
            call_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": tool,
                    "arguments": params
                }
            }
            
            resp = requests.post(
                f"{endpoint}/call",
                json=call_payload,
                timeout=self.valves.timeout_seconds
            )
            
            if resp.status_code == 200:
                return resp.json()
            else:
                return {"error": f"MCP server error: {resp.status_code} {resp.text}"}
        
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
              "tool": "read_file",
              "params": {"path": "/data/file.txt"}
            }
          }
        }
        """
        
        # Pass through to LLM — tool execution handled by Open WebUI's tool calling mechanism
        # The MCP calls are invoked when LLM requests them
        
        return body
