# TASK-011 — Validate auto-refresh cycle

**Issue:** #6
**Result: PASS (mechanism)** — polling is correctly implemented. The refreshed
*payload* is empty for GPU data, but that is #5's defect, not this one's.

## Findings

The original issue's correction is accurate: there is no `setInterval(refresh, 5000)`
in the Dashboard. Polling lives in hooks, each with its own cadence:

| Hook | Endpoint | Interval |
| --- | --- | --- |
| `useGpuStatus` | `/status` | 3000 ms — 1000 ms while `state.switching` |
| `useLoadouts` | `/loadouts` | 3000 ms |
| `useServices` | `/api/services` | 10000 ms |
| `useSystemMetrics` | — | 10000 ms |
| `useActivity` / `useAlerts` | — | 30000 ms |
| `GPUTelemetrySection` | — | 5000 ms (component-local) |

`useGpuStatus` (`ui/src/hooks/useGpuStatus.js:24-26`) adapts its cadence during a
profile switch, which is the behaviour the task asks for. Every hook clears its
interval on unmount, so there is no timer leak.

## Method note

The issue's step 2 (`docker exec ollama ollama run mistral:7b ...`) would start a
GPU workload — a state change on the box, outside the read-only remit. Instead the
polling contract was verified from source and `/status` was sampled twice 5s apart.

## Evidence

Two `/status` samples, 5s apart, are byte-identical:

```json
{"active_profile":null,"switching":false,"last_switched":null,"running_services":[],"gpus":[]}
```

This is consistent with polling working and the payload genuinely not changing —
`gpus` is empty on both reads because of #5, so a value-changed assertion cannot be
made from GPU telemetry until that is fixed.

## Verdict

The auto-refresh cycle is implemented correctly. Re-run the value-changes-over-time
half of this task once #5 restores GPU telemetry.
