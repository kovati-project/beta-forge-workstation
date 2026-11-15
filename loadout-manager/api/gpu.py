"""The single NVML reader shared by main.py (/status, VRAM gate) and api/metrics.py.

NVML failure used to be swallowed and reported as an empty GPU list, which the
UI could not tell apart from "no GPUs" (TASK-010 / #5). read_gpu_telemetry()
returns an explicit availability flag and error string instead. `gpus` is
always a list, so consumers written against the old shape keep working.

NVML is initialised per call (init -> query -> shutdown in finally), so a
driver that becomes healthy after container start is picked up without a
restart.
"""

import logging
import time
from typing import Dict, Optional

import pynvml

logger = logging.getLogger(__name__)

# Repeated polls must not flood the log with an identical failure every 3s.
_GPU_ERROR_RELOG_SECS = 300
_gpu_last_error: Optional[str] = None
_gpu_last_error_logged = 0.0


def _log_gpu_telemetry(error: Optional[str], exc: Optional[BaseException] = None) -> None:
    """Log availability transitions; re-log a persisting failure only occasionally."""
    global _gpu_last_error, _gpu_last_error_logged
    if error is None:
        if _gpu_last_error is not None:
            logger.info(f"GPU telemetry recovered (was: {_gpu_last_error})")
            _gpu_last_error = None
        return
    now = time.monotonic()
    if error != _gpu_last_error or now - _gpu_last_error_logged >= _GPU_ERROR_RELOG_SECS:
        logger.error(f"GPU telemetry unavailable: {error}", exc_info=exc)
        _gpu_last_error = error
        _gpu_last_error_logged = now


def _gpu_unavailable(stage: str, exc: Optional[BaseException] = None,
                     message: Optional[str] = None) -> Dict:
    if message is None:
        message = f"{type(exc).__name__}: {exc}"
    error = f"{stage}: {message}"[:300]
    _log_gpu_telemetry(error, exc)
    return {"available": False, "gpus": [], "error": error}


def read_gpu_telemetry() -> Dict:
    """Read raw per-GPU metrics from NVML.

    Returns {"available": bool, "gpus": [...], "error": str | None}. When NVML
    cannot be initialised, enumerated or queried, `available` is False, `gpus`
    is [] and `error` says why. Zero visible devices is also reported as
    unavailable: on this workstation it means the container cannot see the GPUs.
    `power_w` is None when the power sensor is unsupported (unknown, not 0 W).
    """
    try:
        pynvml.nvmlInit()
    except Exception as e:
        return _gpu_unavailable("nvmlInit", e)

    stage = "enumerate devices"
    try:
        count = pynvml.nvmlDeviceGetCount()
        if count == 0:
            return _gpu_unavailable(
                stage, message="NVML initialised but reports 0 GPU devices "
                               "(check NVIDIA_VISIBLE_DEVICES and the device reservation)")
        gpus = []
        for i in range(count):
            stage = f"query GPU {i}"
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
            try:
                power_w = round(pynvml.nvmlDeviceGetPowerUsage(handle) / 1000, 1)
            except Exception:
                power_w = None
            try:
                _pci = pynvml.nvmlDeviceGetPciInfo(handle)
                bus_id = _pci.busId.decode() if isinstance(_pci.busId, bytes) else _pci.busId
            except Exception:
                bus_id = None
            gpus.append({
                "index": i,
                "vram_used_gb": round(mem.used / 1024**3, 1),
                "vram_total_gb": round(mem.total / 1024**3, 1),
                "vram_free_gb": round(mem.free / 1024**3, 1),
                "utilization_pct": util.gpu,
                "temp_c": temp,
                "power_w": power_w,
                "bus_id": bus_id,
            })
    except Exception as e:
        return _gpu_unavailable(stage, e)
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass

    _log_gpu_telemetry(None)
    return {"available": True, "gpus": gpus, "error": None}
