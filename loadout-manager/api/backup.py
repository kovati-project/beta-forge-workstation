"""Backup API: runs scripts/backup.sh and reports the runs it left on disk.

backup.sh backs up the named volumes, bind-mounted service data, Postgres dumps
and configs (not model weights) into BACKUP_ROOT/<YYYYmmdd-HHMMSS>/ and writes
a MANIFEST.txt listing what failed. It bind-mounts host paths into
`docker run alpine`, so it must see the host's paths: the API runs it in a
short-lived helper container from this image with /data and the repo mounted
at their host paths, not inside this container.

Restore is deliberately not offered here. Restoring volumes and databases means
stopping their consumers and has never been tested end to end; each run's
MANIFEST.txt carries the manual restore steps.
"""

import asyncio
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter()

# Same path inside this container (read-only mount) and on the host.
BACKUP_ROOT = Path(os.getenv("BACKUP_ROOT", "/data/backups"))
DATA_ROOT = os.getenv("DATA_ROOT", "/data")
# Host path of the repo checkout: the parent of docker/ (HOST_COMPOSE_DIR).
HOST_COMPOSE_DIR = os.getenv("HOST_COMPOSE_DIR", "")
HELPER_IMAGE = os.getenv("BACKUP_HELPER_IMAGE", "loadout-manager:latest")
HELPER_NAME = "loadout-backup"

RUN_ID = re.compile(r"^\d{8}-\d{6}$")
ANSI = re.compile(r"\x1b\[[0-9;]*m")
SCHEDULE = {
    "schedule": "daily 02:00",
    "schedule_source": "systemd ai-workstation-backup.timer "
                       "(installed by scripts/setup-systemd-service.sh)",
    "schedule_editable": False,
}

_run_lock = asyncio.Lock()


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def _describe(run: Path) -> Dict:
    """One backup run as the UI shows it, read from what is on disk."""
    files = [f for f in run.iterdir() if f.is_file()]
    manifest = run / "MANIFEST.txt"
    failed: List[str] = []
    if not manifest.exists():
        status = "incomplete"  # still running, or the script died before the end
    else:
        text = manifest.read_text(errors="replace")
        if "## FAILED" in text:
            failed = [l.strip() for l in text.split("## FAILED", 1)[1].split("##", 1)[0]
                      .splitlines() if l.strip()]
        status = "fail" if failed else "success"
    size = sum(f.stat().st_size for f in files)
    return {
        "id": run.name,
        "date": datetime.strptime(run.name, "%Y%m%d-%H%M%S").strftime("%Y-%m-%d %H:%M"),
        "size": _human(size),
        "size_bytes": size,
        "files": len([f for f in files if f.name != "MANIFEST.txt"]),
        "status": status,
        "failed": failed,
        "path": str(run),
        "restorable": False,
    }


def _runs() -> List[Dict]:
    if not BACKUP_ROOT.is_dir():
        return []
    runs = [d for d in BACKUP_ROOT.iterdir() if d.is_dir() and RUN_ID.match(d.name)]
    return [_describe(d) for d in sorted(runs, key=lambda d: d.name, reverse=True)]


def _host_repo() -> Optional[str]:
    return str(Path(HOST_COMPOSE_DIR).parent.as_posix()) if HOST_COMPOSE_DIR else None


def _helper_command(repo: str) -> List[str]:
    return [
        "docker", "run", "--rm", "--name", HELPER_NAME,
        "-v", "/var/run/docker.sock:/var/run/docker.sock",
        "-v", f"{DATA_ROOT}:{DATA_ROOT}",
        "-v", f"{repo}:{repo}:ro",
        "-e", f"DATA_ROOT={DATA_ROOT}",
        "-e", f"BACKUP_ROOT={BACKUP_ROOT.as_posix()}",
        "--entrypoint", "bash",
        HELPER_IMAGE, f"{repo}/scripts/backup.sh", "all",
    ]


@router.get("/backup/config")
async def get_backup_config() -> Dict:
    runs = _runs()
    last = runs[0] if runs else None
    return {
        **SCHEDULE,
        "destination": str(BACKUP_ROOT),
        "last_backup": ({"date": last["date"], "size": last["size"], "status": last["status"]}
                        if last else None),
    }


@router.patch("/backup/config")
async def update_backup_config() -> Dict:
    raise HTTPException(
        status_code=501,
        detail="The backup schedule is the systemd timer ai-workstation-backup.timer on the "
               "host; change it there (systemctl edit ai-workstation-backup.timer).")


@router.get("/backup/history")
async def get_backup_history(n: int = 10) -> Dict:
    return {"backups": _runs()[:max(n, 0)]}


@router.post("/backup/run")
async def run_backup_now():
    """Run scripts/backup.sh now and stream its output (SSE)."""
    repo = _host_repo()
    if repo is None:
        raise HTTPException(status_code=503, detail="HOST_COMPOSE_DIR is not set; cannot "
                                                    "locate scripts/backup.sh on the host")
    if _run_lock.locked():
        raise HTTPException(status_code=409, detail="A backup is already running")

    async def events():
        # Taken here, not in the handler: a client that disconnects before the
        # body starts would otherwise leave it held forever. The fixed helper
        # container name stops a second run that slips past the check above.
        if _run_lock.locked():
            yield "data: ✗ A backup is already running\n\n"
            return
        await _run_lock.acquire()
        try:
            yield "data: Running scripts/backup.sh in a helper container...\n\n"
            proc = await asyncio.create_subprocess_exec(
                *_helper_command(repo),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
            async for line in proc.stdout:
                text = ANSI.sub("", line.decode(errors="replace")).rstrip()
                if text:
                    yield f"data: {text}\n\n"
            rc = await proc.wait()
            if rc == 0:
                yield "data: ✓ Backup complete\n\n"
            else:
                yield f"data: ✗ Backup failed (exit {rc}); see the run's MANIFEST.txt\n\n"
        except Exception as e:
            yield f"data: ✗ Error: {e}\n\n"
        finally:
            _run_lock.release()

    return StreamingResponse(events(), media_type="text/event-stream")


@router.post("/backup/restore/{backup_id}")
async def restore_backup(backup_id: str):
    raise HTTPException(
        status_code=501,
        detail="Restore is not available from the API. Follow the restore steps in "
               f"{BACKUP_ROOT}/<run>/MANIFEST.txt, stopping the affected services first.")


@router.delete("/backup/{backup_id}")
async def delete_backup(backup_id: str) -> Dict:
    if not RUN_ID.match(backup_id):
        raise HTTPException(status_code=400, detail="Invalid backup id")
    if not (BACKUP_ROOT / backup_id).is_dir():
        raise HTTPException(status_code=404, detail=f"Backup {backup_id} not found")
    if _run_lock.locked():
        raise HTTPException(status_code=409, detail="A backup is running")
    # Run files are root-owned mode 600 and BACKUP_ROOT is read-only here, so
    # the delete runs as root in a throwaway container.
    root = BACKUP_ROOT.as_posix()
    proc = await asyncio.create_subprocess_exec(
        "docker", "run", "--rm", "-v", f"{root}:{root}", "alpine",
        "rm", "-rf", f"{root}/{backup_id}",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    out, _ = await proc.communicate()
    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Delete failed: "
                                                    f"{(out or b'').decode(errors='replace')[-300:]}")
    return {"status": "deleted", "backup_id": backup_id}
