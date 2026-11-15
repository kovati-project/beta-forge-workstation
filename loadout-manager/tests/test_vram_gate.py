"""
TASK-025 / issue #15 — VRAM conflict gate.

Assertions are on HTTP status classes and on "was anything started", never on
message text. The BUG-3..BUG-6 tests were strict xfails documenting defects in
the original gate; they are plain tests now that the defects are fixed.

The gate counts free VRAM on the profile's own exclusive_gpus only (BUG-3), so
boundary tests put the free memory on those GPUs and fill the others with
memory the gate must ignore.

The free-memory check credits a driver reserve per GPU (an empty card never
reports all its memory free), so the boundary is
`required - RESERVE * len(exclusive_gpus)`. The reserve is pinned here so an
environment override cannot move the boundaries.
"""

import datetime as _dt

import pytest

RESERVE = 0.5


@pytest.fixture(autouse=True)
def _pin_reserve(lm, monkeypatch):
    monkeypatch.setattr(lm.main, "VRAM_RESERVE_GB_PER_GPU", RESERVE)


def threshold(h, name, required):
    """Least free VRAM (summed over the profile's GPUs) the gate accepts."""
    return required - RESERVE * len(h.profiles[name]["exclusive_gpus"])


def set_free_after_down(h, free_gb):
    """Model teardown freeing memory: the first `down` changes what NVML reports."""
    def rule(c):
        if c.verb == "down":
            h.set_free(free_gb)
    h.docker.rules.append(rule)

# Profiles that declare vram_required_gb > 0. Every GPU profile does (BUG-5).
GATED = [
    ("inference-small", 16),
    ("inference-pair-a", 44),
    ("inference-pair-b", 44),
    ("inference-4gpu", 88),
    ("dual-stack", 96),
    ("image-studio", 72),
    ("training-lora-image", 48),
    ("training-lora-text", 90),
    ("training-unsloth", 48),
    ("inference-4gpu-large", 96),
]


def free_on_own_gpus(h, name, per_profile_total, elsewhere):
    """Spread `per_profile_total` GiB evenly over the profile's exclusive GPUs;
    every other GPU reports `elsewhere` GiB free."""
    own = [int(i) for i in h.profiles[name]["exclusive_gpus"]]
    h.set_free([per_profile_total / len(own) if i in own else elsewhere
                for i in range(4)])


def is_4xx(resp):
    return 400 <= resp.status_code < 500


def assert_nothing_happened(h):
    """Refused activation: no docker call at all, state untouched."""
    assert h.docker.calls == [], f"unexpected docker calls: {h.docker.calls}"
    assert h.state["switching"] is False
    assert h.state["active_profile"] is None
    assert h.state["running_services"] == []


# ── Core gate behaviour ──────────────────────────────────────────────────────

def test_insufficient_vram_is_refused_and_starts_nothing(lm):
    lm.set_free(10)  # 40 GiB free in total; training-lora-text needs 90
    r = lm.activate("training-lora-text")
    assert is_4xx(r), r.text
    assert r.status_code == 409
    assert_nothing_happened(lm)


@pytest.mark.parametrize("name,required", GATED)
def test_just_below_requirement_is_refused(lm, name, required):
    # Other GPUs fully free: their memory must not count towards the requirement.
    # 0.4 below the boundary keeps clear of the 0.1 GB rounding in telemetry.
    free_on_own_gpus(lm, name, threshold(lm, name, required) - 0.4, elsewhere=24)
    r = lm.activate(name)
    assert is_4xx(r)
    assert_nothing_happened(lm)


@pytest.mark.parametrize("name,required", GATED)
def test_exactly_at_requirement_is_accepted_and_starts(lm, name, required):
    # Boundary: the gate refuses `free + reserve < required`, so free exactly at
    # the threshold must pass, with nothing free on the GPUs the profile does not use.
    free_on_own_gpus(lm, name, threshold(lm, name, required), elsewhere=0)
    r = lm.activate(name)
    assert r.status_code == 200, r.text
    assert lm.docker.starts, "an accepted activation must start the profile"
    assert lm.state["active_profile"] == name
    assert lm.state["switching"] is False


def test_sufficient_vram_passes_and_requested_services_started(lm):
    lm.set_free(24)
    r = lm.activate("training-lora-text")
    assert r.status_code == 200
    (up,) = lm.docker.starts
    assert up.cmd[-1] == "axolotl"
    assert up.compose_files == ["compose.training.yml"]


def test_refusal_does_not_disturb_a_running_profile(lm):
    """A VRAM refusal must not tear down what is currently running. The pair is
    compatible, so only the VRAM gate can refuse it: on 16 GB cards
    training-lora-image's 48 GB cannot fit on GPU1+GPU2."""
    assert "inference-small" not in lm.profiles["training-lora-image"].get("incompatible_with", [])
    assert "training-lora-image" not in lm.profiles["inference-small"].get("incompatible_with", [])
    lm.make_active("inference-small")
    lm.set_free(10, total_gb=16.0)
    r = lm.activate("training-lora-image")
    assert r.status_code == 409
    assert lm.docker.calls == []
    assert lm.state["active_profile"] == "inference-small"
    assert lm.state["running_services"] == ["ollama"]


# ── Telemetry unavailable ────────────────────────────────────────────────────

def _break_nvml(h, mode):
    if mode == "init_fails":
        h.nvml.init_error = RuntimeError("NVML Shared Library Not Found")
    elif mode == "no_devices":
        h.nvml.devices = []
    elif mode == "memory_query_fails":
        h.nvml.memory_error = RuntimeError("GPU is lost")


@pytest.mark.parametrize("mode", ["init_fails", "no_devices", "memory_query_fails"])
@pytest.mark.parametrize("name,_required", GATED)
def test_telemetry_unavailable_fails_closed_for_gated_profiles(lm, name, _required, mode):
    _break_nvml(lm, mode)
    r = lm.activate(name)
    assert is_4xx(r)
    assert_nothing_happened(lm)


def test_idle_is_not_blocked_by_missing_telemetry(lm):
    """idle declares vram_required_gb: 0 — it must stay reachable with NVML down."""
    lm.telemetry_down()
    assert lm.activate("idle").status_code == 200


@pytest.mark.parametrize("name", ["inference-small", "inference-pair-a", "inference-pair-b"])
def test_telemetry_unavailable_fails_closed_without_declared_requirement(lm, name):
    lm.telemetry_down()
    r = lm.activate(name)
    assert is_4xx(r)
    assert lm.docker.starts == []


@pytest.mark.parametrize("name", ["inference-small", "inference-pair-a", "inference-pair-b"])
def test_low_vram_refused_without_declared_requirement(lm, name):
    lm.set_free(0.5)  # essentially no VRAM anywhere
    r = lm.activate(name)
    assert is_4xx(r)
    assert lm.docker.starts == []


# ── Defects in how the gate computes "available" ─────────────────────────────

def test_gate_counts_only_the_profiles_exclusive_gpus(lm):
    # unsloth: exclusive_gpus [0,3], needs 48. GPU0/3 have 5 free each (10),
    # GPU1/2 have 24 free each. Total 58 >= 48, but the GPUs it will use hold 10.
    lm.set_free([5, 24, 24, 5])
    r = lm.activate("training-unsloth")
    assert is_4xx(r)
    assert lm.docker.starts == []


@pytest.mark.parametrize("active,target", [
    ("inference-small", "image-studio"),         # the data's own 'compatible_with' pair
    ("training-lora-text", "training-lora-text"),  # plain restart of the active profile
])
def test_vram_held_by_the_outgoing_profile_does_not_block_the_switch(lm, active, target):
    lm.make_active(active)
    # The active profile's own containers are holding almost all VRAM...
    lm.set_free([1, 1, 1, 1])
    # ...and teardown frees it.
    set_free_after_down(lm, 24)
    r = lm.activate(target)
    assert r.status_code == 200, "teardown would have freed this VRAM"
    assert len(lm.docker.starts) == 1
    assert lm.state["active_profile"] == target
    assert lm.state["last_error"] is None


@pytest.mark.parametrize("name", ["dual-stack", "inference-4gpu-large"])
def test_whole_card_requirements_are_reachable_on_empty_cards(lm, name):
    """
    dual-stack and inference-4gpu-large require 96 GB on a 4 x 24 GB box (every
    byte). Empty cards never report all of it free; the driver reserve credit
    makes them reachable. Free figures are illustrative, NOT measured.
    """
    lm.set_free([23.6] * 4)  # 94.4 free + 4 x 0.5 reserve >= 96
    assert lm.activate(name).status_code == 200
    assert lm.state["active_profile"] == name


@pytest.mark.parametrize("name", ["dual-stack", "inference-4gpu-large"])
def test_whole_card_requirements_refuse_more_than_the_reserve_in_use(lm, name):
    lm.set_free([23.4] * 4)  # 0.6 GB/card in use: more than the reserve
    assert lm.activate(name).status_code == 409
    assert lm.docker.calls == []


def test_restart_of_a_96gb_profile_succeeds_with_realistic_free_memory(lm):
    """Review item 5: the capacity pre-check and the post-teardown check must
    agree, or a 96 GB switch tears down the running profile and is then always
    refused."""
    lm.make_active("dual-stack")
    lm.set_free(1)
    set_free_after_down(lm, 23.6)  # what an empty 24 GB card typically reports
    assert lm.activate("dual-stack").status_code == 200
    assert len(lm.docker.starts) == 1
    assert lm.state["active_profile"] == "dual-stack"


def test_outgoing_profile_still_holding_vram_after_teardown_aborts_the_start(lm):
    """BUG-4 counterpart: with a profile running, the endpoint cannot know how
    much VRAM teardown will free, so it accepts and do_switch re-checks after
    teardown. If the memory is still taken then, nothing is started."""
    lm.make_active("inference-small")
    lm.set_free([1, 1, 1, 1])  # and it stays taken after `down`
    assert lm.activate("image-studio").status_code == 200
    assert len(lm.docker.downs) == 3
    assert lm.docker.starts == []
    assert lm.state["active_profile"] is None
    assert lm.state["running_services"] == []
    assert lm.state["last_error"]
    assert lm.state["switching"] is False


# ── Scheduled switches go through the same gate (BUG-6) ──────────────────────

class _FixedDatetime(_dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 1, 5, 3, 0, 0)  # a Monday, 03:00


class _StopLoop(Exception):
    pass


@pytest.mark.anyio
async def test_scheduled_switch_is_subject_to_the_vram_gate(lm, monkeypatch):
    import asyncio as real_asyncio
    main = lm.main
    lm.set_free(1)  # nowhere near the 90 GB training-lora-text needs
    monkeypatch.setattr(main, "datetime", _FixedDatetime)
    monkeypatch.setattr(main, "schedule", [{
        "id": "sch-test", "profile": "training-lora-text",
        "time": "03:00", "days": None, "enabled": True}])
    main._last_fired.clear()

    async def sleep(delay):
        if delay == 30:                # the scheduler loop's own cadence: stop after one pass
            raise _StopLoop()

    lm.sleep_hook = sleep

    with pytest.raises(_StopLoop):
        await main.scheduler_loop()
    await real_asyncio.gather(*lm.tasks)

    # No docker call at all: refused before teardown, not aborted after it.
    assert lm.docker.calls == [], "scheduler acted on a profile that fails the VRAM gate"
    assert lm.state["active_profile"] is None


async def _run_one_scheduler_pass(lm, monkeypatch, profile):
    import asyncio as real_asyncio
    main = lm.main
    monkeypatch.setattr(main, "datetime", _FixedDatetime)
    monkeypatch.setattr(main, "schedule", [{
        "id": "sch-test", "profile": profile,
        "time": "03:00", "days": None, "enabled": True}])
    main._last_fired.clear()

    async def sleep(delay):
        if delay == 30:
            raise _StopLoop()

    lm.sleep_hook = sleep
    with pytest.raises(_StopLoop):
        await main.scheduler_loop()
    await real_asyncio.gather(*lm.tasks)


@pytest.mark.anyio
async def test_scheduled_switch_is_subject_to_the_incompatibility_gate(lm, monkeypatch):
    lm.make_active("inference-4gpu")  # declared incompatible with training-lora-text
    await _run_one_scheduler_pass(lm, monkeypatch, "training-lora-text")
    assert lm.docker.calls == [], "scheduler tore down / started across an incompatible pair"
    assert lm.state["active_profile"] == "inference-4gpu"


@pytest.mark.anyio
async def test_scheduled_switch_that_passes_the_gates_still_runs(lm, monkeypatch):
    await _run_one_scheduler_pass(lm, monkeypatch, "training-lora-text")
    assert len(lm.docker.starts) == 1
    assert lm.state["active_profile"] == "training-lora-text"
