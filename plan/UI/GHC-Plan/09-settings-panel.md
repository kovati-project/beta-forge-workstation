# Step 09 — Settings Panel

> **Prerequisites:** Steps 01–08 complete. Read `plan/UI/GHC-Plan/00-overview.md`.
> **Reference spec:** `plan/UI/Steps/09-settings-panel.md`

---

## Goal

Implement the Settings panel (`/#/settings`) — five stacked sections:

| Section | Content |
|---------|---------|
| **Secrets** | `.env` key names + per-key rotate + rotate-all with two-step confirm |
| **Network** | Jumpbox IP edit, WireGuard status, Caddy, mode field |
| **Auth** | Authentik status + user table with action dropdown |
| **Stack Management** | Image table, Update All (SSE stream log), per-service rollback |
| **Backups** | Cron schedule editor, Run Now, history table |
| **Platform** | First-boot wizard summary (shown always; re-run gated) |

**Layout:** Secrets + (Network stacked on Auth) in a two-column top row; remaining sections single-column below.

**Appliance mode:** Most write operations are hidden or read-only. Use `state.systemMode === 'appliance'` from AppContext throughout.

**Security rule: secret values are never shown anywhere on this page.** No "reveal" button exists.

---

## Deliverables

### 1. Mock data — `ui/src/data/settingsMock.js`

```js
// TODO Step 10: replace with live API responses

export const MOCK_SECRETS = [
  { key: 'POSTGRES_PASSWORD',    last_rotated_days: 60, affects: ['langfuse','n8n','dify'] },
  { key: 'LANGFUSE_SECRET_KEY',  last_rotated_days: 60, affects: ['langfuse'] },
  { key: 'MINIO_SECRET_KEY',     last_rotated_days: 60, affects: ['minio'] },
  { key: 'AUTHENTIK_SECRET_KEY', last_rotated_days: 60, affects: ['authentik'] },
  { key: 'N8N_ENCRYPTION_KEY',   last_rotated_days: 60, affects: ['n8n'] },
  { key: 'DIFY_SECRET_KEY',      last_rotated_days: 60, affects: ['dify'] },
  { key: 'LANGFUSE_SALT',        last_rotated_days: 60, affects: ['langfuse'] },
  { key: 'GRAFANA_ADMIN_PASS',   last_rotated_days: 60, affects: ['grafana'] },
  { key: 'QDRANT_API_KEY',       last_rotated_days: 60, affects: ['qdrant'] },
  { key: 'SEARXNG_SECRET',       last_rotated_days: 60, affects: ['searxng'] },
  { key: 'OPENWEBUI_SECRET',     last_rotated_days: 60, affects: ['open-webui'] },
  { key: 'MINIO_ACCESS_KEY',     last_rotated_days: 60, affects: ['minio'] },
  { key: 'CADDY_API_TOKEN',      last_rotated_days: 60, affects: ['caddy'] },
  { key: 'JWT_SECRET',           last_rotated_days: 60, affects: ['loadout-manager'] },
];

export const MOCK_NETWORK = {
  jumpbox_ip: '10.0.0.1',
  wireguard: { status: 'connected', peers: 2 },
  caddy_running: true,
  mode: 'workstation',
  interfaces: [
    { name: 'eth1', ip: '192.168.1.100', speed: '1GbE', role: 'Management' },
    { name: 'eth0', ip: '10.0.0.5',      speed: '10GbE', role: 'Data' },
  ],
};

export const MOCK_AUTH = {
  authentik: { status: 'running', http_port: 9080 },
  forward_auth_services: ['open-webui', 'n8n'],
  users: [
    { username: 'kasemo',  email: 'k@example.com',   last_login: '2h ago',  role: 'admin' },
    { username: 'devuser', email: 'dev@example.com',  last_login: '3d ago',  role: 'user'  },
  ],
};

export const MOCK_STACK_IMAGES = [
  { service: 'vllm-pair-a',    image: 'vllm/vllm-openai:v0.9.1',  digest: 'a1b2c3d4',  previous_digest: 'e5f6a7b8', pulled_at: '3d ago' },
  { service: 'ollama',         image: 'ollama/ollama:0.6.8',        digest: 'c5d6e7f8',  previous_digest: null,       pulled_at: '3d ago' },
  { service: 'open-webui',     image: 'ghcr.io/open-webui:main',   digest: '9a0b1c2d',  previous_digest: '3e4f5a6b', pulled_at: '3d ago' },
  { service: 'n8n',            image: 'n8nio/n8n:1.42.0',           digest: '3e4f5a6b',  previous_digest: null,       pulled_at: '3d ago' },
  { service: 'langfuse',       image: 'langfuse/langfuse:3.1.0',   digest: '7c8d9e0f',  previous_digest: '1a2b3c4d', pulled_at: '3d ago' },
  { service: 'grafana',        image: 'grafana/grafana:11.0.0',     digest: '5f6a7b8c',  previous_digest: null,       pulled_at: '7d ago' },
  { service: 'minio',          image: 'minio/minio:RELEASE.2024-01',digest: '9d0e1f2a',  previous_digest: null,       pulled_at: '7d ago' },
];

export const MOCK_BACKUP_CONFIG = {
  schedule: '0 6 * * *',
  destination: '/data/backups/',
};

export const MOCK_BACKUP_HISTORY = [
  { id: 1, ts: '2026-06-05 06:00', size_gb: 42, status: 'ok'   },
  { id: 2, ts: '2026-06-04 06:00', size_gb: 41, status: 'ok'   },
  { id: 3, ts: '2026-06-03 06:00', size_gb: 43, status: 'fail' },
  { id: 4, ts: '2026-06-02 06:00', size_gb: 41, status: 'ok'   },
  { id: 5, ts: '2026-06-01 06:00', size_gb: 40, status: 'ok'   },
];

export const MOCK_PLATFORM = {
  wizard_completed:  true,
  wizard_date:       '2026-06-01 14:22',
  hardware:          '4× RTX A5500 · NVLink A(0↔3) B(1↔2)',
  profile_assigned:  'dual-stack',
  secrets_status:    'generated',
  network_status:    'configured',
  stack_status:      'provisioned',
};
```

---

### 2. `ui/src/pages/Settings.jsx`

```jsx
import { useApp }         from '../context/AppContext';
import { Secrets }        from './settings/Secrets';
import { Network }        from './settings/Network';
import { Auth }           from './settings/Auth';
import { StackManager }   from './settings/StackManager';
import { Backups }        from './settings/Backups';
import { Platform }       from './settings/Platform';
import './Settings.css';

export function Settings() {
  const { state } = useApp();
  const isAppliance = state.systemMode === 'appliance';

  return (
    <div className="settings-page">
      <div className="settings-top-row">
        <Secrets isAppliance={isAppliance} />
        <div className="settings-right-col">
          <Network isAppliance={isAppliance} />
          <Auth isAppliance={isAppliance} />
        </div>
      </div>
      <StackManager isAppliance={isAppliance} />
      <Backups isAppliance={isAppliance} />
      <Platform isAppliance={isAppliance} />
    </div>
  );
}
```

```css
/* Settings.css */
@import '../tokens.css';

.settings-page       { display: flex; flex-direction: column; gap: 16px; }

.settings-top-row    { display: grid; grid-template-columns: 1fr 380px; gap: 16px; align-items: start; }
.settings-right-col  { display: flex; flex-direction: column; gap: 16px; }

@media (max-width: 1100px) {
  .settings-top-row { grid-template-columns: 1fr; }
}
```

---

### 3. `ui/src/pages/settings/Secrets.jsx`

Rotate flow:
1. `window.confirm` with service list
2. `POST /api/secrets/{key}/rotate` → `{ key, affects, status: "rotating" }`
3. Show per-affected-service spinner (mock 2s delay, then "✓")
4. Update "Last Rotated" to "just now"

Rotate All flow:
1. Modal step 1: confirmation question
2. Modal step 2: type "rotate all" in input to enable the final button

Appliance mode: table replaced with a locked notice. Rotate buttons removed entirely (not just disabled).

```jsx
import { useState } from 'react';
import { Panel }    from '../../components/Panel';
import { Btn }      from '../../components/Btn';
import { Tag }      from '../../components/Tag';
import { MOCK_SECRETS } from '../../data/settingsMock';
import './SettingsShared.css';

const PAGE_SIZE = 8;

export function Secrets({ isAppliance }) {
  const [secrets,   setSecrets]  = useState(MOCK_SECRETS);
  const [showAll,   setShowAll]  = useState(false);
  const [rotating,  setRotating] = useState({}); // { [key]: ['svc-a', 'svc-b', ...] }
  const [rotated,   setRotated]  = useState({}); // { [key]: true }
  const [rotateAll, setRotateAll]= useState(null); // null | { step: 1|2, input: '' }

  const visible = showAll ? secrets : secrets.slice(0, PAGE_SIZE);

  async function handleRotate(key, affects) {
    const ok = window.confirm(
      `Rotate ${key}?\n\nThis will restart: ${affects.join(', ')}.\nThese services will be briefly unavailable.`
    );
    if (!ok) return;

    setRotating(r => ({ ...r, [key]: affects }));
    try {
      await fetch(`/api/secrets/${encodeURIComponent(key)}/rotate`, { method: 'POST' });
    } catch { /* API not ready — mock the delay */ }

    // Mock: 2s delay per service then mark done
    await new Promise(res => setTimeout(res, 2000));
    setRotating(r => { const n = { ...r }; delete n[key]; return n; });
    setRotated(r => ({ ...r, [key]: true }));
    setSecrets(prev => prev.map(s => s.key === key ? { ...s, last_rotated_days: 0 } : s));
  }

  async function handleRotateAll() {
    // step 2 confirmed
    setRotateAll(null);
    setRotating(Object.fromEntries(secrets.map(s => [s.key, s.affects])));
    try {
      for (const s of secrets) {
        await fetch(`/api/secrets/${encodeURIComponent(s.key)}/rotate`, { method: 'POST' });
        setRotating(r => { const n = { ...r }; delete n[s.key]; return n; });
        setRotated(r => ({ ...r, [s.key]: true }));
      }
    } catch { /* mock: still clear all */ }
    setRotating({});
    setSecrets(prev => prev.map(s => ({ ...s, last_rotated_days: 0 })));
  }

  if (isAppliance) {
    return (
      <Panel title={`Secrets · ${secrets.length} keys`}>
        <div className="settings-locked-notice">
          🔒 Secrets managed by administrator.
        </div>
      </Panel>
    );
  }

  return (
    <Panel title={`Secrets · ${secrets.length} keys · docker/.env`}>
      <table className="settings-table">
        <thead>
          <tr><th>Key</th><th>Last Rotated</th><th>Affects</th><th></th></tr>
        </thead>
        <tbody>
          {visible.map(s => {
            const isRotating = !!rotating[s.key];
            return (
              <tr key={s.key}>
                <td className="secret-key">{s.key}</td>
                <td className="secret-rotated">
                  {rotated[s.key] ? 'just now' : `${s.last_rotated_days}d ago`}
                </td>
                <td>
                  {s.affects.map(a => (
                    <Tag key={a} variant="gray">{a}</Tag>
                  ))}
                  {isRotating && (
                    <span className="rotate-progress">
                      {rotating[s.key].map(svc => (
                        <span key={svc} className="rotate-svc-spin">↻ {svc}</span>
                      ))}
                    </span>
                  )}
                </td>
                <td>
                  <Btn
                    variant="amber"
                    size="sm"
                    disabled={isRotating}
                    onClick={() => handleRotate(s.key, s.affects)}
                  >
                    {isRotating ? '…' : 'Rotate'}
                  </Btn>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {!showAll && secrets.length > PAGE_SIZE && (
        <button className="show-all-btn" onClick={() => setShowAll(true)}>
          + {secrets.length - PAGE_SIZE} more · Show All
        </button>
      )}

      <div className="secrets-footer">
        <Btn variant="red" size="sm" onClick={() => setRotateAll({ step: 1, input: '' })}>
          Rotate All {secrets.length} Secrets
        </Btn>
      </div>

      {/* Two-step Rotate All modal */}
      {rotateAll && (
        <div className="modal-overlay" onClick={() => setRotateAll(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              Rotate All Secrets
              <button className="modal-close" onClick={() => setRotateAll(null)}>✕</button>
            </div>

            {rotateAll.step === 1 && (
              <div className="modal-body">
                <p className="modal-text">
                  Rotate all {secrets.length} secrets? All services will restart sequentially.
                  Expect several minutes of partial downtime.
                </p>
                <div className="modal-actions">
                  <Btn variant="gray" size="sm" onClick={() => setRotateAll(null)}>Cancel</Btn>
                  <Btn variant="red"  size="sm" onClick={() => setRotateAll({ step: 2, input: '' })}>
                    Continue
                  </Btn>
                </div>
              </div>
            )}

            {rotateAll.step === 2 && (
              <div className="modal-body">
                <p className="modal-text">Type <strong>rotate all</strong> to confirm:</p>
                <input
                  className="form-input"
                  autoFocus
                  value={rotateAll.input}
                  onChange={e => setRotateAll(r => ({ ...r, input: e.target.value }))}
                  placeholder="rotate all"
                />
                <div className="modal-actions">
                  <Btn variant="gray" size="sm" onClick={() => setRotateAll(null)}>Cancel</Btn>
                  <Btn
                    variant="red" size="sm"
                    disabled={rotateAll.input !== 'rotate all'}
                    onClick={handleRotateAll}
                  >
                    Rotate All
                  </Btn>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </Panel>
  );
}
```

---

### 4. `ui/src/pages/settings/Network.jsx`

Jumpbox IP edit: click "Edit" → text input appears with "Save" + "Cancel". On Save: `PATCH /api/network { jumpbox_ip }`.

Mode field: editable `<select>` in workstation mode, plain text in appliance mode.

WireGuard "Config ↗" and Caddy "Config ↗" open new tabs (or modal if no web UI).

```jsx
import { useState } from 'react';
import { Panel }    from '../../components/Panel';
import { Btn }      from '../../components/Btn';
import { DotStatus }from '../../components/DotStatus';
import { MOCK_NETWORK } from '../../data/settingsMock';
import './SettingsShared.css';

export function Network({ isAppliance }) {
  const [net,       setNet]      = useState(MOCK_NETWORK);
  const [editing,   setEditing]  = useState(false);
  const [ipDraft,   setIpDraft]  = useState(net.jumpbox_ip);
  const [saving,    setSaving]   = useState(false);

  async function saveJumpboxIp() {
    setSaving(true);
    try {
      await fetch('/api/network', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ jumpbox_ip: ipDraft }),
      });
      setNet(n => ({ ...n, jumpbox_ip: ipDraft }));
    } catch { /* API not ready */ }
    setSaving(false);
    setEditing(false);
  }

  async function saveMode(mode) {
    try {
      await fetch('/api/network', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
      setNet(n => ({ ...n, mode }));
    } catch { /* API not ready */ }
  }

  return (
    <Panel title="Network">
      <table className="settings-kv-table">
        <tbody>
          <tr>
            <td className="kv-label">Jumpbox IP</td>
            <td className="kv-value">
              {editing && !isAppliance ? (
                <span className="inline-edit">
                  <input
                    className="inline-input"
                    value={ipDraft}
                    onChange={e => setIpDraft(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && saveJumpboxIp()}
                    autoFocus
                  />
                  <Btn variant="cyan" size="sm" onClick={saveJumpboxIp} disabled={saving}>
                    {saving ? '…' : 'Save'}
                  </Btn>
                  <Btn variant="gray" size="sm" onClick={() => { setEditing(false); setIpDraft(net.jumpbox_ip); }}>
                    Cancel
                  </Btn>
                </span>
              ) : (
                <span className="kv-inline">
                  {net.jumpbox_ip}
                  {!isAppliance && (
                    <button className="kv-edit-btn" onClick={() => setEditing(true)}>Edit</button>
                  )}
                </span>
              )}
            </td>
          </tr>

          <tr>
            <td className="kv-label">WireGuard</td>
            <td className="kv-value">
              <span className="kv-status-row">
                <DotStatus status={net.wireguard.status === 'connected' ? 'green' : 'red'} />
                {net.wireguard.status} · {net.wireguard.peers} peer{net.wireguard.peers !== 1 ? 's' : ''}
                <button className="kv-link-btn" onClick={() => window.open(`http://${net.jumpbox_ip}:51820`, '_blank')}>
                  Config ↗
                </button>
              </span>
            </td>
          </tr>

          <tr>
            <td className="kv-label">Caddy Proxy</td>
            <td className="kv-value">
              <span className="kv-status-row">
                <DotStatus status={net.caddy_running ? 'green' : 'red'} />
                {net.caddy_running ? 'running' : 'stopped'}
                <button className="kv-link-btn" onClick={() => window.open(`http://${net.jumpbox_ip}:2019`, '_blank')}>
                  Config ↗
                </button>
              </span>
            </td>
          </tr>

          {net.interfaces.map(iface => (
            <tr key={iface.name}>
              <td className="kv-label">{iface.role} IF</td>
              <td className="kv-value kv-dim">{iface.name} · {iface.ip} ({iface.speed})</td>
            </tr>
          ))}

          <tr>
            <td className="kv-label">Mode</td>
            <td className="kv-value">
              {isAppliance ? (
                <span className="kv-locked">appliance 🔒</span>
              ) : (
                <select
                  className="kv-select"
                  value={net.mode}
                  onChange={e => saveMode(e.target.value)}
                >
                  <option value="workstation">workstation</option>
                  <option value="appliance">appliance</option>
                </select>
              )}
            </td>
          </tr>
        </tbody>
      </table>
    </Panel>
  );
}
```

---

### 5. `ui/src/pages/settings/Auth.jsx`

"Open ↗" and "+ Add User" open Authentik admin in new tab — KOVATI OS does not replicate Authentik's full UI.

Action dropdown `[▼]` per user row: use a `<details>` element for the popup (no portal needed at this scale).

```jsx
import { useState }      from 'react';
import { Panel }         from '../../components/Panel';
import { Btn }           from '../../components/Btn';
import { DotStatus }     from '../../components/DotStatus';
import { Tag }           from '../../components/Tag';
import { MOCK_AUTH }     from '../../data/settingsMock';
import './SettingsShared.css';

export function Auth({ isAppliance }) {
  const [auth,   setAuth]   = useState(MOCK_AUTH);

  const authentikUrl = `http://${window.location.hostname}:${auth.authentik.http_port}`;

  async function revokeAllSessions(username) {
    if (!window.confirm(`Revoke all sessions for ${username}?`)) return;
    try {
      await fetch(`/api/auth/users/${username}/sessions`, { method: 'DELETE' });
    } catch { /* API not ready */ }
  }

  async function deleteUser(username) {
    if (!window.confirm(`Delete user ${username}? This cannot be undone.`)) return;
    try {
      await fetch(`/api/auth/users/${username}`, { method: 'DELETE' });
      setAuth(a => ({ ...a, users: a.users.filter(u => u.username !== username) }));
    } catch { /* API not ready */ }
  }

  return (
    <Panel title="Auth">
      <div className="auth-service-row">
        <DotStatus status={auth.authentik.status === 'running' ? 'green' : 'red'} />
        <span>Authentik SSO :{auth.authentik.http_port}</span>
        <button className="kv-link-btn" onClick={() => window.open(authentikUrl, '_blank')}>
          Open ↗
        </button>
      </div>

      <div className="auth-fwdauth">
        Forward auth: {auth.forward_auth_services.map(s => (
          <Tag key={s} variant="gray">{s}</Tag>
        ))}
      </div>

      <div className="auth-users-header">
        <span>Users</span>
        {!isAppliance && (
          <button
            className="kv-link-btn"
            onClick={() => window.open(`${authentikUrl}/if/admin/#/identity/users`, '_blank')}
          >
            + Add User ↗
          </button>
        )}
      </div>

      <table className="settings-table">
        <thead>
          <tr><th>Username</th><th>Email</th><th>Last Login</th><th>Role</th><th></th></tr>
        </thead>
        <tbody>
          {auth.users.map(u => (
            <tr key={u.username}>
              <td>{u.username}</td>
              <td className="kv-dim">{u.email}</td>
              <td className="kv-dim">{u.last_login}</td>
              <td><Tag variant={u.role === 'admin' ? 'cyan' : 'gray'}>{u.role}</Tag></td>
              <td>
                {!isAppliance && (
                  <details className="action-dropdown">
                    <summary className="action-dropdown-btn">▼</summary>
                    <div className="action-dropdown-menu">
                      <button onClick={() => window.open(`${authentikUrl}/if/admin/#/identity/users`, '_blank')}>
                        Edit in Authentik ↗
                      </button>
                      <button onClick={() => revokeAllSessions(u.username)}>
                        Revoke All Sessions
                      </button>
                      <button className="action-destructive" onClick={() => deleteUser(u.username)}>
                        Delete User
                      </button>
                    </div>
                  </details>
                )}
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

### 6. `ui/src/pages/settings/StackManager.jsx`

**Update All** uses `fetch` with a `ReadableStream` response (not `EventSource`, because it's a POST):

```js
const res = await fetch('/api/stack/update', { method: 'POST' });
const reader = res.body.getReader();
const dec = new TextDecoder();
while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  // Parse SSE format "data: ...\n\n"
  dec.decode(value).split('\n')
    .filter(l => l.startsWith('data: '))
    .forEach(l => appendLog(l.slice(6)));
}
```

Digest display: show first 8 chars. Full digest in `title` attribute tooltip.

```jsx
import { useState, useRef } from 'react';
import { Panel }    from '../../components/Panel';
import { Btn }      from '../../components/Btn';
import { Tag }      from '../../components/Tag';
import { MOCK_STACK_IMAGES } from '../../data/settingsMock';
import './SettingsShared.css';

export function StackManager({ isAppliance }) {
  const [images,   setImages]  = useState(MOCK_STACK_IMAGES);
  const [updating, setUpdating]= useState(false);
  const [updateLog,setLog]     = useState([]); // SSE lines
  const [rollingBack, setRollingBack] = useState(null); // service name

  const logRef = useRef(null);

  function appendLog(line) {
    setLog(prev => [...prev, line]);
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }

  async function handleUpdateAll() {
    const ok = window.confirm('Pull latest images and restart all services? Brief downtime per service.');
    if (!ok) return;
    setUpdating(true);
    setLog([]);

    try {
      const res = await fetch('/api/stack/update', { method: 'POST' });
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        dec.decode(value).split('\n')
          .filter(l => l.startsWith('data: '))
          .forEach(l => appendLog(l.slice(6)));
      }
    } catch {
      // Mock progress for UI testing
      const mockLines = [
        'Pulling vllm-pair-a...', '  Pulling image: 4.3 GB...', '  ✓ Pulled new image sha256:a1b2',
        '  Restarting container... ✓ Running (2.1s)',
        'Pulling ollama...', '  ✓ Already up to date', '  Restarting container... ✓ Running (0.9s)',
        '✓ All services updated',
      ];
      for (const line of mockLines) {
        await new Promise(r => setTimeout(r, 400));
        appendLog(line);
      }
    }
    setUpdating(false);
  }

  async function handleRollback(service, previousDigest) {
    if (!previousDigest) return;
    const ok = window.confirm(`Roll back ${service} to ${previousDigest}?`);
    if (!ok) return;
    setRollingBack(service);
    try {
      await fetch(`/api/stack/rollback/${service}`, { method: 'POST' });
    } catch { /* API not ready */ }
    await new Promise(r => setTimeout(r, 1500));
    setRollingBack(null);
  }

  return (
    <Panel title="Stack Management">
      {isAppliance ? (
        <div className="settings-locked-notice">
          🔒 Updates managed via validated stack snapshots. Contact your administrator.
        </div>
      ) : (
        <div className="stack-update-row">
          <Btn variant="cyan" size="md" onClick={handleUpdateAll} disabled={updating}>
            {updating ? '↻ Updating…' : 'Update All Services'}
          </Btn>
          <span className="stack-update-meta">Last update: 3d ago · all ✓</span>
        </div>
      )}

      {updateLog.length > 0 && (
        <div className="stack-log" ref={logRef}>
          {updateLog.map((l, i) => (
            <div key={i} className={`stack-log-line ${l.startsWith('✓') ? 'log-ok' : l.startsWith('  ') ? 'log-indent' : ''}`}>
              {l}
            </div>
          ))}
        </div>
      )}

      <table className="settings-table">
        <thead>
          <tr><th>Service</th><th>Image</th><th>Digest</th><th>Pulled</th><th></th></tr>
        </thead>
        <tbody>
          {images.map(img => (
            <tr key={img.service}>
              <td>{img.service}</td>
              <td className="stack-image">{img.image}</td>
              <td>
                <span className="stack-digest" title={img.digest}>
                  {img.digest.slice(0, 8)}
                </span>
              </td>
              <td className="kv-dim">{img.pulled_at}</td>
              <td>
                {!isAppliance && img.previous_digest && (
                  <Btn
                    variant="gray" size="sm"
                    disabled={rollingBack === img.service}
                    onClick={() => handleRollback(img.service, img.previous_digest)}
                  >
                    {rollingBack === img.service ? '↻' : 'RB'}
                  </Btn>
                )}
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

### 7. `ui/src/pages/settings/Backups.jsx`

Schedule editor: inline 5-field cron editor (min, hr, dom, mon, dow), toggled by "Edit Schedule".

Run Now: button becomes "Backup running… ↻" while running; SSE or mock progress shown inline.

```jsx
import { useState } from 'react';
import { Panel }    from '../../components/Panel';
import { Btn }      from '../../components/Btn';
import { Tag }      from '../../components/Tag';
import { MOCK_BACKUP_CONFIG, MOCK_BACKUP_HISTORY } from '../../data/settingsMock';
import './SettingsShared.css';

function parseCron(expr) {
  const [min, hr, dom, mon, dow] = expr.split(' ');
  return { min, hr, dom, mon, dow };
}

function buildCron({ min, hr, dom, mon, dow }) {
  return `${min} ${hr} ${dom} ${mon} ${dow}`;
}

export function Backups({ isAppliance }) {
  const [config,    setConfig]   = useState(MOCK_BACKUP_CONFIG);
  const [history,   setHistory]  = useState(MOCK_BACKUP_HISTORY);
  const [cronEdit,  setCronEdit] = useState(false);
  const [cronDraft, setCronDraft]= useState(() => parseCron(MOCK_BACKUP_CONFIG.schedule));
  const [running,   setRunning]  = useState(false);
  const [backupLog, setBackupLog]= useState([]);

  async function saveSchedule() {
    const schedule = buildCron(cronDraft);
    try {
      await fetch('/api/backup/config', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ schedule }),
      });
      setConfig(c => ({ ...c, schedule }));
    } catch { setConfig(c => ({ ...c, schedule })); }
    setCronEdit(false);
  }

  async function handleRunNow() {
    setRunning(true);
    setBackupLog(['Starting backup…']);
    try {
      await fetch('/api/backup/run', { method: 'POST' });
    } catch { /* mock progress */ }
    const mockLines = [
      'Archiving /data/models/ (10.1 TB)…', 'Archiving /data/datasets/ (2.3 TB)…',
      'Writing to /data/backups/2026-06-06-0600.tar.gz…', '✓ Backup complete — 42 GB',
    ];
    for (const l of mockLines) {
      await new Promise(r => setTimeout(r, 700));
      setBackupLog(prev => [...prev, l]);
    }
    setHistory(prev => [
      { id: Date.now(), ts: new Date().toISOString().slice(0, 16).replace('T', ' '), size_gb: 42, status: 'ok' },
      ...prev,
    ]);
    setRunning(false);
  }

  async function deleteBackup(id) {
    if (!window.confirm('Delete this backup archive? It cannot be recovered.')) return;
    try {
      await fetch(`/api/backup/${id}`, { method: 'DELETE' });
    } catch { /* API not ready */ }
    setHistory(prev => prev.filter(b => b.id !== id));
  }

  async function retryBackup() {
    await handleRunNow();
  }

  const fields = [
    { key: 'min', label: 'min' },
    { key: 'hr',  label: 'hr' },
    { key: 'dom', label: 'dom' },
    { key: 'mon', label: 'mon' },
    { key: 'dow', label: 'dow' },
  ];

  return (
    <Panel title="Backups">
      <div className="backup-meta">
        <div className="backup-meta-row">
          <span className="kv-label">Last backup</span>
          <span>{history[0]?.ts} · {history[0]?.size_gb} GB · ✓ success</span>
        </div>

        <div className="backup-meta-row">
          <span className="kv-label">Schedule</span>
          {cronEdit && !isAppliance ? (
            <span className="cron-editor">
              {fields.map(f => (
                <span key={f.key} className="cron-field">
                  <input
                    className="cron-input"
                    value={cronDraft[f.key]}
                    onChange={e => setCronDraft(d => ({ ...d, [f.key]: e.target.value }))}
                  />
                  <span className="cron-field-label">{f.label}</span>
                </span>
              ))}
              <Btn variant="cyan" size="sm" onClick={saveSchedule}>Save</Btn>
              <Btn variant="gray" size="sm" onClick={() => { setCronEdit(false); setCronDraft(parseCron(config.schedule)); }}>
                Cancel
              </Btn>
            </span>
          ) : (
            <span className="kv-inline">
              <code>{config.schedule}</code>
              {!isAppliance && (
                <button className="kv-edit-btn" onClick={() => setCronEdit(true)}>Edit Schedule</button>
              )}
            </span>
          )}
        </div>

        <div className="backup-meta-row">
          <span className="kv-label">Destination</span>
          <span className="kv-inline">
            <code>{config.destination}</code>
            <button className="kv-link-btn" onClick={() => window.open(`http://${window.location.hostname}:9001/browser/`, '_blank')}>
              Browse ↗
            </button>
          </span>
        </div>
      </div>

      <div className="backup-run-row">
        <Btn variant="cyan" size="md" onClick={handleRunNow} disabled={running}>
          {running ? '↻ Backup running…' : 'Run Backup Now'}
        </Btn>
      </div>

      {backupLog.length > 0 && (
        <div className="stack-log">
          {backupLog.map((l, i) => (
            <div key={i} className={`stack-log-line ${l.startsWith('✓') ? 'log-ok' : ''}`}>{l}</div>
          ))}
        </div>
      )}

      <div className="settings-section-label">History</div>
      <table className="settings-table">
        <thead>
          <tr><th>Date</th><th>Size</th><th>Status</th><th></th></tr>
        </thead>
        <tbody>
          {history.slice(0, 10).map(b => (
            <tr key={b.id}>
              <td className="kv-dim">{b.ts}</td>
              <td>{b.size_gb} GB</td>
              <td>
                <Tag variant={b.status === 'ok' ? 'green' : 'red'}>
                  {b.status === 'ok' ? '✓ ok' : '✗ fail'}
                </Tag>
              </td>
              <td className="backup-actions">
                {b.status === 'fail' && (
                  <Btn variant="amber" size="sm" onClick={retryBackup}>Retry</Btn>
                )}
                <Btn variant="red" size="sm" onClick={() => deleteBackup(b.id)}>Delete</Btn>
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

### 8. `ui/src/pages/settings/Platform.jsx`

Shown always. "Re-run First-Boot Wizard" button visible only in workstation mode.

```jsx
import { Panel } from '../../components/Panel';
import { Btn }   from '../../components/Btn';
import { Tag }   from '../../components/Tag';
import { MOCK_PLATFORM } from '../../data/settingsMock';
import './SettingsShared.css';

export function Platform({ isAppliance }) {
  const p = MOCK_PLATFORM; // TODO Step 10: GET /api/platform

  async function rerunWizard() {
    const ok = window.confirm(
      'Re-run the first-boot wizard? This will re-detect hardware and re-apply baseline configuration. Confirm only if directed by support.'
    );
    if (!ok) return;
    window.location.hash = '/setup';
  }

  return (
    <Panel title="Platform Setup">
      <div className="platform-status">
        <span>First-boot wizard:</span>
        <Tag variant="green">✓ Completed {p.wizard_date}</Tag>
      </div>

      <table className="settings-kv-table platform-kv">
        <tbody>
          <tr><td className="kv-label">Hardware</td><td>{p.hardware}</td></tr>
          <tr><td className="kv-label">Profile</td><td>{p.profile_assigned}</td></tr>
          <tr><td className="kv-label">Secrets</td><td><Tag variant="green">{p.secrets_status}</Tag></td></tr>
          <tr><td className="kv-label">Network</td><td><Tag variant="green">{p.network_status}</Tag></td></tr>
          <tr><td className="kv-label">Stack</td><td><Tag variant="green">{p.stack_status}</Tag></td></tr>
        </tbody>
      </table>

      {!isAppliance && (
        <div style={{ marginTop: 12 }}>
          <Btn variant="amber" size="sm" onClick={rerunWizard}>
            Re-run First-Boot Wizard
          </Btn>
        </div>
      )}
    </Panel>
  );
}
```

---

### 9. `ui/src/pages/settings/SettingsShared.css`

```css
@import '../../tokens.css';

/* Tables */
.settings-table { width: 100%; border-collapse: collapse; font-size: 9px; margin-top: 8px; }
.settings-table th {
  text-align: left; color: var(--text3); font-size: 8px;
  border-bottom: 1px solid var(--border); padding: 4px 8px;
}
.settings-table td { padding: 6px 8px; color: var(--text2); border-bottom: 1px solid var(--border); }
.settings-table tr:last-child td { border-bottom: none; }

/* Key-value layout */
.settings-kv-table { width: 100%; border-collapse: collapse; font-size: 10px; }
.settings-kv-table td { padding: 5px 0; vertical-align: middle; }
.kv-label  { color: var(--text3); width: 100px; flex-shrink: 0; font-size: 9px; }
.kv-value  { color: var(--text2); }
.kv-dim    { color: var(--text3); font-size: 9px; }
.kv-locked { color: var(--text3); font-style: italic; }
.kv-inline { display: flex; align-items: center; gap: 8px; }
.kv-status-row { display: flex; align-items: center; gap: 6px; }

/* Inline edit */
.inline-edit  { display: flex; align-items: center; gap: 6px; }
.inline-input {
  background: var(--surface3); border: 1px solid var(--border);
  border-radius: 3px; color: var(--text);
  font-family: var(--mono); font-size: 9px; padding: 3px 8px;
  width: 130px;
}

/* Link / edit buttons */
.kv-link-btn, .kv-edit-btn {
  background: none; border: 1px solid var(--border);
  border-radius: 2px; color: var(--cyan); cursor: pointer;
  font-size: 9px; padding: 2px 7px; white-space: nowrap;
}
.kv-link-btn:hover, .kv-edit-btn:hover { border-color: var(--cyan); }

/* KV select */
.kv-select {
  background: var(--surface3); border: 1px solid var(--border);
  border-radius: 3px; color: var(--text2);
  font-family: var(--mono); font-size: 9px; padding: 2px 6px;
}

/* Secrets */
.secret-key     { font-family: var(--mono); font-size: 9px; color: var(--text); }
.secret-rotated { font-size: 9px; color: var(--text3); white-space: nowrap; }

.rotate-progress { display: flex; gap: 4px; flex-wrap: wrap; margin-left: 4px; }
.rotate-svc-spin { font-size: 9px; color: var(--amber); animation: spin .8s linear infinite; display: inline-block; }
@keyframes spin { to { transform: rotate(360deg); } }

.show-all-btn {
  width: 100%; margin-top: 6px;
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 3px; color: var(--text3); cursor: pointer;
  font-size: 9px; padding: 5px;
}

.secrets-footer { margin-top: 10px; padding-top: 8px; border-top: 1px solid var(--border); }

/* Section label */
.settings-section-label {
  font-size: 8px; color: var(--text3); text-transform: uppercase;
  letter-spacing: .06em; margin: 10px 0 4px;
}

/* Locked notice */
.settings-locked-notice {
  font-size: 9px; color: var(--text3);
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 3px; padding: 10px 12px;
}

/* Auth */
.auth-service-row {
  display: flex; align-items: center; gap: 6px;
  font-size: 10px; margin-bottom: 6px;
}
.auth-fwdauth { font-size: 9px; color: var(--text3); margin-bottom: 8px; display: flex; gap: 4px; flex-wrap: wrap; }
.auth-users-header {
  display: flex; justify-content: space-between; align-items: center;
  font-size: 9px; color: var(--text3); margin-bottom: 4px;
}

/* Action dropdown */
.action-dropdown         { position: relative; display: inline-block; }
.action-dropdown summary { cursor: pointer; list-style: none; }
.action-dropdown-btn {
  background: var(--surface3); border: 1px solid var(--border);
  border-radius: 2px; color: var(--text3); cursor: pointer;
  font-size: 9px; padding: 2px 8px;
}
.action-dropdown-menu {
  position: absolute; right: 0; top: 100%; z-index: 10;
  background: var(--surface); border: 1px solid var(--border2);
  border-radius: var(--radius); min-width: 160px;
  box-shadow: 0 4px 12px rgba(0,0,0,.4);
  overflow: hidden;
}
.action-dropdown-menu button {
  display: block; width: 100%; text-align: left;
  background: none; border: none; color: var(--text2); cursor: pointer;
  font-size: 9px; padding: 7px 12px;
  border-bottom: 1px solid var(--border);
}
.action-dropdown-menu button:last-child { border-bottom: none; }
.action-dropdown-menu button:hover { background: var(--surface2); }
.action-destructive { color: var(--red) !important; }

/* Stack */
.stack-update-row {
  display: flex; align-items: center; gap: 10px; margin-bottom: 10px;
}
.stack-update-meta { font-size: 9px; color: var(--text3); }
.stack-image       { font-size: 9px; color: var(--text3); font-family: var(--mono); max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.stack-digest      { font-family: var(--mono); font-size: 9px; color: var(--text3); cursor: default; }

.stack-log {
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: var(--radius); max-height: 160px; overflow-y: auto;
  padding: 8px; margin-bottom: 10px; font-family: var(--mono);
}
.stack-log-line { font-size: 9px; color: var(--text2); line-height: 1.5; }
.stack-log-line.log-indent { color: var(--text3); padding-left: 12px; }
.stack-log-line.log-ok     { color: var(--green); }

/* Backups */
.backup-meta       { display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
.backup-meta-row   { display: flex; align-items: center; gap: 8px; font-size: 10px; }
.backup-run-row    { margin-bottom: 8px; }
.backup-actions    { display: flex; gap: 4px; }

.cron-editor  { display: flex; align-items: center; gap: 4px; flex-wrap: wrap; }
.cron-field   { display: flex; flex-direction: column; align-items: center; gap: 1px; }
.cron-input   {
  background: var(--surface3); border: 1px solid var(--border);
  border-radius: 2px; color: var(--text); font-family: var(--mono); font-size: 9px;
  padding: 2px 4px; width: 32px; text-align: center;
}
.cron-field-label { font-size: 7px; color: var(--text3); }

/* Platform */
.platform-status { display: flex; align-items: center; gap: 8px; font-size: 10px; margin-bottom: 10px; }
.platform-kv td  { padding: 4px 0; }

/* Modal (reused from Expose) */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,.6);
  z-index: 100; display: flex; align-items: center; justify-content: center; padding: 24px;
}
.modal {
  background: var(--surface); border: 1px solid var(--border2);
  border-radius: var(--radius); min-width: 360px; max-width: 480px; width: 100%;
}
.modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 14px; font-size: 11px; font-weight: 600; color: var(--text);
  border-bottom: 1px solid var(--border);
}
.modal-close { background: none; border: none; color: var(--text3); cursor: pointer; font-size: 12px; }
.modal-body  { padding: 14px; display: flex; flex-direction: column; gap: 12px; }
.modal-text  { font-size: 10px; color: var(--text2); line-height: 1.5; margin: 0; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; }
.form-input {
  background: var(--surface3); border: 1px solid var(--border);
  border-radius: 3px; color: var(--text); font-family: var(--mono);
  font-size: 10px; padding: 5px 8px; width: 100%;
}
```

---

## Acceptance Criteria

- [ ] **Layout:** Two-column top row (Secrets left, Network + Auth stacked right); single-column below
- [ ] **Secrets (workstation):** Table shows all 14 key names, no values; "Rotate" shows `window.confirm` with service list; on confirm spins per-service and updates "just now"; "Rotate All" requires two-step modal with "rotate all" text confirm
- [ ] **Secrets (appliance):** Table replaced with locked notice; all Rotate buttons absent
- [ ] **Network:** Jumpbox IP shows inline edit on "Edit" click; saves via PATCH; WireGuard and Caddy show status dot; "Config ↗" opens new tab; mode `<select>` disabled in appliance mode
- [ ] **Auth:** Authentik status shown with dot; "Open ↗" opens new tab; "+ Add User ↗" opens Authentik admin (not a local modal); user action dropdown uses `<details>` element; Delete user shows confirm
- [ ] **Stack (workstation):** "Update All" shows confirm then streams SSE log lines; rollback button shown only when `previous_digest` exists; digest truncated to 8 chars with full value in tooltip
- [ ] **Stack (appliance):** "Update All" replaced with locked message; rollback buttons absent
- [ ] **Backups:** "Edit Schedule" reveals inline 5-field cron editor; "Run Backup Now" becomes spinner during run with inline log; failed backup row shows "[Retry]"; Delete confirms before removing
- [ ] **Platform:** Summary table always visible; "Re-run" button absent in appliance mode

---

## Deferred issues addressed in Step 09

**Loadout activation confirmation dialog (from step 03 feedback):** GHC skipped `window.confirm` in `Loadout.jsx`. Fix it now:

In `Loadout.jsx` (or `useLoadouts.js`), before calling `POST /activate/{name}`, add:
```js
const ok = window.confirm(
  `Switch to "${name}"? Services will restart. This will take 15–30 seconds.`
);
if (!ok) return;
```
This should be applied to the `handleActivate` function in the Loadout page.

---

## Feedback

Write `plan/UI/GHC-Feedback/09-feedback.md` when done.

**Required in Notes:**
- Confirm the `<details>` dropdown for user actions closes when clicking elsewhere. If not, note the workaround.
- Report whether the SSE ReadableStream approach for Update All worked in dev (Vite proxied POST). If not, describe the workaround.
- Confirm the inline cron editor validates input before saving (e.g. rejects non-numeric values).
- Report what fix was applied to the Loadout activation confirmation dialog.
