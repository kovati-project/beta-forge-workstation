# KOVATI OS — Component Spec 08
## Monitor Panel
*GPU telemetry · system metrics · LLM traces · log viewer · alerts*

---

## 1. Purpose

The Monitor panel is the operator's observability hub. It aggregates data from four separate sources (pynvml, Prometheus, Langfuse, Docker) into a unified interface. The alert badge on the sidebar nav item is driven by live Prometheus alerts — the Monitor panel is where the operator goes to diagnose and resolve them.

---

## 2. Layout

```
┌─────────────────────────────────────────────────────────┐
│ [Active Alerts banner — shown if alertCount > 0]        │
├─────────────────────────────────────────────────────────┤
│ GPU TELEMETRY                                           │
│ 4-panel VRAM charts + utilization/temp gauges           │
├─────────────────────────────────────────────────────────┤
│ SYSTEM METRICS                                          │
│ CPU heatmap · RAM · Disk I/O · Network                  │
├─────────────────────────────────────────────────────────┤
│ LLM TRACES                  │ CONTAINER HEALTH          │
│ (Langfuse)                  │ (cAdvisor/Prometheus)     │
├─────────────────────────────────────────────────────────┤
│ LOG VIEWER                                              │
│ Container selector · filter · log stream               │
├─────────────────────────────────────────────────────────┤
│ ALERT HISTORY                                           │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Active Alerts Banner

Shown when `alertCount > 0`. Positioned above all other content, full-width.

```
┌─────────────────────────────────────────────────────────┐
│ ⚠  2 active alerts                                      │
│    GPU0 temp 74°C (warn threshold 70°C)                 │
│    ComfyUI container restarted 3× in 1h                 │
│                                                         │
│    [View Alert History ↓]                               │
└─────────────────────────────────────────────────────────┘
```

Background: `rgba(255,179,71,0.08)`, border: `rgba(255,179,71,0.3)`, text: `--amber`.

One line per active alert, truncated to 80 chars. "View Alert History" scrolls to the alert history section.

---

## 4. GPU Telemetry

Source: `GET /api/metrics/gpu` — returns 30 minutes of history at 3s resolution.

### Chart Layout

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ GPU 0 VRAM      │  │ GPU 3 VRAM      │  │ GPU 1 VRAM      │  │ GPU 2 VRAM      │
│ (cyan active)   │  │ (cyan active)   │  │ (green idle)    │  │ (green idle)    │
│  sparkline      │  │  sparkline      │  │  sparkline      │  │  sparkline      │
└─────────────────┘  └─────────────────┘  └─────────────────┘  └─────────────────┘
```

GPU pairs ordered: active pair first (GPU 0+3 if inference-pair-a), then idle pair. This keeps the interesting data prominent.

### Chart Implementation

Rendered on `<canvas>` elements (no library). Per chart:

- **X-axis:** 0 → 30 minutes, no labels (time is implicit)
- **Y-axis:** 0 → 24 GB (fixed, not autoscaled — allows comparison between GPUs)
- **Line:** 1.5px stroke, color matches GPU state (cyan/green/amber)
- **Fill:** Gradient from stroke color at 20% opacity to transparent (below the line)
- **Last value label:** Displayed as text in top-right of chart area: `21.4 GB`
- **Chart size:** 100% width of container, `80px` height

```js
// Chart render function
function renderGpuChart(canvas, data, color, maxGb = 24) {
  const ctx = canvas.getContext('2d');
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const pts = data.map((v, i) => [
    (i / (data.length - 1)) * w,
    h - (v / maxGb) * h
  ]);

  // Fill
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, color.replace(')', ', 0.2)').replace('rgb', 'rgba'));
  grad.addColorStop(1, 'transparent');
  ctx.beginPath();
  ctx.moveTo(pts[0][0], h);
  pts.forEach(([x, y]) => ctx.lineTo(x, y));
  ctx.lineTo(pts[pts.length-1][0], h);
  ctx.fillStyle = grad;
  ctx.fill();

  // Line
  ctx.beginPath();
  pts.forEach(([x, y], i) => i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y));
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.stroke();
}
```

Charts update every 3s when new `/status` data arrives (append new point, drop oldest).

### GPU Gauges (below charts)

Six horizontal gauge bars, two rows × three:

| Gauge | Source | Color |
|-------|--------|-------|
| GPU0 Utilization | `/status` | cyan |
| GPU3 Utilization | `/status` | cyan |
| GPU0 Temperature | `/status` | amber if >60°C, red if >75°C |
| GPU3 Temperature | `/status` | amber/red |
| CPU Load | Prometheus | red if >90%, amber if >70% |
| RAM Used | Prometheus | green |

Each gauge: label (10px `--text3`) + 4px track + fill + numeric value (9px, colored).

---

## 5. System Metrics

Source: `GET /api/metrics/system` (Prometheus HTTP API, 10s refresh).

### CPU Heatmap

32 cores × 2 threads = 64 per-CPU-thread utilization values from Prometheus `node_cpu_seconds_total`.

Displayed as a 64-cell grid (8 cols × 8 rows), each cell colored by utilization:

| Utilization | Color |
|-------------|-------|
| 0–20% | `--surface3` |
| 20–50% | `rgba(0,217,255,0.2)` |
| 50–80% | `--amber` at 60% opacity |
| 80–100% | `--red` |

Tooltip on hover: `CPU {n}: {pct}%`

### System Metric Bars

```
RAM       [████████████████████████░░░░░] 468 / 512 GB  91%
Disk I/O  [██░░░░░░░░░░░░░░░░░░░░░░░░░░] 420 MB/s read  48 MB/s write
Network   [████░░░░░░░░░░░░░░░░░░░░░░░░] 2.4 Gbps rx   180 Mbps tx
```

All use `VBar` component. Disk I/O and network show both read/write or rx/tx as two sub-bars.

Prometheus queries:
- RAM: `node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes`
- Disk I/O: `rate(node_disk_read_bytes_total{device="sda"}[1m])` and write equivalent
- Network: `rate(node_network_receive_bytes_total{device="eth0"}[1m])` and transmit

---

## 6. LLM Traces

Source: `GET /api/traces` (Langfuse API proxied, paginated).

```
┌──────────────────────────────────────────────────────────────────┐
│ LLM Traces                   Langfuse :3002       [Filter ▾]    │
│                                                                  │
│ Time     │ Model         │ P.tok │ C.tok │ Latency │ Score       │
├──────────────────────────────────────────────────────────────────┤
│ 14:28:04 │ qwen2.5-32b   │ 1,842 │   512 │  1.24s  │ —          │
│ 14:27:51 │ qwen2.5-32b   │ 3,210 │ 1,024 │  2.18s  │ —          │
│ 14:27:20 │ qwen2.5-7b    │   892 │   256 │  0.41s  │ —          │
│ 14:26:44 │ qwen2.5-32b   │12,048 │ 2,048 │  4.92s ⚠│ —          │
└──────────────────────────────────────────────────────────────────┘
│ [Load More]                                 Showing 4 of 248    │
└──────────────────────────────────────────────────────────────────┘
```

**Latency coloring:** green <2s, amber 2–5s, red >5s. ⚠ glyph added for red rows.

**Row click → expand:**
```
┌──────────────────────────────────────────────────────────────────┐
│ ▾ 14:26:44 · qwen2.5-32b · 4.92s                                │
│                                                                  │
│ Prompt (redacted):   [Reveal]                                   │
│ ██████████████████ (1st 20 chars shown, rest blocked)           │
│                                                                  │
│ Completion (redacted): [Reveal]                                 │
│ ██████████████████                                              │
│                                                                  │
│ Metadata: session_id=abc123 · tags=n8n-workflow                 │
└──────────────────────────────────────────────────────────────────┘
```

Prompt/completion redacted by default (privacy-sensitive). "Reveal" button shows full content. "Redact" button re-hides.

**Filter panel (dropdown):**
- Model: select from list of models seen in traces
- Date range: start/end date pickers
- Latency threshold: slider (only show traces above N seconds)
- Tag: text input

Filters sent as query params to `GET /api/traces?model=&date_from=&latency_min=`.

---

## 7. Container Health

Source: cAdvisor via Prometheus, `GET /api/metrics/containers`.

```
┌─────────────────────────────────────────────────────┐
│ Container Health                                    │
│                                                     │
│ Service       │ Restarts │ Mem (MB) │ CPU% │ OOM    │
│ vllm-pair-a   │ 0        │ 2,100    │ 12   │ no     │
│ comfyui       │ 3        │ 1,840    │  8   │ yes ⚠  │
│ n8n           │ 0        │  420     │  2   │ no     │
└─────────────────────────────────────────────────────┘
```

**Restart count ≥3:** Row background `--red-dim`, amber warning. "OOM yes" row: `--red` text.

---

## 8. Log Viewer

Full interactive log tail for any running container.

```
┌──────────────────────────────────────────────────────────────┐
│ LOG VIEWER                                                   │
│ [vllm-pair-a ▾]  [filter / grep: ____________] [ALL ▾]      │
│                                                              │
│ ┌ ─────────────────────────────────────────────────────── ┐ │
│   14:28:33 [INFO]  POST /v1/chat/completions 200 · 1.24s   │ │
│   14:27:51 [INFO]  POST /v1/chat/completions 200 · 2.18s   │ │
│   14:26:12 [WARN]  kv cache util 94%                        │ │
│   14:24:00 [INFO]  loaded Qwen2.5-32B-Instruct             │ │
│ └ ─────────────────────────────────────────────────────── ┘ │
│                                                              │
│ [▲ Scroll Lock]  Showing last 200 lines  [↓ Jump to Bottom] │
└──────────────────────────────────────────────────────────────┘
```

**Service selector:** Dropdown of all running containers from `GET /api/services`. Changing selection closes existing SSE and opens new one.

**Log level filter:** ALL / INFO / WARN / ERROR. Applied client-side (filter rendered lines by detected level prefix `[INFO]`, `[WARN]`, `[ERROR]`).

**Grep filter:** Client-side text filter. Applied in real-time on `oninput`. Matching text highlighted in `--cyan`.

**Scroll lock:** Auto-scroll to bottom when new lines arrive, unless user has scrolled up. "Scroll Lock" button at top-right toggles auto-scroll. Clicking "↓ Jump to Bottom" re-enables auto-scroll.

**Log line display:**
- `10px`, `--mono`, `line-height: 1.8`
- Timestamp: `--text3`
- `[INFO]`: `--cyan`
- `[WARN]`: `--amber`
- `[ERROR]`: `--red`
- Message: `--text`
- Background: `#070b1c`

**Initial load:** `GET /api/services/{name}/logs?n=200` on mount.  
**Streaming:** `EventSource /api/services/{name}/logs/stream` appends new lines.

---

## 9. Alert History

Source: Prometheus alertmanager API (proxied) or `GET /api/alerts/history`.

```
┌──────────────────────────────────────────────────────────────────┐
│ Alert History — Last 7 days                                      │
│                                                                  │
│ Name                │ Severity │ Fired            │ Duration     │
├──────────────────────────────────────────────────────────────────┤
│ GPU0TempHigh        │ ⚠ warn   │ 2026-06-05 14:22 │ ongoing      │
│ ComfyUIRestartLoop  │ ⚠ warn   │ 2026-06-05 08:12 │ ongoing      │
│ DiskUsageHigh       │ ⚠ warn   │ 2026-06-03 11:00 │ 2h 14m       │
│ GPU3TempCritical    │ ✖ crit   │ 2026-06-01 16:45 │ 8m           │
└──────────────────────────────────────────────────────────────────┘
```

**Severity tags:** `Tag variant="amber"` for warn, `Tag variant="red"` for critical.

**Ongoing duration:** "ongoing" in `--red` text for still-firing alerts.

---

## 10. API Dependencies

| Data | Endpoint | Frequency |
|------|----------|-----------|
| GPU history | `GET /api/metrics/gpu` | On mount + 3s append |
| System metrics | `GET /api/metrics/system` | 10s |
| Container health | `GET /api/metrics/containers` | 10s |
| LLM traces | `GET /api/traces` | On mount + Load More |
| Log initial | `GET /api/services/{name}/logs?n=200` | On service select |
| Log stream | SSE `/api/services/{name}/logs/stream` | Continuous |
| Active alerts | `GET /api/alerts` | 30s (shared with sidebar badge) |
| Alert history | `GET /api/alerts/history` | On mount |
