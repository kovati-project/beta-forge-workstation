"""Storage and data management API endpoints."""

import os
import shutil
from typing import Dict, List
from fastapi import APIRouter, HTTPException
from pathlib import Path

try:
    from config import DATA_DIR
except ImportError:
    from ..config import DATA_DIR

router = APIRouter()

# Try to initialize MinIO client
try:
    from minio import Minio
    minio_client = Minio(
        "localhost:9000",
        access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
        secure=False
    )
except Exception as e:
    print(f"Warning: MinIO not available: {e}")
    minio_client = None


@router.get("/storage/buckets")
async def list_buckets() -> Dict:
    """List all MinIO buckets with sizes."""
    if not minio_client:
        return {"buckets": []}
    
    try:
        buckets = minio_client.list_buckets()
        result = []
        for bucket in buckets:
            size = 0
            try:
                for obj in minio_client.list_objects(bucket.name, recursive=True):
                    size += obj.size
            except:
                pass
            
            result.append({
                "name": bucket.name,
                "size": size,
                "created": bucket.creation_date.isoformat() if bucket.creation_date else None,
            })
        return {"buckets": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/storage/list")
async def list_storage(path: str = "") -> Dict:
    """List files in storage directory."""
    try:
        full_path = DATA_DIR / path if path else DATA_DIR
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Path not found")
        
        files = []
        for item in full_path.iterdir():
            files.append({
                "name": item.name,
                "size": item.stat().st_size if item.is_file() else 0,
                "is_dir": item.is_dir(),
                "modified": item.stat().st_mtime,
            })
        
        return {"files": files, "path": str(full_path)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/storage/preview")
async def preview_file(path: str, n: int = 3) -> Dict:
    """Preview first N lines of a file."""
    try:
        full_path = DATA_DIR / path
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        lines = []
        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                if i >= n:
                    break
                lines.append(line.strip())
        
        return {
            "path": path,
            "lines": lines,
            "total_lines": i + 1,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/storage/summary")
async def get_storage_summary() -> Dict:
    """Get storage usage summary."""
    try:
        # Disk usage
        disk_stat = shutil.disk_usage(DATA_DIR)
        
        summary = {
            "disk": {
                "total": disk_stat.total,
                "used": disk_stat.used,
                "free": disk_stat.free,
                "percent": (disk_stat.used / disk_stat.total * 100) if disk_stat.total > 0 else 0,
            },
            "models": 0,
            "datasets": 0,
            "checkpoints": 0,
        }
        
        # Calculate directory sizes
        for dir_name in ["models", "datasets", "checkpoints"]:
            dir_path = DATA_DIR / dir_name
            if dir_path.exists():
                size = sum(
                    f.stat().st_size for f in dir_path.rglob('*') if f.is_file()
                )
                summary[dir_name] = size
        
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/storage/file")
async def delete_file(path: str) -> Dict:
    """Delete a file."""
    try:
        full_path = DATA_DIR / path
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        if full_path.is_file():
            full_path.unlink()
        else:
            shutil.rmtree(full_path)
        
        return {"status": "deleted", "path": path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
