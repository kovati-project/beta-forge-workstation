"""Metrics and monitoring API endpoints."""

import logging
import time
from collections import deque
from typing import Dict, List, Optional, Tuple
import httpx
import psutil
from fastapi import APIRouter

try:
    from config import PROMETHEUS_URL
except ImportError:
    from ..config import PROMETHEUS_URL
from .gpu import read_gpu_telemetry

router = APIRouter()
logger = logging.getLogger(__name__)

# GPU VRAM history: 30 min at 3s resolution = 600 samples per GPU
gpu_history = {i: deque(maxlen=600) for i in range(4)}


def _read_gpus() -> Tuple[Dict[int, Dict], Optional[str]]:
    """Read NVML via the shared reader (api/gpu.py). Returns ({gpu_index: metrics}, error).

    error is None when the GPUs were read; otherwise the reader's error string
    and the dict is empty.
    """
    telemetry = read_gpu_telemetry()
    gpus = {
        g["index"]: {
            "vram_used_gb":  g["vram_used_gb"],
            "vram_total_gb": g["vram_total_gb"],
            "utilization":   g["utilization_pct"],
            "temp":          g["temp_c"],
            "power_w":       g["power_w"],
        }
        for g in telemetry["gpus"]
    }
    return gpus, telemetry["error"]


def _nvml_gpu_vram_used_gb() -> Optional[float]:
    """Return total VRAM used (GB) across all GPUs, or None when unavailable."""
    gpus, _ = _read_gpus()
    if not gpus:
        return None
    return round(sum(g["vram_used_gb"] for g in gpus.values()), 1)


@router.get("/metrics/gpu")
async def get_gpu_metrics() -> Dict:
    """Per-GPU telemetry: VRAM, utilization, temp, and 30-min VRAM history.

    Top-level `available` says whether NVML telemetry could be read. When it
    could not, `error` says why and every GPU reports null metrics rather than
    zeros.
    """
    gpus, error = _read_gpus()
    result: Dict = {}

    for i in range(4):
        g = gpus.get(i)
        if g is not None:
            gpu_history[i].append(g["vram_used_gb"])
            result[f"GPU{i}"] = {
                **g,
                "active":       g["utilization"] > 5 or g["vram_used_gb"] > 2.0,
                "vram_history": list(gpu_history[i]),
            }
        else:
            # Keep the slot and keys so the Monitor page still renders; null
            # means "unknown" (the UI applies ?? fallbacks to these fields).
            result[f"GPU{i}"] = {
                "vram_used_gb":  None,
                "vram_total_gb": None,
                "utilization":   None,
                "temp":          None,
                "power_w":       None,
                "active":        False,
                "vram_history":  list(gpu_history[i]),
            }

    result["available"] = bool(gpus)
    if error is not None:
        result["error"] = error
    return result


@router.get("/metrics/system")
async def get_system_metrics() -> Dict:
    """System metrics via psutil + nvml. No Prometheus dependency."""
    vm = psutil.virtual_memory()

    # Storage: prefer /data (mounted data volume), fall back to root
    try:
        disk = psutil.disk_usage("/data")
    except Exception:
        disk = psutil.disk_usage("/")

    vram_used_gb = _nvml_gpu_vram_used_gb()

    return {
        "uptime_seconds":  int(time.time() - psutil.boot_time()),
        "cpu_load_pct":    round(psutil.cpu_percent(interval=0.2), 1),
        "ram_used_gb":     round(vm.used  / 1024 ** 3, 1),
        "ram_total_gb":    round(vm.total / 1024 ** 3, 1),
        "vram_used_gb":    vram_used_gb,  # None when NVML telemetry unavailable
        "storage_used_tb": round(disk.used  / 1024 ** 4, 2),
        "storage_used_pct": round(disk.percent, 1),
    }


async def _prometheus_scalar(query: str) -> float:
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query})
            data = r.json()
            if data.get("data", {}).get("result"):
                return float(data["data"]["result"][0]["value"][1])
    except Exception:
        pass
    return 0.0


@router.get("/metrics/containers")
async def get_container_metrics() -> List[Dict]:
    """Container metrics from Prometheus/cAdvisor."""
    containers = []
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                f"{PROMETHEUS_URL}/api/v1/query",
                params={"query": 'container_memory_usage_bytes{name!=""}'},
            )
            data = r.json()
            for result in data.get("data", {}).get("result", []):
                name = result.get("metric", {}).get("name", "unknown")
                mem_bytes = float(result["value"][1])
                containers.append({
                    "name": name,
                    "memory_mb": round(mem_bytes / 1024 ** 2, 1),
                    "cpu_percent": 0,
                    "restarts": 0,
                    "oom_killed": False,
                })
    except Exception as e:
        print(f"Container metrics query failed: {e}")
    return containers
