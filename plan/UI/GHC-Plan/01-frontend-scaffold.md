# Step 01 — Frontend Scaffold & Shell

> **Prerequisites:** Read `plan/UI/GHC-Plan/00-overview.md` before starting.
> **Reference spec:** `plan/UI/Steps/01-frontend-shell.md` (full layout diagrams, component API)

---

## Goal

Scaffold the React 18 + Vite frontend, implement the persistent Shell layout (sidebar + topbar),
wire up routing and global state, and confirm the app renders correctly in both dev and production
build modes.

No real data is needed yet. Stub all API calls with static mock data. The next step (Dashboard)
will connect live polling.

---

## Deliverables

### 1. Scaffold the `ui/` project

From the repo root (`ai-workstation-project/`):

```bash
npm create vite@latest ui -- --template react
cd ui
npm install react-router-dom
```

**Do not** install Tailwind, styled-components, or any CSS framework.

---

### 2. `ui/src/tokens.css`

Create this file with the canonical token set. Copy exactly from `00-overview.md §Design Tokens`.
No deviations. Every other CSS file imports this via `@import './tokens.css'`.

---

### 3. `ui/index.html`

Replace the Vite default `<head>` content with:

```html
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>KOVATI OS</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
</head>
```

---

### 4. `ui/src/tokens.css` + `ui/src/shell.css`

`shell.css` handles the two-column layout and topbar. Key structure:

```css
@import './tokens.css';

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: var(--mono);
  background: var(--bg);
  color: var(--text);
  font-size: 12px;
  height: 100vh;
  overflow: hidden;
}

.shell {
  display: flex;
  height: 100vh;
}

.sidebar {
  width: 180px;
  flex-shrink: 0;
  background: var(--surface);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
}

.main-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.topbar {
  height: 44px;
  flex-shrink: 0;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 16px;
  gap: 12px;
}

.page-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}
```

---

### 5. `ui/src/context/AppContext.jsx`

Global state with mock initial values so the shell renders without a live backend:

```jsx
import { createContext, useContext, useReducer } from 'react';

const initialState = {
  activeProfile: 'inference-pair-a',   // mock
  switching: false,
  lastSwitched: Date.now() / 1000 - 3600,
  runningServices: ['vllm-pair-a', 'ollama'],
  gpus: [
    { index: 0, vram_used_gb: 21.4, vram_total_gb: 24, vram_free_gb: 2.6,
      utilization_pct: 92, temp_c: 74, power_w: 198, nvlink_bridge: 'A' },
    { index: 1, vram_used_gb: 1.2,  vram_total_gb: 24, vram_free_gb: 22.8,
      utilization_pct: 3,  temp_c: 42, power_w: 45,  nvlink_bridge: 'B' },
    { index: 2, vram_used_gb: 0.8,  vram_total_gb: 24, vram_free_gb: 23.2,
      utilization_pct: 1,  temp_c: 39, power_w: 38,  nvlink_bridge: 'B' },
    { index: 3, vram_used_gb: 19.8, vram_total_gb: 24, vram_free_gb: 4.2,
      utilization_pct: 88, temp_c: 71, power_w: 189, nvlink_bridge: 'A' },
  ],
  services: {},
  alertCount: 2,    // mock — shows badge on Monitor nav item
  systemMode: 'workstation',
};

function reducer(state, action) {
  switch (action.type) {
    case 'SET_GPU_STATUS':  return { ...state, ...action.payload };
    case 'SET_SERVICES':    return { ...state, services: action.payload };
    case 'SET_ALERT_COUNT': return { ...state, alertCount: action.payload };
    case 'SET_SYSTEM_MODE': return { ...state, systemMode: action.payload };
    default: return state;
  }
}

const AppContext = createContext(null);
export const useApp = () => useContext(AppContext);

export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  return (
    <AppContext.Provider value={{ state, dispatch }}>
      {children}
    </AppContext.Provider>
  );
}
```

---

### 6. Reusable Components

Create each in `ui/src/components/`. These will be used by every panel. Keep them simple —
no business logic, just rendering.

**`Tag.jsx`**
```jsx
// Usage: <Tag variant="cyan">inference-pair-a</Tag>
export function Tag({ variant = 'gray', children }) {
  return <span className={`tag tag-${variant}`}>{children}</span>;
}
```

CSS (in `components/Tag.css`):
```css
@import '../tokens.css';
.tag {
  display: inline-block;
  font-size: 10px;
  font-weight: 500;
  letter-spacing: .2px;
  padding: 2px 7px;
  border-radius: 3px;
  font-family: var(--mono);
}
.tag-cyan   { background: var(--cyan-dim);   color: var(--cyan);   border: 1px solid rgba(0,217,255,.25); }
.tag-green  { background: var(--green-dim);  color: var(--green);  border: 1px solid rgba(74,222,128,.25); }
.tag-amber  { background: var(--amber-dim);  color: var(--amber);  border: 1px solid rgba(255,179,71,.25); }
.tag-red    { background: var(--red-dim);    color: var(--red);    border: 1px solid rgba(248,113,113,.25); }
.tag-purple { background: var(--purple-dim); color: var(--purple); border: 1px solid rgba(192,132,252,.25); }
.tag-gray   { background: var(--surface2);   color: var(--text2);  border: 1px solid var(--border); }
```

**`Btn.jsx`**
```jsx
// Usage: <Btn variant="cyan" size="md" onClick={fn}>Activate</Btn>
export function Btn({ variant = 'gray', size = 'md', onClick, disabled, children }) {
  return (
    <button
      className={`btn btn-${variant} btn-${size}`}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}
```

CSS: cyan border + `--cyan` color, hover brightens background, disabled fades to 40% opacity.

**`DotStatus.jsx`**
```jsx
// Usage: <DotStatus status="green" />
export function DotStatus({ status = 'gray' }) {
  return <span className={`dot dot-${status}`} />;
}
```

CSS: 7px circle, colors map to semantic vars (`--green`, `--amber`, `--red`, `--text3`).

**`VBar.jsx`**
```jsx
// Usage: <VBar pct={89} variant="cyan" />
export function VBar({ pct, variant = 'cyan' }) {
  return (
    <div className="vbar-track">
      <div className={`vbar-fill vbar-${variant}`} style={{ width: `${Math.min(pct, 100)}%` }} />
    </div>
  );
}
```

CSS: track is 6px height, `--surface3` background, fill is `--cyan` / `--amber` / `--green`.

**`Panel.jsx`**
```jsx
// Usage: <Panel title="GPU Status" subtitle="3s refresh">{children}</Panel>
export function Panel({ title, subtitle, children }) {
  return (
    <div className="panel">
      {title && (
        <div className="panel-header">
          <span className="panel-title">{title}</span>
          {subtitle && <span className="panel-subtitle">{subtitle}</span>}
        </div>
      )}
      <div className="panel-body">{children}</div>
    </div>
  );
}
```

**`Toggle.jsx`**
```jsx
// Usage: <Toggle checked={true} onChange={fn} disabled={false} />
export function Toggle({ checked, onChange, disabled }) {
  return (
    <label className={`toggle ${disabled ? 'toggle-disabled' : ''}`}>
      <input type="checkbox" checked={checked} onChange={onChange} disabled={disabled} />
      <span className="toggle-track">
        <span className="toggle-thumb" />
      </span>
    </label>
  );
}
```

CSS: 28×14px track, 10px thumb, `--cyan` fill when checked.

---

### 7. `ui/src/components/Shell.jsx`, `Sidebar.jsx`, `Topbar.jsx`

Implement the persistent shell. See `plan/UI/Steps/01-frontend-shell.md §7` for the exact
layout diagram and §8 for topbar spec.

**Sidebar nav items** (in order):

Section header "CONTROL":
- Dashboard → `/#/dashboard`
- Loadout → `/#/loadout`
- Tools → `/#/tools`

Section header "WORKLOADS":
- Training → `/#/training`
- Resources → `/#/resources`

Section header "PLATFORM":
- Expose → `/#/expose`
- Monitor → `/#/monitor` (shows `alertCount` badge from AppContext when > 0)
- Settings → `/#/settings`

Active state: use `useLocation()` from React Router to match the current hash path.

**Sidebar footer** (below nav, border-top):
- Animated green pulse dot
- Text: `4× RTX A5500 · 96 GB`
- Text: `uptime —` (static for now; wired in a later step)

**Topbar:**
- Left: `KOVATI OS › [Page Name]` — page name derived from current route path
- Right: active loadout tag (cyan), running count tag (green), idle count tag (amber), clock

Clock: `setInterval` updating every second, format `HH:MM:SS` 24-hour.

For this step, running/idle counts are hardcoded stubs (`"— running"`, `"— idle"`). They will
be wired to real service data in Step 02.

---

### 8. `ui/src/App.jsx`

```jsx
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AppProvider } from './context/AppContext';
import { Shell } from './components/Shell';
import { Dashboard }  from './pages/Dashboard';
import { Loadout }    from './pages/Loadout';
import { Tools }      from './pages/Tools';
import { Training }   from './pages/Training';
import { Resources }  from './pages/Resources';
import { Expose }     from './pages/Expose';
import { Monitor }    from './pages/Monitor';
import { Settings }   from './pages/Settings';
import { Setup }      from './pages/Setup';

export default function App() {
  return (
    <HashRouter>
      <AppProvider>
        <Routes>
          <Route path="/setup" element={<Setup />} />
          <Route path="/*" element={
            <Shell>
              <Routes>
                <Route index element={<Navigate to="/dashboard" replace />} />
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/loadout"   element={<Loadout />} />
                <Route path="/tools"     element={<Tools />} />
                <Route path="/training"  element={<Training />} />
                <Route path="/resources" element={<Resources />} />
                <Route path="/expose"    element={<Expose />} />
                <Route path="/monitor"   element={<Monitor />} />
                <Route path="/settings"  element={<Settings />} />
              </Routes>
            </Shell>
          } />
        </Routes>
      </AppProvider>
    </HashRouter>
  );
}
```

`/setup` renders outside `<Shell>` — it is a full-page flow. For now, `Setup.jsx` can be a
placeholder: `<div style={{color:'var(--text)',padding:40}}>First-Boot Wizard (Step 11)</div>`.

---

### 9. Page Stubs

Create all 8 page files with minimal placeholder content. Each should render inside the shell
without errors:

```jsx
// pages/Dashboard.jsx
export function Dashboard() {
  return <div className="page-placeholder">Dashboard — Step 02</div>;
}
```

Repeat for Loadout, Tools, Training, Resources, Expose, Monitor, Settings.

---

### 10. `vite.config.js`

```js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api':      { target: 'http://localhost:8800', changeOrigin: true },
      '/status':   { target: 'http://localhost:8800', changeOrigin: true },
      '/loadouts': { target: 'http://localhost:8800', changeOrigin: true },
      '/activate': { target: 'http://localhost:8800', changeOrigin: true },
      '/health':   { target: 'http://localhost:8800', changeOrigin: true },
    }
  },
  build: {
    outDir: '../loadout-manager/static',
    emptyOutDir: true,
  }
});
```

---

### 11. FastAPI static file mount

Add to the **end** of `loadout-manager/main.py` (after all route definitions):

```python
from fastapi.staticfiles import StaticFiles
import os

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
```

The `if os.path.isdir` guard prevents errors when the static dir doesn't exist yet (during
development, the Vite dev server is used instead).

---

## Acceptance Criteria

- [ ] `cd ui && npm run dev` — shell renders at `http://localhost:5173/#/dashboard` with no
  console errors
- [ ] Sidebar shows all 8 nav items in the correct section groups
- [ ] Clicking each nav item navigates to the correct route; active item is highlighted with
  cyan left border
- [ ] Monitor nav item shows a red badge with count `2` (from mock alertCount in AppContext)
- [ ] Topbar shows: `KOVATI OS › Dashboard`, cyan tag `inference-pair-a`, and a live clock
- [ ] Sidebar footer shows the animated green pulse dot
- [ ] All 8 page stubs render without errors (check by clicking each nav item)
- [ ] `npm run build` completes without errors and outputs files to `loadout-manager/static/`
- [ ] `uvicorn main:app --port 8800` serves the built app at `http://localhost:8800`

---

## Notes

- The mock GPU data in `AppContext` uses realistic values (used ≤ total). Do not use placeholder
  values that exceed the 24 GB per-card limit.
- JetBrains Mono requires the Google Fonts link in `index.html` — confirm the font loads by
  inspecting `body` computed styles in DevTools.
- If the Vite dev server and FastAPI are both running, the dev server at `:5173` is the correct
  target for development. `:8800` serves the production build.

---

## Feedback

When done, write `plan/UI/GHC-Feedback/01-feedback.md` following the template in
`plan/UI/GHC-Plan/00-overview.md §How to Write Feedback`.
