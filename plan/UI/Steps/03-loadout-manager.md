# KOVATI OS — Component Spec 03
## Loadout Manager
*Profile switcher · NVLink topology diagram · switching state machine*

---

## 1. Purpose

The Loadout panel is the most critical operator action surface. It is the only place where GPU resource allocation is changed. Everything else in the UI is read-only or manages individual services within a fixed allocation. The loadout panel controls which services run and which GPUs they own.

Design principle: **make the current state legible before making actions available**. The operator should understand what is happening before they commit to a change.

---

## 2. Layout

```
┌─────────────────────────────────────────────────────────┐
│ NVLink TOPOLOGY DIAGRAM (full width)                    │
│  [GPU 0]━━Bridge A━━[GPU 3]   [GPU 1]━━Bridge B━━[GPU 2]│
│  VRAM bars live inside each GPU box                     │
├─────────────────────────────────────────────────────────┤
│ SWITCHING BANNER (shown only during profile switch)     │
├─────────────────────────────────────────────────────────┤
│ PROFILE CARDS GRID (2-column, wraps to 3 on wide)      │
│  8 cards total                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 3. NVLink Topology Diagram

Rendered as an inline SVG (not a canvas). The diagram is a live display of GPU state, not decorative.

### Layout

```
  [GPU 0]━━━━━━━━━ Bridge A (56.25 GB/s) ━━━━━━━━━[GPU 3]

  [GPU 1]━━━━━━━━━ Bridge B (56.25 GB/s) ━━━━━━━━━[GPU 2]
```

Two rows × two GPUs. GPUs are ordered: row 1 = Bridge A pair (0, 3), row 2 = Bridge B pair (1, 2). This matches physical cable topology.

### GPU Box Contents

Each GPU box (`80×56px` SVG rect):
- **Header**: `GPU {index}` — 10px, font-weight 600
- **VRAM text**: `{used}/{total} GB` — 9px, `--text2`
- **Utilization + Temp**: `{util}% · {temp}°C` — 8px, `--text3`

### Color States

| State | Box Fill | Box Stroke | Bridge Line |
|-------|----------|------------|-------------|
| Idle (VRAM < 5%) | `rgba(107,114,152,.06)` | `--border` | `--border`, dashed |
| Inference active | `rgba(0,217,255,.12)` | `--cyan` | `--cyan`, dashed animated |
| Training active | `rgba(255,179,71,.12)` | `--amber` | `--amber`, dashed animated |
| Image gen active | `rgba(192,132,252,.12)` | `--purple` | `--purple`, dashed |

### VRAM Fill Bar (inside each GPU box)

A 6px-tall filled rect inside the box at the bottom, proportional to `vram_used_gb / 24`. Color matches box stroke.

### Bridge Lines

- Active bridge: `stroke-dasharray: 6,3`, animated `stroke-dashoffset` scrolling at 1s loop to show data flow
- Idle bridge: `stroke-dasharray: 4,4`, static, low opacity

### Bridge Labels

Centered between the two GPU boxes:
- `Bridge A · 56.25 GB/s` (when active: color `--cyan`)
- `Bridge B · 56.25 GB/s` (when idle: color `--text3`)

### SVG Dimensions

- ViewBox: `0 0 680 160`
- Left GPU column: x=10–90
- Right GPU column: x=270–350
- Bridge line: x1=90 → x2=270, y=center of row

---

## 4. Profile Cards Grid

`display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px;`

Eight cards, one per profile from `GET /loadouts`.

### Card States

| State | Visual Treatment |
|-------|-----------------|
| Active | `border: 2px solid --cyan`, `background: rgba(0,217,255,.06)`, "ACTIVE" badge top-right |
| Available | `border: 1px solid --border`, hover `--border2` |
| Incompatible | `opacity: 0.5`, lock icon overlay, hover shows tooltip |
| Switching in progress | All cards: Activate button disabled, spinner on active card |

### Card Structure

```
┌────────────────────────────────────┐
│                       [ACTIVE]     │  ← badge (9px, top-right)
│  inference-pair-a                  │  ← profile name (12px bold)
│  TP · GPU 0+3 · 32B–40B models    │  ← description (10px --text3)
│                                    │
│  [0■] [1□] [2□] [3■]              │  ← mini GPU diagram
│     Bridge A ━━━━━                 │  ← bridge indicator (if NVLink pair)
│                                    │
│  [vllm-pair-a] [ollama]            │  ← service tags
│                                    │
│  VRAM  ~48 GB · 96 GB avail ✓     │  ← VRAM check
│                                    │
│  [────────── Activate ──────────]  │
└────────────────────────────────────┘
```

### Mini GPU Diagram

Four small squares (20×16px each, gap 3px) representing GPUs 0–3.

Color states:
- Claimed by this profile: colored fill (cyan/amber/purple) + colored border
- Not claimed: empty fill + `--border`
- Number inside each square: GPU index

If the profile uses a NVLink pair, draw a thin line connecting the two claimed squares.

### VRAM Pre-Check

Computed client-side from current `/status` data:
- `required_vram` = profile's required VRAM (from `/loadouts` response)
- `available_vram` = sum of `vram_free_gb` for GPUs claimed by the profile

Display:
- `~48 GB · 96 GB avail ✓` → green check if `available_vram > required_vram`
- `~48 GB · 12 GB avail ✗` → red, shows which profile is using the GPU

On Activate button hover, show a tooltip with the full breakdown.

### Incompatibility Lock

When a profile is incompatible with the currently active profile:
- `opacity: 0.5` on the card
- Lock icon (🔒, 12px) in top-right instead of ACTIVE badge
- Tooltip on hover: `Incompatible with {active_profile} — stop {active_profile} first`
- Activate button: `disabled`, `cursor: not-allowed`

---

## 5. Activate Flow (State Machine)

```
IDLE
  │
  ├─ user clicks Activate
  │
CONFIRM (if training-lora-text or exclusive profile)
  │ Dialog: "This will stop all inference services. Confirm?"
  │
  ├─ user confirms → POST /activate/{name}
  │
SWITCHING
  │ - Poll /status every 1s
  │ - Show switching banner (see section 6)
  │ - All Activate buttons disabled
  │
  ├─ /status returns switching: false
  │
ACTIVE
  │ - New profile name in topbar tag
  │ - Card borders update
  │ - Activity feed logs the switch
  │ - Poll drops back to 3s
```

### Confirmation Required For

- Any profile that would stop currently-running inference services
- `training-lora-text` (always, exclusive)
- Any profile where `switching` from inference to training

### No Confirmation Required For

- Switching between stopped profiles
- Activating when no profile is active

---

## 6. Switching Banner

Shown when `switching: true` in `/status` response. Full-width, between topology and profile grid.

```
┌─────────────────────────────────────────────────────────┐
│  ⟳  SWITCHING TO inference-pair-a                      │
│                                                         │
│  [████████░░░░░░░░░░░░░░] stopping services…           │
│                                                         │
│  GPU VRAM draining — do not power off                   │
└─────────────────────────────────────────────────────────┘
```

**Animated progress bar**: Indeterminate (no known completion time). Shimmer animation left-to-right.

**Phase text** (from `/status` `switching_phase` field, if available):
- `stopping services…`
- `draining VRAM…`
- `starting services…`

**GPU cards pulse** (in topology diagram): CSS `animation: borderPulse 1s ease-in-out infinite` on all active GPU boxes during the drain phase.

**Estimated time**: `~3–5 seconds` shown as static text. Remove once `switching: false`.

---

## 7. `GET /loadouts` Response Schema

```json
{
  "profiles": [
    {
      "name": "inference-pair-a",
      "description": "Tensor-parallel, GPU 0+3, 32B–40B",
      "gpus": [0, 3],
      "nvlink_pairs": [[0, 3]],
      "services": ["vllm-pair-a", "ollama"],
      "vram_required_gb": 48,
      "use_case": "32B–40B fast inference (NVLink A)",
      "accent": "cyan",
      "exclusive": false,
      "incompatible_with": ["training-lora-text", "training-lora-image"],
      "active": true
    }
  ]
}
```

---

## 8. API Calls

| Action | Endpoint | Method | Notes |
|--------|----------|--------|-------|
| Load profiles | `/loadouts` | GET | On mount, then on each /status poll |
| Load GPU state | `/status` | GET | 3s / 1s adaptive |
| Activate profile | `/activate/{name}` | POST | Returns immediately; poll for completion |
| Stop all | `/stop` | POST | Requires confirmation dialog |

---

## 9. Edge Cases

**Switching interrupted (service fails to start):** `/status` returns `switching: false` but `active_profile` is null or the previous profile. Show error banner: `⚠ Profile switch failed — {error_message}`. Offer "Retry" and "Stop All" buttons.

**No profiles loaded:** Show empty state with "No profiles found — check profiles.yaml" message.

**Profile with 0 GPU requirement (CPU-only):** Show mini GPU diagram with all four squares grayed. No VRAM check needed.

**All 96 GB in use (dual-stack active):** VRAM pre-check shows red for any profile that requires VRAM drain. Tooltip explains which services must stop.
