"""Alerts API — active system alerts from Prometheus Alertmanager."""

import logging
from typing import List, Dict
import httpx
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

ALERTMANAGER_URL = "http://localhost:9093"


async def _fetch_alertmanager() -> List[Dict]:
    """Pull active alerts from Alertmanager. Returns [] on any failure."""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{ALERTMANAGER_URL}/api/v2/alerts?active=true&silenced=false&inhibited=false")
            if r.status_code == 200:
                raw = r.json()
                return [
                    {
                        "name": a.get("labels", {}).get("alertname", "unknown"),
                        "severity": a.get("labels", {}).get("severity", "info"),
                        "summary": a.get("annotations", {}).get("summary", ""),
                        "instance": a.get("labels", {}).get("instance", ""),
                        "starts_at": a.get("startsAt", ""),
                    }
                    for a in raw
                ]
    except Exception as e:
        logger.debug("Alertmanager not reachable: %s", e)
    return []


@router.get("/alerts")
async def get_alerts() -> List[Dict]:
    """Return currently firing alerts."""
    return await _fetch_alertmanager()


@router.get("/alerts/history")
async def get_alert_history() -> Dict:
    """Return recent alert history (placeholder — extend with a persistent store)."""
    return {"alerts": []}
