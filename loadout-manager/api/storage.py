"""Storage and data management API endpoints."""

import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pathlib import Path

try:
    from config import DATA_DIR
except ImportError:
    from ..config import DATA_DIR

router = APIRouter()

QDRANT_URL = "http://localhost:6333"

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

try:
    import psutil
    _have_psutil = True
except ImportError:
    _have_psutil = False

try:
    import psycopg2
    _have_psycopg2 = True
except ImportError:
    _have_psycopg2 = False

import httpx


def _fmt(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def _get_partitions() -> List[Dict]:
    """Return disk partitions with usage stats."""
    if not _have_psutil:
        try:
            stat = shutil.disk_usage(DATA_DIR)
            return [{
                "device": "unknown",
                "mountpoint": str(DATA_DIR),
                "fstype": "unknown",
                "total": stat.total,
                "used": stat.used,
                "free": stat.free,
                "percent": round(stat.used / stat.total * 100, 1) if stat.total else 0,
                "total_human": _fmt(stat.total),
                "used_human": _fmt(stat.used),
                "free_human": _fmt(stat.free),
            }]
        except Exception:
            return []

    result = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            result.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "fstype": part.fstype,
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent": round(usage.percent, 1),
                "total_human": _fmt(usage.total),
                "used_human": _fmt(usage.used),
                "free_human": _fmt(usage.free),
            })
        except Exception:
            continue
    return result


def _mountpoint_for(path: str, partitions: List[Dict]) -> str:
    """Find the best-matching mountpoint for a given path."""
    best = ""
    for p in partitions:
        mp = p["mountpoint"]
        if path.startswith(mp) and len(mp) > len(best):
            best = mp
    return best or "/"


def _get_minio_collections(partitions: List[Dict]) -> List[Dict]:
    if not minio_client:
        return []
    try:
        buckets = minio_client.list_buckets()
        result = []
        for bucket in buckets:
            size = 0
            count = 0
            try:
                for obj in minio_client.list_objects(bucket.name, recursive=True):
                    size += obj.size or 0
                    count += 1
            except Exception:
                pass
            result.append({
                "name": bucket.name,
                "object_count": count,
                "size_bytes": size,
                "size_human": _fmt(size),
                "created": bucket.creation_date.isoformat() if bucket.creation_date else None,
                "mountpoint": _mountpoint_for(str(DATA_DIR), partitions),
            })
        return result
    except Exception:
        return []


async def _get_qdrant_collections(partitions: List[Dict]) -> List[Dict]:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{QDRANT_URL}/collections")
            data = resp.json()
            collections = data.get("result", {}).get("collections", [])
            result = []
            for col in collections:
                name = col.get("name", "")
                points = 0
                vectors_config = None
                try:
                    info_resp = await client.get(f"{QDRANT_URL}/collections/{name}")
                    info = info_resp.json().get("result", {})
                    points = info.get("points_count", 0)
                    vectors_config = info.get("config", {}).get("params", {}).get("vectors", None)
                except Exception:
                    pass
                result.append({
                    "name": name,
                    "points_count": points,
                    "vectors_config": vectors_config,
                    "size_bytes": 0,
                    "size_human": "—",
                    "mountpoint": _mountpoint_for(str(DATA_DIR), partitions),
                })
            return result
    except Exception:
        return []


def _get_postgres_collections(partitions: List[Dict]) -> List[Dict]:
    if not _have_psycopg2:
        return []
    try:
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            user=os.getenv("POSTGRES_USER", "postgres"),
            password=os.getenv("POSTGRES_PASSWORD", ""),
            database="postgres",
            connect_timeout=2,
        )
        cur = conn.cursor()
        cur.execute(
            "SELECT datname, pg_database_size(datname) FROM pg_database "
            "WHERE datistemplate = false ORDER BY datname"
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        mp = _mountpoint_for(str(DATA_DIR), partitions)
        return [
            {
                "name": row[0],
                "size_bytes": row[1] or 0,
                "size_human": _fmt(row[1] or 0),
                "mountpoint": mp,
            }
            for row in rows
        ]
    except Exception:
        return []


def _get_filesystem_collections(partitions: List[Dict]) -> List[Dict]:
    result = []
    for name in ("models", "datasets", "checkpoints", "backups"):
        dir_path = DATA_DIR / name
        size = 0
        if dir_path.exists():
            try:
                size = sum(f.stat().st_size for f in dir_path.rglob("*") if f.is_file())
            except Exception:
                pass
        result.append({
            "name": name,
            "path": str(dir_path),
            "size_bytes": size,
            "size_human": _fmt(size) if size else "0 B",
            "mountpoint": _mountpoint_for(str(DATA_DIR), partitions),
        })
    return result


@router.get("/storage/summary")
async def get_storage_summary() -> Dict:
    """Get full storage summary: partitions + all collections."""
    partitions = _get_partitions()
    minio = _get_minio_collections(partitions)
    qdrant = await _get_qdrant_collections(partitions)
    postgres = _get_postgres_collections(partitions)
    filesystem = _get_filesystem_collections(partitions)

    return {
        "partitions": partitions,
        "collections": {
            "minio": minio,
            "qdrant": qdrant,
            "postgres": postgres,
            "filesystem": filesystem,
        },
    }


@router.get("/storage/detail")
async def get_storage_detail(type: str, name: str) -> Dict:
    """Get verbose detail for a specific collection."""
    partitions = _get_partitions()

    def _hardware_card(mp: str) -> Dict:
        part = next((p for p in partitions if p["mountpoint"] == mp), None)
        if part:
            return {
                "device": part["device"],
                "mountpoint": part["mountpoint"],
                "fstype": part["fstype"],
                "total_human": part["total_human"],
                "used_human": part["used_human"],
                "free_human": part["free_human"],
                "percent": part["percent"],
            }
        return {"device": "—", "mountpoint": mp or "—", "fstype": "—",
                "total_human": "—", "used_human": "—", "free_human": "—", "percent": 0}

    mp = _mountpoint_for(str(DATA_DIR), partitions)

    if type == "minio":
        if not minio_client:
            raise HTTPException(status_code=503, detail="MinIO unavailable")
        try:
            items = []
            for obj in minio_client.list_objects(name, recursive=True):
                items.append({
                    "name": obj.object_name,
                    "size_human": _fmt(obj.size or 0),
                    "size_bytes": obj.size or 0,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                })
            items.sort(key=lambda x: x["size_bytes"], reverse=True)
            return {
                "type": "minio",
                "name": name,
                "hardware": _hardware_card(mp),
                "items": items,
                "meta": {"object_count": len(items)},
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    elif type == "qdrant":
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{QDRANT_URL}/collections/{name}")
                data = resp.json().get("result", {})
                config = data.get("config", {}).get("params", {})
                return {
                    "type": "qdrant",
                    "name": name,
                    "hardware": _hardware_card(mp),
                    "items": [],
                    "meta": {
                        "status": data.get("status"),
                        "points_count": data.get("points_count", 0),
                        "segments_count": data.get("segments_count", 0),
                        "vectors_config": config.get("vectors", None),
                        "distance": config.get("distance", None),
                        "on_disk_payload": config.get("on_disk_payload", None),
                    },
                }
        except Exception as e:
            raise HTTPException(status_code=503, detail=f"Qdrant unavailable: {e}")

    elif type == "postgres":
        if not _have_psycopg2:
            raise HTTPException(status_code=503, detail="psycopg2 not installed")
        try:
            conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", "5432")),
                user=os.getenv("POSTGRES_USER", "postgres"),
                password=os.getenv("POSTGRES_PASSWORD", ""),
                database=name,
                connect_timeout=2,
            )
            cur = conn.cursor()
            cur.execute(
                "SELECT tablename, pg_total_relation_size(quote_ident(tablename)) "
                "FROM pg_tables WHERE schemaname = 'public' ORDER BY 2 DESC"
            )
            rows = cur.fetchall()
            cur.close()
            conn.close()
            items = [
                {"name": r[0], "size_human": _fmt(r[1] or 0), "size_bytes": r[1] or 0}
                for r in rows
            ]
            return {
                "type": "postgres",
                "name": name,
                "hardware": _hardware_card(mp),
                "items": items,
                "meta": {"table_count": len(items)},
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    elif type == "filesystem":
        dir_path = DATA_DIR / name
        if not dir_path.exists():
            raise HTTPException(status_code=404, detail=f"Directory not found: {name}")
        try:
            items = []
            for entry in dir_path.iterdir():
                size = 0
                if entry.is_file():
                    size = entry.stat().st_size
                elif entry.is_dir():
                    try:
                        size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
                    except Exception:
                        pass
                items.append({
                    "name": entry.name,
                    "is_dir": entry.is_dir(),
                    "size_bytes": size,
                    "size_human": _fmt(size) if size else "0 B",
                    "modified": datetime.fromtimestamp(entry.stat().st_mtime).isoformat(),
                })
            items.sort(key=lambda x: x["size_bytes"], reverse=True)
            return {
                "type": "filesystem",
                "name": name,
                "hardware": _hardware_card(mp),
                "items": items,
                "meta": {"path": str(dir_path), "item_count": len(items)},
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    else:
        raise HTTPException(status_code=400, detail=f"Unknown type: {type}")


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
            except Exception:
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
        i = 0
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= n:
                    break
                lines.append(line.strip())
        return {"path": path, "lines": lines, "total_lines": i + 1}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/storage/file")
async def delete_file(path: str) -> Dict:
    """Delete a file or directory."""
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
