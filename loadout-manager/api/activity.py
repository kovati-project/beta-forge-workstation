"""Activity logging API endpoints."""

import time
from collections import deque
from typing import Dict, List
from fastapi import APIRouter

router = APIRouter()

# In-memory activity log (last 100 events)
activity_log = deque(maxlen=100)


def log_event(event_type: str, detail: str):
    """Log an event to the activity log."""
    event = {
        "ts": time.time(),
        "type": event_type,
        "detail": detail,
    }
    activity_log.appendleft(event)


@router.get("/activity")
async def get_activity(n: int = 10) -> Dict:
    """Get last N activity log entries."""
    return {
        "events": list(activity_log)[:n]
    }
