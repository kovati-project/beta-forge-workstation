# Step 04 — Tools Panel

> **Prerequisites:** Steps 01–03 complete. Read `plan/UI/GHC-Plan/00-overview.md`.
> **Reference spec:** `plan/UI/Steps/04-tools-panel.md`

---

## Goal

Implement the Tools panel (`/#/tools`):

1. **9 accordion groups** — all expanded by default, collapsible
2. **Service cards (collapsed row)** — status dot, name, port, GPU tags, status tag, Open button, toggle, expand chevron
3. **Service cards (expanded detail)** — image, uptime, CPU%, memory, 3-line log tail
4. **Toggle behavior** — optimistic UI, confirmation for GPU-consuming services, disabled for loadout-managed services
5. **Focus behavior** — `?focus={name}` from Dashboard scrolls and highlights the target card

`/api/services`, `/api/services/{name}`, and `/api/services/{name}/logs` do not exist yet
(Step 10). Use mock data with `// TODO Step 10` comments. `/loadouts` and `/status` already exist.

---

## Deliverables

### 1. Service Catalog (source of truth for this step)

Create `ui/src/data/serviceCatalog.js` — static metadata, never changes at runtime.
The `status`, `uptime_seconds`, `cpu_pct`, `mem_gb`, and `image` fields come from the API.
Everything else is static.

```js
// Fields: name, group, port (null if no port), gpus ([] if CPU-only), composeFile
export const SERVICE_CATALOG = [
  // Group 1: Text Inference
  { name: 'ollama',         group: 'Text Inference',       port: 11434, gpus: [0, 3], composeFile: 'compose.inference.yml' },
  { name: 'vllm-pair-a',   group: 'Text Inference',       port: 8000,  gpus: [0, 3], composeFile: 'compose.inference.yml' },
  { name: 'vllm-pair-b',   group: 'Text Inference',       port: 8001,  gpus: [1, 2], composeFile: 'compose.inference.yml' },
  { name: 'vllm-4gpu',     group: 'Text Inference',       port: 8002,  gpus: [0,1,2,3], composeFile: 'compose.inference.yml' },
  { name: 'llama-cpp',     group: 'Text Inference',       port: 8080,  gpus: [0],    composeFile: 'compose.inference.yml' },
  { name: 'tabby',         group: 'Text Inference',       port: 9090,  gpus: [0],    composeFile: 'compose.inference.yml' },
  { name: 'litellm',       group: 'Text Inference',       port: 4000,  gpus: [],     composeFile: 'compose.inference.yml' },

  // Group 2: Image Studio
  { name: 'comfyui',       group: 'Image Studio',         port: 8188,  gpus: [0, 3], composeFile: 'compose.studio.yml' },
  { name: 'a1111',         group: 'Image Studio',         port: 7860,  gpus: [0, 3], composeFile: 'compose.studio.yml' },
  { name: 'invokeai',      group: 'Image Studio',         port: 9091,  gpus: [0, 3], composeFile: 'compose.studio.yml' },
  { name: 'real-esrgan',   group: 'Image Studio',         port: 7861,  gpus: [0],    composeFile: 'compose.studio.yml' },
  { name: 'rembg',         group: 'Image Studio',         port: 7000,  gpus: [],     composeFile: 'compose.studio.yml' },

  // Group 3: Training
  { name: 'axolotl',       group: 'Training',             port: null,  gpus: [0, 3], composeFile: 'compose.training.yml' },
  { name: 'kohya',         group: 'Training',             port: 7862,  gpus: [1, 2], composeFile: 'compose.training.yml' },
  { name: 'unsloth',       group: 'Training',             port: null,  gpus: [0],    composeFile: 'compose.training.yml' },
  { name: 'label-studio',  group: 'Training',             port: 8081,  gpus: [],     composeFile: 'compose.training.yml' },
  { name: 'jupyterlab',    group: 'Training',             port: 8888,  gpus: [],     composeFile: 'compose.training.yml' },

  // Group 4: Agentic & Workflow
  { name: 'n8n',           group: 'Agentic & Workflow',   port: 5678,  gpus: [],     composeFile: 'compose.agentic.yml' },
  { name: 'dify',          group: 'Agentic & Workflow',   port: 3001,  gpus: [],     composeFile: 'compose.agentic.yml' },
  { name: 'openhands',     group: 'Agentic & Workflow',   port: 3002,  gpus: [],     composeFile: 'compose.agentic.yml' },
  { name: 'mcp-filesystem',group: 'Agentic & Workflow',   port: 3100,  gpus: [],     composeFile: 'compose.agentic.yml' },
  { name: 'mcp-browser',   group: 'Agentic & Workflow',   port: 3101,  gpus: [],     composeFile: 'compose.agentic.yml' },
  { name: 'mcp-code-exec', group: 'Agentic & Workflow',   port: 3102,  gpus: [],     composeFile: 'compose.agentic.yml' },
  { name: 'mcp-fetch',     group: 'Agentic & Workflow',   port: 3103,  gpus: [],     composeFile: 'compose.agentic.yml' },

  // Group 5: Voice I/O
  { name: 'faster-whisper',group: 'Voice I/O',            port: 9000,  gpus: [0],    composeFile: 'compose.voice.yml' },
  { name: 'piper-tts',     group: 'Voice I/O',            port: 9001,  gpus: [],     composeFile: 'compose.voice.yml' },

  // Group 6: Chat UI
  { name: 'open-webui',    group: 'Chat UI',              port: 3000,  gpus: [],     composeFile: 'compose.webui.yml' },
  { name: 'searxng',       group: 'Chat UI',              port: 4001,  gpus: [],     composeFile: 'compose.webui.yml' },

  // Group 7: Storage & Vector
  { name: 'minio',         group: 'Storage & Vector',     port: 9002,  gpus: [],     composeFile: 'compose.storage.yml' },
  { name: 'qdrant',        group: 'Storage & Vector',     port: 6333,  gpus: [],     composeFile: 'compose.storage.yml' },
  { name: 'postgres',      group: 'Storage & Vector',     port: 5432,  gpus: [],     composeFile: 'compose.storage.yml' },
  { name: 'langfuse',      group: 'Storage & Vector',     port: 3003,  gpus: [],     composeFile: 'compose.storage.yml' },

  // Group 8: Observability
  { name: 'prometheus',    group: 'Observability',        port: 9090,  gpus: [],     composeFile: 'compose.monitoring.yml' },
  { name: 'grafana',       group: 'Observability',        port: 3004,  gpus: [],     composeFile: 'compose.monitoring.yml' },
  { name: 'dcgm-exporter', group: 'Observability',        port: 9400,  gpus: [],     composeFile: 'compose.monitoring.yml' },
  { name: 'node-exporter', group: 'Observability',        port: 9100,  gpus: [],     composeFile: 'compose.monitoring.yml' },
  { name: 'cadvisor',      group: 'Observability',        port: 8082,  gpus: [],     composeFile: 'compose.monitoring.yml' },

  // Group 9: Auth & Security
  { name: 'authentik',     group: 'Auth & Security',      port: 9080,  gpus: [],     composeFile: 'compose.auth.yml' },
];

export const GROUP_ORDER = [
  'Text Inference', 'Image Studio', 'Training', 'Agentic & Workflow',
  'Voice I/O', 'Chat UI', 'Storage & Vector', 'Observability', 'Auth & Security',
];

// {host} is resolved from window.location.hostname at runtime
export function serviceUrl(name, host) {
  const MAP = {
    'ollama':          `http://${host}:11434`,
    'vllm-pair-a':    `http://${host}:8000`,
    'vllm-pair-b':    `http://${host}:8001`,
    'vllm-4gpu':      `http://${host}:8002`,
    'llama-cpp':      `http://${host}:8080`,
    'tabby':          `http://${host}:9090`,
    'litellm':        `http://${host}:4000`,
    'comfyui':        `http://${host}:8188`,
    'a1111':          `http://${host}:7860`,
    'invokeai':       `http://${host}:9091`,
    'kohya':          `http://${host}:7862`,
    'jupyterlab':     `http://${host}:8888`,
    'n8n':            `http://${host}:5678`,
    'dify':           `http://${host}:3001`,
    'open-webui':     `http://${host}:3000`,
    'minio':          `http://${host}:9002`,
    'qdrant':         `http://${host}:6333`,
    'langfuse':       `http://${host}:3003`,
    'prometheus':     `http://${host}:9090`,
    'grafana':        `http://${host}:3004`,
    'authentik':      `http://${host}:9080`,
  };
  return MAP[name] ?? null;
}
```

---

### 2. Mock Service Runtime Data

Create `ui/src/data/servicesMock.js`. Used until `/api/services` is available in Step 10.

```js
// TODO Step 10: replace with live /api/services response
export function buildMockServices(runningServices = []) {
  const MOCK = {
    'vllm-pair-a':   { status: 'running',  port: 8000, gpus: [0,3], image: 'vllm/vllm-openai:v0.9.1',  uptime_seconds: 8040,  cpu_pct: 12.4, mem_gb: 2.1, managed_by_loadout: 'inference-pair-a' },
    'ollama':        { status: 'running',  port: 11434,gpus: [0,3], image: 'ollama/ollama:0.3.6',       uptime_seconds: 8040,  cpu_pct: 2.1,  mem_gb: 0.4, managed_by_loadout: 'inference-pair-a' },
    'vllm-pair-b':   { status: 'stopped',  port: 8001, gpus: [1,2], image: 'vllm/vllm-openai:v0.9.1',  uptime_seconds: 0,     cpu_pct: 0,    mem_gb: 0 },
    'vllm-4gpu':     { status: 'stopped',  port: 8002, gpus: [0,1,2,3], image: 'vllm/vllm-openai:v0.9.1', uptime_seconds: 0, cpu_pct: 0, mem_gb: 0 },
    'llama-cpp':     { status: 'stopped',  port: 8080, gpus: [0],   image: 'ghcr.io/ggerganov/llama.cpp:server', uptime_seconds: 0, cpu_pct: 0, mem_gb: 0 },
    'comfyui':       { status: 'stopped',  port: 8188, gpus: [0,3], image: 'yanwk/comfyui-boot:latest', uptime_seconds: 0, cpu_pct: 0, mem_gb: 0 },
    'a1111':         { status: 'stopped',  port: 7860, gpus: [0,3], image: 'sd-webui/automatic1111:v1.9.4', uptime_seconds: 0, cpu_pct: 0, mem_gb: 0 },
    'axolotl':       { status: 'stopped',  port: null, gpus: [0,3], image: 'winglian/axolotl:main-py3.10-cu121', uptime_seconds: 0, cpu_pct: 0, mem_gb: 0 },
    'kohya':         { status: 'stopped',  port: 7862, gpus: [1,2], image: 'bmaltais/kohya-ss:latest', uptime_seconds: 0, cpu_pct: 0, mem_gb: 0 },
    'n8n':           { status: 'running',  port: 5678, gpus: [],    image: 'n8nio/n8n:1.28.0', uptime_seconds: 172800, cpu_pct: 0.4, mem_gb: 0.3 },
    'open-webui':    { status: 'running',  port: 3000, gpus: [],    image: 'ghcr.io/open-webui/open-webui:main', uptime_seconds: 172800, cpu_pct: 1.2, mem_gb: 0.8 },
    'minio':         { status: 'running',  port: 9002, gpus: [],    image: 'minio/minio:RELEASE.2024-01-28', uptime_seconds: 864000, cpu_pct: 0.1, mem_gb: 0.2 },
    'qdrant':        { status: 'running',  port: 6333, gpus: [],    image: 'qdrant/qdrant:v1.7.4', uptime_seconds: 864000, cpu_pct: 0.2, mem_gb: 1.1 },
    'postgres':      { status: 'running',  port: 5432, gpus: [],    image: 'postgres:16-alpine', uptime_seconds: 864000, cpu_pct: 0.1, mem_gb: 0.3 },
    'langfuse':      { status: 'running',  port: 3003, gpus: [],    image: 'ghcr.io/langfuse/langfuse:2.x', uptime_seconds: 864000, cpu_pct: 0.5, mem_gb: 0.6 },
    'prometheus':    { status: 'running',  port: 9090, gpus: [],    image: 'prom/prometheus:v2.48.0', uptime_seconds: 864000, cpu_pct: 0.3, mem_gb: 0.5 },
    'grafana':       { status: 'running',  port: 3004, gpus: [],    image: 'grafana/grafana:10.2.3', uptime_seconds: 864000, cpu_pct: 0.2, mem_gb: 0.4 },
    'authentik':     { status: 'running',  port: 9080, gpus: [],    image: 'ghcr.io/goauthentik/server:2024.2', uptime_seconds: 864000, cpu_pct: 0.6, mem_gb: 1.2 },
  };
  return MOCK;
}

export const MOCK_LOG_LINES = {
  'vllm-pair-a': [
    '14:28:33 [INFO]  POST /v1/chat/completions 200 · 1.24s',
    '14:27:51 [INFO]  POST /v1/chat/completions 200 · 2.18s',
    '14:26:12 [WARN]  kv cache utilization 94%',
  ],
  'ollama': [
    '14:29:01 [INFO]  llm runner started llama 3.1 8B',
    '14:28:44 [INFO]  request processed in 842ms',
    '14:27:10 [INFO]  model loaded from cache',
  ],
};
```

---

### 3. `ui/src/components/AccordionGroup.jsx`

```jsx
import { useState } from 'react';
import './AccordionGroup.css';

export function AccordionGroup({ title, serviceCount, children }) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="accordion-group">
      <button
        className="accordion-header"
        onClick={() => setExpanded(e => !e)}
        aria-expanded={expanded}
      >
        <span className="accordion-arrow">{expanded ? '▾' : '▸'}</span>
        <span className="accordion-title">{title}</span>
        <span className="accordion-count">{serviceCount}</span>
      </button>
      {expanded && (
        <div className="accordion-body">{children}</div>
      )}
    </div>
  );
}
```

```css
/* AccordionGroup.css */
@import '../tokens.css';

.accordion-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.accordion-header {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 4px;
  padding: 7px 10px;
  cursor: pointer;
  text-align: left;
  font-family: var(--mono);
  font-size: 10px;
  font-weight: 500;
  color: var(--text2);
  letter-spacing: .5px;
  text-transform: uppercase;
}

.accordion-header:hover {
  background: var(--surface2);
}

.accordion-arrow {
  font-size: 9px;
  color: var(--text3);
}

.accordion-title {
  flex: 1;
}

.accordion-count {
  font-size: 9px;
  color: var(--text3);
}

.accordion-body {
  display: flex;
  flex-direction: column;
  gap: 1px;
  padding-left: 0;
}
```

---

### 4. `ui/src/components/ServiceCard.jsx`

One component handles both collapsed and expanded states via internal toggle.

```jsx
import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { DotStatus } from './DotStatus';
import { Tag }       from './Tag';
import { Btn }       from './Btn';
import { Toggle }    from './Toggle';
import { serviceUrl } from '../data/serviceCatalog';
import { MOCK_LOG_LINES } from '../data/servicesMock';
import './ServiceCard.css';

function formatUptime(seconds) {
  if (!seconds || seconds === 0) return '—';
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h === 0) return `${m}m`;
  if (h < 24) return `${h}h ${m}m`;
  return `${Math.floor(h / 24)}d ${h % 24}h`;
}

function dotForStatus(status) {
  if (status === 'running' || status === 'healthy') return 'green';
  if (status === 'starting' || status === 'degraded') return 'amber';
  if (status === 'error') return 'red';
  return 'gray';
}

function statusVariant(status) {
  if (status === 'running') return 'green';
  if (status === 'starting' || status === 'degraded') return 'amber';
  if (status === 'error') return 'red';
  return 'gray';
}

function colorizeLog(line) {
  if (line.includes('[WARN]'))  return <span style={{ color: 'var(--amber)' }}>{line}</span>;
  if (line.includes('[ERROR]')) return <span style={{ color: 'var(--red)' }}>{line}</span>;
  if (line.includes('[INFO]'))  return <span style={{ color: 'var(--text2)' }}>{line}</span>;
  return <span style={{ color: 'var(--text3)' }}>{line}</span>;
}

export const ServiceCard = React.memo(function ServiceCard({
  service,        // static metadata from serviceCatalog
  runtime,        // live data from AppContext.services or mock
  managedBy,      // profile name if this service is loadout-managed, else null
  initialExpanded,
  onToggle,       // (name, targetRunning) => void
}) {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(initialExpanded ?? false);
  const [logs, setLogs]         = useState(null);
  const [localStatus, setLocalStatus] = useState(null); // optimistic state

  const status = localStatus ?? runtime?.status ?? 'stopped';
  const isRunning = status === 'running' || status === 'starting';
  const host = window.location.hostname;
  const url  = serviceUrl(service.name, host);

  async function fetchDetail() {
    // TODO Step 10: replace mock with real API
    try {
      const res = await fetch(`/api/services/${service.name}/logs?n=3`);
      if (!res.ok) throw new Error('not ready');
      const data = await res.json();
      setLogs(data.lines ?? []);
    } catch {
      setLogs(MOCK_LOG_LINES[service.name] ?? ['(no recent log lines)']);
    }
  }

  function handleExpand() {
    const next = !expanded;
    setExpanded(next);
    if (next && logs === null) fetchDetail();
  }

  async function handleToggle(targetOn) {
    if (managedBy) return; // should not reach here; button is disabled

    if (!targetOn) {
      const isGpuService = service.gpus.length > 0;
      if (isGpuService && !window.confirm(`Stop ${service.name}? This will interrupt active requests.`)) {
        return;
      }
    }

    // Optimistic update
    setLocalStatus(targetOn ? 'starting' : 'stopping');

    const endpoint = targetOn
      ? `/api/services/${service.name}/start`
      : `/api/services/${service.name}/stop`;

    try {
      const res = await fetch(endpoint, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      // Real status comes from next /api/services poll (useServices in Shell)
      // Clear optimistic state after a timeout so polling takes over
      setTimeout(() => setLocalStatus(null), 15000);
    } catch (e) {
      console.error(`Toggle failed for ${service.name}:`, e);
      setLocalStatus(null); // revert
    }
  }

  return (
    <div
      className={`service-card ${managedBy ? 'service-card-managed' : ''}`}
      id={`svc-${service.name}`}
    >
      {/* Collapsed row */}
      <div className="service-card-row">
        <DotStatus status={dotForStatus(status)} />

        <span className="service-name">{service.name}</span>

        {service.port && (
          <span className="service-port">:{service.port}</span>
        )}

        {service.gpus.length > 0 && (
          <div className="service-gpu-tags">
            {service.gpus.map(g => (
              <Tag key={g} variant="cyan">GPU{g}</Tag>
            ))}
          </div>
        )}

        <Tag variant={statusVariant(status)}>{status}</Tag>

        {url && (
          <Btn
            variant="gray"
            size="sm"
            onClick={() => window.open(url, '_blank')}
            title={`Open ${service.name} in new tab`}
          >
            Open↗
          </Btn>
        )}

        <div
          title={managedBy ? `Managed by loadout [${managedBy}] — switch profile to change` : undefined}
          className={managedBy ? 'service-toggle-managed' : ''}
        >
          <Toggle
            checked={isRunning}
            disabled={!!managedBy}
            onChange={e => handleToggle(e.target.checked)}
          />
        </div>

        <button
          className="service-expand-btn"
          onClick={handleExpand}
          aria-expanded={expanded}
          aria-label="Toggle detail"
        >
          {expanded ? '▾' : '▸'}
        </button>
      </div>

      {/* Expanded detail */}
      {expanded && (
        <div className="service-card-detail">
          <div className="service-detail-grid">
            <span className="detail-label">Image</span>
            <span className="detail-value">{runtime?.image ?? '—'}</span>

            <span className="detail-label">Uptime</span>
            <span className="detail-value">{formatUptime(runtime?.uptime_seconds)}</span>

            <span className="detail-label">CPU</span>
            <span className="detail-value">{runtime?.cpu_pct != null ? `${runtime.cpu_pct}%` : '—'}</span>

            <span className="detail-label">Memory</span>
            <span className="detail-value">{runtime?.mem_gb != null ? `${runtime.mem_gb} GB` : '—'}</span>
          </div>

          <div className="service-logs">
            <div className="service-logs-header">Recent logs</div>
            {logs === null ? (
              <div className="service-logs-loading">loading…</div>
            ) : (
              logs.map((line, i) => (
                <div key={i} className="service-log-line">{colorizeLog(line)}</div>
              ))
            )}
            <button
              className="service-logs-link"
              onClick={() => navigate(`/monitor?service=${service.name}`)}
            >
              View full logs →
            </button>
          </div>
        </div>
      )}
    </div>
  );
});
```

> **Note:** Add `import React from 'react'` at the top of `ServiceCard.jsx` so `React.memo` resolves.

---

### 5. `ServiceCard.css`

```css
@import '../tokens.css';

.service-card {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}

.service-card:last-child {
  border-bottom: none;
}

.service-card-managed {
  background: rgba(0,217,255,.03);
}

.service-card-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 10px;
  min-height: 36px;
}

.service-name {
  flex: 1;
  font-size: 11px;
  font-weight: 500;
  color: var(--text);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.service-port {
  font-size: 9px;
  color: var(--text3);
  background: var(--surface3);
  border-radius: 3px;
  padding: 1px 6px;
  flex-shrink: 0;
}

.service-gpu-tags {
  display: flex;
  gap: 2px;
  flex-shrink: 0;
}

.service-toggle-managed {
  opacity: 0.5;
  cursor: not-allowed;
}

.service-expand-btn {
  background: none;
  border: none;
  color: var(--text3);
  cursor: pointer;
  font-size: 10px;
  font-family: var(--mono);
  padding: 2px 4px;
  flex-shrink: 0;
}

.service-expand-btn:hover {
  color: var(--text2);
}

/* Expanded detail */
.service-card-detail {
  padding: 0 10px 10px 10px;
  border-top: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 0;
}

.service-detail-grid {
  display: grid;
  grid-template-columns: 56px 1fr;
  gap: 3px 8px;
  margin-top: 8px;
}

.detail-label {
  font-size: 9px;
  color: var(--text3);
  align-self: center;
}

.detail-value {
  font-size: 10px;
  color: var(--text2);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.service-logs {
  background: #070b1c;
  border-radius: 3px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.service-logs-header {
  font-size: 9px;
  color: var(--text3);
  margin-bottom: 4px;
  letter-spacing: .3px;
}

.service-log-line {
  font-size: 10px;
  font-family: var(--mono);
  line-height: 1.5;
  white-space: pre;
  overflow: hidden;
  text-overflow: ellipsis;
}

.service-logs-loading {
  font-size: 9px;
  color: var(--text3);
}

.service-logs-link {
  background: none;
  border: none;
  font-family: var(--mono);
  font-size: 9px;
  color: var(--cyan);
  cursor: pointer;
  text-align: left;
  padding: 0;
  margin-top: 4px;
}

.service-logs-link:hover {
  text-decoration: underline;
}
```

---

### 6. `ui/src/pages/Tools.jsx`

```jsx
import { useEffect, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { AccordionGroup } from '../components/AccordionGroup';
import { ServiceCard }    from '../components/ServiceCard';
import { SERVICE_CATALOG, GROUP_ORDER } from '../data/serviceCatalog';
import { buildMockServices } from '../data/servicesMock';
import './Tools.css';

export function Tools() {
  const { state } = useApp();
  const location  = useLocation();

  // Merge live service data with catalog (fall back to mock)
  const services = useMemo(() => {
    const live = Object.keys(state.services).length > 0 ? state.services : buildMockServices();
    return live;
  }, [state.services]);

  // Determine which services are loadout-managed
  const [loadoutServices, setLoadoutServices] = React.useState(new Set());
  useEffect(() => {
    fetch('/loadouts')
      .then(r => r.json())
      .then(data => {
        const list = Array.isArray(data) ? data : (data.profiles ?? []);
        const active = list.find(p => p.name === state.activeProfile);
        setLoadoutServices(new Set(active?.services ?? []));
      })
      .catch(() => {});
  }, [state.activeProfile]);

  // Focus behavior: scroll to ?focus={name} and auto-expand
  useEffect(() => {
    const focus = new URLSearchParams(location.search).get('focus');
    if (!focus) return;
    setTimeout(() => {
      const el = document.getElementById(`svc-${focus}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.style.outline = '2px solid var(--cyan)';
        setTimeout(() => { el.style.outline = ''; }, 2000);
      }
    }, 100);
  }, [location.search]);

  // Build groups
  const groups = useMemo(() => {
    return GROUP_ORDER.map(groupName => ({
      name: groupName,
      services: SERVICE_CATALOG.filter(s => s.group === groupName),
    }));
  }, []);

  const focusedService = new URLSearchParams(location.search).get('focus');

  return (
    <div className="tools-page">
      <div className="tools-header">
        Service Catalog
        <span className="tools-header-sub">
          {GROUP_ORDER.length} groups · {SERVICE_CATALOG.length} services
        </span>
      </div>

      <div className="tools-groups">
        {groups.map(group => (
          <AccordionGroup
            key={group.name}
            title={group.name}
            serviceCount={group.services.length}
          >
            <div className="service-group-cards">
              {group.services.map(svc => (
                <ServiceCard
                  key={svc.name}
                  service={svc}
                  runtime={services[svc.name]}
                  managedBy={
                    loadoutServices.has(svc.name) && state.runningServices.includes(svc.name)
                      ? state.activeProfile
                      : null
                  }
                  initialExpanded={svc.name === focusedService}
                />
              ))}
            </div>
          </AccordionGroup>
        ))}
      </div>
    </div>
  );
}
```

> Add `import React from 'react'` at the top of Tools.jsx to support the `React.useState` call inside Tools.
> Alternatively, import `useState` from 'react' directly and replace `React.useState` with `useState`.

---

### 7. `ui/src/pages/Tools.css`

```css
@import '../tokens.css';

.tools-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tools-header {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  display: flex;
  align-items: center;
  gap: 10px;
}

.tools-header-sub {
  font-size: 10px;
  font-weight: 400;
  color: var(--text3);
}

.tools-groups {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.service-group-cards {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  margin-top: 2px;
}
```

---

## Acceptance Criteria

- [ ] All 9 accordion groups render with correct service counts
- [ ] Accordion header collapses/expands the service list on click
- [ ] Each service row shows: status dot, name, port badge, GPU tags (only for GPU services), status tag, Open↗ button (only if URL exists), toggle, expand chevron
- [ ] Loadout-managed services have a `--cyan-dim` row background, disabled toggle, and tooltip on hover
- [ ] Toggle ON: changes status tag to amber "starting" immediately (optimistic)
- [ ] Toggle OFF on GPU service: shows `window.confirm` before proceeding
- [ ] Expanding a card fetches (or mock-loads) log lines; "View full logs →" navigates to `/#/monitor?service={name}`
- [ ] `?focus=vllm-pair-a` scrolls to the vllm-pair-a card, highlights it with cyan outline for 2s, auto-expands it
- [ ] `npm run dev` shows no console errors on `/tools` with the mock data
- [ ] `ServiceCard` is wrapped in `React.memo`; opening DevTools Profiler should show it does not re-render when unrelated services update

---

## Feedback

Write `plan/UI/GHC-Feedback/04-feedback.md` when done.

**Required in Notes:**
- Any service names in the catalog where the Toggle start/stop API returned unexpected errors in testing (i.e., the endpoint existed but behaved differently than expected). Note exact HTTP responses.
- Confirm whether `window.location.hostname` gives the correct host when accessed over LAN. If not, describe the fix applied.
