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

router = APIRouter()
logger = logging.getLogger(__name__)

# GPU VRAM history: 30 min at 3s resolution = 600 samples per GPU
gpu_history = {i: deque(maxlen=600) for i in range(4)}

# NVML is initialised lazily and per request (init -> query -> shutdown in
# finally), so a driver that becomes healthy after container start is picked up
# without a restart. After a failed attempt, retries are suppressed for
# _NVML_RETRY_SECONDS so a dead driver is not hammered on every poll.
_NVML_RETRY_SECONDS = 15
_NVML_LOG_REPEAT_SECONDS = 300

_nvml_last_fail_ts = 0.0                   # monotonic time of last failure
_nvml_last_error: Optional[str] = None     # "<ExceptionType>: <msg>" of last failure
_nvml_was_available: Optional[bool] = None  # None until first attempt
_nvml_last_logged_error: Optional[str] = None
_nvml_last_logged_ts = 0.0


def _fmt_exc(e: BaseException) -> str:
    return f"{type(e).__name__}: {e}"


def _note_nvml_state(error: Optional[str]) -> None:
    """Log availability changes: once per distinct error (and again every
    ~5 min while it persists), and recovery at INFO."""
    global _nvml_was_available, _nvml_last_logged_error, _nvml_last_logged_ts
    now = time.monotonic()
    if error is None:
        if _nvml_was_available is False:
            logger.info("NVIDIA telemetry recovered")
        _nvml_was_available = True
        _nvml_last_logged_error = None
        return
    _nvml_was_available = False
    if (error != _nvml_last_logged_error
            or now - _nvml_last_logged_ts >= _NVML_LOG_REPEAT_SECONDS):
        logger.warning("NVIDIA telemetry unavailable: %s", error)
        _nvml_last_logged_error = error
        _nvml_last_logged_ts = now


def _read_gpus() -> Tuple[Dict[int, Dict], Optional[str]]:
    """Query NVML once. Returns ({gpu_index: metrics}, error).

    error is None when every GPU was read; otherwise a "<ExceptionType>: <msg>"
    string (init failure, no devices, or the first per-GPU failure). GPUs that
    could not be read are absent from the dict.
    """
    global _nvml_last_fail_ts, _nvml_last_error

    if (_nvml_last_error is not None
            and time.monotonic() - _nvml_last_fail_ts < _NVML_RETRY_SECONDS):
        return {}, _nvml_last_error  # inside backoff window, don't re-attempt

    try:
        import pynvml
        pynvml.nvmlInit()
    except Exception as e:
        _nvml_last_fail_ts = time.monotonic()
        _nvml_last_error = _fmt_exc(e)
        _note_nvml_state(_nvml_last_error)
        return {}, _nvml_last_error

    gpus: Dict[int, Dict] = {}
    error: Optional[str] = None
    try:
        count = 0
        try:
            count = pynvml.nvmlDeviceGetCount()
            if count < 1:
                error = "NoGpuError: NVML reported 0 devices"
        except Exception as e:
            error = _fmt_exc(e)
        for i in range(min(4, count)):
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                mem  = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                try:
                    power_w = round(pynvml.nvmlDeviceGetPowerUsage(handle) / 1000, 1)
                except Exception:
                    power_w = None  # sensor unsupported: unknown, not 0 W
            except Exception as e:
                if error is None:
                    error = f"GPU{i}: {_fmt_exc(e)}"
                continue
            gpus[i] = {
                "vram_used_gb":  round(mem.used  / 1024 ** 3, 2),
                "vram_total_gb": round(mem.total / 1024 ** 3, 1),
                "utilization":   util.gpu,
                "temp":          temp,
                "power_w":       power_w,
            }
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass

    if gpus:
        _nvml_last_error = None  # reads work; clear the backoff
    else:
        error = error or "NoGpuError: no GPU data returned"
        _nvml_last_fail_ts = time.monotonic()
        _nvml_last_error = error
    _note_nvml_state(error)
    return gpus, error


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
    could not (or only partly), `error` carries "<ExceptionType>: <msg>" and
    the affected GPUs report null metrics rather than zeros.
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
