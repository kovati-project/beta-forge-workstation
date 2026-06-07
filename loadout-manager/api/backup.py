"""Backup management API endpoints."""

import asyncio
import glob
import os
import subprocess
from datetime import datetime
from typing import Dict, Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

router = APIRouter()

BACKUP_DIR = os.getenv("BACKUP_DIR", "/data/backups")
RESTORE_TARGET = os.getenv("RESTORE_TARGET", "/data")

BACKUP_CONFIG = {
    "schedule": "0 6 * * *",
    "destination": BACKUP_DIR,
    "last_backup": {
        "date": "2026-06-05 06:00",
        "size": "42 GB",
        "status": "success",
    }
}

BACKUP_HISTORY = [
    {"id": "1", "date": "2026-06-05 06:00", "size": "42 GB", "status": "success",
     "archive": f"{BACKUP_DIR}/backup-20260605-0600.tar.gz"},
    {"id": "2", "date": "2026-06-04 06:00", "size": "41 GB", "status": "success",
     "archive": f"{BACKUP_DIR}/backup-20260604-0600.tar.gz"},
    {"id": "3", "date": "2026-06-03 06:00", "size": "43 GB", "status": "fail",
     "archive": None},
]


def _get_backup_by_id(backup_id: str) -> Optional[Dict]:
    return next((b for b in BACKUP_HISTORY if b["id"] == backup_id), None)


@router.get("/backup/config")
async def get_backup_config() -> Dict:
    return BACKUP_CONFIG


@router.patch("/backup/config")
async def update_backup_config(schedule: str = None) -> Dict:
    if schedule:
        BACKUP_CONFIG["schedule"] = schedule
    return BACKUP_CONFIG


@router.get("/backup/history")
async def get_backup_history(n: int = 10) -> Dict:
    # Merge in any archives actually present on disk
    on_disk = {os.path.basename(p): p for p in glob.glob(f"{BACKUP_DIR}/backup-*.tar.gz")}
    for entry in BACKUP_HISTORY:
        archive = entry.get("archive")
        if archive and os.path.exists(archive):
            entry["size_bytes"] = os.path.getsize(archive)
        entry["restorable"] = bool(archive and os.path.exists(archive))
    return {"backups": BACKUP_HISTORY[:n]}


@router.post("/backup/run")
async def run_backup_now(request: Request):
    """Run backup immediately (SSE stream)."""
    async def event_generator():
        try:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M")
            archive_path = f"{BACKUP_DIR}/backup-{timestamp}.tar.gz"
            os.makedirs(BACKUP_DIR, exist_ok=True)

            yield f"data: Starting backup at {timestamp}...\n\n"
            yield f"data: Archive target: {archive_path}\n\n"

            # Stream tar progress via --checkpoint
            cmd = [
                "tar", "--create", "--gzip",
                "--checkpoint=1000", "--checkpoint-action=echo=#%{read,MiB}MiB",
                f"--file={archive_path}",
                "--exclude=/data/backups",
                RESTORE_TARGET,
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            async for line in proc.stdout:
                decoded = line.decode().strip()
                if decoded:
                    yield f"data: {decoded}\n\n"

            await proc.wait()

            if proc.returncode == 0:
                size_bytes = os.path.getsize(archive_path) if os.path.exists(archive_path) else 0
                size_gb = round(size_bytes / (1024 ** 3), 1)
                entry = {
                    "id": str(len(BACKUP_HISTORY) + 1),
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "size": f"{size_gb} GB",
                    "status": "success",
                    "archive": archive_path,
                }
                BACKUP_HISTORY.insert(0, entry)
                BACKUP_CONFIG["last_backup"] = {"date": entry["date"], "size": entry["size"], "status": "success"}
                yield f"data: ✓ Backup complete: {size_gb} GB → {archive_path}\n\n"
            else:
                yield f"data: ✗ Backup failed (exit {proc.returncode})\n\n"
        except Exception as e:
            yield f"data: Error: {e}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/backup/restore/{backup_id}")
async def restore_backup(backup_id: str):
    """Restore from a backup archive (SSE stream)."""
    entry = _get_backup_by_id(backup_id)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Backup {backup_id} not found")

    archive = entry.get("archive")
    if not archive:
        raise HTTPException(status_code=400, detail="This backup has no archive (failed backup)")
    if not os.path.exists(archive):
        raise HTTPException(status_code=404, detail=f"Archive not found on disk: {archive}")

    async def event_generator():
        try:
            yield f"data: Starting restore from {archive}...\n\n"
            yield f"data: Target: {RESTORE_TARGET}\n\n"
            yield f"data: ⚠ This will overwrite existing data — ensure services are stopped\n\n"

            # Stop managed services before restoring
            yield f"data: Stopping Docker services...\n\n"
            stop_proc = await asyncio.create_subprocess_exec(
                "docker", "compose",
                "--project-directory", "/opt/loadout",
                "stop",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            async for line in stop_proc.stdout:
                decoded = line.decode().strip()
                if decoded:
                    yield f"data:   {decoded}\n\n"
            await stop_proc.wait()
            yield f"data: Services stopped.\n\n"

            # Extract archive
            yield f"data: Extracting {os.path.basename(archive)}...\n\n"
            cmd = [
                "tar", "--extract", "--gzip",
                "--checkpoint=1000", "--checkpoint-action=echo=#%{read,MiB}MiB read",
                f"--file={archive}",
                f"--directory={RESTORE_TARGET}",
                "--strip-components=1",
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            async for line in proc.stdout:
                decoded = line.decode().strip()
                if decoded:
                    yield f"data: {decoded}\n\n"
            await proc.wait()

            if proc.returncode == 0:
                yield f"data: ✓ Restore complete. Restart services to apply.\n\n"
            else:
                yield f"data: ✗ Restore failed (exit {proc.returncode}) — check data integrity\n\n"
        except Exception as e:
            yield f"data: Error: {e}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.delete("/backup/{backup_id}")
async def delete_backup(backup_id: str) -> Dict:
    global BACKUP_HISTORY
    entry = _get_backup_by_id(backup_id)
    if entry and entry.get("archive") and os.path.exists(entry["archive"]):
        os.remove(entry["archive"])
    BACKUP_HISTORY = [b for b in BACKUP_HISTORY if b["id"] != backup_id]
    return {"status": "deleted", "backup_id": backup_id}
