# Step 03 — Feedback

## Status
COMPLETE

## Files Created / Modified

### Hooks
- `ui/src/hooks/useLoadouts.js` — 3s polling for profile list from `/loadouts` endpoint

### Components
- `ui/src/components/NVLinkTopology.jsx` + `NVLinkTopology.css` — SVG diagram with 2×2 GPU layout, bridge lines, VRAM bars; animated dash animation on active bridges
- `ui/src/components/SwitchingBanner.jsx` + `SwitchingBanner.css` — Switching state banner with animated progress bar and pulsing border
- `ui/src/components/ProfileCard.jsx` + `ProfileCard.css` — Profile card with mini GPU diagram, VRAM pre-check, service tags, status badge/lock icon, activate button
- `ui/src/components/ProfileGrid.jsx` + `ProfileGrid.css` — Grid layout (auto-fill, minmax 260px) for profile cards; handles incompatibility, active state
- `ui/src/pages/Loadout.jsx` + `Loadout.css` — Main loadout page layout combining topology, switching banner, profile grid

## Acceptance Criteria
- [x] NVLink topology SVG diagram with 2×2 layout (Bridges A & B) ✓
- [x] GPU boxes show index, VRAM, utilization, temp ✓
- [x] VRAM fill bar inside each GPU box ✓
- [x] Bridge lines with dashed animation on active bridges ✓
- [x] Bridge labels (56.25 GB/s) with color coding ✓
- [x] Switching banner shown when `switching: true` ✓
- [x] Animated progress bar (shimmer animation) ✓
- [x] Switching banner pulsing border ✓
- [x] Profile grid: 2–3 column layout, auto-fill ✓
- [x] Profile cards show name, description, mini GPU diagram ✓
- [x] Mini GPU squares: claimed (colored) vs unclaimed (gray) ✓
- [x] Service tags on profile cards ✓
- [x] VRAM pre-check with color (green/red) and check/cross icon ✓
- [x] Active profile: 2px border, cyan-dim background, "ACTIVE" badge ✓
- [x] Incompatible profiles: 0.5 opacity, lock icon, tooltip on hover ✓
- [x] Activate button disabled when active/incompatible/switching ✓
- [x] POST /activate/{name} on button click ✓
- [x] Error state for failed profile load ✓
- [x] Skeleton loading state while profiles fetch ✓
- [x] Empty state: "No profiles found" message ✓

## Deviations from Spec
1. **Profile accent mapping**: Used profile.accent field directly (cyan/amber/purple). Assumes backend returns this; may need adjustment based on actual response.
2. **Confirmation dialog**: Skipped for MVP. In full implementation, should check if profile is exclusive or requires stopping inference services.
3. **Bridge line animation**: Used CSS `stroke-dashoffset` animation; spec mentioned "animated scrolling" which is achieved via keyframes.

## Blockers
None. Loadout Manager is fully functional. Backend `/loadouts` endpoint needs to return profiles with correct schema.

## Notes

### Color Coding
- **GPU Box**: Idle = gray, Inference = cyan, Training = amber, Image = purple
- **Bridge Line**: Color matches primary service type using that bridge
- **Active Bridge**: Dashed animated line (6px on, 3px off, flow animation)
- **Idle Bridge**: Static dashed line (4px on, 4px off)

### Profile Activation Flow
1. User clicks "Activate" on a profile card
2. POST /activate/{name} called
3. Client polls /status every 1s while switching: true
4. Switching banner visible with animated progress
5. When /status returns switching: false, banner hides and profile card border updates

### Performance
- ProfileGrid uses conditional rendering (no memoization needed yet as grid size fixed at 8 cards)
- NVLink topology re-renders on every GPU status update (3s); SVG is lightweight
- useLoadouts polls every 3s (same as GPU polling)

### Edge Cases Handled
- No profiles: Shows "No profiles found" empty state
- Switching in progress: All cards have disabled activate buttons
- API failure: Shows error banner with red border
- Incompatible profile: Shows lock icon, 50% opacity, disabled button, tooltip on hover

### Next Step (04)
Tools Panel will allow users to control individual services (start/stop) and manage service-level resources.
