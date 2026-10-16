"""
/api/operations/* — the Operations panel's actions.

Every defect is xfail(strict=True): these endpoints report success without
doing anything. A fix makes its test XPASS and fails the run until the marker
is removed.
"""

import pytest


def _ran_something(api):
    return bool(api.exec.calls) or bool(api.docker.calls)


@pytest.mark.xfail(
    strict=True,
    reason="OPS-1: POST /operations/backup returns 'started' with a made-up id and "
           "runs nothing. The real backup is POST /api/backup/run (scripts/backup.sh).")
def test_operations_backup_runs_a_backup_or_is_gone(api):
    r = api.client.post("/api/operations/backup")
    assert r.status_code in (404, 410, 501) or _ran_something(api)


@pytest.mark.xfail(
    strict=True,
    reason="OPS-2: POST /operations/restart-service returns 'restarting' and "
           "restarts nothing.")
def test_restart_service_restarts_something(api):
    r = api.client.post("/api/operations/restart-service", params={"service": "langfuse"})
    assert r.status_code >= 400 or _ran_something(api)


@pytest.mark.xfail(
    strict=True,
    reason="OPS-3: POST /operations/system-update returns 'update_queued' and "
           "queues nothing.")
def test_system_update_does_something(api):
    r = api.client.post("/api/operations/system-update")
    assert r.status_code >= 400 or _ran_something(api)


@pytest.mark.xfail(
    strict=True,
    reason="OPS-4: /operations/diagnostics is a hard-coded list of passes "
           "('All 4 GPUs: 24GB each', '2 bridges connected', ...); it reports "
           "GPU memory as passing while NVML is unreachable.")
def test_diagnostics_reflect_gpu_telemetry(api, lm):
    lm.telemetry_down()
    checks = api.client.get("/api/operations/diagnostics").json()["diagnostics"]
    gpu = next(c for c in checks if c["check"] == "GPU Memory")
    assert gpu["status"] != "pass"
