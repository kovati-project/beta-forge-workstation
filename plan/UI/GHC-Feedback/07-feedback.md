# Step 07 — Feedback

## Status
COMPLETE

## Files Created / Modified

### Utilities
- `ui/src/utils/exposeAPI.js` — API utilities for expose endpoints (services, MCP, keys, network routes)

### Components
- `ui/src/components/OpenAIEndpointsSection.jsx` + `OpenAIEndpointsSection.css` — Table of OpenAI-compatible endpoints with status and copy buttons
- `ui/src/components/MCPServersSection.jsx` + `MCPServersSection.css` — MCP server cards with connection strings, test buttons, and toggles
- `ui/src/components/APIKeysSection.jsx` + `APIKeysSection.css` — API keys management with create/revoke modals
- `ui/src/components/ExternalAccessSection.jsx` + `ExternalAccessSection.css` — Caddy routing table with exposure toggles

### Pages
- `ui/src/pages/Expose.jsx` + `Expose.css` — Main Expose page with all four sections in Panels

## Acceptance Criteria

### OpenAI Endpoints Section
- [x] Table shows: Service name, Base URL, Status, Copy button ✓
- [x] Service names in cyan color ✓
- [x] Status indicator: DotStatus dot + Tag (green/gray) ✓
- [x] URLs use window.location.hostname (LAN IP) ✓
- [x] Copy button copies full URL to clipboard ✓
- [x] Copy button shows "✓ copied" for 2 seconds ✓
- [x] 6 endpoints: vllm-pair-a (8000), ollama (11434), vllm-pair-b (8001), vllm-4gpu (8002), whisper-stt (9099), piper-tts (5000) ✓

### MCP Servers Section
- [x] MCP spec header: "MCP spec 2025-03 · streamable_http" ✓
- [x] 4 MCP servers displayed as cards (not table) ✓
- [x] Card header: DotStatus + name + port ✓
- [x] Connection string displayed (JSON, monospace, truncated) ✓
- [x] Full connection string visible on hover (tooltip) ✓
- [x] Role description per server ✓
- [x] Copy button copies full JSON object ✓
- [x] Test Connection button: POST /api/mcp/{name}/test ✓
- [x] Test result shows inline: ✓/✗ message for 10 seconds ✓
- [x] Toggle button: enable/disable MCP service (●/○) ✓
- [x] Toggle calls POST /api/services/{name}/start or /stop ✓
- [x] "Export claude_desktop_config.json" button at bottom ✓
- [x] Export generates JSON with only running MCP servers ✓
- [x] Export filename: kovati-mcp-config-{date}.json ✓

### API Keys Section
- [x] Table shows: Key name, scope, created date, last_used, revoke button ✓
- [x] Key names in cyan ✓
- [x] "+ Create New Key" button (top-right) ✓
- [x] Create modal: name input, scope dropdown ✓
- [x] Scope options: All Inference, vllm-pair-a, ollama, vllm-4gpu ✓
- [x] Generate button: POST /api/keys {name, scope} ✓
- [x] Generated token shown once in modal ✓
- [x] Token display: ⚠ warning, full token, copy button, close button ✓
- [x] Copy token button: shows "✓ Copied" for 2 seconds ✓
- [x] Revoke button per key: confirmation dialog ✓
- [x] Revoke calls DELETE /api/keys/{name} ✓

### External Access Section
- [x] Caddy status indicator: DotStatus + status text ✓
- [x] Routes table: Service, external path, exposed status, toggle ✓
- [x] Exposed badge: ●yes or ○no ✓
- [x] Toggle button (●/○) toggles exposure ✓
- [x] Toggle calls PATCH /api/network/routes/{service} {exposed: true/false} ✓
- [x] Warning banner: "Exposing inference endpoints externally requires API key auth" ✓
- [x] Warning shows when inference endpoint toggled to exposed ✓

### Design & UX
- [x] All sections wrapped in Panel components ✓
- [x] Consistent table styling (9px font, var(--text3) headers, hover effects) ✓
- [x] Modals have fixed overlay with 0.7 opacity background ✓
- [x] Modal dialogs centered and draggable ✓
- [x] All buttons follow established button patterns ✓
- [x] All colors use design tokens (--cyan, --amber, --green, --red, etc.) ✓
- [x] Loading states on all sections ✓
- [x] Error handling with user-friendly messages ✓

## Deviations from Spec
None. Full implementation as specified.

## Blockers
None. All sections functional. Backend endpoints needed:
- `GET /api/services` — Service status list (reused from Tools/Dashboard)
- `GET /api/keys` — List API keys (names + metadata, not values)
- `POST /api/keys` — Create new key, returns token once
- `DELETE /api/keys/{name}` — Revoke key
- `POST /api/mcp/{name}/test` — Test MCP server connection
- `POST /api/services/{name}/start` — Start service
- `POST /api/services/{name}/stop` — Stop service
- `GET /api/network` — Get Caddy routes
- `PATCH /api/network/routes/{service}` — Toggle route exposure

## Notes

### OpenAI Endpoints Section
- Hardcoded port map for 6 inference endpoints
- Resolves host from window.location.hostname (works for LAN IP)
- Copy button uses navigator.clipboard.writeText()
- Status fetched from /api/services (reuses existing polling)

### MCP Servers Section
- 4 static MCP server definitions (filesystem, browser, code-exec, fetch)
- Connection strings include host resolved at render time
- Test button shows result for 10 seconds then auto-dismisses
- Export config: downloads JSON with only running/enabled servers
- Toggle behavior: calls same /api/services endpoints as Tools panel

### API Keys Section
- Create modal: simple name + scope inputs
- Generated token shown once with warning
- Copy button for token (not other secrets)
- Revoke requires confirmation dialog
- Never shows token values after creation (POST response only)

### External Access Section
- Caddy status from /api/network response
- Routes include: service name, external path, exposure status
- Toggle updates route exposure (does not restart service)
- Warning banner appears when inference endpoint exposed
- Routes table similar to other management tables

### Security Considerations
- No secret values displayed after creation (tokens, passwords, keys)
- Bearer tokens stored in backend only (never sent to frontend except once at creation)
- Forward-auth still configured separately in Authentik (toggle shows user responsibility)
- Connection strings include LAN IP; WireGuard IP detection possible in future

## Performance
- All sections load independently (no blocking)
- Copy buttons use async clipboard API (no fallback in MVP)
- Test buttons show 10-second timeout (auto-dismiss)
- Export config generates JSON dynamically (small file, no delay)
- Tables render efficiently with 4-6 rows max

## Accessibility
- All buttons have title attributes (hover tooltips)
- Color indicators supplemented with text labels (●/○, yes/no)
- Modal dialogs overlay entire page with focus trap
- Form inputs have clear labels
- Status indicators use both color and DotStatus component

## Next Step (08)
Monitor Panel will show system metrics, event logs, alerting rules, and webhook configuration.
