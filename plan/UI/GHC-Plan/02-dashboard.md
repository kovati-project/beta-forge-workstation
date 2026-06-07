# Step 02 — Dashboard

> **Prerequisites:** Step 01 complete. Read `plan/UI/GHC-Plan/00-overview.md` before starting.
> **Reference spec:** `plan/UI/Steps/02-dashboard.md` (full layout diagrams, component API)

---

## Goal

Implement the Dashboard page (`/#/dashboard`). It is the default landing view and must show:

1. Real-time GPU status (4 cards, polled from existing `/status` endpoint)
2. Active loadout banner (from AppContext state + `/loadouts` fetch)
3. System metrics summary (mocked — backend endpoint added in Step 10)
4. Service health grid (mocked — backend endpoint added in Step 10)
5. Activity feed (mocked — backend endpoint added in Step 10)

Endpoints 3–5 do not exist yet. Use mock data with a `// TODO Step 10` comment.
Endpoint 1 (`GET /status`) and 2 (`GET /loadouts`) already exist — use them live.

---

## Deliverables

### 1. Update `ui/src/context/AppContext.jsx`

Two small additions to the existing file:

**a) Add `bus_id` to each GPU in the mock data:**

```js
gpus: [
  { index: 0, bus_id: '0000:21:00.0', vram_used_gb: 21.4, vram_total_gb: 24, vram_free_gb: 2.6,
    utilization_pct: 92, temp_c: 74, power_w: 198, nvlink_bridge: 'A' },
  { index: 1, bus_id: '0000:22:00.0', vram_used_gb: 1.2,  vram_total_gb: 24, vram_free_gb: 22.8,
    utilization_pct: 3,  temp_c: 42, power_w: 45,  nvlink_bridge: 'B' },
  { index: 2, bus_id: '0000:41:00.0', vram_used_gb: 0.8,  vram_total_gb: 24, vram_free_gb: 23.2,
    utilization_pct: 1,  temp_c: 39, power_w: 38,  nvlink_bridge: 'B' },
  { index: 3, bus_id: '0000:43:00.0', vram_used_gb: 19.8, vram_total_gb: 24, vram_free_gb: 4.2,
    utilization_pct: 88, temp_c: 71, power_w: 189, nvlink_bridge: 'A' },
],
```

**b) Add a `SWITCH_ALL_STOP` action to the reducer:**

```js
case 'SWITCH_ALL_STOP':
  return { ...state, switching: false, activeProfile: null, runningServices: [] };
```

No other changes to AppContext.

---

### 2. `ui/src/hooks/useSystemMetrics.js`

10s polling hook for `/api/metrics/system`. Falls back to mock data if the endpoint is
not yet available (HTTP 404 or network error). Returns null while loading (triggers skeleton).

```js
import { useState, useEffect } from 'react';

// TODO Step 10: real endpoint available after backend API refactor
const MOCK_METRICS = {
  cpu_pct: 12,
  ram_used_gb: 94,
  ram_total_gb: 512,
  vram_used_gb_total: 43.2,
  storage_used_tb: 18.4,
  storage_total_tb: 48,
};

export function useSystemMetrics() {
  const [metrics, setMetrics] = useState(null);

  useEffect(() => {
    async function poll() {
      try {
        const res = await fetch('/api/metrics/system');
        if (!res.ok) throw new Error('not ready');
        setMetrics(await res.json());
      } catch {
        setMetrics(MOCK_METRICS);
      }
    }
    poll();
    const id = setInterval(poll, 10000);
    return () => clearInterval(id);
  }, []);

  return metrics;
}
```

---

### 3. `ui/src/hooks/useActivityFeed.js`

30s polling hook for `/GET /api/activity`. Falls back to mock events if not yet available.

```js
import { useState, useEffect } from 'react';

// TODO Step 10: real endpoint available after backend API refactor
const MOCK_ACTIVITY = [
  { ts: Date.now() / 1000 - 600,   type: 'SWITCH',  detail: '→ inference-pair-a' },
  { ts: Date.now() / 1000 - 10800, type: 'BACKUP',  detail: 'Completed · 42 GB' },
  { ts: Date.now() / 1000 - 23400, type: 'TRAIN',   detail: 'img-lora done (1000 st)' },
  { ts: Date.now() / 1000 - 64800, type: 'RESTART', detail: 'comfyui OOM recovery' },
  { ts: Date.now() / 1000 - 90000, type: 'TRAIN',   detail: 'Qwen2.5-7B epoch 3/3' },
  { ts: Date.now() / 1000 - 97200, type: 'SWITCH',  detail: '→ training-lora-text' },
  { ts: Date.now() / 1000 - 172800,type: 'UPDATE',  detail: 'vllm → 0.9.1' },
];

export function useActivityFeed() {
  const [events, setEvents] = useState([]);

  useEffect(() => {
    async function poll() {
      try {
        const res = await fetch('/api/activity');
        if (!res.ok) throw new Error('not ready');
        const data = await res.json();
        setEvents(data.events ?? []);
      } catch {
        setEvents(MOCK_ACTIVITY);
      }
    }
    poll();
    const id = setInterval(poll, 30000);
    return () => clearInterval(id);
  }, []);

  return events;
}
```

---

### 4. `ui/src/pages/Dashboard.jsx`

Full implementation. Import all reusable components; do not inline their styles.

```jsx
import { useEffect, useState, useMemo, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { useSystemMetrics } from '../hooks/useSystemMetrics';
import { useActivityFeed } from '../hooks/useActivityFeed';
import { Panel } from '../components/Panel';
import { Tag } from '../components/Tag';
import { Btn } from '../components/Btn';
import { VBar } from '../components/VBar';
import { DotStatus } from '../components/DotStatus';
import './Dashboard.css';

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatTimeSince(epochSec) {
  if (!epochSec) return '—';
  const diff = Math.max(0, Date.now() / 1000 - epochSec);
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) {
    const h = Math.floor(diff / 3600);
    const m = Math.floor((diff % 3600) / 60);
    return `${h}h ${m}m ago`;
  }
  return `${Math.floor(diff / 86400)}d ago`;
}

function formatActivityTs(epochSec) {
  const now = Date.now() / 1000;
  const diff = now - epochSec;
  const d = new Date(epochSec * 1000);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  if (d.getDate() === today.getDate() && diff < 86400) {
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  }
  if (d.getDate() === yesterday.getDate()) return 'Yest';
  return `${Math.floor(diff / 86400)}d`;
}

function profileAccent(profileName) {
  if (!profileName) return 'gray';
  const n = profileName.toLowerCase();
  if (n.includes('train') || n.includes('lora')) return 'amber';
  if (n.includes('image') || n.includes('studio') || n.includes('comfy')) return 'purple';
  return 'cyan';
}

const ACTIVITY_TAG_VARIANT = {
  SWITCH: 'cyan', BACKUP: 'green', TRAIN: 'amber',
  UPDATE: 'green', RESTART: 'gray', ERROR: 'red',
};

// ── Mock service list for the health grid ─────────────────────────────────
// TODO Step 10: replaced by real /api/services response
const MOCK_SERVICES = {
  'vllm-pair-a':   { port: 8000, category: 'inference' },
  'vllm-pair-b':   { port: 8001, category: 'inference' },
  'ollama':        { port: 11434, category: 'inference' },
  'llama-cpp':     { port: 8080, category: 'inference' },
  'tabby':         { port: 9090, category: 'inference' },
  'litellm':       { port: 4000, category: 'inference' },
  'comfyui':       { port: 7860, category: 'image' },
  'a1111':         { port: 7861, category: 'image' },
  'fooocus':       { port: 7862, category: 'image' },
  'axolotl':       { port: null, category: 'training' },
  'kohya':         { port: null, category: 'training' },
  'open-webui':    { port: 3000, category: 'webui' },
  'text-gen-webui':{ port: 7870, category: 'webui' },
  'n8n':           { port: 5678, category: 'agentic' },
  'dify':          { port: 3001, category: 'agentic' },
  'minio':         { port: 9000, category: 'storage' },
  'qdrant':        { port: 6333, category: 'storage' },
  'postgres':      { port: 5432, category: 'storage' },
  'prometheus':    { port: 9091, category: 'monitoring' },
  'grafana':       { port: 3002, category: 'monitoring' },
  'langfuse':      { port: 3003, category: 'monitoring' },
  'authentik':     { port: 9001, category: 'auth' },
};

const CATEGORY_ORDER = ['inference', 'image', 'training', 'webui', 'agentic', 'storage', 'monitoring', 'auth'];

// ── Sub-components ────────────────────────────────────────────────────────────

function GpuCard({ gpu, claimed, accent }) {
  const vramPct = gpu.vram_total_gb > 0
    ? Math.min((gpu.vram_used_gb / gpu.vram_total_gb) * 100, 100)
    : 0;

  const tempColor = gpu.temp_c > 85 ? 'var(--red)'
    : gpu.temp_c > 75 ? 'var(--amber)'
    : 'var(--green)';

  const borderClass = gpu.temp_c > 85 ? 'gpu-card-hot'
    : gpu.temp_c > 75 ? 'gpu-card-warm'
    : claimed ? 'gpu-card-claimed'
    : 'gpu-card-default';

  const vramVariant = gpu.temp_c > 75 ? 'amber'
    : claimed ? 'cyan'
    : gpu.vram_used_gb < 1.2 ? 'green'
    : 'cyan';

  const utilVariant = gpu.utilization_pct > 20 ? 'cyan' : 'green';

  const serviceVariant = claimed ? accent : 'gray';
  const serviceLabel = claimed
    ? (gpu.vram_used_gb >= 1 ? accent === 'amber' ? 'training' : accent === 'purple' ? 'image' : 'inference' : 'idle')
    : 'idle';

  return (
    <div className={`gpu-card ${borderClass}`}>
      <div className="gpu-card-header">
        <div className="gpu-card-id">
          <span className="gpu-index">GPU {gpu.index}</span>
          {gpu.bus_id && <span className="gpu-bus">· {gpu.bus_id}</span>}
        </div>
        <span className="gpu-bridge-badge">BRIDGE {gpu.nvlink_bridge}</span>
      </div>
      <div className="gpu-name">RTX A5500</div>

      <div className="gpu-metrics">
        <div className="gpu-metric-row">
          <span className="gpu-metric-label">VRAM</span>
          <VBar pct={vramPct} variant={vramVariant} />
          <span className="gpu-metric-value">{gpu.vram_used_gb.toFixed(1)}/{gpu.vram_total_gb} GB</span>
        </div>
        <div className="gpu-metric-row">
          <span className="gpu-metric-label">Util</span>
          <VBar pct={gpu.utilization_pct} variant={utilVariant} />
          <span className="gpu-metric-value">{gpu.utilization_pct}%</span>
        </div>
        <div className="gpu-metric-row">
          <span className="gpu-metric-label">Temp</span>
          <span style={{ color: tempColor }} className="gpu-metric-value">{gpu.temp_c}°C</span>
        </div>
        <div className="gpu-metric-row">
          <span className="gpu-metric-label">Power</span>
          <span className="gpu-metric-value">{gpu.power_w} W</span>
        </div>
      </div>

      <div className="gpu-card-footer">
        <Tag variant={serviceVariant}>{serviceLabel}</Tag>
      </div>
    </div>
  );
}

function LoadoutBanner({ state, claimedGpus, navigate }) {
  const accent = profileAccent(state.activeProfile);
  const vramClaimed = claimedGpus.size * 24;

  async function handleStopAll() {
    if (!window.confirm('Stop all services? This will interrupt any running workloads.')) return;
    try {
      await fetch('/stop', { method: 'POST' });
    } catch (e) {
      console.error('Stop all failed:', e);
    }
  }

  if (state.switching) {
    return (
      <Panel title="ACTIVE LOADOUT">
        <div className="loadout-switching">
          <span className="switching-icon">⟳</span>
          <span className="switching-label">SWITCHING PROFILE</span>
          <div className="switching-steps">stopping services → draining VRAM → starting services</div>
          <div className="switching-bar">
            <div className="switching-bar-fill" />
          </div>
        </div>
      </Panel>
    );
  }

  if (!state.activeProfile) {
    return (
      <Panel title="ACTIVE LOADOUT">
        <div className="loadout-empty">
          <span className="loadout-empty-msg">No active profile — select a loadout to begin</span>
          <Btn variant="cyan" onClick={() => navigate('/loadout')}>Go to Loadout →</Btn>
        </div>
      </Panel>
    );
  }

  return (
    <Panel title="ACTIVE LOADOUT">
      <div className="loadout-content">
        <div className="loadout-name-row">
          <span className={`loadout-profile-name loadout-accent-${accent}`}>
            {state.activeProfile}
          </span>
          {claimedGpus.size > 0 && (
            <Tag variant={accent}>
              NVLink {[...claimedGpus].includes(0) ? 'A' : 'B'} · GPU {[...claimedGpus].join('+')}
            </Tag>
          )}
        </div>
        <div className="loadout-sub">
          {vramClaimed > 0 && `${vramClaimed} GB claimed · `}
          switched {formatTimeSince(state.lastSwitched)}
        </div>
        <div className="loadout-services">
          {state.runningServices.map(s => (
            <Tag key={s} variant={accent}>{s}</Tag>
          ))}
        </div>
        <div className="loadout-actions">
          <Btn variant="cyan" size="sm" onClick={() => navigate('/loadout')}>Switch Profile →</Btn>
          <Btn variant="red"  size="sm" onClick={handleStopAll}>Stop All</Btn>
        </div>
      </div>
    </Panel>
  );
}

function SystemMetricsPanel({ metrics }) {
  if (!metrics) {
    return (
      <Panel title="SYSTEM">
        <div className="metrics-grid">
          {[0,1,2,3].map(i => <div key={i} className="metric-card skeleton" />)}
        </div>
      </Panel>
    );
  }

  const ramPct = metrics.ram_total_gb > 0 ? metrics.ram_used_gb / metrics.ram_total_gb : 0;
  const storagePct = metrics.storage_total_tb > 0 ? metrics.storage_used_tb / metrics.storage_total_tb : 0;

  const cards = [
    {
      value: `${metrics.cpu_pct}%`,
      label: 'CPU Load',
      color: metrics.cpu_pct > 90 ? 'var(--red)' : metrics.cpu_pct > 70 ? 'var(--amber)' : 'var(--cyan)',
    },
    {
      value: `${Math.round(metrics.ram_used_gb)} GB`,
      label: 'RAM',
      color: ramPct < 0.8 ? 'var(--green)' : 'var(--amber)',
    },
    {
      value: `${metrics.vram_used_gb_total.toFixed(1)} GB`,
      label: 'VRAM Used',
      color: 'var(--cyan)',
    },
    {
      value: `${metrics.storage_used_tb.toFixed(1)} TB`,
      label: 'Storage',
      color: storagePct > 0.8 ? 'var(--amber)' : 'var(--text)',
    },
  ];

  return (
    <Panel title="SYSTEM">
      <div className="metrics-grid">
        {cards.map(c => (
          <div key={c.label} className="metric-card">
            <span className="metric-big-num" style={{ color: c.color }}>{c.value}</span>
            <span className="metric-big-label">{c.label}</span>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function ServiceHealthGrid({ services, navigate }) {
  const tiles = useMemo(() => {
    const src = Object.keys(services).length > 0 ? services : MOCK_SERVICES;
    return CATEGORY_ORDER.flatMap(cat =>
      Object.entries(src)
        .filter(([, v]) => v.category === cat)
        .map(([name, v]) => ({ name, ...v, status: v.status ?? 'stopped' }))
    );
  }, [services]);

  function dotForStatus(status) {
    if (status === 'running' || status === 'healthy') return 'green';
    if (status === 'starting' || status === 'degraded') return 'amber';
    if (status === 'error') return 'red';
    return 'gray';
  }

  return (
    <Panel title="SERVICES" subtitle={`${tiles.filter(t => t.status === 'running').length} running`}>
      <div className="service-grid">
        {tiles.map(t => (
          <div
            key={t.name}
            className="service-tile"
            onClick={() => navigate(`/tools?focus=${t.name}`)}
            title={t.name}
          >
            <div className="service-tile-name">
              <DotStatus status={dotForStatus(t.status)} />
              <span>{t.name}</span>
            </div>
            {t.port && <div className="service-tile-port">:{t.port}</div>}
          </div>
        ))}
      </div>
    </Panel>
  );
}

function ActivityFeedPanel({ events }) {
  return (
    <Panel title="ACTIVITY">
      {events.length === 0 ? (
        <div className="activity-empty">No recent events</div>
      ) : (
        <div className="activity-list">
          {events.map((ev, i) => (
            <div key={i} className="activity-row">
              <span className="activity-ts">{formatActivityTs(ev.ts)}</span>
              <Tag variant={ACTIVITY_TAG_VARIANT[ev.type] ?? 'gray'}>{ev.type}</Tag>
              <span className="activity-detail">{ev.detail}</span>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export function Dashboard() {
  const { state } = useApp();
  const navigate = useNavigate();
  const metrics = useSystemMetrics();
  const events  = useActivityFeed();

  // Fetch loadout profile list once to determine claimed GPUs
  const [loadouts, setLoadouts] = useState(null);
  useEffect(() => {
    fetch('/loadouts')
      .then(r => r.json())
      .then(setLoadouts)
      .catch(() => setLoadouts([]));
  }, []);

  const claimedGpus = useMemo(() => {
    if (!loadouts || !state.activeProfile) return new Set();
    const profile = loadouts.find(p => p.name === state.activeProfile);
    const gpuList = profile?.gpus ?? profile?.gpu_ids ?? [];
    return new Set(gpuList);
  }, [loadouts, state.activeProfile]);

  const accent = profileAccent(state.activeProfile);

  return (
    <div className="dashboard">
      {/* Row 1: GPU cards */}
      <div className="dashboard-gpu-row">
        {state.gpus.map(gpu => (
          <GpuCard
            key={gpu.index}
            gpu={gpu}
            claimed={claimedGpus.has(gpu.index)}
            accent={accent}
          />
        ))}
        {state.gpus.length === 0 && [0,1,2,3].map(i => (
          <div key={i} className="gpu-card gpu-card-default skeleton" />
        ))}
      </div>

      {/* Row 2: Loadout banner + System metrics */}
      <div className="dashboard-row">
        <div className="dashboard-col-2">
          <LoadoutBanner state={state} claimedGpus={claimedGpus} navigate={navigate} />
        </div>
        <div className="dashboard-col-1">
          <SystemMetricsPanel metrics={metrics} />
        </div>
      </div>

      {/* Row 3: Service grid + Activity feed */}
      <div className="dashboard-row">
        <div className="dashboard-col-3">
          <ServiceHealthGrid services={state.services} navigate={navigate} />
        </div>
        <div className="dashboard-col-1">
          <ActivityFeedPanel events={events} />
        </div>
      </div>
    </div>
  );
}
```

---

### 5. `ui/src/pages/Dashboard.css`

```css
@import '../tokens.css';

/* ── Page layout ─────────────────────────────────────────── */
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dashboard-gpu-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.dashboard-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: flex-start;
}

.dashboard-col-1 { flex: 1; min-width: 180px; }
.dashboard-col-2 { flex: 2; min-width: 300px; }
.dashboard-col-3 { flex: 3; min-width: 360px; }

/* ── GPU cards ───────────────────────────────────────────── */
.gpu-card {
  flex: 1;
  min-width: 180px;
  background: var(--surface);
  border-radius: var(--radius);
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid var(--border);
  transition: border-color .2s;
}

.gpu-card-claimed  { border-color: var(--cyan); }
.gpu-card-warm     { border-color: var(--amber); }
.gpu-card-hot      { border-color: var(--red); }

.gpu-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.gpu-card-id {
  display: flex;
  align-items: center;
  gap: 4px;
}

.gpu-index {
  font-size: 10px;
  font-weight: 600;
  color: var(--text);
}

.gpu-bus {
  font-size: 9px;
  color: var(--text3);
}

.gpu-bridge-badge {
  font-size: 8px;
  letter-spacing: .5px;
  color: var(--text3);
  border: 1px solid var(--border2);
  border-radius: 3px;
  padding: 1px 5px;
  font-weight: 500;
}

.gpu-name {
  font-size: 11px;
  font-weight: 500;
  color: var(--text);
}

.gpu-metrics {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.gpu-metric-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.gpu-metric-label {
  font-size: 9px;
  color: var(--text3);
  width: 32px;
  flex-shrink: 0;
  letter-spacing: .3px;
}

.gpu-metric-row .vbar-track {
  flex: 1;
}

.gpu-metric-value {
  font-size: 9px;
  color: var(--text2);
  width: 64px;
  text-align: right;
  flex-shrink: 0;
}

.gpu-card-footer {
  margin-top: 2px;
}

/* ── Skeleton ────────────────────────────────────────────── */
.skeleton {
  background: linear-gradient(90deg, var(--surface) 25%, var(--surface2) 50%, var(--surface) 75%);
  background-size: 400px 100%;
  animation: shimmer 1.4s ease-in-out infinite;
  min-height: 140px;
  border-radius: var(--radius);
}

@keyframes shimmer {
  0%   { background-position: -400px 0; }
  100% { background-position:  400px 0; }
}

/* ── Loadout banner ──────────────────────────────────────── */
.loadout-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.loadout-name-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.loadout-profile-name {
  font-size: 18px;
  font-weight: 600;
}

.loadout-accent-cyan   { color: var(--cyan); }
.loadout-accent-amber  { color: var(--amber); }
.loadout-accent-purple { color: var(--purple); }
.loadout-accent-gray   { color: var(--text2); }

.loadout-sub {
  font-size: 10px;
  color: var(--text3);
}

.loadout-services {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.loadout-actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

.loadout-empty {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 8px 0;
}

.loadout-empty-msg {
  font-size: 11px;
  color: var(--text3);
}

.loadout-switching {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 4px 0;
}

.switching-icon {
  font-size: 16px;
  color: var(--cyan);
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.switching-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--cyan);
  letter-spacing: .5px;
}

.switching-steps {
  font-size: 9px;
  color: var(--text3);
}

.switching-bar {
  height: 4px;
  background: var(--surface3);
  border-radius: 2px;
  overflow: hidden;
}

.switching-bar-fill {
  width: 40%;
  height: 100%;
  background: var(--cyan);
  animation: progress-slide 1.4s ease-in-out infinite;
}

@keyframes progress-slide {
  0%   { transform: translateX(-100%); }
  100% { transform: translateX(350%); }
}

/* ── System metrics ──────────────────────────────────────── */
.metrics-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.metric-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--surface2);
  border-radius: var(--radius);
  padding: 10px 8px;
  gap: 3px;
  min-height: 64px;
}

.metric-big-num {
  font-size: 22px;
  font-weight: 600;
  line-height: 1;
}

.metric-big-label {
  font-size: 9px;
  color: var(--text3);
  text-align: center;
}

/* ── Service health grid ─────────────────────────────────── */
.service-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
  gap: 6px;
}

.service-tile {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 6px 8px;
  cursor: pointer;
  transition: background .15s, border-color .15s;
}

.service-tile:hover {
  background: var(--surface3);
  border-color: var(--border2);
}

.service-tile-name {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 10px;
  font-weight: 600;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.service-tile-port {
  font-size: 9px;
  color: var(--text3);
  margin-top: 2px;
}

/* ── Activity feed ───────────────────────────────────────── */
.activity-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.activity-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
}

.activity-ts {
  font-size: 9px;
  color: var(--text3);
  width: 32px;
  flex-shrink: 0;
}

.activity-detail {
  color: var(--text2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.activity-empty {
  font-size: 10px;
  color: var(--text3);
  padding: 8px 0;
}

/* ── API error state ─────────────────────────────────────── */
.api-error {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: var(--red);
  border: 1px solid var(--red-dim);
  border-radius: var(--radius);
  padding: 6px 10px;
}
```

---

### 6. Mount polling hooks in Shell

GHC created polling hooks in Step 01 but may not have mounted them. Confirm that `Shell.jsx`
mounts `useGpuStatus`, `useServices`, and `useAlerts` and dispatches to AppContext. If they
were wired already, no change is needed. If not, add them to Shell:

```jsx
// inside Shell component body — hooks must be at the top level, not inside JSX
useGpuStatus();
useServices();
useAlerts();
```

These are the only three hooks that run globally (GPU, services, alert count). The dashboard-specific
hooks (useSystemMetrics, useActivityFeed) are mounted only when Dashboard is rendered.

---

## Notes on `/loadouts` Response Shape

The existing `/loadouts` endpoint returns profile objects. The Dashboard uses `profile.gpus` or
`profile.gpu_ids` (try both — handle whichever the actual endpoint returns) to determine which
GPU indices are claimed. If the field name is different, log the actual response shape in the
feedback file so Step 03 (Loadout Manager) can reference it.

---

## Acceptance Criteria

- [ ] Dashboard renders at `/#/dashboard` with no console errors
- [ ] All 4 GPU cards display: bridge badge, bus_id, VRAM bar, utilization bar, temp (color-coded), power
- [ ] GPU card border: cyan on claimed GPUs (0 and 3 in `inference-pair-a` mock), default on unclaimed
- [ ] Loadout banner shows active profile name in cyan, service tags, time since switch
- [ ] "Switch Profile →" button navigates to `/#/loadout`
- [ ] "Stop All" shows `window.confirm` before calling `POST /stop`
- [ ] System metrics shows 4 stat cards (CPU, RAM, VRAM, Storage) — mock data is fine
- [ ] Service health grid renders all 22 mock service tiles ordered by category
- [ ] Clicking a service tile navigates to `/#/tools?focus={name}`
- [ ] Activity feed shows 7 mock events with correct timestamp formatting (HH:MM, Yest, Nd)
- [ ] `switching: true` in AppContext renders the animated progress banner instead of loadout content
- [ ] No active profile shows the "Go to Loadout" empty state
- [ ] GPU skeletons render when `state.gpus` is empty (before first poll)
- [ ] No ghost polling: all intervals cleared on Dashboard unmount

---

## Feedback

When done, write `plan/UI/GHC-Feedback/02-feedback.md` following the template in
`plan/UI/GHC-Plan/00-overview.md §How to Write Feedback`.

If the actual `/loadouts` response shape differs from what the spec describes, include the real
field names in the Notes section of the feedback — this is important for Step 03.
