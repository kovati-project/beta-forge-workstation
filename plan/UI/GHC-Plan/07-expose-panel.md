# Step 07 — Expose Panel

> **Prerequisites:** Steps 01–06 complete. Read `plan/UI/GHC-Plan/00-overview.md`.
> **Reference spec:** `plan/UI/Steps/07-expose-panel.md`

---

## Goal

Implement the Expose panel (`/#/expose`) — four always-visible sections stacked vertically:

1. **OpenAI-Compatible Endpoints** — table of inference/voice URLs with live status + copy button
2. **MCP Servers** — stacked cards with connection strings, test, toggle, JSON config export
3. **API Keys** — table + create modal (token shown exactly once) + revoke
4. **External Access** — Caddy route table with per-service expose toggles

All data endpoints are Step 10 stubs. Provide mock data. `{host}` is always `window.location.hostname`.

**Security standing rule:** The UI never shows a token value after initial creation. The modal's "reveal" state must be cleared when the modal closes — there is no recovery path.

---

## Deliverables

### 1. Mock data — `ui/src/data/exposeMock.js`

```js
// TODO Step 10: replace with live API responses

export const OPENAI_ENDPOINTS = [
  { service: 'vllm-pair-a',  port: 8000, path: '/v1',              status: 'running' },
  { service: 'ollama',       port: 11434, path: '/v1',             status: 'running' },
  { service: 'vllm-pair-b',  port: 8001, path: '/v1',              status: 'stopped' },
  { service: 'vllm-4gpu',    port: 8002, path: '/v1',              status: 'stopped' },
  { service: 'litellm',      port: 4000, path: '/v1',              status: 'running' },
  { service: 'faster-whisper',port: 9000, path: '/v1/audio',       status: 'running' },
  { service: 'piper-tts',    port: 9001, path: '/v1/audio/speech', status: 'running' },
];

export const MCP_SERVERS = [
  { name: 'mcp-filesystem', port: 3100, role: 'Read/write /data/ directory tree',       status: 'running' },
  { name: 'mcp-browser',    port: 3101, role: 'Playwright headless browsing',            status: 'running' },
  { name: 'mcp-code-exec',  port: 3102, role: 'Sandboxed Python/shell execution',       status: 'running' },
  { name: 'mcp-fetch',      port: 3103, role: 'HTTP fetch and web scraping',             status: 'stopped' },
];

export const MOCK_API_KEYS = [
  { name: 'laptop-kasemo', scope: 'vllm-pair-a',   created: 'Jan 10', lastUsed: '2h ago' },
  { name: 'n8n-internal',  scope: 'all-inference', created: 'Dec 15', lastUsed: '4d ago' },
  { name: 'ci-pipeline',   scope: 'ollama',        created: 'Nov 30', lastUsed: 'Never'  },
];

export const SCOPE_OPTIONS = ['all-inference', 'vllm-pair-a', 'vllm-pair-b', 'ollama', 'litellm'];

export const MOCK_CADDY_ROUTES = [
  { service: 'open-webui',  path: '/webui/',   exposed: true  },
  { service: 'n8n',         path: '/n8n/',     exposed: true  },
  { service: 'vllm-pair-a', path: '/v1/',      exposed: false },
  { service: 'grafana',     path: '/grafana/', exposed: false },
];
```

---

### 2. `ui/src/pages/Expose.jsx`

```jsx
import { useApp } from '../context/AppContext';
import { OpenAIEndpoints } from './expose/OpenAIEndpoints';
import { McpServers }      from './expose/McpServers';
import { ApiKeys }         from './expose/ApiKeys';
import { ExternalAccess }  from './expose/ExternalAccess';
import './Expose.css';

export function Expose() {
  const { state } = useApp();
  return (
    <div className="expose-page">
      <OpenAIEndpoints services={state.services} />
      <McpServers services={state.services} />
      <ApiKeys />
      <ExternalAccess systemMode={state.systemMode} />
    </div>
  );
}
```

```css
/* Expose.css */
@import '../tokens.css';
.expose-page { display: flex; flex-direction: column; gap: 16px; }
```

---

### 3. `ui/src/pages/expose/OpenAIEndpoints.jsx`

```jsx
import { useState } from 'react';
import { Panel }     from '../../components/Panel';
import { DotStatus } from '../../components/DotStatus';
import { Tag }       from '../../components/Tag';
import { OPENAI_ENDPOINTS } from '../../data/exposeMock';
import './ExposeShared.css';

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(text).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <button className={`copy-btn ${copied ? 'copy-btn-done' : ''}`} onClick={copy}>
      {copied ? '✓ copied' : '📋'}
    </button>
  );
}

export function OpenAIEndpoints({ services }) {
  const host = window.location.hostname;

  // Merge live status with static endpoint list
  const endpoints = OPENAI_ENDPOINTS.map(ep => ({
    ...ep,
    status: services?.[ep.service]?.status ?? ep.status,
  }));

  return (
    <Panel title="OpenAI-Compatible Endpoints">
      <table className="expose-table">
        <thead>
          <tr><th>Service</th><th>Base URL</th><th>Status</th><th></th></tr>
        </thead>
        <tbody>
          {endpoints.map(ep => {
            const url = `http://${host}:${ep.port}${ep.path}`;
            const running = ep.status === 'running';
            return (
              <tr key={ep.service} className={!running ? 'row-dim' : ''}>
                <td className="ep-service">{ep.service}</td>
                <td className="ep-url">{url}</td>
                <td>
                  <span className="ep-status">
                    <DotStatus status={running ? 'green' : 'gray'} />
                    <Tag variant={running ? 'green' : 'gray'}>{ep.status}</Tag>
                  </span>
                </td>
                <td><CopyButton text={url} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Panel>
  );
}
```

---

### 4. `ui/src/pages/expose/McpServers.jsx`

```jsx
import { useState } from 'react';
import { Panel }     from '../../components/Panel';
import { Btn }       from '../../components/Btn';
import { DotStatus } from '../../components/DotStatus';
import { Toggle }    from '../../components/Toggle';
import { MCP_SERVERS } from '../../data/exposeMock';
import './ExposeShared.css';

function mcpConnectionString(host, port) {
  return JSON.stringify({ type: 'streamable_http', url: `http://${host}:${port}/mcp` });
}

export function McpServers({ services }) {
  const host = window.location.hostname;
  const [testResults, setTestResults] = useState({}); // { [name]: { ok, msg, ts } }
  const [toggleStates, setToggleStates] = useState({}); // { [name]: bool } — optimistic

  const servers = MCP_SERVERS.map(s => ({
    ...s,
    status: toggleStates[s.name] !== undefined
      ? (toggleStates[s.name] ? 'running' : 'stopped')
      : (services?.[s.name]?.status ?? s.status),
  }));

  async function handleTest(name, port) {
    setTestResults(r => ({ ...r, [name]: { pending: true } }));
    try {
      const res = await fetch(`/api/mcp/${name}/test`, { method: 'POST' });
      const data = res.ok ? await res.json() : null;
      setTestResults(r => ({
        ...r,
        [name]: { ok: res.ok, msg: data?.message ?? (res.ok ? '4 tools available' : 'connection refused') },
      }));
    } catch {
      setTestResults(r => ({ ...r, [name]: { ok: false, msg: 'connection refused' } }));
    }
    setTimeout(() => setTestResults(r => { const n = { ...r }; delete n[name]; return n; }), 10000);
  }

  async function handleToggle(name, targetOn) {
    setToggleStates(s => ({ ...s, [name]: targetOn }));
    const endpoint = `/api/services/${name}/${targetOn ? 'start' : 'stop'}`;
    try {
      await fetch(endpoint, { method: 'POST' });
    } catch { /* revert handled by next poll */ }
  }

  function downloadConfig() {
    const running = servers.filter(s => s.status === 'running');
    const config = {
      mcpServers: Object.fromEntries(
        running.map(s => [
          `kovati-${s.name.replace('mcp-', '')}`,
          { type: 'streamable_http', url: `http://${host}:${s.port}/mcp` },
        ])
      ),
    };
    const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = `kovati-mcp-config-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  // WireGuard IP note: show if hostname looks like a WireGuard range
  const isWireGuard = /^10\./.test(host) && host !== '10.0.0.1';

  return (
    <Panel title="MCP Servers" subtitle="MCP spec 2025-03 · streamable_http">
      {isWireGuard && (
        <div className="expose-info-note">
          ℹ Accessed via WireGuard ({host}) — connection strings use this IP. Substitute the LAN IP for direct network access.
        </div>
      )}

      <div className="mcp-server-list">
        {servers.map(s => {
          const connStr = mcpConnectionString(host, s.port);
          const running = s.status === 'running';
          const result  = testResults[s.name];
          return (
            <div key={s.name} className="mcp-card">
              <div className="mcp-card-header">
                <DotStatus status={running ? 'green' : 'gray'} />
                <span className="mcp-name">{s.name}</span>
                <span className="mcp-port">:{s.port}</span>
                <Toggle
                  checked={running}
                  onChange={e => handleToggle(s.name, e.target.checked)}
                />
              </div>

              <div className="mcp-conn-str" title={connStr}>{connStr}</div>
              <div className="mcp-role">{s.role}</div>

              <div className="mcp-actions">
                <CopyJsonButton text={connStr} />
                <Btn variant="gray" size="sm"
                  onClick={() => handleTest(s.name, s.port)}
                  disabled={result?.pending}>
                  {result?.pending ? 'Testing…' : 'Test Connection'}
                </Btn>
              </div>

              {result && !result.pending && (
                <div className={`mcp-test-result ${result.ok ? 'result-ok' : 'result-err'}`}>
                  {result.ok ? `✓ connected — ${result.msg}` : `✗ error: ${result.msg}`}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <Btn variant="gray" size="sm" onClick={downloadConfig}>
        Export claude_desktop_config.json
      </Btn>
    </Panel>
  );
}

function CopyJsonButton({ text }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(text).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }
  return (
    <Btn variant="gray" size="sm" onClick={copy}>
      {copied ? '✓ copied' : 'Copy Connection String'}
    </Btn>
  );
}
```

---

### 5. `ui/src/pages/expose/ApiKeys.jsx`

Token shown once. Modal has two states: `form` → `reveal`. Closing from either state clears everything.

```jsx
import { useState } from 'react';
import { Panel } from '../../components/Panel';
import { Btn }   from '../../components/Btn';
import { Tag }   from '../../components/Tag';
import { MOCK_API_KEYS, SCOPE_OPTIONS } from '../../data/exposeMock';
import './ExposeShared.css';

export function ApiKeys() {
  const [keys, setKeys]       = useState(MOCK_API_KEYS);
  const [modal, setModal]     = useState(null); // null | { phase: 'form' | 'reveal', name, scope, token }

  function openCreate() {
    setModal({ phase: 'form', name: '', scope: SCOPE_OPTIONS[0] });
  }

  function closeModal() {
    setModal(null); // token is gone — intentional
  }

  async function handleGenerate() {
    if (!modal.name.trim()) return;
    try {
      const res = await fetch('/api/keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: modal.name.trim(), scope: modal.scope }),
      });
      const data = res.ok ? await res.json() : null;
      const token = data?.token ?? `sk-kovati-${Math.random().toString(36).slice(2, 18)}`;
      setKeys(prev => [...prev, { name: modal.name.trim(), scope: modal.scope, created: 'today', lastUsed: 'Never' }]);
      setModal(m => ({ ...m, phase: 'reveal', token }));
    } catch {
      // API not ready — generate mock token for UI testing
      const token = `sk-kovati-${Math.random().toString(36).slice(2, 18)}`;
      setKeys(prev => [...prev, { name: modal.name.trim(), scope: modal.scope, created: 'today', lastUsed: 'Never' }]);
      setModal(m => ({ ...m, phase: 'reveal', token }));
    }
  }

  async function handleRevoke(name) {
    if (!window.confirm(`Revoke key "${name}"? Clients using it will lose access immediately.`)) return;
    try {
      await fetch(`/api/keys/${encodeURIComponent(name)}`, { method: 'DELETE' });
    } catch { /* API not ready */ }
    setKeys(prev => prev.filter(k => k.name !== name));
  }

  return (
    <Panel title="API Keys">
      <div className="panel-action-row">
        <Btn variant="cyan" size="sm" onClick={openCreate}>+ Create New Key</Btn>
      </div>

      <table className="expose-table">
        <thead>
          <tr><th>Name</th><th>Scope</th><th>Created</th><th>Last Used</th><th></th></tr>
        </thead>
        <tbody>
          {keys.map(k => (
            <tr key={k.name}>
              <td>{k.name}</td>
              <td><Tag variant="gray">{k.scope}</Tag></td>
              <td>{k.created}</td>
              <td>{k.lastUsed}</td>
              <td>
                <Btn variant="red" size="sm" onClick={() => handleRevoke(k.name)}>Revoke</Btn>
              </td>
            </tr>
          ))}
          {keys.length === 0 && (
            <tr><td colSpan={5} className="empty-row">No API keys — create one above</td></tr>
          )}
        </tbody>
      </table>

      {/* Modal */}
      {modal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <span>{modal.phase === 'form' ? 'Create API Key' : 'Key Created'}</span>
              <button className="modal-close" onClick={closeModal}>✕</button>
            </div>

            {modal.phase === 'form' && (
              <div className="modal-body">
                <div className="form-field">
                  <label className="form-label">Key name</label>
                  <input
                    className="form-input"
                    placeholder="e.g. laptop-kasemo"
                    value={modal.name}
                    onChange={e => setModal(m => ({ ...m, name: e.target.value }))}
                    onKeyDown={e => e.key === 'Enter' && handleGenerate()}
                    autoFocus
                  />
                </div>
                <div className="form-field">
                  <label className="form-label">Scope</label>
                  <select
                    className="form-select"
                    value={modal.scope}
                    onChange={e => setModal(m => ({ ...m, scope: e.target.value }))}
                  >
                    {SCOPE_OPTIONS.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <Btn variant="cyan" size="md" onClick={handleGenerate} disabled={!modal.name.trim()}>
                  Generate Key
                </Btn>
              </div>
            )}

            {modal.phase === 'reveal' && (
              <div className="modal-body">
                <div className="token-warning">
                  ⚠ Copy this token now — it will not be shown again.
                </div>
                <div className="token-display">
                  <code className="token-value">{modal.token}</code>
                  <OneCopyButton text={modal.token} />
                </div>
                <Btn variant="gray" size="sm" onClick={closeModal}>Close</Btn>
              </div>
            )}
          </div>
        </div>
      )}
    </Panel>
  );
}

function OneCopyButton({ text }) {
  const [copied, setCopied] = useState(false);
  function copy() {
    navigator.clipboard.writeText(text).catch(() => {});
    setCopied(true);
  }
  return (
    <Btn variant={copied ? 'gray' : 'cyan'} size="sm" onClick={copy}>
      {copied ? '✓ Copied' : 'Copy Token'}
    </Btn>
  );
}
```

---

### 6. `ui/src/pages/expose/ExternalAccess.jsx`

```jsx
import { useState } from 'react';
import { Panel }     from '../../components/Panel';
import { DotStatus } from '../../components/DotStatus';
import { Toggle }    from '../../components/Toggle';
import { Tag }       from '../../components/Tag';
import { MOCK_CADDY_ROUTES } from '../../data/exposeMock';
import './ExposeShared.css';

const INFERENCE_SERVICES = new Set(['vllm-pair-a', 'vllm-pair-b', 'vllm-4gpu', 'ollama', 'litellm']);

export function ExternalAccess({ systemMode }) {
  const [routes, setRoutes] = useState(MOCK_CADDY_ROUTES);
  const [caddyStatus] = useState('running'); // TODO Step 10: from /api/network
  const isAppliance = systemMode === 'appliance';

  async function handleToggle(service, targetExposed) {
    if (isAppliance) return;

    // Warn if exposing an inference service without checking API key coverage
    if (targetExposed && INFERENCE_SERVICES.has(service)) {
      const ok = window.confirm(
        `Expose "${service}" externally?\n\n⚠ Ensure an API key with scope covering this service exists, otherwise it will be publicly accessible.`
      );
      if (!ok) return;
    }

    setRoutes(prev => prev.map(r => r.service === service ? { ...r, exposed: targetExposed } : r));
    try {
      await fetch(`/api/network/routes/${service}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ exposed: targetExposed }),
      });
    } catch { /* API not ready — optimistic state stands */ }
  }

  const exposedInferenceWithoutKey = routes.some(
    r => r.exposed && INFERENCE_SERVICES.has(r.service)
  );

  return (
    <Panel title="External Access">
      <div className="caddy-status-row">
        <span className="caddy-label">Caddy reverse proxy</span>
        <DotStatus status={caddyStatus === 'running' ? 'green' : 'red'} />
        <Tag variant={caddyStatus === 'running' ? 'green' : 'red'}>{caddyStatus}</Tag>
      </div>

      {isAppliance && (
        <div className="expose-info-note expose-note-locked">
          🔒 Managed by administrator — external routing is read-only in appliance mode.
        </div>
      )}

      {exposedInferenceWithoutKey && !isAppliance && (
        <div className="expose-warn-note">
          ⚠ Exposing inference endpoints externally requires API key auth — ensure keys are configured.
        </div>
      )}

      <table className="expose-table">
        <thead>
          <tr><th>Service</th><th>External Path</th><th>Exposed</th><th></th></tr>
        </thead>
        <tbody>
          {routes.map(r => (
            <tr key={r.service}>
              <td>{r.service}</td>
              <td className="ep-url">https://{window.location.hostname}{r.path}</td>
              <td>
                <span className="ep-status">
                  <DotStatus status={r.exposed ? 'green' : 'gray'} />
                  <Tag variant={r.exposed ? 'green' : 'gray'}>{r.exposed ? 'yes' : 'no'}</Tag>
                </span>
              </td>
              <td>
                <Toggle
                  checked={r.exposed}
                  disabled={isAppliance}
                  onChange={e => handleToggle(r.service, e.target.checked)}
                  title={isAppliance ? 'Managed by administrator' : undefined}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}
```

---

### 7. `ui/src/pages/expose/ExposeShared.css`

Shared styles for all four sections.

```css
@import '../../tokens.css';

/* Tables */
.expose-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 10px;
  margin-top: 8px;
}

.expose-table th {
  text-align: left;
  color: var(--text3);
  font-size: 9px;
  border-bottom: 1px solid var(--border);
  padding: 4px 8px;
}

.expose-table td {
  padding: 6px 8px;
  color: var(--text2);
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}

.expose-table tr:last-child td { border-bottom: none; }

.row-dim td { opacity: 0.5; }

.ep-service { font-weight: 500; color: var(--text); }

.ep-url {
  font-size: 9px;
  color: var(--text3);
  font-family: var(--mono);
  max-width: 280px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ep-status { display: flex; align-items: center; gap: 4px; }

.empty-row {
  color: var(--text3);
  font-style: italic;
  text-align: center;
  padding: 14px !important;
}

/* Copy button */
.copy-btn {
  background: var(--surface3);
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--text3);
  cursor: pointer;
  font-family: var(--mono);
  font-size: 9px;
  padding: 2px 8px;
  transition: color .15s, border-color .15s;
  white-space: nowrap;
}

.copy-btn:hover     { color: var(--text); border-color: var(--border2); }
.copy-btn-done      { color: var(--green); border-color: var(--green); }

/* MCP cards */
.mcp-server-list    { display: flex; flex-direction: column; gap: 10px; margin-bottom: 12px; }

.mcp-card {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.mcp-card-header {
  display: flex;
  align-items: center;
  gap: 6px;
}

.mcp-name { font-size: 11px; font-weight: 600; color: var(--text); flex: 1; }
.mcp-port { font-size: 9px; color: var(--text3); }

.mcp-conn-str {
  font-size: 9px;
  color: var(--text3);
  font-family: var(--mono);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: default;
}

.mcp-role { font-size: 9px; color: var(--text3); }

.mcp-actions { display: flex; gap: 6px; flex-wrap: wrap; }

.mcp-test-result {
  font-size: 9px;
  padding: 3px 0;
}

.result-ok  { color: var(--green); }
.result-err { color: var(--red); }

/* Info / warning notes */
.expose-info-note {
  font-size: 9px;
  color: var(--text3);
  padding: 6px 10px;
  background: var(--surface2);
  border-radius: 3px;
  margin-bottom: 8px;
}

.expose-warn-note {
  font-size: 9px;
  color: var(--amber);
  background: var(--amber-dim);
  border: 1px solid rgba(255,179,71,.3);
  border-radius: 3px;
  padding: 6px 10px;
  margin-bottom: 8px;
}

.expose-note-locked { color: var(--text3); }

/* Caddy status */
.caddy-status-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  font-size: 10px;
}

.caddy-label { color: var(--text3); }

/* Panel action row */
.panel-action-row { margin-bottom: 8px; }

/* API key modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.6);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.modal {
  background: var(--surface);
  border: 1px solid var(--border2);
  border-radius: var(--radius);
  min-width: 360px;
  max-width: 480px;
  width: 100%;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text);
  border-bottom: 1px solid var(--border);
}

.modal-close {
  background: none;
  border: none;
  color: var(--text3);
  cursor: pointer;
  font-size: 12px;
  padding: 2px 4px;
}

.modal-body {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.form-field { display: flex; flex-direction: column; gap: 4px; }
.form-label { font-size: 9px; color: var(--text3); }

.form-input, .form-select {
  background: var(--surface3);
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--text);
  font-family: var(--mono);
  font-size: 10px;
  padding: 5px 8px;
  width: 100%;
}

.token-warning {
  font-size: 10px;
  color: var(--amber);
  background: var(--amber-dim);
  border: 1px solid rgba(255,179,71,.3);
  border-radius: 3px;
  padding: 8px 10px;
}

.token-display {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--surface2);
  border: 1px solid var(--border2);
  border-radius: 3px;
  padding: 8px 10px;
}

.token-value {
  flex: 1;
  font-family: var(--mono);
  font-size: 10px;
  color: var(--cyan);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
```

---

## Acceptance Criteria

- [ ] All four sections render without tabs — stacked vertically as Panels
- [ ] **Endpoints:** Each row shows live status dot from `state.services` (falls back to mock); copy button changes to "✓ copied" for 2s then reverts; `{host}` is `window.location.hostname` not `localhost`
- [ ] **MCP:** Connection string shows full JSON, truncated with ellipsis, full value in `title` tooltip; "Test Connection" shows ✓/✗ result for 10s then clears; toggle calls start/stop; "Export claude_desktop_config.json" downloads a valid JSON file containing only running servers
- [ ] **API Keys:** "+ Create New Key" opens modal with name + scope form; "Generate Key" shows token reveal view; token is never shown again after modal closes; "Revoke" confirms then removes row
- [ ] **External Access:** Toggle calls PATCH /api/network/routes/{service}; exposing inference service shows `window.confirm` warning; in `appliance` mode all toggles are disabled with "Managed by administrator" tooltip
- [ ] `navigator.clipboard.writeText` used for all copy actions (no `document.execCommand`)
- [ ] No console errors on page load or interaction

---

## Feedback

Write `plan/UI/GHC-Feedback/07-feedback.md` when done.

**Required in Notes:**
- Does `window.location.hostname` return the LAN IP (e.g. `10.0.0.5`) or `localhost` when the dev server is accessed from the same machine? This affects whether the connection strings are useful immediately or only over LAN.
- Confirm the file download trick (`URL.createObjectURL(new Blob(...))`) works without any Content-Security-Policy issues in the dev environment.
