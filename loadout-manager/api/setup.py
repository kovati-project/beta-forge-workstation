"""First-boot wizard API endpoints."""

import ipaddress
import json
import os
import re
import subprocess
import secrets as pysecrets
import psutil
import shutil
from pathlib import Path
from typing import Dict, List
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
import asyncio

try:
    from config import DATA_DIR, DOCKER_DIR, GENERATED_SECRETS
except ImportError:
    from ..config import DATA_DIR, DOCKER_DIR, GENERATED_SECRETS
from .envfile import read_env, set_env_values
from . import secrets as secrets_api  # owns COMPOSE_DIR and the compose invocation

router = APIRouter()

# docker/.env, bind-mounted read-write at /compose/.env (docker/compose.loadout.yml).
ENV_FILE = Path(os.getenv("ENV_FILE", "/compose/.env"))
SETUP_COMPLETE_FLAG = DATA_DIR / ".kovati-setup-complete"


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


def _parse_nvlink_pairs(topo: str) -> List[List[int]]:
    """NVLink pairs from `nvidia-smi topo -m`: every NV# cell above the diagonal.

    The matrix header names the GPU columns (GPU0 GPU1 ...); each GPU row then
    has one cell per column, "X" on the diagonal (self) and NV<n> where the
    two GPUs are joined by n bonded NVLinks.
    """
    columns: List[int] = []
    pairs: List[List[int]] = []
    for line in topo.splitlines():
        tokens = line.split()
        if not tokens:
            continue
        if not columns and tokens[0] == "GPU0":
            columns = [int(t[3:]) for t in tokens if re.fullmatch(r"GPU\d+", t)]
            continue
        m = re.fullmatch(r"GPU(\d+)", tokens[0])
        if not columns or not m:
            continue
        row = int(m.group(1))
        for col, cell in zip(columns, tokens[1:1 + len(columns)]):
            if re.fullmatch(r"NV\d+", cell) and row < col:
                pairs.append([row, col])
    return sorted(pairs)


def _detect_nvlink_pairs() -> List[List[int]]:
    """Detect NVLink connected GPU pairs ([] when nvidia-smi is unusable)."""
    try:
        result = subprocess.run(["nvidia-smi", "topo", "-m"],
                                capture_output=True, text=True, timeout=10)
    except Exception:
        return []
    if result.returncode != 0:
        return []
    return _parse_nvlink_pairs(result.stdout or "")


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
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):  # nvidia-ml-py < 12 returned bytes
                name = name.decode('utf-8', errors='ignore')
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
    
    # inference-4gpu is the default stack (Qwen3.8-27B for every LLM client);
    # dual-stack trades it for two unrelated models. Below two GPUs there is no
    # LLM profile: every vLLM service needs a GPU pair or all four.
    if n_gpus == 4:
        profile = "inference-4gpu"
    elif n_gpus == 2 and has_nvlink:
        profile = "inference-pair-a"
    elif n_gpus == 2:
        profile = "inference-pair-b"
    else:
        profile = "idle"
    
    return {
        "recommended": profile,
        "reason": f"{n_gpus} GPU(s), {'NVLink' if has_nvlink else 'no NVLink'}, {total_vram}GB VRAM"
    }


@router.post("/setup/generate-secrets")
async def generate_secrets() -> Dict:
    """Generate every platform secret that docker/.env does not have yet.

    Existing non-empty values are never replaced, so re-running is harmless
    (a running stack's databases keep their passwords), and every other entry
    in the file is kept. Only the newly generated values are returned, once,
    so the wizard can show or download them.
    """
    try:
        ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing = read_env(ENV_FILE)
        new = {k: pysecrets.token_urlsafe(32) for k in GENERATED_SECRETS if not existing.get(k)}
        if new:
            set_env_values(ENV_FILE, new)
        return {
            "keys": list(new),
            "secrets": new,
            "kept": [k for k in GENERATED_SECRETS if k not in new],
            "file": str(ENV_FILE),
        }
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Secret generation failed: {e}")


def _wg_key_file() -> Path:
    """The WireGuard private key lives next to the completion flag (under
    DATA_DIR), never in docker/.env, which several containers read."""
    return SETUP_COMPLETE_FLAG.parent / "wireguard" / "private.key"


def _run_wg(args: List[str], stdin: str = None) -> str:
    try:
        result = subprocess.run(["wg"] + args, input=stdin, capture_output=True,
                                text=True, timeout=5)
    except (OSError, subprocess.SubprocessError) as e:
        raise HTTPException(status_code=500, detail=f"wg {args[0]} failed: {e}")
    out = (result.stdout or "").strip()
    if result.returncode != 0 or not out:
        raise HTTPException(status_code=500, detail=f"wg {args[0]} failed (exit "
                            f"{result.returncode}): {(result.stderr or '').strip()[:200]}")
    return out


def _wireguard_keypair() -> tuple:
    """Reuse the stored key if there is one (a re-run must not break a tunnel
    that is already configured on the jumpbox); otherwise create it 0600."""
    key_file = _wg_key_file()
    if key_file.exists():
        privkey = key_file.read_text().strip()
    else:
        privkey = _run_wg(["genkey"])
        key_file.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(key_file.parent, 0o700)
        fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(privkey + "\n")
    return privkey, _run_wg(["pubkey"], stdin=privkey)


def _ip_or_400(field: str, value) -> str:
    try:
        return str(ipaddress.ip_address(str(value).strip()))
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field} is not an IP address")


def _as_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


@router.post("/setup/network")
async def setup_network(request: Request) -> Dict:
    """Configure network and WireGuard.

    Takes a JSON body (what the wizard UI sends) or query parameters:
    jumpbox_ip, enable_caddy, and optionally lan_ip. Values are validated as
    IP addresses before anything is written, so nothing can inject extra lines
    into docker/.env, and only these keys are changed in it.
    """
    params: Dict = dict(request.query_params)
    if (await request.body()).strip():
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(status_code=400, detail="Body is not valid JSON")
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="Body must be a JSON object")
        params.update(body)

    jumpbox_ip = _ip_or_400("jumpbox_ip", params.get("jumpbox_ip", "10.0.0.1"))
    enable_caddy = _as_bool(params.get("enable_caddy", True))
    updates = {"JUMPBOX_IP": jumpbox_ip,
               "CADDY_ENABLED": "true" if enable_caddy else "false"}
    if params.get("lan_ip"):
        updates["KOVATI_OS_LAN_IP"] = _ip_or_400("lan_ip", params["lan_ip"])

    _, pubkey = _wireguard_keypair()
    updates["WIREGUARD_PUBKEY"] = pubkey
    try:
        ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
        set_env_values(ENV_FILE, updates)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Network setup failed: {e}")
    return {
        "jumpbox_ip": jumpbox_ip,
        "wireguard_pubkey": pubkey,
        "caddy_enabled": enable_caddy,
    }


# Stacks whose containers have to be up for the platform to work; the GPU
# stacks (inference, training, studio) are started by the loadout manager.
CORE_STACKS = [f.strip() for f in os.getenv(
    "KOVATI_CORE_STACKS",
    "compose.storage.yml,compose.auth.yml,compose.monitoring.yml,compose.webui.yml",
).split(",") if f.strip()]
PULL_TIMEOUT_S = int(os.getenv("KOVATI_SETUP_PULL_TIMEOUT", "3600"))  # per stack


def _stack_files() -> List[str]:
    """Every compose file the platform ships, in a stable order."""
    return sorted(p.name for p in secrets_api.COMPOSE_DIR.glob("compose.*.yml"))


def _sse(line: str) -> str:
    return "data: " + line.replace("\n", " ").replace("\r", " ") + "\n\n"


@router.post("/setup/provision")
async def provision_stack():
    """Pull the images of every stack (SSE stream).

    One `docker compose pull` per compose file, including services behind
    compose profiles (the GPU stacks are mostly profiled) and skipping images
    that are built locally. Lines: "Pulling <file>...", then "✓ <file>" or
    "✗ <file>: ...", "Progress: i/n", and a final "✓ All images provisioned"
    only if every pull succeeded.
    """
    async def event_generator():
        files = _stack_files()
        if not files:
            yield _sse(f"✗ No compose files found in {secrets_api.COMPOSE_DIR}")
            return
        failed = []
        for i, cf in enumerate(files):
            yield _sse(f"Pulling {cf}...")
            cmd = secrets_api._compose(cf) + ["--profile", "*", "pull", "--ignore-buildable"]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
                tail = ""

                async def drain():
                    nonlocal tail
                    async for raw in proc.stdout:
                        line = raw.decode(errors="replace").strip()
                        if line:
                            tail = line
                    return await proc.wait()
                try:
                    rc = await asyncio.wait_for(drain(), PULL_TIMEOUT_S)
                except asyncio.TimeoutError:
                    proc.kill()
                    rc, tail = -1, f"timed out after {PULL_TIMEOUT_S}s"
            except Exception as e:
                rc, tail = -1, f"{type(e).__name__}: {e}"
            if rc == 0:
                yield _sse(f"✓ {cf}")
            else:
                failed.append(cf)
                yield _sse(f"✗ {cf}: {tail[:200] or f'exit {rc}'}")
            yield _sse(f"Progress: {i + 1}/{len(files)}")
        if failed:
            yield _sse(f"✗ {len(failed)} of {len(files)} stacks failed to pull: {', '.join(failed)}")
        else:
            yield _sse("✓ All images provisioned")

    return StreamingResponse(event_generator(), media_type="text/event-stream")


async def _compose_output(cf: str, args: List[str]) -> tuple:
    proc = await asyncio.create_subprocess_exec(
        *(secrets_api._compose(cf) + args),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await asyncio.wait_for(proc.communicate(), 30)
    return proc.returncode, (out or b"").decode(errors="replace"), (err or b"").decode(errors="replace")


def _parse_ps(text: str) -> Dict[str, Dict]:
    """`docker compose ps --format json`: an array (older compose) or one
    object per line (2.21+). Keyed by service."""
    text = text.strip()
    if not text:
        return {}
    try:
        rows = json.loads(text)
        rows = rows if isinstance(rows, list) else [rows]
    except ValueError:
        rows = [json.loads(l) for l in text.splitlines() if l.strip()]
    return {r.get("Service"): r for r in rows if isinstance(r, dict)}


async def _check_stack(cf: str) -> List[tuple]:
    """[(label, ok, detail)] for each default (non-profiled) service of cf."""
    try:
        rc, out, err = await _compose_output(cf, ["config", "--services"])
        if rc != 0:
            return [(cf, False, f"compose config failed: {err.strip()[:200]}")]
        expected = [s for s in out.split() if s]
        if not expected:
            return [(cf, False, "no services found")]
        rc, out, err = await _compose_output(cf, ["ps", "-a", "--format", "json"])
        if rc != 0:
            return [(cf, False, f"compose ps failed: {err.strip()[:200]}")]
        running = _parse_ps(out)
    except Exception as e:
        return [(cf, False, f"{type(e).__name__}: {e}")]
    results = []
    for svc in expected:
        row = running.get(svc)
        if not row:
            results.append((svc, False, "not created"))
            continue
        st, health = row.get("State", ""), row.get("Health", "")
        if st != "running":
            results.append((svc, False, st or "unknown state"))
        elif health and health != "healthy":
            results.append((svc, False, health))
        else:
            results.append((svc, True, ""))
    return results


@router.post("/setup/validate")
async def validate_stack():
    """Check that the platform is actually up (SSE stream).

    Every generated secret must be set in docker/.env, and every default
    service of the core stacks must be running (and healthy, where it has a
    healthcheck). Lines: "Checking ...", "✓ <name>" or "✗ <name>: <why>",
    "Progress: passed/total", then "✓ Validation complete" or a "✗" summary.
    """
    async def event_generator():
        passed = total = 0
        yield _sse("Checking secrets...")
        env = read_env(ENV_FILE)
        missing = [k for k in GENERATED_SECRETS if not env.get(k)]
        total += 1
        if missing:
            yield _sse(f"✗ Secrets: {len(missing)} not set (run Generate secrets)")
        else:
            passed += 1
            yield _sse("✓ Secrets")
        for cf in CORE_STACKS:
            yield _sse(f"Checking {cf}...")
            for name, ok, detail in await _check_stack(cf):
                total += 1
                if ok:
                    passed += 1
                    yield _sse(f"✓ {name}")
                else:
                    yield _sse(f"✗ {name}: {detail}")
        yield _sse(f"Progress: {passed}/{total}")
        if passed == total:
            yield _sse("✓ Validation complete")
        else:
            yield _sse(f"✗ Validation failed: {total - passed} of {total} checks failed")

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
