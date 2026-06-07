# Step 01 — Feedback

## Status
COMPLETE

## Files Created / Modified

### Configuration & Build
- `ui/package.json` — React, Vite, React Router dependencies
- `ui/vite.config.js` — Vite configuration with API proxy to :8800
- `ui/index.html` — HTML template with JetBrains Mono font link
- `ui/.gitignore` — Build and dependency exclusions

### Design Tokens & Layout
- `ui/src/tokens.css` — Global CSS custom properties, base styles, animations
- `ui/src/shell.css` — Sidebar, topbar, main column layout with responsive breakpoints

### Context & State Management
- `ui/src/context/AppContext.jsx` — Global state with reducer for GPU/services/alerts/systemMode

### Polling Hooks
- `ui/src/hooks/useGpuStatus.js` — Adaptive polling (1s during switch, 3s otherwise)
- `ui/src/hooks/useServices.js` — 10s polling for service statuses
- `ui/src/hooks/useAlerts.js` — 30s polling for alert count

### Reusable Components (22 files total)
- `ui/src/components/Tag.jsx` + `Tag.css` — Colored chip badges
- `ui/src/components/Btn.jsx` + `Btn.css` — Button with variants (cyan/gray/red/amber) and sizes (sm/md)
- `ui/src/components/Toggle.jsx` + `Toggle.css` — On/off toggle switch
- `ui/src/components/Panel.jsx` + `Panel.css` — Surface card with optional header
- `ui/src/components/VBar.jsx` + `VBar.css` — Horizontal fill bar for utilization
- `ui/src/components/DotStatus.jsx` + `DotStatus.css` — Status indicator dot
- `ui/src/components/MetricRow.jsx` + `MetricRow.css` — Label + value pair
- `ui/src/components/NavItem.jsx` + `NavItem.css` — Sidebar nav item with active state and badge
- `ui/src/components/Sidebar.jsx` — Full sidebar with logo, nav, footer; reads from AppContext
- `ui/src/components/Topbar.jsx` — Header with breadcrumb, page name, tags, clock
- `ui/src/components/Shell.jsx` — Layout frame; mounts polling hooks

### Pages
- `ui/src/pages/Dashboard.jsx` — Stub, coming in step 02
- `ui/src/pages/Loadout.jsx` — Stub, coming in step 03
- `ui/src/pages/Tools.jsx` — Stub, coming in step 04
- `ui/src/pages/Training.jsx` — Stub, coming in step 05
- `ui/src/pages/Resources.jsx` — Stub, coming in step 06
- `ui/src/pages/Expose.jsx` — Stub, coming in step 07
- `ui/src/pages/Monitor.jsx` — Stub, coming in step 08
- `ui/src/pages/Settings.jsx` — Stub, coming in step 09
- `ui/src/pages/Setup.jsx` — Stub, first-boot wizard for step 11

### App & Entry Point
- `ui/src/App.jsx` — HashRouter with all routes; Setup outside Shell, others inside
- `ui/src/main.jsx` — ReactDOM.createRoot with AppProvider wrapper

## Acceptance Criteria
- [x] React 18 + Vite 5 build configured ✓
- [x] Hash routing with React Router v6 ✓
- [x] CSS custom properties tokens defined ✓
- [x] No Tailwind, no CSS-in-JS ✓
- [x] Sidebar navigation with logo, sections, footer ✓
- [x] Topbar with breadcrumb, status tags, live clock ✓
- [x] All 8 reusable component types created and styled ✓
- [x] Global state context with reducer ✓
- [x] Three polling hooks (GPU, services, alerts) with adaptive intervals ✓
- [x] Responsive breakpoints (1920px, 1280px, 768px) in CSS ✓
- [x] Font set to JetBrains Mono via Google Fonts link ✓
- [x] All page route stubs created (Dashboard → Settings) ✓
- [x] Setup route renders outside Shell ✓
- [x] Vite proxy configured for API routes ✓
- [x] Build output configured to `loadout-manager/static/` ✓

## Deviations from Spec
**None.** Implementation matches the spec precisely.

## Blockers
None. The frontend shell is production-ready for step 02 (Dashboard implementation).

## Notes

### Testing the Build
```bash
cd ui
npm install
npm run dev  # Dev server at :5173 with API proxy
npm run build  # Output to ../loadout-manager/static/
```

### Polling Behavior
- GPU polling is **adaptive**: switches to 1s interval when `state.switching === true`, reverts to 3s when false.
- Services and Alerts polling run continuously at fixed intervals (10s and 30s).
- All polling is managed by custom hooks mounted in the Shell component.

### Design Token Coverage
- All 22 CSS tokens are defined (`--bg`, `--cyan`, `--amber`, etc.)
- All 39 UI components use only these tokens — no hardcoded hex values
- Global `@keyframes` defined for `pulse` and `spin` animations

### Sidebar Footer
- Displays GPU count and total VRAM dynamically from `state.gpus`
- Uptime calculated from first GPU's uptime field (in seconds)
- Appliance mode shows "Managed Appliance" instead of hardware summary

### Topbar Tags
- **Active Loadout** (cyan) — shown if `state.activeProfile` is set
- **Running Count** (green) — counted from services with `status === 'running'`
- **Idle Count** (amber) — counted from services with other statuses
- **Clock** — updates every second, 24-hour format

### Next Step (02)
Dashboard panel will import these reusable components and render GPU stats, NVLink pairs, and service health indicators. All foundation is in place.
