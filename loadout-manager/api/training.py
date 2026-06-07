"""Training workflow API endpoints."""

import asyncio
from dataclasses import dataclass
from typing import Dict, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

try:
    from config import TrainingEngine
except ImportError:
    from ..config import TrainingEngine

router = APIRouter()

# Current training session
current_training = None


class LoRAConfig(BaseModel):
    rank: int = 64
    alpha: int = 128
    lr: str = "2e-5"
    epochs: int = 3
    micro_batch: int = 2
    grad_accum: int = 4


class TrainingConfig(BaseModel):
    engine: str  # "axolotl" | "kohya"
    model: str
    dataset_path: str
    lora_config: LoRAConfig


async def _launch_training(config: TrainingConfig):
    """Launch training container in background."""
    global current_training
    
    try:
        current_training = {
            "engine": config.engine,
            "model": config.model,
            "status": "running",
            "step": 0,
            "loss": 0.0,
        }
    except Exception as e:
        current_training = {
            "error": str(e),
            "status": "failed",
        }


@router.post("/training/start")
async def start_training(config: TrainingConfig, background_tasks: BackgroundTasks) -> Dict:
    """Start a new training job."""
    global current_training
    
    if current_training and current_training.get("status") == "running":
        raise HTTPException(status_code=409, detail="Training already running")
    
    # Validate config
    if config.engine not in [e.value for e in TrainingEngine]:
        raise HTTPException(status_code=400, detail=f"Invalid engine: {config.engine}")
    
    background_tasks.add_task(_launch_training, config)
    
    return {
        "status": "starting",
        "engine": config.engine,
        "model": config.model,
    }


@router.get("/training/status")
async def get_training_status() -> Dict:
    """Get current training job status."""
    if not current_training:
        return {"status": "idle", "active": False}
    
    return {
        "status": current_training.get("status", "unknown"),
        "active": current_training.get("status") == "running",
        "engine": current_training.get("engine"),
        "model": current_training.get("model"),
        "step": current_training.get("step", 0),
        "loss": current_training.get("loss", 0.0),
    }


@router.post("/training/stop")
async def stop_training(background_tasks: BackgroundTasks) -> Dict:
    """Stop current training job."""
    global current_training
    
    if not current_training or current_training.get("status") != "running":
        raise HTTPException(status_code=400, detail="No training running")
    
    async def _stop():
        global current_training
        current_training["status"] = "stopped"
    
    background_tasks.add_task(_stop)
    
    return {"status": "stopping"}


@router.post("/training/export")
async def export_checkpoint(run_name: str) -> Dict:
    """Export training checkpoint."""
    return {
        "status": "exporting",
        "run_name": run_name,
        "destination": f"/data/models/checkpoints/{run_name}/",
    }
