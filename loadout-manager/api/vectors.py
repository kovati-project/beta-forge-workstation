"""Vector database API endpoints."""

from typing import Dict, List
import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter()

QDRANT_URL = "http://localhost:6333"


@router.get("/vectors/collections")
async def list_collections() -> Dict:
    """List all Qdrant collections."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{QDRANT_URL}/collections")
            return await response.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Qdrant unavailable: {e}")


@router.post("/vectors/search")
async def search_vectors(collection: str, query: List[float], limit: int = 10) -> Dict:
    """Search vectors in a collection."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{QDRANT_URL}/collections/{collection}/points/search",
                json={"vector": query, "limit": limit}
            )
            return await response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
