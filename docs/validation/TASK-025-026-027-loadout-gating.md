# TASK-025 / TASK-026 / TASK-027 (+ TASK-013 backend) — Loadout Manager switching gates

**Issues:** #15 (VRAM conflict gate), #16 (training-vs-inference incompatibility gate),
#17 (switch tears down previous services), #8 (switching-state flag, backend side)

**Result: MIXED — validated by mocked test, not against the live workstation.**

| Task | Issue | Result |
|------|-------|--------|
| TASK-025 VRAM conflict gate | #15 | **PARTIAL** — gate exists and fails closed for 7 of 11 profiles, but 3 profiles are ungated, it sums the wrong GPUs, and it runs before teardown |
| TASK-026 incompatibility gate | #16 | **FAIL** — `incompatible_with` is data only; **no backend code enforces it** |
| TASK-027 teardown on switch | #17 | **PASS with defects** — order and state are right on the happy path; failed stop/start handling is not |
| TASK-013 `switching` flag (backend) | #8 | **PASS** for flag logic (never stuck); was not observable by polling during a switch (BUG-10, fixed 2026-10-16 with BUG-11) |

## How this was tested

`loadout-manager/tests/` (pytest, 102 tests): `python -m pytest loadout-manager/tests -q`

```
74 passed, 28 xfailed in ~5s        (pytest 9.1.1, Python 3.14.3, run 3x, stable)
```

Every "defect" below is a test marked `xfail(strict=True)` with a `BUG-n` reason: the suite
is green, and each marker turns into a hard failure (XPASS) the moment the defect is fixed,
forcing the marker to be removed. Run `pytest --runxfail` to see the raw failures.

Mocking (all in `tests/conftest.py`):

- `pynvml` and `docker` are `sys.modules` stubs installed before `main` is imported; the stub
  NVML is driven per test (`set_free([...])`, init failure, zero devices, memory-query failure).
- `subprocess.run` is replaced by `FakeDocker`, which records every call (command, whether
  `state["switching"]` was set, whether it ran on the event loop) and never executes anything.
- `asyncio.sleep` as seen by `main` is replaced (the 3 s GPU-release pause costs nothing and
  tests can park a switch mid-transition).
- State and schedule files are redirected to a temp dir. Nothing touches `/data`.
- Assertions are on status codes and "was anything started / stopped", never on message text.

### What this cannot prove

- That real `docker compose` accepts the exact command lines (`up -d --remove-orphans <svc>`).
- BUG-9 (idle) models `docker compose up` with no `-f` and no compose file in cwd as exit 1.
  That is documented docker behaviour but was **not run on a host**.
- That real NVML reports numbers like the stub's; the "96 GB needs zero headroom" note uses
  illustrative, not measured, free-memory figures.
- Partial-start behaviour of a real `compose up` (BUG-8 is inferred from how compose works,
  tested only as "no cleanup `down` is issued after a failed `up`").
- Anything about the UI beyond reading `ProfileCard.jsx`/`ProfileGrid.jsx`.
- Real timings, load, or multi-worker deployments.

## 1. VRAM gate (#15 / TASK-025)

Gate lives in `activate_profile` (`main.py`): if `vram_required_gb` is present, sum
`vram_free_gb` over **all** GPUs and return 409 if below the requirement.

What works (tests passing):

- Insufficient VRAM -> 409, **zero docker calls**, state untouched, a running profile is not
  disturbed by a refused activation.
- Boundary: `free == required` passes, `free == required - 1` is refused, for all 7 profiles
  that declare a requirement (28 parametrised cases).
- Sufficient VRAM -> 200 and the correct compose file + service list is started.
- Telemetry unavailable (NVML init failure, zero devices, memory query failure) -> **fails
  closed** (409, nothing started) for the 7 gated profiles; `idle` (requirement 0) stays
  reachable.

Defects (xfail strict):

| ID | Defect | Evidence | Proposed fix |
|----|--------|----------|--------------|
| BUG-3 | Gate sums free VRAM across **all** GPUs, not the profile's `exclusive_gpus`. `training-unsloth` (GPU0+GPU3, 48 GB) is admitted with 5 GB free on each of its GPUs because GPU1+GPU2 are empty (total 58 >= 48). | `test_gate_counts_only_the_profiles_exclusive_gpus` | Sum `vram_free_gb` only for `index in exclusive_gpus` (note `exclusive_gpus` entries are strings in YAML, indices are ints). |
| BUG-4 | Gate runs **before** teardown, so VRAM held by the profile being replaced counts as unavailable. `inference-small -> image-studio` (the YAML's own `compatible_with` pair) and a plain restart of `training-lora-text` are refused with 409 although `down` would free the memory. User must `/stop` first. | `test_vram_held_by_the_outgoing_profile_does_not_block_the_switch` (2 cases) | Either credit back VRAM used by the stacks about to be stopped, or perform the check inside `do_switch` after `stop_all_services()`+settle and fail the switch cleanly. |
| BUG-5 | `inference-small`, `inference-pair-a`, `inference-pair-b` have **no** `vram_required_gb`; `"vram_required_gb" in profile` is False so the gate is skipped. They are never refused for low VRAM and **fail open** with telemetry down. | `test_telemetry_unavailable_fails_closed_without_declared_requirement`, `test_low_vram_refused_without_declared_requirement` (3 cases each) | Declare a requirement for all three profiles; treat a missing key as "unknown -> refuse when telemetry is down" rather than "skip". |
| BUG-6 | The gate is only on `POST /activate`. The scheduler calls `do_switch()` directly: a 03:00 schedule entry for `training-lora-text` with 1 GB free started `axolotl`. Any future incompatibility gate placed in the endpoint has the same hole. | `test_scheduled_switch_is_subject_to_the_vram_gate` | Move gate checks into a shared `validate_activation(profile)` called by both the endpoint and the scheduler (and by `do_switch`). |

Observation (characterisation test, green): `dual-stack` and `inference-4gpu-large` require
96 GB on a 4 x 24 GB machine, i.e. every byte, with zero headroom. Real idle GPUs reserve
some memory, so with realistic free figures these profiles would be refused by the gate
forever. Worth measuring on the host (`nvidia-smi` free on an idle card) before trusting the
96 figure; the test uses 23.6 GB/GPU purely as an illustration.

Minor: `get_gpu_info` divides by `1024**3` but labels the result `_gb`; the YAML requirements
are presumably GB. On 24 GB cards the units differ by ~7%.

## 2. Incompatibility gate (#16 / TASK-026)

**Key finding: `incompatible_with` is exposed as data only. Nothing in `main.py` or `api/`
reads it except `list_loadouts` (`main.py:287`).** The only "enforcement" is client-side:
`ui/src/components/ProfileGrid.jsx` computes `isIncompatible` and `ProfileCard.jsx` disables
the button. A direct `curl -X POST /activate/...`, another client, or a schedule entry is not
checked.

Evidence:

- `test_listing_exposes_incompatible_with_from_yaml` (pass): the listing returns the YAML
  lists faithfully for all 11 profiles.
- `test_incompatible_activation_is_refused_and_starts_nothing` (xfail, 6 cases): inference ->
  training, training -> inference, and the GPU0/3 and GPU1/2 overlap cases are all **accepted
  (200)** and proceed to tear down the active profile and start the new one.
- `test_every_declared_incompatible_pair_is_refused` (xfail): **68 of 68** declared
  `(active, target)` pairs are accepted.

Semantic wrinkle worth a decision before implementing the fix: because every switch runs
`down` on all three managed stacks, "activate B while A is active" is really "replace A with
B", never co-existence. For a replace-style switch an incompatibility gate is arguably moot
(A is gone before B starts). Either the gate is meant to force an explicit `/stop` first
(then enforce it), or `incompatible_with` should be dropped from the API in favour of the
VRAM/GPU check. As written, `compatible_with` ("can run simultaneously", plan step 06) is
**unrealisable** through `/activate`: `test_compatible_with_cannot_be_honoured_because_every_switch_tears_down`
shows activating `image-studio` over `inference-small` stops `inference-small`.

Data quality (found while writing the tests):

| ID | Defect | Evidence |
|----|--------|----------|
| BUG-1 | Not enforced in code (above). | 7 xfail cases |
| BUG-2a | **8 one-way declarations**: e.g. `training-unsloth` lists `inference-small` but `inference-small` lists nothing (both own GPU0+GPU3); `inference-pair-a`/`inference-4gpu`/`dual-stack`/`training-lora-text`/`inference-4gpu-large` -> `inference-small`; `inference-pair-a` -> `training-lora-image`; `training-unsloth` -> `training-lora-text`. A gate (or the UI) reading only the target's list lets `inference-small` be activated over `training-unsloth`. | `test_incompatible_with_is_symmetric`, `test_reverse_direction_of_an_asymmetric_pair_is_also_refused` |
| BUG-2b | `inference-small` and `image-studio` are mutually `compatible_with` yet both claim exclusive GPU0. | `test_compatible_with_pairs_do_not_share_exclusive_gpus` |
| obs | Exclusive-GPU overlap not declared incompatible in either direction: `inference-small`/`image-studio`, `inference-pair-a`/`image-studio` (GPU0), `image-studio`/`training-unsloth` (GPU0). `inference-pair-a` also runs ollama on GPU1 which is not in its `exclusive_gpus`. | profile analysis script, see Findings |

Green (stays green once a gate exists): `inference-small <-> training-lora-image` and
`training-unsloth -> inference-pair-b` (disjoint GPUs, undeclared both ways) are accepted;
no profile lists itself; all references resolve to existing profiles; re-activating the
active profile is accepted and behaves as a restart (3 x `down`, 1 x `up`), which is a
sensible reading, subject to BUG-4.

**Proposed fix for BUG-1/2:** derive incompatibility from the *symmetric closure* of
`incompatible_with` plus any `exclusive_gpus` overlap, evaluate it in the same shared
`validate_activation()` used by the endpoint and scheduler, return 409.

## 3. Teardown on switch and the `switching` flag (#17 / TASK-027, #8 / TASK-013)

Passing (happy path):

- A -> B (4 pairs, incl. training <-> inference and a 2-compose-file profile): every compose
  file of A is brought `down` strictly before B's `up`; `up` carries B's `-f` files and exact
  service list.
- All three managed stacks are brought down on every switch (3 x `down`: inference,
  training, studio) regardless of what A was.
- State after success: `active_profile`, `running_services`, `last_switched` (advanced)
  correct in `/status`, `/loadouts`, and persisted to `state.json` without `switching`.
- `switching` is True for all 4 docker calls and False afterwards; `/ws` events are exactly
  `[switching=True, switching=False(new profile)]`.
- **Flag is never stuck**: not on `up` returning non-zero, `up` timing out, docker binary
  missing, a dead websocket client, or an unwritable state file. A persisted `switching: true`
  is not restored after restart.
- Failed start leaves internally consistent state: `active_profile=None`,
  `running_services=[]`, persisted, closing event pushed, and the switch can be retried.
- Concurrency: with a switch parked mid-transition, `/status` shows `switching: true`,
  a second `POST /activate/...` and `POST /stop` both get **409** and issue no docker call;
  the first switch then completes and wins.
- Edge cases: unknown profile -> 404 with no docker call and no state/event change (also
  while switching); `/stop` tears down all three stacks and clears state; `idle` activation
  tears down all stacks.

Defects (xfail strict):

| ID | Defect | Evidence | Proposed fix |
|----|--------|----------|--------------|
| BUG-7 | `stop_all_services()` ignores `returncode` and swallows `TimeoutExpired`; it logs "Stopped" regardless and the switch proceeds to `up` over a stack that may still be running (VRAM conflict is exactly what the gates exist to prevent). | `test_switch_does_not_start_new_profile_if_teardown_failed` (2 cases) | Return success/failure from `stop_all_services`; abort the switch (state unchanged or `error`) when a `down` fails. `/stop` should return 5xx rather than 200 in that case. |
| BUG-8 | Failed/timed-out `up` leaves no cleanup. Multi-service profiles (`dual-stack`) can have started `vllm-pair-a` before `pair-b` fails; state then says `running_services: []` while containers hold VRAM. Also no error is surfaced anywhere: POST already returned 200, status shows only `active_profile: null`. | `test_failed_start_triggers_cleanup_of_partially_started_services` (2 cases) | After a failed `up`, run `stop_all_services()` and record a `last_error` in state/event. |
| BUG-9 | `idle` has `compose_files: []`, `services: []`, so the command becomes `docker compose up -d --remove-orphans` with no `-f`. It fails (no compose file in cwd `/app`) and the switch is recorded as a failure: `active_profile` ends `None`, not `idle`. If cwd ever contains a compose file it would start its default services. (Docker behaviour modelled, not verified on host.) | `test_idle_never_issues_a_bare_compose_up`, `test_idle_becomes_the_active_profile` | In `do_switch`, skip `up` when `services` is empty; set `active_profile = name` after teardown. |
| BUG-10 | `do_switch` is `async` but calls blocking `subprocess.run` directly (3 x `down` at up to 60 s, `up` at up to 120 s). The event loop is frozen for the whole transition: `/status`, `/health`, `/ws` heartbeats stop. With 4 x 150 ms fake calls the loop was blocked 0.62 s contiguous. The `switching` flag is True but cannot be *read* by a polling UI (the 1 s poll in the UI never sees it until the end), which defeats the point of #8. | `test_event_loop_stays_responsive_during_switch` | `await asyncio.to_thread(subprocess.run, ...)` (or `run_in_executor`) for both `stop_all_services` and `up`. |
| BUG-11 | `switching=True` is set inside the background task, not when `/activate` accepts the request. Two back-to-back activations are both accepted (`[200, 200]`, deterministic in the harness): first switch is wasted and the second wins. Today they run sequentially only because of BUG-10; **fixing BUG-10 without fixing this turns it into interleaved switches** (second `down` kills the first `up`). | `test_two_back_to_back_activations_cannot_both_be_accepted` | Set `state["switching"] = True` synchronously in `activate_profile` (and the scheduler) before scheduling the task, clear it in `do_switch`'s `finally`. |

Observation (no test, judgement call): while a switch is in flight `active_profile` still
reports the *outgoing* profile, even though its stacks were already stopped. A UI showing
"A active, switching" is momentarily untrue. Consider reporting `active_profile: null` (or a
`switching_to` field) once teardown begins.

## Findings summary

1. **#16 incompatibility gate does not exist server-side.** Highest-severity item; only the
   UI hides the buttons.
2. The VRAM gate exists and fails closed, but it is measuring the wrong thing (all GPUs, before
   teardown) and skips 3 profiles; a scheduled switch bypasses it entirely.
3. The switch/teardown core is sound on the happy path and the `switching` flag is robust,
   but a failed `down` is ignored, a failed `up` leaves orphans, `idle` cannot be activated,
   and the blocking docker calls make the flag invisible to pollers.
4. `profiles.yaml` has 8 one-way incompatibility declarations and one compatible pair that
   shares an exclusive GPU.
5. BUG-10 and BUG-11 must be fixed together or the second makes the first worse.
   **Fixed together (2026-10-16, branch `fix/switch-off-event-loop`):** docker calls run via
   `asyncio.to_thread`; `/activate`, `/stop` and the scheduler claim the `switching` slot
   synchronously (`_claim_switch()`) before any await. Their tests are now plain tests, plus
   `test_no_docker_call_runs_on_the_event_loop` and `test_stop_and_activate_cannot_both_be_accepted`.

Test-to-source coupling (so a refactor knows what these tests depend on): routes `/activate`,
`/stop`, `/status`, `/loadouts`; `state` dict keys; `main.subprocess.run`; `main.asyncio.sleep`
/ `create_task` / `to_thread`; `main.stop_all_services`; `main.STATE_PATH`, `load_state`, `scheduler_loop`, `schedule`, `_last_fired`,
`datetime`, `_ws_clients`. Message strings are deliberately not asserted.

## Verdict

#16 fails (not implemented), #15 is partial, #17 and the #8 backend flag pass their core
behaviour but with 5 defects around failure handling and loop blocking. None of this was
exercised on the live workstation: the mock results justify the proposed fixes but a
hardware smoke test (activate each profile from each other, with a deliberate `down`
failure and a deliberate port conflict on `up`) is still required to close the issues.
