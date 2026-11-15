"""Alerts API — active alerts from Alertmanager plus an in-app alert history.

Two directions:

* Pull — ``GET /api/alerts`` asks Alertmanager for the currently firing alerts
  (the Monitor page banner and the nav badge poll this).
* Push — ``POST /api/alerts/webhook`` is the Alertmanager ``webhook_configs``
  target (configs/prometheus/alertmanager.yml). Every notification, firing or
  resolved, is recorded in the alert-history store behind
  ``GET /api/alerts/history``, and state changes go to the activity feed.

The history store is a small JSON file (ALERT_HISTORY_PATH, on the
/data/loadout-manager bind mount) so it survives a container restart. It keeps
the last HISTORY_DAYS days, capped at HISTORY_MAX entries.
"""

import hashlib
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from .activity import log_event

logger = logging.getLogger(__name__)

router = APIRouter()

# loadout-manager reaches Alertmanager by container name on the shared
# ai-workstation network (docker/compose.loadout.yml).
ALERTMANAGER_URL = os.getenv("ALERTMANAGER_URL", "http://alertmanager:9093")

ALERT_HISTORY_PATH = Path(os.getenv(
    "ALERT_HISTORY_PATH", "/data/loadout-manager/alert-history.json"))
HISTORY_DAYS = 7
HISTORY_MAX = 500

# key ("<fingerprint>:<startsAt>") -> record. One record per alert occurrence:
# Alertmanager re-sends a firing alert every repeat_interval, which updates the
# same record instead of adding a new one.
_history: Dict[str, Dict] = {}
_loaded = False


# ── Alertmanager webhook payload (version 4) ─────────────────────────────────

class WebhookAlert(BaseModel):
    status: str
    labels: Dict[str, str] = {}
    annotations: Dict[str, str] = {}
    startsAt: str = ""
    endsAt: str = ""
    generatorURL: str = ""
    fingerprint: str = ""


class WebhookPayload(BaseModel):
    version: str = "4"
    groupKey: str = ""
    truncatedAlerts: int = 0
    status: str = ""
    receiver: str = ""
    groupLabels: Dict[str, str] = {}
    commonLabels: Dict[str, str] = {}
    commonAnnotations: Dict[str, str] = {}
    externalURL: str = ""
    alerts: List[WebhookAlert] = []


# ── helpers ──────────────────────────────────────────────────────────────────

_FRACTION = re.compile(r"(\.\d{6})\d+")


def _parse_ts(value: Optional[str]) -> Optional[datetime]:
    """Parse an Alertmanager RFC 3339 timestamp (may carry nanoseconds)."""
    if not value:
        return None
    try:
        v = _FRACTION.sub(r"\1", value.strip()).replace("Z", "+00:00")
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # Alertmanager uses the zero time for "not ended yet".
        return None if dt.year <= 1 else dt
    except ValueError:
        return None


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _fingerprint(alert: WebhookAlert) -> str:
    if alert.fingerprint:
        return alert.fingerprint
    blob = json.dumps(alert.labels, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def _describe(labels: Dict[str, str], annotations: Dict[str, str]) -> str:
    return (annotations.get("summary") or annotations.get("description")
            or labels.get("alertname", ""))


def _load() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    try:
        data = json.loads(ALERT_HISTORY_PATH.read_text())
        for rec in data.get("alerts", []):
            if "id" in rec:
                _history[rec["id"]] = rec
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning("Could not read alert history %s: %s", ALERT_HISTORY_PATH, e)


def _save() -> None:
    try:
        ALERT_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = ALERT_HISTORY_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps({"alerts": list(_history.values())}))
        os.replace(tmp, ALERT_HISTORY_PATH)
    except Exception as e:
        logger.warning("Could not write alert history %s: %s", ALERT_HISTORY_PATH, e)


def _prune(now: datetime) -> None:
    cutoff = now - timedelta(days=HISTORY_DAYS)
    for key, rec in list(_history.items()):
        if rec["status"] == "resolved":
            last = _parse_ts(rec.get("resolved_at")) or _parse_ts(rec.get("last_seen"))
            if last and last < cutoff:
                del _history[key]
    if len(_history) > HISTORY_MAX:
        oldest = sorted(_history, key=lambda k: _history[k]["last_seen"])
        for key in oldest[: len(_history) - HISTORY_MAX]:
            del _history[key]


def _record(alert: WebhookAlert, receiver: str, now: datetime) -> None:
    name = alert.labels.get("alertname", "unknown")
    started = _parse_ts(alert.startsAt) or now
    fp = _fingerprint(alert)
    key = f"{fp}:{_iso(started)}"
    rec = _history.get(key)
    previous = rec["status"] if rec else None
    if rec is None:
        rec = _history[key] = {
            "id": key,
            "fingerprint": fp,
            "name": name,
            "fired_at": _iso(started),
            "resolved_at": None,
            "duration": None,
        }
    rec.update(
        status="resolved" if alert.status == "resolved" else "firing",
        severity=alert.labels.get("severity", "info"),
        component=alert.labels.get("component", ""),
        instance=alert.labels.get("instance", ""),
        summary=alert.annotations.get("summary", ""),
        description=_describe(alert.labels, alert.annotations),
        receiver=receiver,
        generator_url=alert.generatorURL,
        last_seen=_iso(now),
    )
    if rec["status"] == "resolved":
        ended = _parse_ts(alert.endsAt) or now
        rec["resolved_at"] = _iso(ended)
        rec["duration"] = max(0, int((ended - started).total_seconds()))

    # Activity feed: state changes only, not Alertmanager's periodic repeats.
    if rec["status"] != previous:
        if rec["status"] == "firing":
            log_event("alert", f"{name} firing ({rec['severity']}): {rec['description']}")
        else:
            log_event("alert", f"{name} resolved after {rec['duration']}s")


def record_webhook(payload: WebhookPayload) -> int:
    """Record every alert in an Alertmanager notification. Returns the count."""
    _load()
    now = datetime.now(timezone.utc)
    for alert in payload.alerts:
        _record(alert, payload.receiver, now)
    _prune(now)
    _save()
    return len(payload.alerts)


def history() -> List[Dict]:
    """Recorded alerts, newest first."""
    _load()
    _prune(datetime.now(timezone.utc))
    return sorted(_history.values(), key=lambda r: r["fired_at"], reverse=True)


async def _fetch_alertmanager() -> Optional[List[Dict]]:
    """Pull active alerts from Alertmanager. Returns None if it is unreachable."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{ALERTMANAGER_URL}/api/v2/alerts?active=true&silenced=false&inhibited=false")
            if r.status_code == 200:
                return [
                    {
                        "name": a.get("labels", {}).get("alertname", "unknown"),
                        "severity": a.get("labels", {}).get("severity", "info"),
                        "summary": a.get("annotations", {}).get("summary", ""),
                        "description": _describe(a.get("labels", {}), a.get("annotations", {})),
                        "instance": a.get("labels", {}).get("instance", ""),
                        "starts_at": a.get("startsAt", ""),
                    }
                    for a in r.json()
                ]
    except Exception as e:
        logger.debug("Alertmanager not reachable: %s", e)
    return None


# ── routes ───────────────────────────────────────────────────────────────────

@router.get("/alerts")
async def get_alerts() -> List[Dict]:
    """Return currently firing alerts.

    Asks Alertmanager first; if it is unreachable, falls back to the alerts the
    webhook last recorded as firing.
    """
    live = await _fetch_alertmanager()
    if live is not None:
        return live
    return [
        {
            "name": r["name"],
            "severity": r["severity"],
            "summary": r["summary"],
            "description": r["description"],
            "instance": r["instance"],
            "starts_at": r["fired_at"],
        }
        for r in history() if r["status"] == "firing"
    ]


@router.get("/alerts/history")
async def get_alert_history() -> Dict:
    """Return alerts recorded by the webhook over the last HISTORY_DAYS days."""
    return {"alerts": history()}


@router.post("/alerts/webhook")
async def alertmanager_webhook(payload: WebhookPayload) -> Dict:
    """Alertmanager webhook receiver (payload version 4)."""
    if payload.version != "4":
        logger.warning("Alertmanager webhook payload version %s (expected 4)", payload.version)
    return {"status": "ok", "recorded": record_webhook(payload)}
