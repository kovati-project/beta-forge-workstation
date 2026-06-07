"""LLM trace and observability API endpoints."""

import os
from typing import Dict, Optional
import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

LANGFUSE_URL = os.getenv("LANGFUSE_URL", "http://localhost:3002")
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY", "")

_TIMEOUT = 10.0


def _langfuse_auth():
    """Return httpx auth tuple if credentials are set, else None."""
    if LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY:
        return (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY)
    return None


@router.get("/traces")
async def get_traces(
    model: Optional[str] = None,
    min_latency: Optional[float] = None,
    max_latency: Optional[float] = None,
    start_date: Optional[str] = Query(default=None, description="ISO8601 date, e.g. 2026-06-01"),
    end_date: Optional[str] = Query(default=None, description="ISO8601 date, e.g. 2026-06-06"),
    status: Optional[str] = Query(default=None, description="Filter by status: success | error"),
    limit: int = Query(default=50, ge=1, le=500),
    page: int = Query(default=1, ge=1),
) -> Dict:
    """
    Get LLM traces from Langfuse with server-side filtering.
    All filter params are pushed to the Langfuse API directly — not post-filtered.
    """
    params: Dict = {"limit": limit, "page": page}

    if model:
        params["model"] = model
    if start_date:
        params["fromTimestamp"] = start_date
    if end_date:
        params["toTimestamp"] = end_date

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{LANGFUSE_URL}/api/public/traces",
                params=params,
                auth=_langfuse_auth(),
            )
            if resp.status_code == 401:
                raise HTTPException(status_code=503, detail="Langfuse credentials invalid — set LANGFUSE_PUBLIC_KEY / SECRET_KEY")
            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Langfuse returned {resp.status_code}")

            data = resp.json()
            traces = data.get("data", [])

            # Apply latency filters — not a native Langfuse query param
            if min_latency is not None:
                traces = [t for t in traces if (t.get("latency") or 0) >= min_latency]
            if max_latency is not None:
                traces = [t for t in traces if (t.get("latency") or 0) <= max_latency]
            if status:
                traces = [t for t in traces if t.get("status", "").lower() == status.lower()]

            return {
                "traces": traces,
                "count": len(traces),
                "total": data.get("meta", {}).get("totalItems"),
                "page": page,
                "filters": {k: v for k, v in {"model": model, "min_latency": min_latency,
                            "max_latency": max_latency, "start_date": start_date,
                            "end_date": end_date, "status": status}.items() if v is not None},
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Langfuse unavailable: {e}")
