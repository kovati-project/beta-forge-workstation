# TASK-012 — Validate active profile display

**Issue:** #7
**Result: FAIL** — two independent defects, either of which alone would break the
display. The banner cannot show an active profile under any circumstances.

## Defect 1 — frontend reads field names the API does not send

`useGpuStatus` passes the raw `/status` JSON straight through
(`ui/src/hooks/useGpuStatus.js:14`, `setGpuStatus(data)`), and `setGpuStatus`
dispatches it unchanged as the reducer payload
(`ui/src/context/AppContext.jsx:65-67`). The reducer then destructures **camelCase**
keys from a **snake_case** payload (`AppContext.jsx:22`):

| Reducer expects | API sends | Result |
| --- | --- | --- |
| `activeProfile` | `active_profile` | `undefined` |
| `runningServices` | `running_services` | `undefined` |
| `switching` | `switching` | works |
| `gpus` | `gpus` | works |

Because the reducer merges with `activeProfile: activeProfile \|\| state.activeProfile`
(`AppContext.jsx:25`), an `undefined` read falls back to the previous value — which
is seeded `null` (`AppContext.jsx:8`). `state.activeProfile` is therefore
**permanently `null`**, so `ActiveLoadoutBanner` always takes its empty branch
(`ui/src/components/ActiveLoadoutBanner.jsx:43-48`, "No active profile — select a
loadout to begin") and never reaches the render at line 84.

`runningServices` is broken by the same mismatch and never populates.

## Defect 2 — backend reports no active profile while hardware says otherwise

`GET /status` returns:

```json
{"active_profile":null,"switching":false,"last_switched":null,"running_services":[],"gpus":[]}
```

Concurrently, `nvidia-smi` shows ~23 GB resident on GPU0 and ~22 GB on GPU3 — the
NVLink Bridge A pair (`nvidia-smi topo -m` confirms `NV4` between GPU0 and GPU3),
which is exactly the `inference-pair-a` GPU assignment. A vLLM model is loaded and
serving, yet the manager reports no active profile and no running services.

This is the in-memory `state` dict (`loadout-manager/main.py:72`) having lost its
contents across a process restart — the condition #48 exists to fix.

## Verdict

Fails on both counts. Defect 1 is a one-line-per-field fix in the reducer and is
independently actionable now; the banner will stay blank even after #48 lands
unless it is fixed. Defect 2 is #48's scope.
