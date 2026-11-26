"""
GET /metrics — Prometheus text exposition for the loadout-manager scrape job
(TASK-060 / #28).

Checks the series the ProfileServiceDown alert depends on
(loadout_service_expected per active-profile container), the switching / NVML
edge cases, that appliance-mode forward-auth does not block the scrape, and
that configs/prometheus/prometheus.yml agrees with this endpoint and with
profiles.yaml (scrape address, profile-gated job labels).

Not proven here: that a real Prometheus reaches loadout-manager:8800 over
ai-workstation (host check; see the PR). promtool covers the alert rules.
"""

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
PROM_YML = REPO / "configs" / "prometheus" / "prometheus.yml"

_SAMPLE = re.compile(r'^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{(.*)\})? (\S+)$')
_LABEL = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"')


def _parse(text):
    """Exposition text -> {name: [(labels dict, float value)]}; asserts the
    HELP/TYPE lines precede every family's samples."""
    out, typed = {}, set()
    for line in text.splitlines():
        if line.startswith("# TYPE "):
            typed.add(line.split()[2])
            continue
        if not line or line.startswith("#"):
            continue
        m = _SAMPLE.match(line)
        assert m, f"not exposition format: {line!r}"
        name, _, raw, value = m.groups()
        assert name in typed, f"{name} sample before its # TYPE line"
        labels = dict(_LABEL.findall(raw or ""))
        out.setdefault(name, []).append((labels, float(value)))
    return out


def _scrape(lm):
    r = lm.client.get("/metrics")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/plain; version=0.0.4")
    assert r.text.endswith("\n")
    return _parse(r.text)


def _expected(m):
    return {lbl["service"]: lbl["profile"] for lbl, v in m.get("loadout_service_expected", []) if v == 1}


def test_metrics_idle(lm):
    m = _scrape(lm)
    assert m["loadout_manager_up"] == [({}, 1.0)]
    assert m["loadout_switching"] == [({}, 0.0)]
    assert "loadout_active_profile_info" not in m
    assert _expected(m) == {}


def test_metrics_active_profile_expects_its_containers(lm):
    lm.make_active("image-studio")
    m = _scrape(lm)
    assert m["loadout_active_profile_info"] == [({"profile": "image-studio"}, 1.0)]
    # derived from profiles.yaml services, which are the container names
    assert _expected(m) == {svc: "image-studio"
                            for svc in lm.profiles["image-studio"]["services"]}
    assert set(_expected(m)) == {"comfyui", "rembg", "vllm-pair-b"}


def test_metrics_no_expected_services_while_switching(lm):
    lm.make_active("inference-4gpu")
    lm.state["switching"] = True
    m = _scrape(lm)
    assert m["loadout_switching"] == [({}, 1.0)]
    assert _expected(m) == {}


def test_metrics_unknown_profile_expects_nothing(lm):
    # e.g. a persisted state.json naming a profile since removed from profiles.yaml
    lm.state.update(active_profile="gone-profile", running_services=["x"])
    m = _scrape(lm)
    assert m["loadout_active_profile_info"] == [({"profile": "gone-profile"}, 1.0)]
    assert _expected(m) == {}


def test_metrics_gpu_vram(lm):
    lm.set_free([4.0, 24.0, 24.0, 12.5], total_gb=24.0)
    m = _scrape(lm)
    gib = 1024 ** 3
    assert m["loadout_gpu_telemetry_available"] == [({}, 1.0)]
    used = {lbl["gpu"]: v for lbl, v in m["loadout_gpu_vram_used_bytes"]}
    total = {lbl["gpu"]: v for lbl, v in m["loadout_gpu_vram_total_bytes"]}
    assert used == {"0": 20 * gib, "1": 0.0, "2": 0.0, "3": 11.5 * gib}
    assert total == {str(i): 24 * gib for i in range(4)}


def test_metrics_gpu_telemetry_down_still_serves(lm):
    lm.telemetry_down()
    m = _scrape(lm)
    assert m["loadout_manager_up"] == [({}, 1.0)]
    assert m["loadout_gpu_telemetry_available"] == [({}, 0.0)]
    assert "loadout_gpu_vram_used_bytes" not in m


def test_label_values_are_escaped(lm):
    lm.state.update(active_profile='we"ird\\name\nx')
    r = lm.client.get("/metrics")
    assert 'loadout_active_profile_info{profile="we\\"ird\\\\name\\nx"} 1' in r.text


def test_metrics_reachable_without_forward_auth_in_appliance_mode(lm, monkeypatch):
    monkeypatch.setenv("KOVATI_OS_MODE", "appliance")
    assert lm.client.get("/status").status_code == 401   # still guarded
    r = lm.client.get("/metrics")
    assert r.status_code == 200
    assert "loadout_manager_up 1" in r.text


# ── prometheus.yml agrees with this endpoint and profiles.yaml ───────────────

def _jobs():
    cfg = yaml.safe_load(PROM_YML.read_text(encoding="utf-8"))
    return {j["job_name"]: j for j in cfg["scrape_configs"]}


def _target_labels(job):
    (sc,) = job["static_configs"]
    return sc["targets"], sc.get("labels", {})


def test_prometheus_scrapes_loadout_manager_metrics():
    job = _jobs()["loadout-manager"]
    targets, labels = _target_labels(job)
    assert job["metrics_path"] == "/metrics"
    assert targets == ["loadout-manager:8800"]
    # a `service` target label would rename loadout_service_expected's own
    # `service` label to exported_service and break the ProfileServiceDown join
    assert "service" not in labels


def test_prometheus_does_not_scrape_services_without_metrics():
    assert not {"ollama", "comfyui", "open-webui"} & set(_jobs())


def test_profile_gated_jobs_are_labelled_with_their_container(main_module):
    profiles = main_module.load_profiles()
    in_profiles = {svc for p in profiles.values() for svc in p["services"]}

    gated = {}
    for name, job in _jobs().items():
        targets, labels = _target_labels(job)
        host = targets[0].split(":")[0]
        if labels.get("profile_gated") == "true":
            gated[name] = labels["service"]
            # service label == container name == the service in profiles.yaml
            assert labels["service"] == host, name
            assert host in in_profiles, name
        else:
            # every target whose container is started by a loadout profile
            # must be marked, or ServiceDown fires while it is not active
            assert host not in in_profiles, \
                f"{name} scrapes profile-managed {host} but is not profile_gated"
    assert gated == {"vllm-pair-a": "vllm-pair-a", "vllm-pair-b": "vllm-pair-b",
                     "vllm-4gpu": "vllm-4gpu", "vllm-embed": "vllm-embed"}
