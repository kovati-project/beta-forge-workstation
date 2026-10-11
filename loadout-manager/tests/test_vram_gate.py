"""
TASK-025 / issue #15 — VRAM conflict gate.

Assertions are on HTTP status classes and on "was anything started", never on
message text. Tests marked xfail(strict=True) document defects found in the
current gate; they flip to failures (XPASS) the moment the defect is fixed, so
the marker must then be removed.
"""

import datetime as _dt

import pytest

# Profiles that declare vram_required_gb > 0 (the only ones the gate can act on).
GATED = [
    ("inference-4gpu", 88),
    ("dual-stack", 96),
    ("image-studio", 72),
    ("training-lora-image", 48),
    ("training-lora-text", 90),
    ("training-unsloth", 48),
    ("inference-4gpu-large", 96),
]


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
    lm.set_free([(required - 1) / 4] * 4)
    r = lm.activate(name)
    assert is_4xx(r)
    assert_nothing_happened(lm)


@pytest.mark.parametrize("name,required", GATED)
def test_exactly_at_requirement_is_accepted_and_starts(lm, name, required):
    # Boundary: the gate uses `free < required`, so free == required must pass.
    lm.set_free([required / 4] * 4)
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
    """A refused activation must not tear down what is currently running."""
    lm.make_active("inference-small")
    lm.set_free(10)
    r = lm.activate("dual-stack")
    assert is_4xx(r)
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


@pytest.mark.xfail(
    strict=True,
    reason="BUG-5: inference-small / inference-pair-a / inference-pair-b have no "
           "vram_required_gb, so the gate is skipped entirely and fails OPEN when "
           "telemetry is down (and cannot refuse on low VRAM at all).")
@pytest.mark.parametrize("name", ["inference-small", "inference-pair-a", "inference-pair-b"])
def test_telemetry_unavailable_fails_closed_without_declared_requirement(lm, name):
    lm.telemetry_down()
    r = lm.activate(name)
    assert is_4xx(r)
    assert lm.docker.starts == []


@pytest.mark.xfail(
    strict=True,
    reason="BUG-5: profiles without vram_required_gb are never refused for low VRAM.")
@pytest.mark.parametrize("name", ["inference-small", "inference-pair-a", "inference-pair-b"])
def test_low_vram_refused_without_declared_requirement(lm, name):
    lm.set_free(0.5)  # essentially no VRAM anywhere
    r = lm.activate(name)
    assert is_4xx(r)
    assert lm.docker.starts == []


# ── Defects in how the gate computes "available" ─────────────────────────────

@pytest.mark.xfail(
    strict=True,
    reason="BUG-3: gate sums free VRAM across ALL GPUs, not the profile's "
           "exclusive_gpus. training-unsloth owns GPU0+GPU3 but is admitted on "
           "the strength of free memory on GPU1+GPU2.")
def test_gate_counts_only_the_profiles_exclusive_gpus(lm):
    # unsloth: exclusive_gpus [0,3], needs 48. GPU0/3 have 5 free each (10),
    # GPU1/2 have 24 free each. Total 58 >= 48, but the GPUs it will use hold 10.
    lm.set_free([5, 24, 24, 5])
    r = lm.activate("training-unsloth")
    assert is_4xx(r)
    assert lm.docker.starts == []


@pytest.mark.xfail(
    strict=True,
    reason="BUG-4: gate runs BEFORE teardown, so VRAM held by the currently "
           "running profile (about to be stopped by the switch itself) counts "
           "as unavailable and legitimate switches are refused.")
@pytest.mark.parametrize("active,target", [
    ("inference-small", "image-studio"),         # the data's own 'compatible_with' pair
    ("training-lora-text", "training-lora-text"),  # plain restart of the active profile
])
def test_vram_held_by_the_outgoing_profile_does_not_block_the_switch(lm, active, target):
    lm.make_active(active)
    # The active profile's own containers are holding almost all VRAM.
    lm.set_free([1, 1, 1, 1])
    r = lm.activate(target)
    assert r.status_code == 200, "teardown would have freed this VRAM"


def test_four_gpu_profiles_need_zero_headroom_on_24gb_cards(lm):
    """
    Characterisation, not an assertion of correctness: dual-stack and
    inference-4gpu-large require 96 GB on a 4 x 24 GB box (every byte). Real
    idle GPUs never report their full capacity as free (driver/context
    reservation), so with realistic numbers these profiles are unreachable
    through the gate. Free figures below are illustrative, NOT measured.
    """
    lm.set_free([23.6] * 4)  # 94.4 GB free in total
    assert lm.activate("dual-stack").status_code == 409
    assert lm.activate("inference-4gpu-large").status_code == 409
    assert lm.docker.calls == []


# ── Gate is only on the HTTP path ────────────────────────────────────────────

class _FixedDatetime(_dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 1, 5, 3, 0, 0)  # a Monday, 03:00


class _StopLoop(Exception):
    pass


@pytest.mark.xfail(
    strict=True,
    reason="BUG-6: the VRAM gate lives only in POST /activate. Scheduled switches "
           "call do_switch() directly and bypass VRAM and compatibility checks.")
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

    assert lm.docker.starts == [], "scheduler started a profile that fails the VRAM gate"
