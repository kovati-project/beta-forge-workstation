"""
TASK-027 / issue #17 — a switch tears down the previous profile's services.
TASK-013 / issue #8  — backend side of the `switching` flag and transitions.

Mechanics under test (main.py): POST /activate/{name} -> background do_switch():
  switching=True -> stop_all_services() (docker compose down x3) -> sleep(3)
  -> docker compose up -d --remove-orphans <services> -> state update
  -> switching=False (finally).

TestClient runs the background task to completion before the POST returns, so
"during the transition" is observed from inside the fake subprocess (Call.switching),
from the pushed /ws events, and, for true concurrency, via async tests that park
the switch mid-flight.
"""

import asyncio
import json
import subprocess
import time

import pytest

ALL_COMPOSE = {"compose.inference.yml", "compose.training.yml", "compose.studio.yml"}


def is_4xx(resp):
    return 400 <= resp.status_code < 500


# ── Teardown ordering and state update ───────────────────────────────────────

@pytest.mark.parametrize("a,b", [
    ("inference-small", "training-lora-image"),
    ("training-lora-text", "inference-4gpu"),
    ("image-studio", "training-unsloth"),
    ("dual-stack", "inference-pair-b"),
])
def test_switch_stops_previous_stacks_before_starting_the_new_profile(lm, a, b):
    lm.make_active(a)
    r = lm.activate(b)
    assert r.status_code == 200, r.text

    (up,) = lm.docker.starts
    downs = lm.docker.downs
    # Every compose file the OUTGOING profile used was taken down...
    stopped_files = {f for c in downs for f in c.compose_files}
    assert set(lm.profiles[a]["compose_files"]) <= stopped_files
    # ...and every stop happened strictly before the start.
    assert downs and all(c.seq < up.seq for c in downs)

    # The new profile is what was started.
    assert up.compose_files == lm.profiles[b]["compose_files"]
    assert up.cmd[-len(lm.profiles[b]["services"]):] == lm.profiles[b]["services"]


def test_switch_stops_all_three_managed_stacks(lm):
    lm.make_active("inference-small")
    lm.activate("training-lora-image")
    assert {f for c in lm.docker.downs for f in c.compose_files} == ALL_COMPOSE
    assert len(lm.docker.downs) == 3


def test_state_after_successful_switch(lm, main_module):
    lm.make_active("inference-small")
    before = lm.state["last_switched"]
    assert lm.activate("training-lora-image").status_code == 200

    s = lm.client.get("/status").json()
    assert s["active_profile"] == "training-lora-image"
    assert s["running_services"] == ["kohya", "label-studio"]
    assert s["switching"] is False
    assert s["last_switched"] > before

    # Persisted for restart, and `switching` is deliberately not persisted.
    saved = json.loads(main_module.STATE_PATH.read_text())
    assert saved["active_profile"] == "training-lora-image"
    assert saved["running_services"] == ["kohya", "label-studio"]
    assert "switching" not in saved


def test_listing_reflects_new_active_profile(lm):
    lm.make_active("inference-small")
    lm.activate("training-lora-image")
    body = lm.client.get("/loadouts").json()
    assert [n for n, p in body.items() if p["active"]] == ["training-lora-image"]


# ── `switching` flag ─────────────────────────────────────────────────────────

def test_switching_true_for_every_docker_call_and_false_afterwards(lm):
    lm.make_active("inference-small")
    assert lm.state["switching"] is False
    lm.activate("training-lora-image")
    assert len(lm.docker.calls) == 4  # 3 x down + 1 x up
    assert all(c.switching is True for c in lm.docker.calls)
    assert lm.state["switching"] is False


def test_ws_events_bracket_the_transition(lm):
    lm.make_active("inference-small")
    lm.activate("training-lora-image")
    ev = lm.ws.events
    assert [e["switching"] for e in ev] == [True, False]
    # Opening event: flag raised. Closing event: flag lowered, new profile visible.
    assert ev[-1]["active_profile"] == "training-lora-image"
    assert ev[-1]["running_services"] == ["kohya", "label-studio"]


def test_dead_websocket_client_cannot_wedge_the_flag(lm):
    lm.add_ws(fail=True)
    lm.activate("training-lora-image")
    assert lm.state["switching"] is False
    assert lm.state["active_profile"] == "training-lora-image"


def test_unwritable_state_file_cannot_wedge_the_flag(lm, monkeypatch, tmp_path):
    blocker = tmp_path / "file-not-dir"
    blocker.write_text("x")
    monkeypatch.setattr(lm.main, "STATE_PATH", blocker / "state.json")
    assert lm.activate("training-lora-image").status_code == 200
    assert lm.state["switching"] is False
    assert lm.state["active_profile"] == "training-lora-image"


def test_persisted_switching_true_is_not_restored_after_restart(lm, tmp_path, monkeypatch):
    p = tmp_path / "persisted.json"
    p.write_text(json.dumps({"active_profile": "inference-small", "switching": True,
                             "last_switched": 5.0, "running_services": ["ollama"]}))
    monkeypatch.setattr(lm.main, "STATE_PATH", p)
    lm.main.load_state()
    assert lm.state["switching"] is False
    assert lm.state["active_profile"] == "inference-small"


# ── Failure paths ────────────────────────────────────────────────────────────

FAILURES = {
    "up_nonzero_rc": lambda d: d.fail("up", rc=1, stderr="port already allocated"),
    "up_timeout": lambda d: d.raise_on("up", subprocess.TimeoutExpired("docker", 120)),
    "docker_binary_missing": lambda d: d.raise_on("up", FileNotFoundError("docker")),
}


@pytest.mark.parametrize("mode", FAILURES)
def test_failed_start_leaves_flag_and_state_consistent(lm, mode, main_module):
    FAILURES[mode](lm.docker)
    lm.make_active("inference-small")
    r = lm.activate("training-lora-image")

    # Accepted at the door: failure is only visible afterwards, through state.
    assert r.status_code == 200
    # The flag is NOT stuck.
    assert lm.state["switching"] is False
    assert lm.client.get("/status").json()["switching"] is False
    # Old profile was already torn down, new one never came up: nothing active.
    assert lm.state["active_profile"] is None
    assert lm.state["running_services"] == []
    saved = json.loads(main_module.STATE_PATH.read_text())
    assert saved["active_profile"] is None
    assert saved["running_services"] == []
    # Closing event pushed so clients can leave the "switching" UI.
    assert lm.ws.events[-1]["switching"] is False
    assert lm.ws.events[-1]["active_profile"] is None


def test_failed_switch_can_be_retried(lm):
    lm.docker.fail("up")
    assert lm.activate("training-lora-image").status_code == 200
    assert lm.state["active_profile"] is None
    lm.docker.rules.clear()
    assert lm.activate("training-lora-image").status_code == 200
    assert lm.state["active_profile"] == "training-lora-image"


@pytest.mark.xfail(
    strict=True,
    reason="BUG-8: when `up -d` fails part-way (multi-service profiles start some "
           "containers before one fails; a timeout kills the CLI mid-start) nothing "
           "cleans up. State says running_services == [] while containers run, "
           "holding VRAM and invisible to the manager.")
@pytest.mark.parametrize("mode", ["up_nonzero_rc", "up_timeout"])
def test_failed_start_triggers_cleanup_of_partially_started_services(lm, mode):
    FAILURES[mode](lm.docker)
    lm.activate("dual-stack")
    (up,) = lm.docker.starts
    cleanup = [c for c in lm.docker.downs if c.seq > up.seq]
    assert cleanup, "state was reset to 'nothing running' but no `down` followed the failed `up`"


@pytest.mark.xfail(
    strict=True,
    reason="BUG-7: stop_all_services() ignores returncode and swallows timeouts; "
           "the switch proceeds to `up` on top of a stack that may still be "
           "running (logs even say 'Stopped').")
@pytest.mark.parametrize("how", ["nonzero_rc", "timeout"])
def test_switch_does_not_start_new_profile_if_teardown_failed(lm, how):
    if how == "nonzero_rc":
        lm.docker.fail("down", rc=1, stderr="cannot stop container")
    else:
        lm.docker.raise_on("down", subprocess.TimeoutExpired("docker", 60))
    lm.make_active("inference-4gpu")
    lm.activate("training-lora-text")
    assert lm.docker.starts == []


# ── Event loop ───────────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_event_loop_stays_responsive_during_switch(lm, async_client):
    lm.docker.delay = 0.15  # each fake docker call blocks for 150 ms

    max_gap = 0.0
    stop = False

    async def heartbeat():
        nonlocal max_gap
        last = time.monotonic()
        while not stop:
            await asyncio.sleep(0.01)
            now = time.monotonic()
            max_gap = max(max_gap, now - last)
            last = now

    hb = asyncio.create_task(heartbeat())
    await asyncio.sleep(0.05)
    r = await async_client.post("/activate/training-lora-image")
    stop = True
    await hb

    assert r.status_code == 200
    assert max_gap < 0.1, f"event loop was blocked for {max_gap:.2f}s during the switch"


# ── Concurrency / rejection while switching ──────────────────────────────────

@pytest.mark.anyio
async def test_activation_and_stop_are_rejected_while_switching(lm, async_client):
    parked = asyncio.Event()
    release = asyncio.Event()

    async def sleep(delay):
        parked.set()
        await release.wait()
    lm.sleep_hook = sleep

    first = asyncio.create_task(async_client.post("/activate/training-lora-image"))
    await asyncio.wait_for(parked.wait(), 5)

    # Mid-transition: flag is up and visible to a second client.
    s = (await async_client.get("/status")).json()
    assert s["switching"] is True

    calls_before = len(lm.docker.calls)
    r2 = await async_client.post("/activate/inference-small")
    assert is_4xx(r2)
    assert r2.status_code == 409
    r3 = await async_client.post("/stop")
    assert r3.status_code == 409
    assert len(lm.docker.calls) == calls_before, "rejected requests must not touch docker"

    release.set()
    r1 = await asyncio.wait_for(first, 5)
    assert r1.status_code == 200
    assert lm.state["switching"] is False
    assert lm.state["active_profile"] == "training-lora-image"  # the 2nd request did not win
    assert len(lm.docker.starts) == 1


@pytest.mark.anyio
async def test_two_back_to_back_activations_cannot_both_be_accepted(lm, async_client):
    r1, r2 = await asyncio.gather(
        async_client.post("/activate/training-lora-image"),
        async_client.post("/activate/inference-small"),
    )
    codes = sorted([r1.status_code, r2.status_code])
    assert codes[0] == 200 and is_4xx_code(codes[1]), codes
    assert len(lm.docker.starts) == 1


def is_4xx_code(code):
    return 400 <= code < 500


def test_no_docker_call_runs_on_the_event_loop(lm):
    lm.make_active("inference-small")
    assert lm.activate("training-lora-image").status_code == 200
    lm.client.post("/stop")
    assert lm.docker.calls, "expected docker calls"
    assert [c for c in lm.docker.calls if c.on_loop] == []


@pytest.mark.anyio
async def test_stop_and_activate_cannot_both_be_accepted(lm, async_client):
    lm.make_active("inference-small")
    r_stop, r_act = await asyncio.gather(
        async_client.post("/stop"),
        async_client.post("/activate/training-lora-image"),
    )
    codes = sorted([r_stop.status_code, r_act.status_code])
    assert codes[0] == 200 and is_4xx_code(codes[1]), codes
    assert lm.state["switching"] is False


def test_stop_releases_the_switch_slot_even_if_stopping_fails(lm, monkeypatch):
    async def boom():
        raise RuntimeError("docker socket gone")
    monkeypatch.setattr(lm.main, "stop_all_services", boom)
    with pytest.raises(RuntimeError):
        lm.client.post("/stop")
    assert lm.state["switching"] is False


# ── Edge cases ───────────────────────────────────────────────────────────────

def test_unknown_profile_is_404_and_touches_nothing(lm):
    lm.make_active("inference-small")
    before = lm.snapshot()
    r = lm.activate("no-such-profile")
    assert r.status_code == 404
    assert lm.docker.calls == []
    assert lm.snapshot() == before
    assert lm.ws.events == []


def test_unknown_profile_is_404_even_while_switching(lm):
    lm.state["switching"] = True
    assert lm.activate("no-such-profile").status_code == 404


def test_activate_while_switching_flag_set_is_409_and_starts_nothing(lm):
    lm.state["switching"] = True
    r = lm.activate("inference-small")
    assert r.status_code == 409
    assert lm.docker.calls == []


def test_stop_while_switching_is_409(lm):
    lm.state["switching"] = True
    assert lm.client.post("/stop").status_code == 409
    assert lm.docker.calls == []


def test_stop_tears_down_everything_and_clears_state(lm):
    lm.make_active("training-lora-text")
    r = lm.client.post("/stop")
    assert r.status_code == 200
    assert {f for c in lm.docker.downs for f in c.compose_files} == ALL_COMPOSE
    assert lm.docker.starts == []
    assert lm.state["active_profile"] is None
    assert lm.state["running_services"] == []
    assert lm.state["switching"] is False


# ── idle ─────────────────────────────────────────────────────────────────────

def test_idle_activation_tears_down_all_stacks(lm):
    lm.make_active("inference-4gpu")
    assert lm.activate("idle").status_code == 200
    assert {f for c in lm.docker.downs for f in c.compose_files} == ALL_COMPOSE
    assert lm.state["switching"] is False


@pytest.mark.xfail(
    strict=True,
    reason="BUG-9: idle has compose_files: [] and services: [], so do_switch builds "
           "`docker compose up -d --remove-orphans` with no -f. That fails (no "
           "compose file in cwd) or, if cwd ever holds one, starts its default "
           "services. Either way idle cannot be activated. Modelled, not verified "
           "against a real docker host.")
def test_idle_never_issues_a_bare_compose_up(lm):
    lm.make_active("inference-4gpu")
    lm.activate("idle")
    bare = [c for c in lm.docker.starts if not c.compose_files]
    assert bare == [], bare


@pytest.mark.xfail(
    strict=True,
    reason="BUG-9: consequence of the bare `up` — the switch is recorded as a "
           "failure and active_profile ends up None instead of 'idle'.")
def test_idle_becomes_the_active_profile(lm):
    lm.make_active("inference-4gpu")
    lm.activate("idle")
    assert lm.state["active_profile"] == "idle"
    assert lm.state["running_services"] == []
