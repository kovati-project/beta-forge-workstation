# TASK-010 — Validate GPU widget data accuracy

**Issue:** #5
**Result: FAIL** — the Dashboard GPU widgets cannot be accurate, because the backend
supplies no GPU data at all while real workloads are resident on GPU0 and GPU3.

## Method

`nvidia-smi` on the host and the loadout-manager API were sampled back to back
(~0.2s apart) so the two readings describe the same moment.

## Evidence

Host truth — `nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu,temperature.gpu,power.draw,pci.bus_id`:

| GPU | VRAM used | VRAM total | Util | Temp | Power | Bus ID |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | 23335 MiB | 24564 MiB | 0% | 35 °C | 23.09 W | 00000000:21:00.0 |
| 1 | 1 MiB | 24564 MiB | 0% | 37 °C | 9.15 W | 00000000:22:00.0 |
| 2 | 1 MiB | 24564 MiB | 0% | 35 °C | 9.91 W | 00000000:41:00.0 |
| 3 | 22824 MiB | 24564 MiB | 0% | 40 °C | 23.62 W | 00000000:43:00.0 |

GPU0 and GPU3 hold ~23 GB each — the NVLink Bridge A pair, consistent with a
resident vLLM `inference-pair-a` model.

API — `GET /status`:

```json
{"active_profile":null,"switching":false,"last_switched":null,"running_services":[],"gpus":[]}
```

API — `GET /api/metrics/gpu`:

```json
{"GPU0":{"vram_used_gb":0.0,"vram_total_gb":24.0,"utilization":0,"temp":0,"power_w":0,"active":false,"vram_history":[]}, ...}
```

All four GPUs report identical zeros and `active: false`.

## Findings

1. **`/status` returns `gpus: []`.** `get_gpu_info()` (`loadout-manager/main.py:85-116`)
   wraps its whole pynvml block in `try/except` and returns `[]` on any failure
   (`main.py:114-116`), logging `GPU info fetch failed`. An empty list is
   indistinguishable from "no GPUs" to the frontend, so `GpuCard` renders its
   skeleton branch (`ui/src/components/GpuCard.jsx:8-16`) rather than surfacing an error.

2. **`/api/metrics/gpu` reports structural zeros, not an error.** It returns a
   well-formed four-GPU object with every metric zeroed, which reads as "idle
   hardware" rather than "telemetry unavailable" — the more misleading of the two
   failure modes, and the one an operator would act on.

3. **Both endpoints fail while `nvidia-smi` succeeds on the host**, so the GPUs and
   the driver are healthy. The fault is pynvml inside the loadout-manager
   container, not the hardware. This is the same condition TASK-003 (#4) closed on
   2026-06-30; it is either regressed or was closed prematurely.

4. **`GpuCard` renders four fields the backend never emits.** `nvlink_bridge`,
   `claimed_by_profile`, `active_service` and `service_type` are read at
   `GpuCard.jsx:22-46,60-64,92-96`, but `get_gpu_info()` emits only `index`,
   `vram_used_gb`, `vram_total_gb`, `vram_free_gb`, `utilization_pct`, `temp_c`,
   `power_w` and `bus_id` (`main.py:103-112`). The bridge badge, claimed-GPU border
   and service tag are therefore permanently inert even once telemetry is restored.

## Not covered

Root-causing the pynvml failure inside the container needs `docker logs` /
`docker exec`, which the `nestled` account cannot do (not in the `docker` group).
Deferred rather than assumed.

## Verdict

TASK-010 fails. Fix the telemetry path before this validation can be re-run; the
widget-accuracy question is not answerable while the backend reports nothing.
Finding 4 is independent and actionable now.
