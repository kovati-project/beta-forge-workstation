"""
/api/mcp/* — probes the MCP servers over streamable HTTP.

A fake MCP server (httpx.MockTransport) stands in for the containers. It
behaves like mcp-proxy / FastMCP: POST /mcp only, requires the streamable-HTTP
Accept header, answers ``initialize`` as SSE with an Mcp-Session-Id, and rejects
later requests that do not carry that session id.
"""

import json

import httpx
import pytest

SESSION = "sess-123"


class FakeMCP:
    def __init__(self, json_response=False, down=()):
        self.json_response = json_response
        self.down = set(down)
        self.calls = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        port = request.url.port
        if port in self.down:
            raise httpx.ConnectError("refused", request=request)
        if request.url.path != "/mcp":
            return httpx.Response(404)
        if request.method == "DELETE":
            self.calls.append((port, "DELETE"))
            return httpx.Response(200)
        if "text/event-stream" not in request.headers.get("accept", ""):
            return httpx.Response(406)

        msg = json.loads(request.content)
        method = msg["method"]
        self.calls.append((port, method))
        if method != "initialize" and request.headers.get("mcp-session-id") != SESSION:
            return httpx.Response(400, json={"error": "missing session"})
        if "id" not in msg:
            return httpx.Response(202)

        if method == "initialize":
            result = {"protocolVersion": "2025-03-26", "capabilities": {"tools": {}},
                      "serverInfo": {"name": f"fake-{port}", "version": "9.9"}}
        elif method == "tools/list":
            result = {"tools": [{"name": "t1"}, {"name": "t2"}]}
        else:
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": msg["id"],
                                             "error": {"code": -32601, "message": "nope"}})
        body = {"jsonrpc": "2.0", "id": msg["id"], "result": result}
        headers = {"mcp-session-id": SESSION}
        if self.json_response:
            return httpx.Response(200, json=body, headers=headers)
        return httpx.Response(200, text=f"event: message\ndata: {json.dumps(body)}\n\n",
                              headers={**headers, "content-type": "text/event-stream"})


@pytest.fixture
def mcp(lm, monkeypatch):
    from api import mcp as mod

    fake = FakeMCP()
    real = httpx.AsyncClient

    def client(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(fake)
        return real(*args, **kwargs)

    monkeypatch.setattr(mod.httpx, "AsyncClient", client)
    return fake


def test_servers_all_up_over_streamable_http(lm, mcp):
    r = lm.client.get("/api/mcp/servers")
    assert r.status_code == 200
    body = r.json()
    assert body["summary"] == {"total": 4, "up": 4, "down": 0}
    fs = next(s for s in body["servers"] if s["name"] == "filesystem")
    assert fs["url"].endswith(":3100/mcp")
    assert fs["capabilities"] == ["tools"]
    # Full handshake, then the session is closed.
    assert [m for p, m in mcp.calls if p == 3100] == ["initialize", "notifications/initialized", "DELETE"]


def test_server_down_is_reported(lm, mcp):
    mcp.down.add(3102)
    body = lm.client.get("/api/mcp/servers").json()
    ce = next(s for s in body["servers"] if s["name"] == "code-exec")
    assert ce["status"] == "down" and "not running" in ce["error"]
    assert body["summary"]["down"] == 1


@pytest.mark.parametrize("name", ["fetch", "mcp-fetch"])
def test_ui_test_route_accepts_container_name(lm, mcp, name):
    r = lm.client.post(f"/api/mcp/{name}/test")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "fetch"
    assert body["message"] == "fake-3103 9.9: 2 tools"


def test_query_param_test_route_still_works(lm, mcp):
    r = lm.client.post("/api/mcp/test", params={"name": "browser"})
    assert r.status_code == 200 and r.json()["port"] == 3101


def test_test_route_down_is_503(lm, mcp):
    mcp.down.add(3101)
    assert lm.client.post("/api/mcp/mcp-browser/test").status_code == 503


def test_unknown_server_is_404(lm, mcp):
    assert lm.client.post("/api/mcp/nope/test").status_code == 404
    assert lm.client.get("/api/mcp/servers/nope/tools").status_code == 404


def test_tools_list_with_json_responses(lm, mcp):
    mcp.json_response = True
    r = lm.client.get("/api/mcp/servers/mcp-filesystem/tools")
    assert r.status_code == 200
    assert r.json() == {"server": "filesystem", "tools": [{"name": "t1"}, {"name": "t2"}], "count": 2}
