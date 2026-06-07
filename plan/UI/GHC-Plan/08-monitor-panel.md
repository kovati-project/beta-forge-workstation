# Step 08 — Monitor Panel

> **Prerequisites:** Steps 01–07 complete. Read `plan/UI/GHC-Plan/00-overview.md`.
> **Reference spec:** `plan/UI/Steps/08-monitor-panel.md`

---

## Goal

Implement the Monitor panel (`/#/monitor`) — a single scrollable page with these sections top-to-bottom:

1. **Active Alerts Banner** — dismissible amber/red bar when `state.alertCount > 0`
2. **GPU Telemetry** — `<canvas>` sparklines (30 min history) + gauge VBars per GPU
3. **System Metrics** — CPU core heatmap (8×8) + RAM / Disk I/O / Network bars
4. **LLM Traces** (left) + **Container Health** (right) — side-by-side
5. **Log Viewer** — SSE stream, service selector, level filter, grep with highlight
6. **Alert History** — 7-day table

The `?service={name}` URL param pre-selects the Log Viewer service (linked from Tools panel).

All APIs are Step 10 stubs — provide complete mock data.

---

## Deliverables

### 1. Mock data — `ui/src/data/monitorMock.js`

```js
// TODO Step 10: replace with live API responses

/** Generate a realistic-looking 600-sample history for one GPU */
function makeGpuHistory(base, drift) {
  const data = [];
  let v = base;
  for (let i = 0; i < 600; i++) {
    v = Math.max(0, Math.min(24, v + (Math.random() - 0.48) * drift));
    data.push(+v.toFixed(2));
  }
  return data;
}

// 30-min VRAM history per GPU (600 points @ 3s interval)
export const MOCK_GPU_HISTORY = {
  0: makeGpuHistory(14, 0.4),  // active — pair A
  3: makeGpuHistory(13, 0.4),  // active — pair A
  1: makeGpuHistory(1.2, 0.1), // idle
  2: makeGpuHistory(0.8, 0.1), // idle
};

export const MOCK_GPU_UTIL_HISTORY = {
  0: makeGpuHistory(78, 2),
  3: makeGpuHistory(74, 2),
  1: makeGpuHistory(5, 1),
  2: makeGpuHistory(3, 1),
};

// 64-cell CPU utilization (%)
export function makeCpuHeatmap() {
  return Array.from({ length: 64 }, (_, i) =>
    i < 16 ? 20 + Math.random() * 65 : Math.random() * 25
  );
}

export const MOCK_SYSTEM_METRICS = {
  cpu_pct: 32,
  ram_used_gb: 94,
  ram_total_gb: 512,
  disk_read_mbps: 12.4,
  disk_write_mbps: 8.7,
  net_rx_mbps: 42.1,
  net_tx_mbps: 6.3,
};

export const MOCK_TRACES = [
  { id: '7a2f', ts: '14:32:01', model: 'qwen2.5-32b-instruct', tokens_in: 312,  tokens_out: 204, latency_ms: 1820, tag: 'webui',    prompt: 'Explain the Fourier transform in simple terms.', completion: 'The Fourier transform…' },
  { id: '3b8c', ts: '14:31:47', model: 'qwen2.5-32b-instruct', tokens_in: 1024, tokens_out: 512, latency_ms: 5210, tag: 'n8n',      prompt: 'You are a JSON extractor…', completion: '{"name":"…"' },
  { id: 'c9d1', ts: '14:30:55', model: 'ollama/llama3.1',       tokens_in: 88,   tokens_out: 64,  latency_ms: 980,  tag: 'api-key', prompt: 'Summarise this text.',      completion: 'The text discusses…'   },
  { id: 'f0e2', ts: '14:29:12', model: 'qwen2.5-32b-instruct', tokens_in: 412,  tokens_out: 310, latency_ms: 6800, tag: 'webui',   prompt: 'Write a Python script to…', completion: 'Here is a Python script…' },
  { id: '1a3b', ts: '14:28:04', model: 'faster-whisper',        tokens_in: 0,    tokens_out: 240, latency_ms: 2100, tag: 'api-key', prompt: '[audio 18s]',                completion: 'I'd like to schedule…'  },
  { id: '5d7e', ts: '14:26:33', model: 'ollama/llama3.1',       tokens_in: 66,   tokens_out: 44,  latency_ms: 540,  tag: 'api-key', prompt: 'What is 2 + 2?',             completion: '4'                    },
];

export const MOCK_CONTAINERS = [
  { name: 'vllm-pair-a',     status: 'running', restarts: 0, oom: false,  cpu_pct: 82, mem_gb: 14.2, image: 'vllm-openai:0.6.1'   },
  { name: 'ollama',          status: 'running', restarts: 1, oom: false,  cpu_pct: 12, mem_gb: 4.8,  image: 'ollama:0.3.14'        },
  { name: 'open-webui',      status: 'running', restarts: 0, oom: false,  cpu_pct: 1,  mem_gb: 0.3,  image: 'open-webui:0.4.5'     },
  { name: 'n8n',             status: 'running', restarts: 3, oom: false,  cpu_pct: 2,  mem_gb: 0.5,  image: 'n8nio/n8n:1.40.0'    },
  { name: 'mcp-filesystem',  status: 'running', restarts: 0, oom: false,  cpu_pct: 0,  mem_gb: 0.1,  image: 'kovati-mcp:latest'    },
  { name: 'comfyui',         status: 'stopped', restarts: 0, oom: false,  cpu_pct: 0,  mem_gb: 0,    image: 'comfyui:latest'       },
  { name: 'searxng',         status: 'running', restarts: 5, oom: true,   cpu_pct: 3,  mem_gb: 0.4,  image: 'searxng:2024.10'      },
];

export const MOCK_ALERT_HISTORY = [
  { id: 1, ts: '2026-06-05 14:31', severity: 'warn', source: 'searxng',       msg: 'OOM kill — container restarted',         ongoing: false },
  { id: 2, ts: '2026-06-05 11:14', severity: 'warn', source: 'vllm-pair-b',   msg: 'CUDA OOM — request rejected',            ongoing: false },
  { id: 3, ts: '2026-06-04 09:02', severity: 'crit', source: 'loadout-mgr',   msg: 'Profile activation timed out after 60s', ongoing: false },
  { id: 4, ts: '2026-06-04 08:55', severity: 'warn', source: 'disk',          msg: '/data 94% full',                         ongoing: true  },
];

export const MOCK_LOG_LINES = [
  '2026-06-05T14:32:04 [INFO] vllm-pair-a: Request 7a2f processed in 1820ms',
  '2026-06-05T14:32:01 [INFO] vllm-pair-a: Incoming request — 312 input tokens',
  '2026-06-05T14:31:50 [WARN] n8n: Workflow retry attempt 2/3',
  '2026-06-05T14:31:47 [INFO] vllm-pair-a: Request 3b8c processed in 5210ms',
  '2026-06-05T14:31:44 [INFO] vllm-pair-a: Incoming request — 1024 input tokens',
  '2026-06-05T14:31:30 [INFO] ollama: Model qwen2.5-7b already loaded',
  '2026-06-05T14:31:10 [INFO] open-webui: Session connected',
  '2026-06-05T14:30:55 [INFO] ollama: Request c9d1 processed in 980ms',
  '2026-06-05T14:30:52 [INFO] ollama: Incoming request — 88 input tokens',
  '2026-06-05T14:30:40 [INFO] loadout-mgr: Health check OK — 5 services nominal',
  '2026-06-05T14:30:25 [INFO] mcp-filesystem: List /data/datasets — 42 entries',
  '2026-06-05T14:29:18 [WARN] vllm-pair-a: Queue depth 8 — high load',
  '2026-06-05T14:29:12 [INFO] vllm-pair-a: Request f0e2 processed in 6800ms',
  '2026-06-05T14:28:55 [ERROR] searxng: OOM kill — restarting',
  '2026-06-05T14:28:04 [INFO] faster-whisper: Audio decode 18s in 2100ms',
];
```

---

### 2. Directory structure

```
ui/src/pages/
  Monitor.jsx
  Monitor.css
  monitor/
    AlertsBanner.jsx
    GpuTelemetry.jsx
    SystemMetrics.jsx
    LlmTraces.jsx
    ContainerHealth.jsx
    LogViewer.jsx
    AlertHistory.jsx
```

---

### 3. `ui/src/pages/Monitor.jsx`

```jsx
import { useLocation }       from 'react-router-dom';
import { useApp }            from '../context/AppContext';
import { AlertsBanner }      from './monitor/AlertsBanner';
import { GpuTelemetry }      from './monitor/GpuTelemetry';
import { SystemMetrics }     from './monitor/SystemMetrics';
import { LlmTraces }         from './monitor/LlmTraces';
import { ContainerHealth }   from './monitor/ContainerHealth';
import { LogViewer }         from './monitor/LogViewer';
import { AlertHistory }      from './monitor/AlertHistory';
import './Monitor.css';

export function Monitor() {
  const { state } = useApp();
  const search    = new URLSearchParams(useLocation().search);
  const focusSvc  = search.get('service') ?? null;

  return (
    <div className="monitor-page">
      <AlertsBanner count={state.alertCount} />
      <GpuTelemetry gpus={state.gpus} />
      <SystemMetrics gpus={state.gpus} />
      <div className="monitor-row">
        <LlmTraces />
        <ContainerHealth />
      </div>
      <LogViewer focusService={focusSvc} services={state.services} />
      <AlertHistory />
    </div>
  );
}
```

```css
/* Monitor.css */
@import '../tokens.css';
.monitor-page { display: flex; flex-direction: column; gap: 16px; }
.monitor-row  { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 1100px) { .monitor-row { grid-template-columns: 1fr; } }
```

---

### 4. `ui/src/pages/monitor/AlertsBanner.jsx`

```jsx
import { useState } from 'react';
import './AlertsBanner.css';

export function AlertsBanner({ count }) {
  const [dismissed, setDismissed] = useState(false);
  if (!count || dismissed) return null;

  return (
    <div className="alerts-banner">
      <span className="alerts-icon">⚠</span>
      <span>{count} active alert{count !== 1 ? 's' : ''} — see Alert History below</span>
      <button className="alerts-dismiss" onClick={() => setDismissed(true)}>✕</button>
    </div>
  );
}
```

```css
/* AlertsBanner.css */
@import '../../tokens.css';
.alerts-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--amber-dim);
  border: 1px solid rgba(255,179,71,.35);
  border-radius: var(--radius);
  padding: 8px 12px;
  font-size: 10px;
  color: var(--amber);
}
.alerts-icon      { font-size: 12px; }
.alerts-banner span:nth-child(2) { flex: 1; }
.alerts-dismiss {
  background: none; border: none;
  color: var(--amber); cursor: pointer; font-size: 11px;
}
```

---

### 5. `ui/src/pages/monitor/GpuTelemetry.jsx`

GPU sparkline charts use `<canvas>` — no chart library. The panel maintains its own 600-sample VRAM history per GPU, separate from AppContext (which only has the current value).

On mount: fetch 30-min history from `/api/metrics/gpu`. On each `state.gpus` update: append new VRAM reading and drop oldest if > 600.

**GPU ordering:** active-profile pair first, idle pair second. Derive from `state.gpus[i].profile` or `state.gpus[i].status` field: GPUs whose `vram_used_gb > 1` considered active.

```jsx
import { useEffect, useRef, useState } from 'react';
import { Panel }                       from '../../components/Panel';
import { VBar }                        from '../../components/VBar';
import { Tag }                         from '../../components/Tag';
import { MOCK_GPU_HISTORY }            from '../../data/monitorMock';
import './GpuTelemetry.css';

// GPU accent colors matching profiles
const GPU_COLORS = { 0: '#00e5ff', 1: '#00e5ff', 2: '#00e5ff', 3: '#00e5ff' };

/**
 * Render a VRAM history sparkline onto a canvas element.
 * @param {HTMLCanvasElement} canvas
 * @param {number[]} data  – array of values (up to 600)
 * @param {string} color   – CSS hex color for the line
 * @param {number} maxGb   – Y-axis max (fixed 24 for RTX A5500)
 */
function renderGpuChart(canvas, data, color, maxGb) {
  if (!canvas || !data.length) return;
  const ctx = canvas.getContext('2d');
  const W   = canvas.width;
  const H   = canvas.height;
  ctx.clearRect(0, 0, W, H);

  const padB = 4; // leave bottom gap
  const drawH = H - padB;

  // Background
  ctx.fillStyle = '#1a1a2e';
  ctx.fillRect(0, 0, W, H);

  // Grid line at 50%
  ctx.strokeStyle = 'rgba(255,255,255,0.05)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  const midY = drawH * (1 - 0.5);
  ctx.moveTo(0, midY); ctx.lineTo(W, midY);
  ctx.stroke();

  if (data.length < 2) return;

  const pts = data.slice(-600);
  const step = W / (pts.length - 1);

  // Gradient fill
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  // Parse hex color to rgba — color is always a 7-char '#rrggbb'
  const r = parseInt(color.slice(1, 3), 16);
  const g = parseInt(color.slice(3, 5), 16);
  const b = parseInt(color.slice(5, 7), 16);
  grad.addColorStop(0, `rgba(${r},${g},${b},0.35)`);
  grad.addColorStop(1, `rgba(${r},${g},${b},0.02)`);

  ctx.beginPath();
  ctx.moveTo(0, drawH * (1 - pts[0] / maxGb));
  for (let i = 1; i < pts.length; i++) {
    ctx.lineTo(i * step, drawH * (1 - pts[i] / maxGb));
  }
  ctx.lineTo((pts.length - 1) * step, H);
  ctx.lineTo(0, H);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Line
  ctx.beginPath();
  ctx.moveTo(0, drawH * (1 - pts[0] / maxGb));
  for (let i = 1; i < pts.length; i++) {
    ctx.lineTo(i * step, drawH * (1 - pts[i] / maxGb));
  }
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.stroke();
}

export function GpuTelemetry({ gpus }) {
  const historyRef = useRef({
    0: [...MOCK_GPU_HISTORY[0]],
    1: [...MOCK_GPU_HISTORY[1]],
    2: [...MOCK_GPU_HISTORY[2]],
    3: [...MOCK_GPU_HISTORY[3]],
  });
  const canvasRefs = [useRef(null), useRef(null), useRef(null), useRef(null)];
  const [fetched, setFetched] = useState(false);

  // Sort GPUs: most-loaded first (active pair at top)
  const orderedGpus = gpus.length
    ? [...gpus].sort((a, b) => b.vram_used_gb - a.vram_used_gb)
    : [0, 1, 2, 3].map(i => ({
        index: i, name: `GPU ${i}`, vram_used_gb: MOCK_GPU_HISTORY[i].at(-1),
        vram_total_gb: 24, temp_c: 45 + i * 3, util_pct: i < 2 ? 70 : 5,
      }));

  function redrawAll() {
    orderedGpus.forEach((gpu, canvasIdx) => {
      const idx = gpu.index ?? gpu;
      renderGpuChart(
        canvasRefs[canvasIdx].current,
        historyRef.current[idx],
        GPU_COLORS[idx],
        24
      );
    });
  }

  // Initial history fetch
  useEffect(() => {
    fetch('/api/metrics/gpu')
      .then(r => r.json())
      .then(data => {
        if (data.history) {
          Object.assign(historyRef.current, data.history);
          setFetched(true);
        }
      })
      .catch(() => setFetched(true)); // use mock history on failure
  }, []);

  // Append new point on each GPU poll (every 3s)
  useEffect(() => {
    if (!gpus.length) return;
    gpus.forEach(gpu => {
      const hist = historyRef.current[gpu.index];
      if (!hist) return;
      hist.push(gpu.vram_used_gb);
      if (hist.length > 600) hist.shift();
    });
    redrawAll();
  }, [gpus]); // eslint-disable-line react-hooks/exhaustive-deps

  // Initial render once mock data is ready
  useEffect(() => {
    if (fetched || !gpus.length) redrawAll();
  }); // runs after each render — canvas draw is idempotent

  const activeGpu = orderedGpus[0];
  const idleGpu   = orderedGpus[2];

  return (
    <Panel title="GPU Telemetry" subtitle="30 min VRAM history · 3 s poll">
      <div className="gpu-telem-grid">
        {orderedGpus.map((gpu, idx) => {
          const gIdx = gpu.index ?? idx;
          return (
            <div key={gIdx} className="gpu-telem-card">
              <div className="gpu-telem-header">
                <span className="gpu-telem-name">{gpu.name ?? `GPU ${gIdx}`}</span>
                <Tag variant={gpu.vram_used_gb > 2 ? 'cyan' : 'gray'}>
                  {gpu.vram_used_gb?.toFixed(1)} / 24 GB
                </Tag>
                <span className="gpu-telem-temp">{gpu.temp_c ?? '--'}°C</span>
              </div>
              <canvas
                ref={canvasRefs[idx]}
                width={280}
                height={80}
                className="gpu-chart"
              />
              <div className="gpu-telem-footer">
                <span>UTIL {gpu.util_pct ?? '--'}%</span>
                <span className="gpu-chart-axis-label">0 ────────────────── 30 min</span>
                <span>24 GB</span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="gpu-gauge-row">
        <VBar label={`GPU${orderedGpus[0]?.index ?? 0} util`} value={orderedGpus[0]?.util_pct ?? 0} max={100} variant="cyan" />
        <VBar label={`GPU${orderedGpus[0]?.index ?? 0} temp`} value={orderedGpus[0]?.temp_c ?? 0} max={90} variant="amber" />
        <VBar label={`GPU${orderedGpus[1]?.index ?? 3} util`} value={orderedGpus[1]?.util_pct ?? 0} max={100} variant="cyan" />
        <VBar label={`GPU${orderedGpus[1]?.index ?? 3} temp`} value={orderedGpus[1]?.temp_c ?? 0} max={90} variant="amber" />
        <VBar label="CPU" value={32} max={100} variant="gray" />
        <VBar label="RAM" value={Math.round(94 / 512 * 100)} max={100} variant="gray" />
      </div>
    </Panel>
  );
}
```

```css
/* GpuTelemetry.css */
@import '../../tokens.css';

.gpu-telem-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 12px;
}

.gpu-telem-card {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 8px;
}

.gpu-telem-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.gpu-telem-name {
  font-size: 10px;
  font-weight: 600;
  color: var(--text);
  flex: 1;
}

.gpu-telem-temp {
  font-size: 9px;
  color: var(--text3);
}

.gpu-chart {
  display: block;
  width: 100%;
  height: 80px;
  border-radius: 3px;
}

.gpu-telem-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 8px;
  color: var(--text3);
  margin-top: 4px;
}

.gpu-chart-axis-label { color: var(--border2); }

.gpu-gauge-row {
  display: flex;
  gap: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--border);
}
```

---

### 6. `ui/src/pages/monitor/SystemMetrics.jsx`

CPU heatmap: 8×8 grid of colored cells representing all 64 threads. Color by utilization tier:
- `< 25%` → `var(--surface3)` (near-idle)
- `25–50%` → `#1a3a2a` (low activity, subtle green)
- `50–75%` → `var(--amber-dim)` (moderate)
- `> 75%` → `rgba(239,68,68,.35)` (hot, reddish)

```jsx
import { useEffect, useState } from 'react';
import { Panel }               from '../../components/Panel';
import { makeCpuHeatmap, MOCK_SYSTEM_METRICS } from '../../data/monitorMock';
import './SystemMetrics.css';

function cpuCellColor(pct) {
  if (pct > 75) return 'rgba(239,68,68,.4)';
  if (pct > 50) return 'var(--amber-dim)';
  if (pct > 25) return '#1a3a2a';
  return 'var(--surface3)';
}

function MetricBar({ label, used, max, unitLabel, secondaryUsed, secondaryLabel }) {
  const pct  = Math.min(100, (used  / max) * 100);
  const pct2 = secondaryUsed !== undefined ? Math.min(100, (secondaryUsed / max) * 100) : null;
  return (
    <div className="metric-bar-row">
      <span className="metric-bar-label">{label}</span>
      <div className="metric-bar-track">
        <div className="metric-bar-fill"   style={{ width: `${pct}%` }} />
        {pct2 !== null && (
          <div className="metric-bar-fill secondary" style={{ width: `${pct2}%`, left: `${pct}%` }} />
        )}
      </div>
      <span className="metric-bar-value">
        {used.toFixed(1)}{secondaryLabel && ` ↑ / ${secondaryUsed?.toFixed(1)} ↓`} {unitLabel}
      </span>
    </div>
  );
}

export function SystemMetrics({ gpus }) {
  const [cpuCells, setCpuCells] = useState(() => makeCpuHeatmap());
  const [metrics,  setMetrics]  = useState(MOCK_SYSTEM_METRICS);

  // Refresh every 10s
  useEffect(() => {
    async function fetchMetrics() {
      try {
        const data = await fetch('/api/metrics/system').then(r => r.json());
        setMetrics(data);
      } catch { /* use mock */ }
      setCpuCells(makeCpuHeatmap()); // TODO Step 10: use real per-core data
    }
    fetchMetrics();
    const t = setInterval(fetchMetrics, 10_000);
    return () => clearInterval(t);
  }, []);

  return (
    <Panel title="System Metrics">
      <div className="sysmet-layout">
        {/* Left: CPU heatmap */}
        <div className="sysmet-cpu">
          <div className="sysmet-section-label">CPU · 64 threads · {metrics.cpu_pct}% avg</div>
          <div className="cpu-heatmap" title="Each cell = one logical CPU core">
            {cpuCells.map((pct, i) => (
              <div
                key={i}
                className="cpu-cell"
                style={{ background: cpuCellColor(pct) }}
                title={`CPU ${i}: ${pct.toFixed(0)}%`}
              />
            ))}
          </div>
          <div className="cpu-legend">
            <span className="legend-item legend-idle">Idle</span>
            <span className="legend-item legend-low">Low</span>
            <span className="legend-item legend-med">Med</span>
            <span className="legend-item legend-hot">Hot</span>
          </div>
        </div>

        {/* Right: metric bars */}
        <div className="sysmet-bars">
          <div className="sysmet-section-label">Memory</div>
          <MetricBar
            label="RAM"
            used={metrics.ram_used_gb}
            max={metrics.ram_total_gb}
            unitLabel="GB"
          />
          <div className="sysmet-section-label">Disk I/O</div>
          <MetricBar
            label="Read"
            used={metrics.disk_read_mbps}
            max={1000}
            unitLabel="MB/s"
          />
          <MetricBar
            label="Write"
            used={metrics.disk_write_mbps}
            max={1000}
            unitLabel="MB/s"
          />
          <div className="sysmet-section-label">Network</div>
          <MetricBar
            label="RX"
            used={metrics.net_rx_mbps}
            max={1000}
            unitLabel="Mb/s"
          />
          <MetricBar
            label="TX"
            used={metrics.net_tx_mbps}
            max={1000}
            unitLabel="Mb/s"
          />
        </div>
      </div>
    </Panel>
  );
}
```

```css
/* SystemMetrics.css */
@import '../../tokens.css';

.sysmet-layout { display: grid; grid-template-columns: 180px 1fr; gap: 16px; align-items: start; }

.sysmet-section-label { font-size: 8px; color: var(--text3); margin: 8px 0 4px; text-transform: uppercase; letter-spacing: .06em; }
.sysmet-section-label:first-child { margin-top: 0; }

/* CPU Heatmap */
.cpu-heatmap {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 2px;
  width: 160px;
}

.cpu-cell {
  width: 100%;
  aspect-ratio: 1;
  border-radius: 1px;
  cursor: default;
  transition: opacity .15s;
}

.cpu-cell:hover { opacity: .8; }

.cpu-legend { display: flex; gap: 6px; margin-top: 6px; }

.legend-item { font-size: 8px; padding: 1px 5px; border-radius: 2px; }
.legend-idle { background: var(--surface3);         color: var(--text3); }
.legend-low  { background: #1a3a2a;                 color: #5daf7a;     }
.legend-med  { background: var(--amber-dim);        color: var(--amber); }
.legend-hot  { background: rgba(239,68,68,.4);      color: #ff6b6b;     }

/* Metric bars */
.metric-bar-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.metric-bar-label { font-size: 9px; color: var(--text3); width: 32px; flex-shrink: 0; }

.metric-bar-track {
  flex: 1;
  height: 6px;
  background: var(--surface3);
  border-radius: 3px;
  overflow: hidden;
  position: relative;
}

.metric-bar-fill {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: var(--cyan-dim);
  border-radius: 3px;
  transition: width .4s ease;
}

.metric-bar-fill.secondary { background: var(--text3); }

.metric-bar-value { font-size: 9px; color: var(--text2); width: 60px; text-align: right; white-space: nowrap; }
```

---

### 7. `ui/src/pages/monitor/LlmTraces.jsx`

```jsx
import { useState } from 'react';
import { Panel }    from '../../components/Panel';
import { Tag }      from '../../components/Tag';
import { MOCK_TRACES } from '../../data/monitorMock';
import './LlmTraces.css';

const LATENCY_VARIANT = ms => ms < 2000 ? 'green' : ms < 5000 ? 'amber' : 'red';
const REDACT = text => text.length > 40 ? text.slice(0, 40) + ' [redacted]' : '[redacted]';

export function LlmTraces() {
  const [traces,   setTraces]   = useState(MOCK_TRACES);
  const [expanded, setExpanded] = useState(null);
  const [revealed, setRevealed] = useState(new Set());
  const [filter,   setFilter]   = useState({ model: '', latency: '', tag: '' });
  const [loading,  setLoading]  = useState(false);
  const [page,     setPage]     = useState(1);
  const PAGE = 6;

  const filtered = traces.filter(t => {
    if (filter.model   && !t.model.includes(filter.model))     return false;
    if (filter.latency === '>5s'  && t.latency_ms <= 5000)     return false;
    if (filter.latency === '>2s'  && t.latency_ms <= 2000)     return false;
    if (filter.latency === '<2s'  && t.latency_ms >= 2000)     return false;
    if (filter.tag     && t.tag !== filter.tag)                return false;
    return true;
  });

  const visible = filtered.slice(0, page * PAGE);

  function toggleExpand(id) {
    setExpanded(prev => prev === id ? null : id);
  }

  function reveal(id) {
    setRevealed(prev => new Set([...prev, id]));
  }

  async function loadMore() {
    setLoading(true);
    try {
      const res = await fetch(`/api/traces?offset=${traces.length}`);
      const data = res.ok ? await res.json() : null;
      if (data?.traces?.length) setTraces(prev => [...prev, ...data.traces]);
      else setPage(p => p + 1);
    } catch {
      setPage(p => p + 1);
    }
    setLoading(false);
  }

  const models = [...new Set(MOCK_TRACES.map(t => t.model))];
  const tags   = [...new Set(MOCK_TRACES.map(t => t.tag))];

  return (
    <Panel title="LLM Traces" subtitle={`${filtered.length} requests`}>
      <div className="traces-filter-row">
        <select className="traces-filter-sel" value={filter.model} onChange={e => setFilter(f => ({ ...f, model: e.target.value }))}>
          <option value="">All models</option>
          {models.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
        <select className="traces-filter-sel" value={filter.latency} onChange={e => setFilter(f => ({ ...f, latency: e.target.value }))}>
          <option value="">Any latency</option>
          <option value="<2s">&lt; 2s</option>
          <option value=">2s">&gt; 2s</option>
          <option value=">5s">&gt; 5s</option>
        </select>
        <select className="traces-filter-sel" value={filter.tag} onChange={e => setFilter(f => ({ ...f, tag: e.target.value }))}>
          <option value="">Any source</option>
          {tags.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
      </div>

      <table className="traces-table">
        <thead>
          <tr><th>Time</th><th>Model</th><th>Tokens</th><th>Latency</th><th>Source</th><th></th></tr>
        </thead>
        <tbody>
          {visible.map(t => (
            <>
              <tr key={t.id} className={`trace-row ${expanded === t.id ? 'trace-expanded' : ''}`}
                onClick={() => toggleExpand(t.id)} style={{ cursor: 'pointer' }}>
                <td className="trace-ts">{t.ts}</td>
                <td className="trace-model">{t.model}</td>
                <td className="trace-tokens">{t.tokens_in}→{t.tokens_out}</td>
                <td>
                  <Tag variant={LATENCY_VARIANT(t.latency_ms)}>
                    {(t.latency_ms / 1000).toFixed(2)}s
                  </Tag>
                </td>
                <td><Tag variant="gray">{t.tag}</Tag></td>
                <td className="trace-chevron">{expanded === t.id ? '▾' : '▸'}</td>
              </tr>
              {expanded === t.id && (
                <tr key={`${t.id}-detail`} className="trace-detail-row">
                  <td colSpan={6}>
                    <div className="trace-detail">
                      <div className="trace-detail-label">
                        Prompt
                        {!revealed.has(`${t.id}-p`) && (
                          <button className="reveal-btn" onClick={() => reveal(`${t.id}-p`)}>Reveal</button>
                        )}
                      </div>
                      <pre className="trace-detail-text">
                        {revealed.has(`${t.id}-p`) ? t.prompt : REDACT(t.prompt)}
                      </pre>
                      <div className="trace-detail-label">
                        Completion
                        {!revealed.has(`${t.id}-c`) && (
                          <button className="reveal-btn" onClick={() => reveal(`${t.id}-c`)}>Reveal</button>
                        )}
                      </div>
                      <pre className="trace-detail-text">
                        {revealed.has(`${t.id}-c`) ? t.completion : REDACT(t.completion)}
                      </pre>
                    </div>
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>

      {visible.length < filtered.length && (
        <button className="load-more-btn" onClick={loadMore} disabled={loading}>
          {loading ? 'Loading…' : `Load More (${filtered.length - visible.length} remaining)`}
        </button>
      )}
    </Panel>
  );
}
```

```css
/* LlmTraces.css */
@import '../../tokens.css';

.traces-filter-row { display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }

.traces-filter-sel {
  background: var(--surface3);
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--text2);
  font-size: 9px;
  font-family: var(--mono);
  padding: 3px 6px;
}

.traces-table { width: 100%; border-collapse: collapse; font-size: 9px; }
.traces-table th {
  text-align: left; color: var(--text3); font-size: 8px;
  border-bottom: 1px solid var(--border); padding: 4px 6px;
}
.traces-table td { padding: 5px 6px; color: var(--text2); border-bottom: 1px solid var(--border); }

.trace-row:hover td       { background: var(--surface2); }
.trace-expanded td        { background: var(--surface2); }
.trace-ts                 { color: var(--text3); font-size: 8px; white-space: nowrap; }
.trace-model              { max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.trace-tokens             { color: var(--text3); }
.trace-chevron            { color: var(--text3); text-align: right; }

.trace-detail-row td      { padding: 0; }
.trace-detail             { padding: 8px 10px; background: var(--surface3); }
.trace-detail-label       { font-size: 8px; color: var(--text3); margin-bottom: 3px; display: flex; align-items: center; gap: 6px; }

.reveal-btn {
  background: none; border: 1px solid var(--border);
  border-radius: 2px; color: var(--text3); cursor: pointer;
  font-size: 8px; padding: 1px 6px;
}

.trace-detail-text {
  font-size: 9px; color: var(--text2); font-family: var(--mono);
  margin: 0 0 8px; white-space: pre-wrap; word-break: break-all;
}

.load-more-btn {
  width: 100%; margin-top: 8px;
  background: var(--surface2); border: 1px solid var(--border);
  border-radius: 3px; color: var(--text3); cursor: pointer;
  font-size: 9px; padding: 6px;
}
```

---

### 8. `ui/src/pages/monitor/ContainerHealth.jsx`

```jsx
import { useEffect, useState } from 'react';
import { Panel }               from '../../components/Panel';
import { DotStatus }           from '../../components/DotStatus';
import { Tag }                 from '../../components/Tag';
import { MOCK_CONTAINERS }     from '../../data/monitorMock';
import './ContainerHealth.css';

export function ContainerHealth() {
  const [containers, setContainers] = useState(MOCK_CONTAINERS);

  useEffect(() => {
    async function fetch_() {
      try {
        const data = await fetch('/api/metrics/containers').then(r => r.json());
        if (Array.isArray(data)) setContainers(data);
      } catch { /* use mock */ }
    }
    fetch_();
    const t = setInterval(fetch_, 10_000);
    return () => clearInterval(t);
  }, []);

  return (
    <Panel title="Container Health">
      <table className="container-table">
        <thead>
          <tr><th>Container</th><th>CPU</th><th>Mem</th><th>Restarts</th><th></th></tr>
        </thead>
        <tbody>
          {containers.map(c => {
            const isHot = c.restarts >= 3;
            return (
              <tr key={c.name} className={isHot ? 'container-row-hot' : ''}>
                <td>
                  <span className="container-name-cell">
                    <DotStatus status={c.status === 'running' ? 'green' : 'gray'} />
                    {c.name}
                    {c.oom && <Tag variant="red">OOM</Tag>}
                  </span>
                </td>
                <td>{c.cpu_pct}%</td>
                <td>{c.mem_gb > 0 ? `${c.mem_gb.toFixed(1)} GB` : '—'}</td>
                <td className={c.restarts >= 3 ? 'restarts-hot' : ''}>{c.restarts}</td>
                <td><span className="container-image">{c.image}</span></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Panel>
  );
}
```

```css
/* ContainerHealth.css */
@import '../../tokens.css';

.container-table { width: 100%; border-collapse: collapse; font-size: 9px; }
.container-table th {
  text-align: left; color: var(--text3); font-size: 8px;
  border-bottom: 1px solid var(--border); padding: 4px 6px;
}
.container-table td { padding: 5px 6px; color: var(--text2); border-bottom: 1px solid var(--border); }
.container-table tr:last-child td { border-bottom: none; }

.container-row-hot td:first-child { color: var(--red); }

.container-name-cell { display: flex; align-items: center; gap: 5px; }
.container-image     { font-size: 8px; color: var(--text3); }
.restarts-hot        { color: var(--red); font-weight: 600; }
```

---

### 9. `ui/src/pages/monitor/LogViewer.jsx`

Key behaviors:
- `?service={name}` (from `focusService` prop) pre-selects the service
- On service change: close existing EventSource, fetch last 200 lines, open new SSE
- Level filter (ALL/INFO/WARN/ERROR) is client-side — filters already-received lines
- Grep filter: highlights matches inline with `<mark>`; does NOT filter out non-matching lines
- Scroll lock: auto-scroll to bottom unless user scrolled up; "↓ Jump to Bottom" button appears when locked

```jsx
import { useEffect, useRef, useState } from 'react';
import { Panel }                       from '../../components/Panel';
import { MOCK_LOG_LINES }              from '../../data/monitorMock';
import './LogViewer.css';

const LEVEL_COLORS = { INFO: 'var(--text2)', WARN: 'var(--amber)', ERROR: 'var(--red)' };

function parseLevel(line) {
  if (line.includes('[ERROR]')) return 'ERROR';
  if (line.includes('[WARN]'))  return 'WARN';
  if (line.includes('[INFO]'))  return 'INFO';
  return 'INFO';
}

function highlight(text, term) {
  if (!term) return text;
  const idx = text.toLowerCase().indexOf(term.toLowerCase());
  if (idx < 0) return text;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="log-highlight">{text.slice(idx, idx + term.length)}</mark>
      {text.slice(idx + term.length)}
    </>
  );
}

export function LogViewer({ focusService, services }) {
  // Build service list from running containers
  const serviceNames = services
    ? Object.keys(services).filter(k => services[k]?.status === 'running')
    : ['vllm-pair-a', 'ollama', 'open-webui', 'n8n', 'mcp-filesystem'];

  const [selected,  setSelected]  = useState(focusService ?? serviceNames[0] ?? '');
  const [lines,     setLines]     = useState(MOCK_LOG_LINES);
  const [levelFilter, setLevel]   = useState('ALL');
  const [grep,      setGrep]      = useState('');
  const [scrollLocked, setLocked] = useState(false);

  const esRef       = useRef(null);
  const logEndRef   = useRef(null);
  const logBodyRef  = useRef(null);

  function connectService(name) {
    if (!name) return;
    // Close existing SSE
    if (esRef.current) { esRef.current.close(); esRef.current = null; }

    // Fetch initial log lines
    fetch(`/api/services/${encodeURIComponent(name)}/logs?n=200`)
      .then(r => r.json())
      .then(data => setLines(Array.isArray(data?.lines) ? data.lines : MOCK_LOG_LINES))
      .catch(() => setLines(MOCK_LOG_LINES));

    // Open SSE stream
    const es = new EventSource(`/api/services/${encodeURIComponent(name)}/logs/stream`);
    es.onmessage = e => {
      setLines(prev => {
        const next = [...prev, e.data];
        return next.length > 1000 ? next.slice(-800) : next; // hard cap
      });
    };
    esRef.current = es;
  }

  // Connect on mount and on service change
  useEffect(() => {
    connectService(selected);
    return () => { esRef.current?.close(); esRef.current = null; };
  }, [selected]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-scroll unless locked
  useEffect(() => {
    if (!scrollLocked) logEndRef.current?.scrollIntoView({ behavior: 'auto' });
  }, [lines, scrollLocked]);

  function onScroll() {
    const el = logBodyRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setLocked(!atBottom);
  }

  // Filtered view
  const visible = lines.filter(l => {
    if (levelFilter !== 'ALL' && parseLevel(l) !== levelFilter) return false;
    if (grep && !l.toLowerCase().includes(grep.toLowerCase())) return false;
    return true;
  });

  return (
    <Panel title="Log Viewer">
      <div className="logviewer-controls">
        <select
          className="log-select"
          value={selected}
          onChange={e => { setSelected(e.target.value); setLines([]); }}
        >
          {serviceNames.map(n => <option key={n} value={n}>{n}</option>)}
        </select>

        <div className="log-level-tabs">
          {['ALL','INFO','WARN','ERROR'].map(l => (
            <button
              key={l}
              className={`log-level-tab ${levelFilter === l ? 'active' : ''} level-${l.toLowerCase()}`}
              onClick={() => setLevel(l)}
            >{l}</button>
          ))}
        </div>

        <input
          className="log-grep-input"
          placeholder="grep…"
          value={grep}
          onChange={e => setGrep(e.target.value)}
        />
      </div>

      <div className="logviewer-body" ref={logBodyRef} onScroll={onScroll}>
        {visible.map((line, i) => {
          const lvl = parseLevel(line);
          return (
            <div key={i} className="log-line" style={{ color: LEVEL_COLORS[lvl] }}>
              {highlight(line, grep)}
            </div>
          );
        })}
        <div ref={logEndRef} />
      </div>

      {scrollLocked && (
        <button
          className="scroll-to-live"
          onClick={() => {
            setLocked(false);
            logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
          }}
        >↓ Jump to Bottom</button>
      )}
    </Panel>
  );
}
```

```css
/* LogViewer.css */
@import '../../tokens.css';

.logviewer-controls {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.log-select {
  background: var(--surface3); border: 1px solid var(--border);
  border-radius: 3px; color: var(--text2);
  font-family: var(--mono); font-size: 9px; padding: 3px 6px;
}

.log-level-tabs { display: flex; gap: 2px; }

.log-level-tab {
  background: var(--surface3); border: 1px solid var(--border);
  border-radius: 2px; color: var(--text3); cursor: pointer;
  font-size: 8px; padding: 3px 7px;
}

.log-level-tab.active          { border-color: var(--cyan); color: var(--cyan); }
.log-level-tab.level-warn      { }
.log-level-tab.active.level-warn   { border-color: var(--amber); color: var(--amber); }
.log-level-tab.active.level-error  { border-color: var(--red);   color: var(--red);   }

.log-grep-input {
  background: var(--surface3); border: 1px solid var(--border);
  border-radius: 3px; color: var(--text2);
  font-family: var(--mono); font-size: 9px; padding: 3px 8px;
  width: 140px;
}

.logviewer-body {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  height: 280px;
  overflow-y: auto;
  padding: 8px;
  position: relative;
}

.log-line {
  font-family: var(--mono);
  font-size: 9px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}

.log-highlight {
  background: rgba(0,229,255,.25);
  color: var(--cyan);
  border-radius: 1px;
}

.scroll-to-live {
  position: relative;
  width: 100%;
  margin-top: 4px;
  background: var(--surface2);
  border: 1px solid var(--cyan);
  border-radius: 3px;
  color: var(--cyan);
  cursor: pointer;
  font-size: 9px;
  padding: 4px;
}
```

---

### 10. `ui/src/pages/monitor/AlertHistory.jsx`

```jsx
import { useEffect, useState } from 'react';
import { Panel }               from '../../components/Panel';
import { Tag }                 from '../../components/Tag';
import { MOCK_ALERT_HISTORY }  from '../../data/monitorMock';
import './AlertHistory.css';

export function AlertHistory() {
  const [alerts, setAlerts] = useState(MOCK_ALERT_HISTORY);

  useEffect(() => {
    fetch('/api/alerts/history')
      .then(r => r.json())
      .then(data => { if (Array.isArray(data)) setAlerts(data); })
      .catch(() => { /* use mock */ });
  }, []);

  return (
    <Panel title="Alert History" subtitle="Last 7 days">
      <table className="alert-table">
        <thead>
          <tr><th>Time</th><th>Severity</th><th>Source</th><th>Message</th><th></th></tr>
        </thead>
        <tbody>
          {alerts.map(a => (
            <tr key={a.id} className={a.ongoing ? 'alert-ongoing' : ''}>
              <td className="alert-ts">{a.ts}</td>
              <td><Tag variant={a.severity === 'crit' ? 'red' : 'amber'}>{a.severity}</Tag></td>
              <td>{a.source}</td>
              <td>{a.msg}</td>
              <td>{a.ongoing && <span className="alert-ongoing-badge">ongoing</span>}</td>
            </tr>
          ))}
          {alerts.length === 0 && (
            <tr><td colSpan={5} className="alert-empty">No alerts in the past 7 days</td></tr>
          )}
        </tbody>
      </table>
    </Panel>
  );
}
```

```css
/* AlertHistory.css */
@import '../../tokens.css';

.alert-table { width: 100%; border-collapse: collapse; font-size: 9px; }
.alert-table th {
  text-align: left; color: var(--text3); font-size: 8px;
  border-bottom: 1px solid var(--border); padding: 4px 8px;
}
.alert-table td { padding: 6px 8px; color: var(--text2); border-bottom: 1px solid var(--border); }
.alert-table tr:last-child td { border-bottom: none; }

.alert-ongoing td { color: var(--red); }
.alert-ongoing-badge {
  font-size: 8px; color: var(--red);
  border: 1px solid var(--red); border-radius: 2px; padding: 1px 5px;
}
.alert-ts    { color: var(--text3); white-space: nowrap; }
.alert-empty { text-align: center; color: var(--text3); font-style: italic; padding: 14px !important; }
```

---

## Router update

Add `/monitor` to App.jsx and the sidebar if not already present.

The sidebar badge showing `state.alertCount` was set up in Step 01. Verify it updates when `alertCount > 0`.

---

## Canvas chart notes

- `canvas.width` and `canvas.height` are the **pixel dimensions** — set them to 280 and 80. The CSS `width: 100%` will stretch the display but the pixel resolution is fixed. For high-DPI, use `devicePixelRatio` scaling (optional — not required for MVP).
- The `renderGpuChart` function is called after every `state.gpus` update (roughly every 3s) and on initial mount. Canvas draws are idempotent.
- Do NOT use `requestAnimationFrame` loops — draw on data change only.

---

## Acceptance Criteria

- [ ] **Alerts banner** renders amber when `state.alertCount > 0`; dismiss button hides it for the session
- [ ] **GPU charts** render on 4 canvases; on each 3s poll a new point is appended and charts redraw; order is active-pair first (highest VRAM)
- [ ] **CPU heatmap** renders 64 cells in an 8×8 grid; cell color follows 4-tier scheme; hover shows `CPU N: X%` tooltip
- [ ] **System bars** show RAM, Disk read, Disk write, Net RX, Net TX
- [ ] **LLM Traces** table shows at least the 6 mock traces; filter dropdowns narrow the list; expand row shows redacted text + Reveal button; latency tag is green/amber/red by threshold
- [ ] **Container Health** shows all 7 mock containers; rows with `restarts >= 3` are red-tinted; OOM flag shown as red Tag
- [ ] **Log Viewer** pre-selects service from `?service=` URL param; switching service fetches new logs and opens new SSE; level filter is client-side; grep highlights matches in `--cyan`; scroll lock shows "↓ Jump to Bottom" when user scrolls up
- [ ] **Alert History** shows all 4 mock alerts; ongoing alert row text is red
- [ ] No canvas errors in console; `ctx.getContext('2d')` always on a mounted canvas

---

## Feedback

Write `plan/UI/GHC-Feedback/08-feedback.md` when done.

**Required in Notes:**
- Did the canvas `width`/`height` attributes need to be set in JavaScript (via `ref.current.width = 280`) or were they set as JSX props and still worked correctly?
- Was `devicePixelRatio` scaling needed for the charts to look sharp, or is the fixed 280×80 resolution acceptable?
- Confirm the `?service=` URL param correctly pre-selects the service in the Log Viewer when navigating from the Tools panel.
