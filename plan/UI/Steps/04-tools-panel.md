# KOVATI OS — Component Spec 04
## Tools Panel
*Service catalog · accordion groups · per-service card with controls*

---

## 1. Purpose

The Tools panel is the operator's complete inventory of every container in the stack. It provides:

- Status visibility for all 30+ services
- Start/stop control for individual services (within loadout constraints)
- Quick-launch to each service's native UI
- Expandable detail view (image, uptime, resource usage, log tail)
- Loadout dependency warnings (prevents accidental disruption)

---

## 2. Layout

```
┌─────────────────────────────────────────────────────────┐
│ PANEL HEADER: "Service Catalog" · "9 groups · 30 svcs" │
├─────────────────────────────────────────────────────────┤
│ [▸ Text Inference]    ← accordion header (clickable)    │
│   vllm-pair-a  ●running  :8000  [GPU0+3]  [Open↗][▲]  │
│   ollama       ●running  :11434 [GPU0]    [Open↗][▲]  │
│   vllm-pair-b  ○stopped  :8001  [GPU1+2]  [Open↗][▲]  │
│   vllm-4gpu    ○stopped  :8002  [GPU0-3]  [Open↗][▲]  │
│                                                         │
│ [▸ Image Studio]                                        │
│   comfyui      ⚠degraded :8188  [GPU0]    [Open↗][▲]  │
│   ...                                                   │
└─────────────────────────────────────────────────────────┘
```

URL parameter: `/#/tools?focus={service_name}` scrolls and highlights the named service card on mount (used by Dashboard service grid clicks).

---

## 3. Accordion Groups

Nine groups, all expanded by default. Clicking a group header collapses/expands.

| # | Group Name | Services |
|---|-----------|---------|
| 1 | Text Inference | Ollama, vLLM Pair A, vLLM Pair B, vLLM 4-GPU |
| 2 | Image Studio | ComfyUI, InvokeAI, Real-ESRGAN, Rembg |
| 3 | Training | Kohya_ss, Axolotl, Unsloth, Label Studio, JupyterLab |
| 4 | Agentic & Workflow | n8n, Dify, OpenHands, MCP Filesystem, MCP Browser, MCP Code-Exec, MCP Fetch |
| 5 | Voice I/O | Faster-Whisper STT, Piper TTS |
| 6 | Chat UI | Open WebUI, SearXNG |
| 7 | Storage & Vector | MinIO, Qdrant, PostgreSQL, Langfuse |
| 8 | Observability | Prometheus, Grafana, DCGM Exporter, Node Exporter, cAdvisor |
| 9 | Auth & Security | Authentik |

**Accordion header:**
- 10px, `--text2`, font-weight 500, all-caps, letter-spacing .5px
- Arrow glyph: `▸` collapsed, `▾` expanded
- Background `--surface`, border `1px solid --border`, border-radius 4px
- Hover: background `--surface2`

---

## 4. Service Card (Collapsed)

One row per service. `display: flex; align-items: center; gap: 10px;`

```
[dot] [name        ] [port ] [gpuTags] [loadout?] [Open↗] [toggle] [▸]
```

| Element | Details |
|---------|---------|
| Status dot | `DotStatus` component — green/amber/red/gray |
| Service name | 11px, font-weight 500, `--text`, flex:1, min-width 0, truncate |
| Port badge | `:8000` — 9px, `--text3`, background `--surface3`, padding 1px 6px |
| GPU tags | `Tag variant="cyan"` per GPU, e.g. `GPU0`, `GPU3` — only for GPU-consuming services |
| Status tag | `Tag` — green "running", amber "starting/degraded", red "error/stopped", gray "disabled" |
| Open button | `Btn variant="gray" size="sm"` → `window.open(serviceUrl, '_blank')` |
| Toggle | `Toggle` component — start/stop container |
| Expand chevron | `▸` / `▾` — toggles detail view |

**Service URLs** (hardcoded map, not from API):
```js
const SERVICE_URLS = {
  'vllm-pair-a':  'http://{host}:8000',
  'ollama':       'http://{host}:11434',
  'comfyui':      'http://{host}:8188',
  'invokeai':     'http://{host}:9090',
  'n8n':          'http://{host}:5678',
  'grafana':      'http://{host}:3001',
  'open-webui':   'http://{host}:3000',
  'jupyterlab':   'http://{host}:8888',
  'langfuse':     'http://{host}:3002',
  'prometheus':   'http://{host}:9091',
  'minio-console':'http://{host}:9001',
  'authentik':    'http://{host}:9080',
  // ... etc
};
// {host} resolved from window.location.hostname at runtime
```

---

## 5. Loadout Dependency Warning

When a service is part of the currently active loadout profile, its toggle is **disabled** and shows a tooltip:

```
Managed by loadout [inference-pair-a]
Switch profile to change
```

The toggle renders with `disabled` attribute and `cursor: not-allowed`. The row background gets a subtle `--cyan-dim` tint to indicate it's under profile control.

Determination: A service is "managed" if its name appears in `runningServices` from `/status` AND is listed in the active profile's `services` array from `/loadouts`.

---

## 6. Service Card (Expanded)

Clicking the `▸` chevron expands an additional detail section below the main row, within the same card.

```
┌──────────────────────────────────────────────────────────┐
│ [● vllm-pair-a  :8000  GPU0+3  running  [Open↗] [▲] ■  │
├──────────────────────────────────────────────────────────┤
│  Image:   vllm/vllm-openai:v0.9.1                       │
│  Uptime:  2h 14m                                         │
│  CPU:     12.4%    Memory: 2.1 GB                        │
│                                                          │
│  Recent logs:                                            │
│  14:28:33 [INFO]  POST /v1/chat/completions 200 · 1.24s  │
│  14:27:51 [INFO]  POST /v1/chat/completions 200 · 2.18s  │
│  14:26:12 [WARN]  kv cache util 94%                      │
└──────────────────────────────────────────────────────────┘
```

**Expanded fields:**
- **Image**: full Docker image tag from `GET /api/services/{name}`
- **Uptime**: formatted duration since container start
- **CPU %**: from cAdvisor via Prometheus
- **Memory**: container memory usage in GB
- **Log tail**: last 3 lines from `GET /api/services/{name}/logs?n=3`

**Log display:**
- `font-family: --mono`, 10px
- Timestamp: `--text3`
- `[INFO]`: `--cyan`
- `[WARN]`: `--amber`
- `[ERROR]`: `--red`
- Background: `#070b1c` (darker than `--bg`)
- Max 3 lines. "View full logs →" link navigates to Monitor panel, pre-selecting this service.

---

## 7. Toggle Behavior

**When toggling ON** (starting a stopped service):
1. Optimistic UI: toggle moves to ON, status tag changes to amber "starting"
2. `POST /api/services/{name}/start`
3. Poll `GET /api/services` — when service appears as running, update to green
4. If start fails: revert toggle, show inline error below the card

**When toggling OFF** (stopping a running service):
1. Show confirmation if service has active connections or is GPU-consuming:
   - `"Stop {name}? This will interrupt active requests."`
2. `POST /api/services/{name}/stop`
3. Optimistic: toggle moves to OFF, status tag → gray "stopping"
4. Poll for confirmation

**When managed by loadout** (toggle disabled):
- No action on click
- Tooltip explains why
- Cursor: `not-allowed`

---

## 8. Focus Behavior (from Dashboard)

When navigating from Dashboard tile click (`/#/tools?focus=comfyui`):

```js
useEffect(() => {
  const focus = new URLSearchParams(location.search).get('focus');
  if (focus) {
    // Small delay for render
    setTimeout(() => {
      const el = document.getElementById(`svc-${focus}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.style.outline = `2px solid var(--cyan)`;
        setTimeout(() => el.style.outline = '', 2000);
      }
    }, 100);
  }
}, []);
```

The focused service card also auto-expands its detail section.

---

## 9. Service Data Schema

```json
{
  "services": {
    "vllm-pair-a": {
      "status": "running",
      "port": 8000,
      "gpus": [0, 3],
      "image": "vllm/vllm-openai:v0.9.1",
      "uptime_seconds": 8040,
      "cpu_pct": 12.4,
      "mem_gb": 2.1,
      "managed_by_loadout": "inference-pair-a",
      "compose_file": "compose.inference.yml"
    }
  }
}
```

---

## 10. API Dependencies

| Data | Endpoint | Frequency |
|------|----------|-----------|
| Service statuses | `GET /api/services` | 10s |
| Service detail | `GET /api/services/{name}` | On expand |
| Log tail | `GET /api/services/{name}/logs?n=3` | On expand |
| Start | `POST /api/services/{name}/start` | On toggle |
| Stop | `POST /api/services/{name}/stop` | On toggle |

---

## 11. Performance

- All accordion groups render lazily — detail rows for collapsed groups are not in the DOM
- Service cards use `React.memo` to prevent re-renders when their individual service data has not changed
- Log tail is fetched on expand, not on load — do not batch-fetch all 30 service log tails on mount
