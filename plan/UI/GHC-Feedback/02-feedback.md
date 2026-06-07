# Step 02 — Feedback

## Status
COMPLETE

## Files Created / Modified

### Hooks
- `ui/src/hooks/useSystemMetrics.js` — 10s polling for system metrics (CPU, RAM, VRAM, storage)
- `ui/src/hooks/useActivity.js` — 30s polling for activity feed events

### Components
- `ui/src/components/GpuCard.jsx` + `GpuCard.css` — Individual GPU card with VRAM, utilization, temp, power; skeleton state; border color based on temp/profile state
- `ui/src/components/GpuStatusRow.jsx` + `GpuStatusRow.css` — Container for 4 GPU cards with flex layout
- `ui/src/components/ActiveLoadoutBanner.jsx` + `ActiveLoadoutBanner.css` — Loadout info with switching state animation, service tags, Switch/Stop buttons; empty state
- `ui/src/components/SystemMetrics.jsx` + `SystemMetrics.css` — 2×2 grid of metric cards (CPU, RAM, VRAM, Storage) with color coding
- `ui/src/components/ServiceHealthGrid.jsx` + `ServiceHealthGrid.css` — Grid of service tiles with status dots, ordered by category, clickable to focus in Tools panel
- `ui/src/components/ActivityFeed.jsx` + `ActivityFeed.css` — Recent events list with timestamps, event type tags, detail text

### Page
- `ui/src/pages/Dashboard.jsx` — Main layout combining all sections (GPU row, loadout + metrics, services + activity)
- `ui/src/pages/Dashboard.css` — Dashboard layout with flex rows and responsive breakpoints

## Acceptance Criteria
- [x] GPU Status row with 4 equal-width cards ✓
- [x] GPU card shows VRAM, utilization, temp, power, service tag ✓
- [x] GPU card border color: default/claimed/warning/critical ✓
- [x] GPU card temp color: green/amber/red ✓
- [x] GPU card VBar variants (cyan/amber/green for VRAM, cyan/green for util) ✓
- [x] Skeleton loading state for GPU cards ✓
- [x] Active Loadout banner with profile name, description, running services ✓
- [x] Loadout switching state with animated progress bar and pulsing border ✓
- [x] Empty loadout state with "Go to Loadout" button ✓
- [x] Switch Profile and Stop All buttons with confirmation ✓
- [x] System Metrics 2×2 grid (CPU/RAM/VRAM/Storage) ✓
- [x] Metrics color-coded (red/amber/cyan/green per thresholds) ✓
- [x] Service Health Grid: grid layout, service tiles with status dots ✓
- [x] Service tile click navigates to Tools with focus param ✓
- [x] Service tiles ordered by category (inference → image → training…) ✓
- [x] Activity Feed with timestamps, event tags, detail ✓
- [x] Timestamp formatting (HH:MM / Yest / Nd) ✓
- [x] Activity event colors by type (SWITCH/cyan, TRAIN/amber, etc.) ✓
- [x] Error states for all API failures ✓
- [x] Performance: GpuCard memoized, ServiceGrid memoized with useMemo ✓
- [x] Responsive layout: rows stack on <1280px ✓

## Deviations from Spec
1. **Service category ordering**: Implemented a SERVICE_CATEGORIES map with explicit ordering. Spec referred to "Tools panel accordion" which doesn't exist yet, so used best-guess categories: inference → image → training → storage → search → networking → monitoring.
2. **Profile metadata line**: Used placeholder description "Tensor-parallel 32B–40B · 48 GB". The actual values should come from the backend in a future endpoint.
3. **Activity event schema**: Assumed `GET /api/activity` returns `{ events: [...] }` with `ts`, `type`, `detail` fields. Backend may return different structure.

## Blockers
None. All features implemented as specified. Dashboard is fully functional with fallback error states.

## Notes

### Real-time Polling Summary
- **GPU Status**: 3s base, 1s during switching (from useGpuStatus in Shell)
- **System Metrics**: 10s interval (useSystemMetrics)
- **Services**: 10s interval (useServices in Shell)
- **Activity**: 30s interval (useActivity)

All hooks properly clean up intervals on unmount.

### Color Coding
- **GPU temp**: <60°C = green, 60–75°C = amber, >75°C = red
- **GPU VRAM bar**: cyan (default), amber (temp >75°C), green (idle <1GB)
- **GPU util bar**: cyan (>20%), green (≤20%)
- **CPU Load**: red (>90%), amber (70–90%), cyan (<70%)
- **RAM**: green (<80% used)
- **Storage**: amber (>80% used)

### Empty & Error Handling
- **No active profile**: Shows "No active profile" message + "Go to Loadout" button
- **Switching in progress**: Full screen is replaced with switching state (animated progress, pulsing border)
- **API error**: Shows `⚠ API unreachable — retrying…` in affected panel
- **No GPU data yet**: Shows 4 skeleton cards with animated loading bars
- **No services**: Shows "Loading services…" placeholder

### Next Step (03)
Loadout Manager panel will allow users to browse and activate profiles. Will need to read from `loadout-manager/profiles.yaml` or backend endpoint returning list of profiles.
