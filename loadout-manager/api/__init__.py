"""API routers for Kovati OS."""

from fastapi import APIRouter
from . import services, metrics, training, storage, models, auth, secrets, network, stack, backup, activity, traces, vectors, mcp, keys, setup, voice, admin, operations

def create_router():
    """Create and configure the main API router."""
    router = APIRouter()
    
    router.include_router(services.router, prefix="/api", tags=["services"])
    router.include_router(metrics.router, prefix="/api", tags=["metrics"])
    router.include_router(training.router, prefix="/api", tags=["training"])
    router.include_router(storage.router, prefix="/api", tags=["storage"])
    router.include_router(models.router, prefix="/api", tags=["models"])
    router.include_router(auth.router, prefix="/api", tags=["auth"])
    router.include_router(secrets.router, prefix="/api", tags=["secrets"])
    router.include_router(network.router, prefix="/api", tags=["network"])
    router.include_router(stack.router, prefix="/api", tags=["stack"])
    router.include_router(backup.router, prefix="/api", tags=["backup"])
    router.include_router(activity.router, prefix="/api", tags=["activity"])
    router.include_router(traces.router, prefix="/api", tags=["traces"])
    router.include_router(vectors.router, prefix="/api", tags=["vectors"])
    router.include_router(mcp.router, prefix="/api", tags=["mcp"])
    router.include_router(keys.router, prefix="/api", tags=["keys"])
    router.include_router(setup.router, prefix="/api", tags=["setup"])
    router.include_router(voice.router, prefix="/api", tags=["voice"])
    router.include_router(admin.router, prefix="/api", tags=["admin"])
    router.include_router(operations.router, prefix="/api", tags=["operations"])
    
    return router

__all__ = [
    "create_router",
    "services",
    "metrics",
    "training",
    "storage",
    "models",
    "auth",
    "secrets",
    "network",
    "stack",
    "backup",
    "activity",
    "traces",
    "vectors",
    "mcp",
    "keys",
    "setup",
]
