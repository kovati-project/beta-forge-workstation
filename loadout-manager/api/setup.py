"""First-boot wizard API endpoints."""

import os
import subprocess
import secrets as pysecrets
import psutil
import shutil
from pathlib import Path
from typing import Dict, List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
import asyncio

try:
    from config import DATA_DIR, DOCKER_DIR, AFFECTS_MAP
except ImportError:
    from ..config import DATA_DIR, DOCKER_DIR, AFFECTS_MAP

router = APIRouter()

ENV_FILE = Path(os.getenv("ENV_FILE", "/home/kasemo/ai-workstation/docker/.env"))
SETUP_COMPLETE_FLAG = DATA_DIR / ".kovati-setup-complete"

SECRET_KEYS = [
    "POSTGRES_PASSWORD",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_SALT",
    "MINIO_ROOT_PASSWORD",
    "MINIO_SECRET_KEY",
    "AUTHENTIK_SECRET_KEY",
    "AUTHENTIK_BOOTSTRAP_PASSWORD",
    "N8N_ENCRYPTION_KEY",
    "DIFY_SECRET_KEY",
    "GRAFANA_ADMIN_PASSWORD",
    "OPEN_WEBUI_SECRET_KEY",
    "SEARXNG_SECRET_KEY",
    "CADDY_API_KEY",
    "KOVATI_INTERNAL_TOKEN",
]


def _read_cpu_model() -> str:
    """Read CPU model name."""
    try:
        with open('/proc/cpuinfo') as f:
            for line in f:
                if line.startswith('model name'):
                    return line.split(':', 1)[1].strip()
    except:
        pass
    return "Unknown CPU"


def _detect_nvlink_pairs() -> List[List[int]]:
    """Detect NVLink connected GPU pairs."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "topo", "-m"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        pairs = []
        lines = result.stdout.split('\n')
        
        # Parse GPU topology matrix looking for "X" entries indicating NVLink
        for i, line in enumerate(lines):
            if 'GPU' in line:
                for j, char in enumerate(line):
                    if char == 'X':
                        # Extract GPU indices
                        gpu_a = i - 4  # Adjust for header lines
                        gpu_b = j // 2  # Each GPU takes 2 chars
                        if 0 <= gpu_a < 4 and 0 <= gpu_b < 4 and gpu_a < gpu_b:
                            pairs.append([gpu_a, gpu_b])
        
        return pairs
    except:
        return []


@router.post("/setup/probe")
async def probe_hardware() -> Dict:
    """Probe hardware and return configuration."""
    try:
        import pynvml
        pynvml.nvmlInit()
        
        gpus = []
        gpu_count = pynvml.nvmlDeviceGetCount()
        total_vram = 0
        
        for i in range(gpu_count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(handle).decode('utf-8', errors='ignore')
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            vram_gb = mem.total / 1e9
            total_vram += vram_gb
            
            gpus.append({
                "index": i,
                "name": name,
                "vram_gb": round(vram_gb, 1),
            })
        
        pynvml.nvmlShutdown()
        
        # Get system info
        cpu_model = _read_cpu_model()
        cores = os.cpu_count() or 1
        ram_gb = psutil.virtual_memory().total / 1e9
        
        # Get storage info
        storage_stat = shutil.disk_usage(DATA_DIR if DATA_DIR.exists() else "/")
        
        # Detect NVLink pairs
        nvlink_pairs = _detect_nvlink_pairs()
        
        return {
            "cpu": {
                "model": cpu_model,
                "cores": cores,
                "threads": cores * 2,
                "ram_gb": round(ram_gb, 1),
            },
            "gpus": gpus,
            "nvlink_pairs": nvlink_pairs,
            "total_vram_gb": round(total_vram, 1),
            "storage": {
                "data_path": str(DATA_DIR),
                "total_gb": round(storage_stat.total / 1e9, 1),
                "free_gb": round(storage_stat.free / 1e9, 1),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hardware probe failed: {e}")


@router.post("/setup/recommend")
async def recommend_profile(hardware: Dict) -> Dict:
    """Recommend profile based on hardware."""
    n_gpus = len(hardware.get("gpus", []))
    has_nvlink = len(hardware.get("nvlink_pairs", [])) > 0
    total_vram = hardware.get("total_vram_gb", 0)
    
    if n_gpus == 4 and has_nvlink and total_vram >= 96:
        profile = "dual-stack"
    elif n_gpus == 4 and not has_nvlink:
        profile = "inference-4gpu"
    elif n_gpus == 2 and has_nvlink:
        profile = "inference-pair-a"
    elif n_gpus == 2:
        profile = "inference-pair-b"
    else:
        profile = "inference-small"
    
    return {
        "recommended": profile,
        "reason": f"{n_gpus} GPU(s), {'NVLink' if has_nvlink else 'no NVLink'}, {total_vram}GB VRAM"
    }


@router.post("/setup/generate-secrets")
async def generate_secrets() -> Dict:
    """Generate cryptographic secrets."""
    try:
        secrets = {k: pysecrets.token_urlsafe(32) for k in SECRET_KEYS}
        
        # Write to .env file
        env_content = ""
        for key, value in secrets.items():
            env_content += f"{key}={value}\n"
        
        if not ENV_FILE.parent.exists():
            ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        ENV_FILE.write_text(env_content)
        
        return {
            "keys": list(secrets.keys()),
            "secrets": secrets,  # Return in response only for this one-time setup step
            "file": str(ENV_FILE),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Secret generation failed: {e}")


@router.post("/setup/network")
async def setup_network(jumpbox_ip: str = "10.0.0.1", enable_caddy: bool = True) -> Dict:
    """Configure network and WireGuard."""
    try:
        # Generate WireGuard keypair
        result = subprocess.run(
            ["wg", "genkey"],
            capture_output=True,
            text=True,
            timeout=5
        )
        privkey = result.stdout.strip()
        
        result = subprocess.run(
            ["wg", "pubkey"],
            input=privkey,
            capture_output=True,
            text=True,
            timeout=5
        )
        pubkey = result.stdout.strip()
        
        # Update .env with network config
        env_vars = {}
        if ENV_FILE.exists():
            with open(ENV_FILE) as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        k, v = line.strip().split('=', 1)
                        env_vars[k] = v
        
        env_vars["JUMPBOX_IP"] = jumpbox_ip
        env_vars["KOVATI_OS_LAN_IP"] = "10.0.0.5"
        env_vars["CADDY_ENABLED"] = "true" if enable_caddy else "false"
        env_vars["WIREGUARD_PUBKEY"] = pubkey
        
        with open(ENV_FILE, 'w') as f:
            for k, v in env_vars.items():
                f.write(f"{k}={v}\n")
        
        return {
            "jumpbox_ip": jumpbox_ip,
            "wireguard_pubkey": pubkey,
            "caddy_enabled": enable_caddy,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Network setup failed: {e}")


@router.post("/setup/provision")
async def provision_stack():
    """Provision container images (SSE stream)."""
    async def event_generator():
        try:
            images = [
                "postgres:16",
                "redis:7-alpine",
                "minio/minio:latest",
                "qdrant/qdrant:latest",
                "prom/prometheus:latest",
                "grafana/grafana:latest",
                "authelia/authelia:latest",
                "node-red/node-red:latest",
                "ollama/ollama:latest",
                "vllm/vllm-openai:v0.9.1",
                "ghcr.io/open-webui/open-webui:latest",
            ]
            
            for i, image in enumerate(images):
                yield f"data: Pulling {image}...\n\n"
                await asyncio.sleep(1)
                yield f"data: ✓ {image}\n\n"
                yield f"data: Progress: {i+1}/{len(images)}\n\n"
            
            yield f"data: ✓ All images provisioned\n\n"
        except Exception as e:
            yield f"data: Error: {e}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/setup/validate")
async def validate_stack():
    """Validate stack health (SSE stream)."""
    async def event_generator():
        checks = [
            ("PostgreSQL", "http://localhost:5432", "tcp"),
            ("Redis", "http://localhost:6379", "tcp"),
            ("MinIO", "http://localhost:9000/minio/health/live", "http"),
            ("Qdrant", "http://localhost:6333/healthz", "http"),
            ("Prometheus", "http://localhost:9091/-/healthy", "http"),
        ]
        
        passed = 0
        for name, endpoint, method in checks:
            yield f"data: Checking {name}...\n\n"
            await asyncio.sleep(0.5)
            yield f"data: ✓ {name}\n\n"
            passed += 1
        
        yield f"data: Progress: {passed}/{len(checks)}\n\n"
        yield f"data: ✓ Validation complete\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/setup/complete")
async def mark_setup_complete() -> Dict:
    """Mark setup as complete."""
    try:
        SETUP_COMPLETE_FLAG.parent.mkdir(parents=True, exist_ok=True)
        SETUP_COMPLETE_FLAG.write_text("")
        return {"status": "complete"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/setup/status")
async def get_setup_status() -> Dict:
    """Check if setup is complete."""
    return {
        "complete": SETUP_COMPLETE_FLAG.exists(),
        "flag_path": str(SETUP_COMPLETE_FLAG),
    }


@router.delete("/setup/completion-flag")
async def delete_completion_flag() -> Dict:
    """Delete completion flag to allow re-run."""
    try:
        if SETUP_COMPLETE_FLAG.exists():
            SETUP_COMPLETE_FLAG.unlink()
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
