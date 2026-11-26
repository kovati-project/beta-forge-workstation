"""
Issue #69 follow-ups: /loadouts card fields and the shared NVML reader.

* GET /loadouts carries `accent` and `nvlink_pairs` for the Loadout page cards.
* /status and /api/metrics/gpu read NVML through the same reader (api/gpu.py),
  so they agree on availability, and /api/metrics/gpu reports null metrics
  (not zeros) with `available: false` when telemetry is down.
"""

import pytest


# ── /loadouts: accent + nvlink_pairs ─────────────────────────────────────────

@pytest.mark.parametrize("name,accent,pairs", [
    ("inference-pair-a",    "cyan",   [[0, 3]]),
    ("inference-pair-b",    "cyan",   [[1, 2]]),
    ("dual-stack",          "cyan",   [[0, 3], [1, 2]]),
    ("image-studio",        "purple", [[1, 2]]),
    ("training-lora-image", "amber",  [[1, 2]]),
    ("training-lora-text",  "amber",  [[0, 3], [1, 2]]),
    ("idle",                "cyan",   []),
])
def test_loadouts_include_accent_and_nvlink_pairs(lm, name, accent, pairs):
    body = lm.client.get("/loadouts").json()
    assert body[name]["accent"] == accent
    assert body[name]["nvlink_pairs"] == pairs


def test_every_loadout_has_accent_and_nvlink_pairs(lm):
    body = lm.client.get("/loadouts").json()
    for name, p in body.items():
        assert p["accent"] in {"cyan", "amber", "purple"}, name
        assert isinstance(p["nvlink_pairs"], list), name


def test_yaml_accent_and_nvlink_pairs_override_the_derived_values(lm, monkeypatch):
    profiles = dict(lm.profiles)
    profiles["idle"] = {**profiles["idle"], "accent": "amber", "nvlink_pairs": [[1, 2]]}
    monkeypatch.setattr(lm.main, "load_profiles", lambda: profiles)
    body = lm.client.get("/loadouts").json()
    assert body["idle"]["accent"] == "amber"
    assert body["idle"]["nvlink_pairs"] == [[1, 2]]


# ── /api/metrics/gpu: telemetry available / unavailable ──────────────────────

def test_metrics_gpu_reports_available_telemetry(lm):
    lm.set_free([20, 24, 24, 24])
    body = lm.client.get("/api/metrics/gpu").json()
    assert body["available"] is True
    assert "error" not in body
    assert body["GPU0"]["vram_used_gb"] == 4.0
    assert body["GPU0"]["vram_total_gb"] == 24.0
    assert body["GPU0"]["power_w"] == 100.0


def _break(lm, mode):
    if mode == "init_fails":
        lm.telemetry_down()
    elif mode == "no_devices":
        lm.nvml.devices = []
    elif mode == "memory_query_fails":
        lm.nvml.memory_error = RuntimeError("GPU is lost")


@pytest.mark.parametrize("mode", ["init_fails", "no_devices", "memory_query_fails"])
def test_metrics_gpu_reports_unavailable_with_null_metrics(lm, mode):
    _break(lm, mode)
    body = lm.client.get("/api/metrics/gpu").json()
    assert body["available"] is False
    assert body["error"]
    for i in range(4):
        gpu = body[f"GPU{i}"]
        for key in ("vram_used_gb", "vram_total_gb", "utilization", "temp", "power_w"):
            assert gpu[key] is None, (i, key)
        assert gpu["active"] is False


@pytest.mark.parametrize("mode", ["init_fails", "no_devices", "memory_query_fails"])
def test_status_and_metrics_agree_on_unavailable_telemetry(lm, mode):
    _break(lm, mode)
    status = lm.client.get("/status").json()["gpu_telemetry"]
    metrics = lm.client.get("/api/metrics/gpu").json()
    assert status["available"] is False and metrics["available"] is False
    assert status["error"] == metrics["error"]


def test_unsupported_power_sensor_is_null_not_zero(lm, monkeypatch):
    import pynvml

    def no_power(handle):
        raise RuntimeError("Not Supported")

    monkeypatch.setattr(pynvml, "nvmlDeviceGetPowerUsage", no_power)
    assert lm.client.get("/status").json()["gpus"][0]["power_w"] is None
    assert lm.client.get("/api/metrics/gpu").json()["GPU0"]["power_w"] is None
