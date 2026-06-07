# KOVATI OS — Component Spec 01
## Frontend Shell
*React 18 + Vite · CSS custom properties · JetBrains Mono*

---

## 1. Purpose

The shell is the persistent structural frame within which all panels render. It owns:

- The full-height two-column layout (sidebar + main area)
- Client-side routing between the eight panels
- The top bar (breadcrumb, global status tags, clock)
- The sidebar (logo, nav items with active state, alert badges, hardware summary)
- Global CSS tokens
- Polling lifecycle management (start/stop polling on mount/unmount)
- Global state context (active profile, service counts, alert count)

Nothing in the shell is page-specific. All page content is rendered as a child inside the main column.

---

## 2. Technology Stack

| Concern | Choice | Notes |
|---------|--------|-------|
| Framework | React 18 | Functional components, hooks throughout |
| Build tool | Vite 5 | Dev server proxies `/api` to `:8800` |
| Routing | React Router v6 | Hash routing (`/#/dashboard`) — no server config required |
| Styling | Plain CSS custom properties | No CSS-in-JS, no Tailwind. One global `tokens.css`, component `.css` files co-located |
| Font | JetBrains Mono (Google Fonts) | Loaded in `index.html` `<link>`, not via JS |
| Icons | Unicode / CSS — no icon library | Keeps the bundle lean; specific glyphs per component |
| State | React Context + `useReducer` | `AppContext` for cross-panel state; local state for panel-internal |
| Build output | `ui/dist/` → served by FastAPI `/static` | `vite build --outDir ../loadout-manager/static` |

---

## 3. File Structure

```
ui/src/
├── main.jsx              # ReactDOM.createRoot, Router, AppProvider
├── App.jsx               # Route definitions, Shell wrapper
├── tokens.css            # All CSS custom properties (single source of truth)
├── shell.css             # Sidebar, topbar, layout styles
├── context/
│   └── AppContext.jsx    # Global state: activeProfile, services, alerts, gpuStatus
├── hooks/
│   ├── useGpuStatus.js   # Polls GET /status every 3s (1s during switch)
│   ├── useServices.js    # Polls GET /api/services every 10s
│   ├── useAlerts.js      # Polls GET /api/alerts every 30s
│   └── useTrainingLog.js # SSE connection to /api/services/{name}/logs/stream
├── components/
│   ├── Shell.jsx         # Layout: sidebar + main column
│   ├── Sidebar.jsx       # Logo, NavItem list, hardware summary footer
│   ├── Topbar.jsx        # Breadcrumb, status tags, clock
│   ├── NavItem.jsx       # Single nav row with active state + optional badge
│   ├── Tag.jsx           # Reusable colored chip (cyan/green/amber/red/purple/gray)
│   ├── Btn.jsx           # Reusable button (cyan/gray/red/amber variants)
│   ├── Toggle.jsx        # On/off toggle switch
│   ├── Panel.jsx         # Surface card with optional header
│   ├── VBar.jsx          # Horizontal fill bar (VRAM, utilization)
│   ├── DotStatus.jsx     # Colored status dot (green/amber/red/gray)
│   └── MetricRow.jsx     # Label + value pair in a row
└── pages/
    ├── Dashboard.jsx
    ├── Loadout.jsx
    ├── Tools.jsx
    ├── Training.jsx
    ├── Resources.jsx
    ├── Expose.jsx
    ├── Monitor.jsx
    ├── Settings.jsx
    └── Setup.jsx          # First-boot wizard (separate route)
```

---

## 4. Routing

```jsx
// App.jsx
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';

<HashRouter>
  <AppProvider>
    <Shell>
      <Routes>
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard"  element={<Dashboard />} />
        <Route path="/loadout"    element={<Loadout />} />
        <Route path="/tools"      element={<Tools />} />
        <Route path="/training"   element={<Training />} />
        <Route path="/resources"  element={<Resources />} />
        <Route path="/expose"     element={<Expose />} />
        <Route path="/monitor"    element={<Monitor />} />
        <Route path="/settings"   element={<Settings />} />
        <Route path="/setup"      element={<Setup />} />  {/* first-boot, outside Shell */}
      </Routes>
    </Shell>
  </AppProvider>
</HashRouter>
```

The `/setup` route renders outside `<Shell>` — it is a full-page flow with its own layout.

---

## 5. Global State (AppContext)

```jsx
// context/AppContext.jsx
const initialState = {
  activeProfile: null,       // string | null
  switching: false,          // bool — drives 1s polling mode
  lastSwitched: null,        // epoch float
  runningServices: [],       // string[]
  gpus: [],                  // GPU status array from /status
  services: {},              // { [name]: { status, port, gpus, uptime, cpu, mem } }
  alertCount: 0,             // int — drives Monitor badge
  systemMode: 'workstation', // 'workstation' | 'appliance'
};

// Actions
// SET_GPU_STATUS    — payload: { activeProfile, switching, gpus, runningServices }
// SET_SERVICES      — payload: { [name]: serviceObject }
// SET_ALERT_COUNT   — payload: number
// SET_SYSTEM_MODE   — payload: 'workstation' | 'appliance'
```

Context is consumed via `useApp()` hook. Polling hooks dispatch to this reducer.

---

## 6. Polling Hooks

### `useGpuStatus.js`

```js
// Adaptive polling: 1s when switching, 3s otherwise
useEffect(() => {
  const interval = switching ? 1000 : 3000;
  const id = setInterval(async () => {
    const data = await fetch('/status').then(r => r.json());
    dispatch({ type: 'SET_GPU_STATUS', payload: data });
  }, interval);
  return () => clearInterval(id);
}, [switching]);
```

### `useServices.js`

```js
// 10s polling, aggregates Docker /containers/json via backend proxy
useEffect(() => {
  const id = setInterval(async () => {
    const data = await fetch('/api/services').then(r => r.json());
    dispatch({ type: 'SET_SERVICES', payload: data });
  }, 10000);
  return () => clearInterval(id);
}, []);
```

### `useTrainingLog.js`

```js
// SSE stream — only active when Training panel is mounted and a job is running
const connect = (serviceName) => {
  const es = new EventSource(`/api/services/${serviceName}/logs/stream`);
  es.onmessage = (e) => setLines(prev => [...prev.slice(-199), e.data]);
  return () => es.close();
};
```

---

## 7. Shell Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  SIDEBAR (180px fixed)      │  MAIN COLUMN (flex: 1)           │
│  ┌───────────────────────┐  │  ┌─────────────────────────────┐ │
│  │ LOGO BLOCK            │  │  │ TOPBAR (44px fixed)         │ │
│  │ KOVATI OS · v1.0.0    │  │  │ breadcrumb · tags · clock   │ │
│  ├───────────────────────┤  │  ├─────────────────────────────┤ │
│  │ NAV ITEMS             │  │  │ PAGE CONTENT                │ │
│  │ ● Dashboard           │  │  │ (overflow-y: auto)          │ │
│  │   Loadout             │  │  │                             │ │
│  │   Tools               │  │  │                             │ │
│  │   Training            │  │  │                             │ │
│  │   Resources           │  │  │                             │ │
│  │   Expose              │  │  │                             │ │
│  │   Monitor [2]         │  │  │                             │ │
│  │   Settings            │  │  │                             │ │
│  ├───────────────────────┤  │  │                             │ │
│  │ STATUS FOOTER         │  │  │                             │ │
│  │ ● 4× A5500 · 96 GB    │  │  │                             │ │
│  │   uptime 14d 06h 42m  │  │  └─────────────────────────────┘ │
│  └───────────────────────┘  │                                   │
└─────────────────────────────────────────────────────────────────┘
```

### Sidebar Sections

**Logo block** (border-bottom):
- Square logomark (26px, background `--cyan`, text `--bg`, font-weight 600)
- Product name: `KOVATI OS` (11px, font-weight 500)
- Sub-label: `v1.0.0-beta · 4× A5500` (9px, `--text3`)

**Nav section headers** (non-clickable, 9px all-caps `--text3`, `letter-spacing: 1px`):
- "CONTROL" above Dashboard, Loadout, Tools
- "WORKLOADS" above Training, Resources
- "PLATFORM" above Expose, Monitor, Settings

**Nav items:**
- 11px, `--text2` default
- Hover: background `rgba(0,217,255,0.05)`, color `--text`
- Active: `border-left: 2px solid --cyan`, background `--cyan-dim`, color `--cyan`
- Alert badge (Monitor): red pill, count from `alertCount` in context

**Status footer** (border-top):
- Animated pulse dot (6px circle, background `--green`, CSS `@keyframes pulse`)
- GPU summary line
- Uptime line (9px, `--text3`)

---

## 8. Topbar

Fixed 44px height, `border-bottom`, `background: --surface`.

Left side:
```
KOVATI OS › [current page name]
```
Page name in `--cyan`. Breadcrumb label is always one level deep (no nesting).

Right side (flex row, gap 12px):
- **Active loadout tag** — `tag-cyan` component, text is `activeProfile` from context
- **Running count tag** — `tag-green`, e.g. "23 running"
- **Idle count tag** — `tag-amber`, e.g. "3 idle"
- **Live clock** — `10px`, `--text3`, `HH:MM:SS` 24h format, updates every second via `setInterval`

---

## 9. Reusable Component API

### `<Tag variant="cyan|green|amber|red|purple|gray">`
```jsx
<Tag variant="cyan">inference-pair-a</Tag>
// renders: background --cyan-dim, color --cyan, border 1px solid rgba(0,217,255,.25)
// 10px font, font-weight 500, letter-spacing .2px, padding 2px 7px, border-radius 3px
```

### `<Btn variant="cyan|gray|red|amber" size="sm|md">`
```jsx
<Btn variant="cyan" onClick={handleActivate}>Activate</Btn>
// md: padding 5px 12px, 10px font
// sm: padding 2px 8px, 9px font
```

### `<Toggle checked={bool} onChange={fn} disabled={bool}>`
```jsx
<Toggle checked={service.running} onChange={() => toggleService(name)} />
// 28×14px track, 10px thumb, cyan when checked
```

### `<Panel title="GPU Status" subtitle="3s refresh">`
```jsx
<Panel title="GPU Status" subtitle="NVLink: A(0↔3)">
  {children}
</Panel>
// panel-header: border-bottom, 10px title, 9px subtitle --text3
// panel-body: padding 12px 14px
```

### `<VBar pct={89} variant="cyan|amber|green">`
```jsx
<VBar pct={89} variant="cyan" />
// 6px height track, border-radius 3px, fill width = pct%
```

### `<DotStatus status="green|amber|red|gray">`
```jsx
<DotStatus status="green" />
// 7px circle, inline-block, margin-right 4px
```

---

## 10. CSS Tokens (`tokens.css`)

```css
:root {
  /* backgrounds */
  --bg:        #0a0e27;
  --surface:   #1a1f3a;
  --surface2:  #232844;
  --surface3:  #2a3050;

  /* borders */
  --border:    #2e3560;
  --border2:   #3d4580;

  /* accents */
  --cyan:      #00d9ff;
  --cyan-dim:  rgba(0,217,255,0.12);
  --amber:     #ffb347;
  --amber-dim: rgba(255,179,71,0.12);
  --purple:    #c084fc;
  --purple-dim:rgba(192,132,252,0.12);
  --green:     #4ade80;
  --green-dim: rgba(74,222,128,0.12);
  --red:       #f87171;
  --red-dim:   rgba(248,113,113,0.12);

  /* text */
  --text:      #e0e0e0;
  --text2:     #9aa0c0;
  --text3:     #6b7298;

  /* layout */
  --radius:    6px;
  --mono:      'JetBrains Mono', 'IBM Plex Mono', monospace;
}
```

All components consume these tokens. No hardcoded hex values in component CSS.

---

## 11. Vite Config

```js
// vite.config.js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8800',
      '/status': 'http://localhost:8800',
      '/loadouts': 'http://localhost:8800',
      '/activate': 'http://localhost:8800',
      '/health': 'http://localhost:8800',
    }
  },
  build: {
    outDir: '../loadout-manager/static',
    emptyOutDir: true,
  }
});
```

In production, FastAPI mounts the built static directory:
```python
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="static", html=True), name="static")
```

---

## 12. Responsiveness

| Breakpoint | Behavior |
|-----------|----------|
| ≥1920px | Full layout, full density |
| ≥1280px | Sidebar shrinks to 160px, some grid columns collapse |
| ≥768px (iPad) | Sidebar collapses to icon-only (44px), tap to expand overlay |
| <768px | Not targeted for v1 |

---

## 13. Appliance Mode

When `systemMode === 'appliance'` (set from `/api/network` response):
- Settings nav item shows lock icon
- Settings panel hides Secrets rotate buttons, Network edit, Stack Update button
- First-boot re-run button is hidden
- Logo sub-label shows "Managed Appliance" instead of hardware summary

---

## 14. Build & Deploy

```bash
# Development
cd ui && npm install && npm run dev
# → dev server at :5173, proxies API to :8800

# Production build
npm run build
# → outputs to loadout-manager/static/

# FastAPI serves both API and UI from :8800
uvicorn main:app --host 0.0.0.0 --port 8800
```
