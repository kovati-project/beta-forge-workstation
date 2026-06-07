"""Metrics and monitoring API endpoints."""

from collections import deque
from typing import Dict, List
import httpx
import psutil
from fastapi import APIRouter

try:
    from config import PROMETHEUS_URL
except ImportError:
    from ..config import PROMETHEUS_URL

router = APIRouter()

# GPU VRAM history: 30 min at 3s resolution = 600 samples per GPU
gpu_history = {i: deque(maxlen=600) for i in range(4)}

try:
    import pynvml
    pynvml.nvmlInit()
    _NVML_OK = True
except Exception as e:
    print(f"Warning: NVIDIA monitoring not available: {e}")
    _NVML_OK = False


def _nvml_gpu_vram_used_gb() -> float:
    """Return total VRAM used (GB) across all GPUs, or 0 on failure."""
    if not _NVML_OK:
        return 0.0
    try:
        total = 0.0
        count = pynvml.nvmlDeviceGetCount()
        for i in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            total += mem.used / 1024 ** 3
        return round(total, 1)
    except Exception:
        return 0.0


def _update_gpu_history():
    if not _NVML_OK:
        return
    try:
        for i in range(min(4, pynvml.nvmlDeviceGetCount())):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            gpu_history[i].append(round(mem.used / 1024 ** 3, 2))
    except Exception:
        pass


@router.get("/metrics/gpu")
async def get_gpu_metrics() -> Dict:
    """GPU VRAM history (30 min at 3s resolution)."""
    _update_gpu_history()
    return {
        f"GPU{i}": {"vram_history": list(gpu_history[i])}
        for i in range(4)
    }


@router.get("/metrics/system")
async def get_system_metrics() -> Dict:
    """System metrics via psutil + nvml. No Prometheus dependency."""
    vm = psutil.virtual_memory()

    # Storage: prefer /data (mounted data volume), fall back to root
    try:
        disk = psutil.disk_usage("/data")
    except Exception:
        disk = psutil.disk_usage("/")

    return {
        "cpu_load_pct":    round(psutil.cpu_percent(interval=0.2), 1),
        "ram_used_gb":     round(vm.used  / 1024 ** 3, 1),
        "ram_total_gb":    round(vm.total / 1024 ** 3, 1),
        "vram_used_gb":    _nvml_gpu_vram_used_gb(),
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
