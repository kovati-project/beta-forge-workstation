# KOVATI OS — Component Spec 07
## Expose Panel
*OpenAI-compatible endpoints · MCP servers · API key management · external access*

---

## 1. Purpose

The Expose panel manages all outward-facing surface area of the platform: which inference endpoints are reachable, how Claude Desktop / Claude Code connect to the MCP servers, which services are reverse-proxied beyond localhost, and which API tokens are active.

This is the panel an operator uses after setting up a new client (a new laptop, a new Claude Desktop install, a remote developer) — they copy connection strings and tokens from here.

---

## 2. Layout

```
┌─────────────────────────────────────────────────────────┐
│ OpenAI-Compatible Endpoints                             │
├─────────────────────────────────────────────────────────┤
│ MCP Servers                                             │
├─────────────────────────────────────────────────────────┤
│ API Keys                                                │
├─────────────────────────────────────────────────────────┤
│ External Access (Caddy routing)                         │
└─────────────────────────────────────────────────────────┘
```

All four sections always visible (no tabs). Each is a `Panel` component.

---

## 3. OpenAI-Compatible Endpoints

Source: `GET /api/services` (status) + static port map.

```
┌──────────────────────────────────────────────────────────────┐
│ OpenAI-Compatible Endpoints                                  │
│                                                              │
│ Service       │ Base URL                   │ Status │ Copy   │
├──────────────────────────────────────────────────────────────┤
│ vllm-pair-a   │ http://host:8000/v1         │ ●run   │ [📋]  │
│ ollama        │ http://host:11434/v1        │ ●run   │ [📋]  │
│ vllm-pair-b   │ http://host:8001/v1         │ ○stop  │ [📋]  │
│ vllm-4gpu     │ http://host:8002/v1         │ ○stop  │ [📋]  │
│ whisper-stt   │ http://host:9099/v1/audio   │ ●run   │ [📋]  │
│ piper-tts     │ http://host:5000/v1/audio/speech │ ●run │ [📋]│
└──────────────────────────────────────────────────────────────┘
```

**`{host}`** is resolved at render time from `window.location.hostname`. The displayed URL is always the LAN IP or hostname the operator used to reach the UI (correct for LAN access), not `localhost`.

**Status indicator:** `DotStatus` + `Tag variant` (green "running", gray "stopped").

**Copy button:** Copies the full base URL to clipboard. On success: button text changes to "✓ copied" for 2 seconds, then reverts. Uses `navigator.clipboard.writeText()`.

**No start/stop controls here** — that is the Tools panel's responsibility.

---

## 4. MCP Servers

Source: `GET /api/services` for status + static MCP config.

```
┌──────────────────────────────────────────────────────────────┐
│ MCP Servers   MCP spec 2025-03 · streamable_http             │
│                                                              │
│ ● mcp-filesystem  :3100                                      │
│   {"type":"streamable_http","url":"http://host:3100/mcp"}   │
│   Role: Read/write /data/ directory tree                     │
│   [Copy Connection String] [Test Connection] [●/○ toggle]   │
│                                                              │
│ ● mcp-browser     :3101                                      │
│   {"type":"streamable_http","url":"http://host:3101/mcp"}   │
│   Role: Playwright headless browsing                         │
│   [Copy Connection String] [Test Connection] [●/○ toggle]   │
│                                                              │
│ ● mcp-code-exec   :3102                                      │
│   {"type":"streamable_http","url":"http://host:3102/mcp"}   │
│   Role: Sandboxed Python/shell execution                     │
│   [Copy Connection String] [Test Connection] [●/○ toggle]   │
│                                                              │
│ ● mcp-fetch       :3103                                      │
│   {"type":"streamable_http","url":"http://host:3103/mcp"}   │
│   Role: HTTP fetch and web scraping                          │
│   [Copy Connection String] [Test Connection] [●/○ toggle]   │
└──────────────────────────────────────────────────────────────┘
```

### MCP Server Card Structure

Per server, laid out as a stacked group (not a table row — too much info):

```
[dot] mcp-filesystem    :3100
{"type":"streamable_http","url":"http://10.0.0.5:3100/mcp"}
Role: Read/write /data/ directory tree
[Copy] [Test] [toggle]
```

**Connection string display:**
- `font-family: --mono`, 10px, `--text3`, truncated with ellipsis if too long
- Full string visible on hover (tooltip)
- Copy button copies the full JSON object: `{"type":"streamable_http","url":"http://{host}:{port}/mcp"}`

**Test Connection button:**
- `POST /api/mcp/{name}/test`
- Sends a ping/capabilities request to the MCP server
- Shows inline result: `✓ connected — 4 tools available` or `✗ error: connection refused`
- Result persists for 10 seconds, then fades

**Toggle (enable/disable):**
- Calls `POST /api/services/{name}/start` or `/stop`
- Same behavior as Tools panel toggle

### Claude Desktop Config Export

Button at bottom of MCP section: **"Export claude_desktop_config.json"**

Generates and downloads a `claude_desktop_config.json` file with all enabled MCP servers:
```json
{
  "mcpServers": {
    "kovati-filesystem": {
      "type": "streamable_http",
      "url": "http://10.0.0.5:3100/mcp"
    },
    "kovati-browser": {
      "type": "streamable_http",
      "url": "http://10.0.0.5:3101/mcp"
    }
  }
}
```

Only includes enabled (running) MCP servers. Filename: `kovati-mcp-config-{date}.json`.

---

## 5. API Keys

Named bearer tokens for external API access when Authentik forward-auth is in use.

Source: `GET /api/keys` — returns names, scopes, metadata (never values after creation).

```
┌──────────────────────────────────────────────────────────────┐
│ API Keys                                [+ Create New Key]   │
│                                                              │
│ Name           │ Scope         │ Created  │ Last Used │ Act  │
├──────────────────────────────────────────────────────────────┤
│ laptop-kasemo  │ vllm-pair-a   │ Jan 10   │ 2h ago    │[Rev] │
│ n8n-internal   │ all-inference │ Dec 15   │ 4d ago    │[Rev] │
│ ci-pipeline    │ ollama        │ Nov 30   │ Never     │[Rev] │
└──────────────────────────────────────────────────────────────┘
```

**"+ Create New Key" button:** Opens a modal:
```
Key name: [____________]
Scope:    [All Inference ▾] / [vllm-pair-a] / [ollama] / [custom...]
          
[Generate Key]
```

On generate: `POST /api/keys` → modal shows the generated token **once**:
```
⚠ Copy this token now — it will not be shown again.
sk-kovati-xxxxxxxxxxxxxxxxxxxx
[Copy Token] [Close]
```

**Revoke button:** `DELETE /api/keys/{name}` — confirmation dialog first.

---

## 6. External Access (Caddy Routing)

Source: `GET /api/network` — returns current Caddy reverse proxy routes.

```
┌──────────────────────────────────────────────────────────────┐
│ External Access                                              │
│ Caddy reverse proxy: ● running                               │
│                                                              │
│ Service       │ External Path          │ Exposed │ Toggle    │
├──────────────────────────────────────────────────────────────┤
│ open-webui    │ https://host/webui/    │ ●yes     │ [●/○]    │
│ n8n           │ https://host/n8n/      │ ●yes     │ [●/○]    │
│ vllm-pair-a   │ https://host/v1/       │ ○no      │ [●/○]    │
│ grafana       │ https://host/grafana/  │ ○no      │ [●/○]    │
└──────────────────────────────────────────────────────────────┘
│ ⚠ Exposing inference endpoints externally requires API key auth│
└──────────────────────────────────────────────────────────────┘
```

**Toggle action:** `PATCH /api/network/routes/{service}` with `{exposed: true/false}` — triggers Caddy config update + reload. Does not restart the service itself.

**Warning banner:** If vllm or ollama is toggled to exposed without an API key on that scope: show amber warning inline.

**Appliance Mode restriction:** In appliance mode, this section is read-only. Toggles show `disabled`. "Managed by administrator" tooltip.

---

## 7. API Dependencies

| Data | Endpoint | Method | Notes |
|------|----------|--------|-------|
| Service status | `GET /api/services` | GET | For endpoint status dots |
| API keys list | `GET /api/keys` | GET | Names + metadata only |
| Create key | `POST /api/keys` | POST | Returns token once |
| Revoke key | `DELETE /api/keys/{name}` | DELETE | |
| MCP test | `POST /api/mcp/{name}/test` | POST | Fires test request |
| Caddy routes | `GET /api/network` | GET | Route listing |
| Update route | `PATCH /api/network/routes/{service}` | PATCH | Toggle exposure |

---

## 8. Security Notes

- Bearer tokens stored in FastAPI in-memory store (v1) or SQLite (v2). Not in `docker/.env`.
- Forward-auth via Authentik applies per-service. The "Exposed" toggle in Caddy and the forward-auth policy in Authentik are separate; both must be configured for secure external access.
- The UI never shows secret values (token values, passwords) after initial creation.
- Connection strings include the LAN IP. If accessed via WireGuard, the operator may need to substitute the WireGuard tunnel IP — a note to this effect appears in the MCP section when `window.location.hostname` resolves to a WireGuard IP range.
