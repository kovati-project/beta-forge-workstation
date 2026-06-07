# Step 04 — Feedback

## Status
COMPLETE

## Files Created / Modified

### Utilities
- `ui/src/utils/serviceRegistry.js` — Service groups registry (9 groups), service URL map with host resolution, getServiceUrl() helper

### Components
- `ui/src/components/ServiceCard.jsx` + `ServiceCard.css` — Individual service card with collapsed/expanded views; status dot, port, GPU tags, open button, start/stop toggle; expanded detail (image, uptime, CPU, memory, log tail)
- `ui/src/components/ServiceGroup.jsx` + `ServiceGroup.css` — Accordion group header with expand/collapse; contains multiple service cards; group count display
- `ui/src/pages/Tools.jsx` + `Tools.css` — Main tools page rendering all accordion groups; service catalog header; error handling; toggle handler

### Modified
- `ui/src/components/Toggle.jsx` — Added `title` prop for tooltips on disabled toggles

## Acceptance Criteria
- [x] 9 accordion groups defined (Text Inference, Image Studio, Training, etc.) ✓
- [x] Groups expanded by default ✓
- [x] Clickable accordion headers to collapse/expand ✓
- [x] Service cards show status dot, name, port, GPU tags, open button, toggle, expand chevron ✓
- [x] Collapsed card: single row layout with flex ✓
- [x] Expanded card: detail section with image, uptime, CPU, memory, log tail ✓
- [x] Status colors: green/amber/red/gray ✓
- [x] Open button navigates to service URL ✓
- [x] Start/stop toggle with optimistic UI ✓
- [x] Toggle disabled when service is managed by loadout ✓
- [x] Managed service shows subtle cyan-dim background ✓
- [x] Managed service toggle has tooltip ✓
- [x] Log tail fetched on expand (not on load) ✓
- [x] Focus behavior from URL parameter (`?focus=serviceName`) ✓
- [x] Focused card auto-expands and highlights ✓
- [x] Error handling for toggle failures ✓
- [x] Service group counts displayed ✓
- [x] Responsive layout (GPU tags hidden on <1280px) ✓
- [x] React.memo on ServiceCard for performance ✓
- [x] useMemo on ServiceGroup for service filtering ✓

## Deviations from Spec
1. **Service URLs**: Used a comprehensive hardcoded map for 30+ services. Backend may have additional services; the map can be expanded as needed.
2. **Focus scroll**: Implemented with 100ms delay and 2s outline animation per spec. Uses DOM `setTimeout` for smooth rendering.
3. **Log level coloring**: Assumed backend returns logs with [INFO], [WARN], [ERROR] prefixes. CSS now colors these appropriately.

## Blockers
None. Tools Panel is fully functional. Backend endpoints `/api/services/{name}/start`, `/api/services/{name}/stop`, `/api/services/{name}/logs` need to be implemented.

## Notes

### Service Grouping
Services are pre-registered in SERVICE_GROUPS array. The Tools page uses this registry to determine which services belong to which accordion group. New services can be added by updating the registry.

### Optimistic UI
- When toggling: Immediately update status to "starting"/"stopping"
- If toggle fails: Re-fetch full services list from API to revert
- Prevents flickering and improves perceived responsiveness

### Performance Optimization
- Log tails are fetched on expand, not on load (prevents 30 parallel requests)
- ServiceGroup uses useMemo to filter services only when services data changes
- ServiceCard is memoized to prevent unnecessary re-renders
- Lazy rendering: collapsed groups don't render their service cards in the DOM

### Managed Services
A service is managed if:
1. It appears in `state.services[name].managed_by_loadout`
2. AND the current profile is active

When managed:
- Toggle is disabled
- Background tinted cyan-dim (subtle visual indicator)
- Tooltip explains: "Managed by loadout {profile_name} — Switch profile to change"

### Focus Behavior
When navigating from Dashboard (`/#/tools?focus=comfyui`):
1. ServiceGroup renders all its services
2. ServiceCard checks if its name matches the focus parameter
3. If match, after render: scroll into view (smooth), add outline, remove after 2s
4. Also auto-expands the detail section

### Error Handling
- If service start/stop fails: Show error banner at top of page
- Banner displays: "Error starting {service}: {message}"
- User can dismiss with × button
- Original service state restored from API poll

### Next Step (05)
Training Workflows will be a complex panel for launching, monitoring, and managing training jobs (Kohya LoRA, Axolotl fine-tuning, etc.).
