"""
POST /api/alerts/webhook — the Alertmanager webhook_configs target (issue #64).

Payloads are Alertmanager's webhook format, version 4. Checks that firing and
resolved notifications land in the alert history (GET /api/alerts/history),
the activity feed, and the active-alerts fallback, and that the receivers in
configs/prometheus/alertmanager.yml actually point at this endpoint.

Not proven here: that a real Alertmanager container reaches loadout-manager over
the ai-workstation network (host check; see the PR).
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]

# Yesterday, not a fixed date: the history drops resolved alerts older than
# HISTORY_DAYS, so a hard-coded date makes these tests fail a week later.
DAY = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
STARTS = f"{DAY}T10:00:00.123456789Z"
ENDS = f"{DAY}T10:05:30.5Z"


def _payload(status, alerts, receiver="critical-gpu"):
    return {
        "version": "4",
        "groupKey": '{}/{severity="critical"}:{alertname="GPUHighTemp"}',
        "truncatedAlerts": 0,
        "status": status,
        "receiver": receiver,
        "groupLabels": {"alertname": "GPUHighTemp"},
        "commonLabels": {"alertname": "GPUHighTemp", "severity": "critical"},
        "commonAnnotations": {},
        "externalURL": "http://alertmanager:9093",
        "alerts": alerts,
    }


def _alert(status, gpu="0", ends="0001-01-01T00:00:00Z", fingerprint=None):
    return {
        "status": status,
        "labels": {"alertname": "GPUHighTemp", "severity": "critical",
                   "component": "gpu", "gpu": gpu, "instance": "dcgm-exporter:9400"},
        "annotations": {"summary": f"GPU {gpu} above 85C",
                        "description": "Temperature high for 5 minutes"},
        "startsAt": STARTS,
        "endsAt": ends,
        "generatorURL": "http://prometheus:9090/graph?g0.expr=DCGM_FI_DEV_GPU_TEMP",
        "fingerprint": fingerprint or f"fp-gpu{gpu}",
    }


@pytest.fixture
def alerts(lm, monkeypatch, tmp_path):
    from api import activity, alerts as mod

    monkeypatch.setattr(mod, "ALERT_HISTORY_PATH", tmp_path / "alert-history.json")
    monkeypatch.setattr(mod, "_history", {})
    monkeypatch.setattr(mod, "_loaded", False)
    activity.activity_log.clear()

    async def unreachable():
        return None
    monkeypatch.setattr(mod, "_fetch_alertmanager", unreachable)

    yield SimpleNamespace(client=lm.client, activity=activity, mod=mod)
    activity.activity_log.clear()


def _history(alerts):
    r = alerts.client.get("/api/alerts/history")
    assert r.status_code == 200
    return r.json()["alerts"]


def test_firing_alert_is_recorded(alerts):
    r = alerts.client.post("/api/alerts/webhook", json=_payload("firing", [_alert("firing")]))
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "recorded": 1}

    [rec] = _history(alerts)
    assert rec["name"] == "GPUHighTemp"
    assert rec["status"] == "firing"
    assert rec["severity"] == "critical"
    assert rec["component"] == "gpu"
    assert rec["receiver"] == "critical-gpu"
    assert rec["fired_at"] == f"{DAY}T10:00:00.123456Z"
    assert rec["description"] == "GPU 0 above 85C"
    assert rec["resolved_at"] is None and rec["duration"] is None

    # surfaces as active (banner) when Alertmanager itself is unreachable
    active = alerts.client.get("/api/alerts").json()
    assert [a["name"] for a in active] == ["GPUHighTemp"]
    assert active[0]["description"] == "GPU 0 above 85C"

    events = alerts.activity.activity_log
    assert [e["type"] for e in events] == ["alert"]
    assert "GPUHighTemp firing" in events[0]["detail"]


def test_resolved_alert_updates_the_same_record(alerts):
    alerts.client.post("/api/alerts/webhook", json=_payload("firing", [_alert("firing")]))
    r = alerts.client.post("/api/alerts/webhook",
                           json=_payload("resolved", [_alert("resolved", ends=ENDS)]))
    assert r.status_code == 200

    [rec] = _history(alerts)
    assert rec["status"] == "resolved"
    assert rec["resolved_at"] == f"{DAY}T10:05:30.500000Z"
    assert rec["duration"] == 330
    assert alerts.client.get("/api/alerts").json() == []

    details = [e["detail"] for e in alerts.activity.activity_log]
    assert len(details) == 2
    assert "resolved after 330s" in details[0]   # newest first


def test_resolved_without_prior_firing_is_still_recorded(alerts):
    alerts.client.post("/api/alerts/webhook",
                       json=_payload("resolved", [_alert("resolved", ends=ENDS)]))
    [rec] = _history(alerts)
    assert rec["status"] == "resolved" and rec["duration"] == 330


def test_repeat_notifications_do_not_duplicate(alerts):
    for _ in range(3):   # Alertmanager re-sends every repeat_interval
        alerts.client.post("/api/alerts/webhook", json=_payload("firing", [_alert("firing")]))
    assert len(_history(alerts)) == 1
    assert len(alerts.activity.activity_log) == 1


def test_grouped_payload_with_mixed_statuses(alerts):
    alerts.client.post("/api/alerts/webhook", json=_payload(
        "firing", [_alert("firing", gpu="0"), _alert("firing", gpu="1")]))
    alerts.client.post("/api/alerts/webhook", json=_payload(
        "firing", [_alert("firing", gpu="0"), _alert("resolved", gpu="1", ends=ENDS)]))

    by_gpu = {r["fingerprint"]: r["status"] for r in _history(alerts)}
    assert by_gpu == {"fp-gpu0": "firing", "fp-gpu1": "resolved"}


def test_history_persists_across_restart(alerts, monkeypatch):
    alerts.client.post("/api/alerts/webhook", json=_payload("firing", [_alert("firing")]))
    assert alerts.mod.ALERT_HISTORY_PATH.exists()

    monkeypatch.setattr(alerts.mod, "_history", {})   # simulate a fresh process
    monkeypatch.setattr(alerts.mod, "_loaded", False)
    assert [r["name"] for r in _history(alerts)] == ["GPUHighTemp"]


def test_rejects_malformed_payload(alerts):
    r = alerts.client.post("/api/alerts/webhook", json={"version": "4", "alerts": [{"labels": {}}]})
    assert r.status_code == 422
    assert _history(alerts) == []


def test_webhook_needs_no_forward_auth_in_appliance_mode(alerts, monkeypatch):
    monkeypatch.setenv("KOVATI_OS_MODE", "appliance")
    r = alerts.client.post("/api/alerts/webhook", json=_payload("firing", [_alert("firing")]))
    assert r.status_code == 200
    # everything else still requires Authentik headers
    assert alerts.client.get("/api/alerts/history").status_code == 401


def test_every_receiver_posts_to_the_webhook_with_send_resolved():
    cfg = yaml.safe_load((REPO / "configs/prometheus/alertmanager.yml").read_text())
    receivers = {r["name"]: r for r in cfg["receivers"]}
    routed = {cfg["route"]["receiver"]} | {r["receiver"] for r in cfg["route"]["routes"]}
    assert routed <= receivers.keys()
    for name in routed:
        hooks = receivers[name].get("webhook_configs", [])
        assert any(h["url"] == "http://loadout-manager:8800/api/alerts/webhook"
                   and h.get("send_resolved") is True for h in hooks), name


def test_loadout_manager_shares_a_network_with_alertmanager():
    def nets(path, service):
        c = yaml.safe_load((REPO / "docker" / path).read_text())
        declared = c.get("networks", {})
        names = c["services"][service].get("networks") or ["default"]
        return {declared.get(n, {}).get("name", n) for n in names}

    assert "ai-workstation" in nets("compose.loadout.yml", "loadout-manager") \
        & nets("compose.monitoring.yml", "alertmanager")
