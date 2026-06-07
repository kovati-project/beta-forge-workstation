# KOVATI OS — Component Spec 02
## Dashboard
*Landing view · real-time system state at a glance*

---

## 1. Purpose

The Dashboard is the default landing view (`/#/dashboard`). An operator opening the UI should immediately understand:

1. The health and load of all four GPUs
2. Which loadout profile is active and for how long
3. The health status of every service in the stack
4. What has happened recently (profile switches, training completions, backup runs)
5. Key system metrics (CPU, RAM, total VRAM in use, storage)

No action is required from the Dashboard — it is read-only except for the "Switch Profile" shortcut button.

---

## 2. Layout

```
┌─────────────────────────────────────────────────────────────┐
│ GPU STATUS ROW (4 cards, equal width, flex)                 │
├─────────────────────────────────────────────────────────────┤
│ ACTIVE LOADOUT BANNER (flex:2) │ SYSTEM METRICS (flex:1)   │
├─────────────────────────────────────────────────────────────┤
│ SERVICE HEALTH GRID (flex:3)   │ ACTIVITY FEED (flex:1)    │
└─────────────────────────────────────────────────────────────┘
```

All rows use `display: flex; gap: 12px; flex-wrap: wrap`.

---

## 3. GPU Status Row

Four equal-width cards, one per GPU. Source: `GET /status` every 3s.

### GPU Card Structure

```
┌──────────────────────────────┐
│ [BRIDGE A badge]  top-right  │
│ GPU 0 · bus 0x21     label   │
│ RTX A5500            name    │
│                              │
│ VRAM  ████████░░  21.4/24 GB │
│ Util  █████████░  92%        │
│ Temp              74°C       │
│ Power             198 W      │
│                              │
│ [vllm-pair-a]     tag        │
└──────────────────────────────┘
```

**Fields:**
- **NVLink badge** (top-right): `BRIDGE A` or `BRIDGE B` — from `nvlink_bridge` field in `/status` response. 8px, letter-spacing .5px, border `--border2`
- **GPU label**: `GPU {index} · bus {bus_id}` — 10px, `--text3`
- **GPU name**: `RTX A5500` — 11px, font-weight 500, `--text`
- **VRAM bar**: `VBar` component, pct = `vram_used_gb / vram_total_gb * 100`. Label: `{used} / {total} GB` right-aligned
- **Utilization bar**: `VBar` component, pct = `utilization_pct`
- **Temperature**: No bar. Color: green <60°C, amber 60–75°C, red >75°C
- **Power draw**: Watts. Color: always `--text` (no threshold coloring)
- **Active service tag**: `Tag` component. Color: cyan if inference, amber if training, purple if image. Gray/"idle" if `vram_used_gb < 1.0`

**Card border state:**
- Default: `border: 1px solid --border`
- GPU claimed by active loadout: `border: 1px solid --cyan`
- GPU temp >75°C: `border: 1px solid --amber` (overrides cyan)
- GPU temp >85°C: `border: 1px solid --red`

**VBar variant rules:**
- VRAM bar: cyan if claimed by active profile, green if idle (<5% used), amber if temp >75°C
- Util bar: cyan if >20%, green if ≤20%

---

## 4. Active Loadout Banner

Source: `activeProfile`, `switching`, `lastSwitched`, `runningServices` from AppContext.

```
┌────────────────────────────────────────────────────────┐
│ ACTIVE LOADOUT                                         │
│                                                        │
│  inference-pair-a          [NVLink A · GPU 0+3]       │
│  Tensor-parallel 32B–40B · 48 GB · switched 2h 14m ago│
│                                                        │
│  [vllm-pair-a] [ollama]   ← running service tags      │
│                                                        │
│  [Switch Profile →]  [Stop All]                       │
└────────────────────────────────────────────────────────┘
```

**Profile name**: 20px, font-weight 600, `--cyan`

**Sub-line** format: `{description} · {vram} GB claimed · switched {time} ago`
- Time formatting: `{N}m ago` if <60min, `{N}h {M}m ago` if <24h, `{N}d ago` if ≥24h

**Switching state**: When `switching: true`, replace content with:
```
┌────────────────────────────────────────────────────────┐
│ ⟳  SWITCHING PROFILE                                   │
│ stopping services → draining VRAM → starting services  │
│ [████████░░░░░░░░░░░░] animated progress bar           │
└────────────────────────────────────────────────────────┘
```
Background pulses with `animation: borderPulse 1s ease-in-out infinite` on the panel border.

**Running service tags**: One `Tag variant="cyan"` per service in `runningServices` array.

**Buttons:**
- "Switch Profile →" (`Btn variant="cyan"`) → navigates to `/#/loadout`
- "Stop All" (`Btn variant="red"`) → calls `POST /stop`, shows confirmation dialog first

---

## 5. System Metrics Panel

Source: `GET /api/metrics/system` (Prometheus, 10s poll).

Four metric cards in a 2×2 grid:

| Metric | Value | Color |
|--------|-------|-------|
| CPU Load | % across all cores | red if >90%, amber if >70%, cyan otherwise |
| RAM | Used GB (e.g. "468 GB") | green if <80% used |
| VRAM Used | Total GB across all GPUs | cyan |
| Data Storage | TB used | amber if >80% |

Each card:
```
┌──────────────┐
│     94%      │  ← big-num: 28px, font-weight 600
│   CPU Load   │  ← big-label: 10px, --text3
└──────────────┘
```

---

## 6. Service Health Grid

Source: `services` from AppContext (`GET /api/services` every 10s).

A CSS grid of small service tiles: `grid-template-columns: repeat(auto-fill, minmax(100px, 1fr))`.

25+ tiles, one per service in the catalog. Each tile:

```
● vllm-pair-a   ← dot + name (10px bold)
  :8000         ← port (9px --text3)
```

**Dot colors:** green = running/healthy, amber = degraded/starting, red = stopped/error, gray = disabled

**Clicking a tile** navigates to `/#/tools` and scrolls to that service's card. Implement via URL state: `/#/tools?focus=vllm-pair-a`.

**Hover:** background `--surface3`, border `--border2`

**Tile order:** Grouped by category (inference first, then image, training, agentic, etc.) — same order as the Tools panel accordion.

---

## 7. Activity Feed

Source: `GET /api/activity` — last 10 events, newest first. Polled every 30s.

```
┌──────────────────────────────────────────┐
│ ACTIVITY                                 │
│                                          │
│ 14:22  [SWITCH]  → inference-pair-a     │
│ 11:08  [BACKUP]  Completed · 42 GB       │
│ 09:34  [TRAIN]   img-lora done (1000 st) │
│ 08:12  [RESTART] comfyui OOM recovery    │
│ Yest   [TRAIN]   Qwen2.5-7B epoch 3/3   │
│ Yest   [SWITCH]  → training-lora-text   │
│ 2d     [UPDATE]  vllm → 0.9.1           │
└──────────────────────────────────────────┘
```

**Timestamp format:**
- <1h ago: `HH:MM`
- 1–24h ago: `HH:MM` (same day)
- Yesterday: `Yest`
- Older: `{N}d`

**Event type tags:** `Tag` component, 9px
- SWITCH → `tag-cyan`
- BACKUP → `tag-green`
- TRAIN → `tag-amber`
- UPDATE → `tag-green`
- RESTART → `tag-gray`
- ERROR → `tag-red`

**Backend event schema:**
```json
{
  "events": [
    {
      "ts": 1748010121.0,
      "type": "SWITCH",
      "detail": "→ inference-pair-a"
    }
  ]
}
```

---

## 8. API Dependencies

| Data | Source | Poll Interval |
|------|--------|---------------|
| GPU cards | `GET /status` | 3s (1s during switch) |
| Active loadout banner | `GET /status` | 3s |
| System metrics | `GET /api/metrics/system` | 10s |
| Service health grid | `GET /api/services` | 10s |
| Activity feed | `GET /api/activity` | 30s |

---

## 9. Empty / Error States

**No profile active:** Loadout banner shows "No active profile — select a loadout to begin" with a large "Go to Loadout" button.

**API unreachable:** All data panels show a `--red` bordered inline error: `⚠ API unreachable — retrying…`. Do not crash the page.

**GPU data missing:** Show skeleton bars (CSS animated gray bars) until first successful `/status` poll.

---

## 10. Performance Notes

- Dashboard is the most polling-intensive page. All intervals must be cleared on component unmount to avoid ghost polling from React strict mode double-render.
- Service tiles are rendered from `Object.entries(services)` — memoize with `useMemo` keyed on service count + health fingerprint to avoid 25-tile re-renders on every 10s poll.
- GPU cards should use `React.memo` — they re-render on every 3s poll.
