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

## Resolution

Branch `fix/gpu-telemetry-honesty`. Verified statically and with pynvml mocked; **not
verified against the live workstation**, so this doc's FAIL verdict stands until
TASK-010 is re-run on the host.

| Finding | Change |
| --- | --- |
| 1. Failure swallowed as `[]` | `get_gpu_telemetry()` in `loadout-manager/main.py` returns `available` / `gpus` / `error`. `/status` and `/health` keep `gpus` (always a list) and add `gpu_telemetry: {available, error}`. The error is `stage: ExceptionType: message` and is logged with a traceback on first occurrence and on change (repeats are re-logged every 5 min, recovery is logged). Zero visible devices is reported as unavailable, not as "no GPUs". `GpuStatusRow` / `GpuCard` render a distinct "Telemetry unavailable" card with the error instead of the skeleton. |
| 2. Fields the backend never emitted | Each GPU now carries `nvlink_bridge` (derived from the `inference-pair-a/b` profiles' `exclusive_gpus`, giving Bridge A = 0+3, Bridge B = 1+2), and `claimed_by_profile`, `active_service`, `service_type` from the active profile's `exclusive_gpus` / `gpu_assignment`. |
| 3. Container pynvml failure | Nothing in the Dockerfile, `requirements.txt` or `compose.loadout.yml` is evidently wrong (see hypotheses below), so none were changed. The `error` string is now readable via `curl /status`, which removes the need for `docker logs` access to root-cause it. |

### Not fixed here

- **`/api/metrics/gpu` still returns structural zeros.** It lives in
  `loadout-manager/api/metrics.py`, outside this change's scope. It also calls
  `nvmlInit()` once at import and latches `_NVML_OK`, so a container that started
  before NVML was usable stays "unavailable" until restarted. Needs its own fix.
- Claims describe the manager's own profile state, not observed processes. A GPU
  holding a model the manager does not know about (state lost, or a model started
  outside a profile switch, as in the observation above) shows VRAM but no claim.

### Remaining hypotheses for the container-side failure, most likely first

Both `/status` (per-call init) and `/api/metrics/gpu` (import-time init) failed
together, which points at NVML initialisation rather than a per-metric error. The
new `gpu_telemetry.error` will say which of these it is.

1. NVML not injected into the running container (`NVMLError_LibraryNotFound`): the
   container was created without the NVIDIA runtime taking effect, e.g. after a
   Docker or nvidia-container-toolkit change. Check
   `docker inspect loadout-manager --format '{{json .HostConfig.DeviceRequests}}'`
   and `docker exec loadout-manager ls /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1`.
   Fix: `docker compose -f docker/compose.loadout.yml up -d --force-recreate`.
2. Driver/library mismatch after a host driver update (`NVMLError_LibraryNotFound`
   or "Driver/library version mismatch"). Same remedy: recreate the container.
3. Stale or conflicting image: built before `nvidia-ml-py` replaced `pynvml==11.5.0`
   (`plan/steps/06-loadout-manager.md`), leaving both packages providing `pynvml`.
   Check `docker exec loadout-manager pip list | grep -i nvml`; rebuild the image.
4. Device cgroup / permission restriction on `/dev/nvidiactl` (`NVMLError_NoPermission`),
   e.g. rootless Docker or `no-cgroups = true` in the toolkit config.
5. A Python-level error inside the per-GPU query loop rather than at init. Unlikely
   given the above, and now reported as `query GPU <n>: <Type>: <message>`.

Unrelated defect noticed: the Dockerfile does not `COPY config.py`, which `api/*`
imports; the container only works because `compose.loadout.yml` bind-mounts
`../loadout-manager` over `/app`.
## Resolution (metrics API)

Addresses finding 2 and the import-time latch behind finding 3, in
`loadout-manager/api/metrics.py` only:

- NVML is now initialised lazily per request (`nvmlInit` ... `nvmlShutdown` in
  `finally`) with a 15 s retry backoff after a failure, so a driver that becomes
  healthy is picked up without restarting the container.
- `/api/metrics/gpu` adds top-level `available` (bool) and, when telemetry is
  missing or partial, `error` (`"<ExceptionType>: <msg>"`). The `GPU0..GPU3`
  keys are unchanged; unreadable GPUs report `null` metrics instead of zeros.
- `/api/metrics/system` returns `vram_used_gb: null` when NVML is unavailable.
- Failures are logged once per distinct error (repeated every ~5 min); recovery
  is logged at INFO.

Verified only against a mocked `pynvml`; not yet re-checked on the live
workstation. Finding 4 and the root cause of the in-container pynvml failure are
not addressed here.
