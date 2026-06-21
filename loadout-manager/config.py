"""Configuration and shared utilities for Kovati OS backend."""

import os
from enum import Enum
from pathlib import Path
from typing import Dict, List

# Paths
BASE_DIR = Path(__file__).parent.parent
DOCKER_DIR = BASE_DIR / "docker"
CONFIG_DIR = BASE_DIR / "configs"
DATA_DIR = Path("/data")
STATIC_DIR = BASE_DIR / "loadout-manager" / "static"

# Environment
APPLIANCE_MODE = os.getenv("KOVATI_OS_MODE", "workstation") == "appliance"
JUMPBOX_IP = os.getenv("JUMPBOX_IP", "10.0.0.1")

# Service discovery
SERVICE_MAP = {
    "vllm-pair-a": "vllm-pair-a",
    "vllm-pair-b": "vllm-pair-b",
    "vllm-4gpu": "vllm-4gpu",
    "ollama": "ollama",
    "open-webui": "open-webui",
    "axolotl": "axolotl",
    "kohya": "kohya",
    "comfyui": "comfyui",
    "invokeai": "invokeai",
    "real-esrgan": "real-esrgan",
    "rembg": "rembg",
    "whisper-stt": "whisper",
    "piper-tts":   "piper",
    "n8n": "n8n",
    "qdrant": "qdrant",
    "minio": "minio",
    "postgres": "postgres",
    "redis": "redis",
    "langfuse": "langfuse",
    "prometheus": "prometheus",
    "grafana": "grafana",
    "caddy": "caddy",
}

PORT_MAP = {
    "vllm-pair-a": 8000,
    "vllm-pair-b": 8001,
    "vllm-4gpu": 8002,
    "ollama": 11434,
    "open-webui": 3000,
    "axolotl": None,
    "kohya": 7860,
    "comfyui": 8188,
    "invokeai": 9090,
    "real-esrgan": 8189,
    "rembg": 8190,
    "whisper-stt": 9099,
    "piper-tts": 5000,
    "n8n": 5678,
    "qdrant": 6333,
    "minio": 9000,
    "postgres": 5432,
    "redis": 6379,
    "langfuse": 3002,
    "prometheus": 9091,   # host port (mapped 9091→9090 inside container)
    "grafana": 3001,       # host port (mapped 3001→3000 inside container)
    "caddy": 80,
}

COMPOSE_FILES = {
    "vllm-pair-a": "compose.inference.yml",
    "vllm-pair-b": "compose.inference.yml",
    "vllm-4gpu":   "compose.inference.yml",
    "ollama":      "compose.inference.yml",
    "open-webui":  "compose.webui.yml",
    "axolotl":     "compose.training.yml",
    "kohya":       "compose.training.yml",
    "comfyui":     "compose.studio.yml",
    "invokeai":    "compose.studio.yml",
    "real-esrgan": "compose.studio.yml",
    "rembg":       "compose.studio.yml",
    "whisper-stt": "compose.voice.yml",
    "piper-tts":   "compose.voice.yml",
    "n8n":         "compose.agentic.yml",
    "qdrant":      "compose.storage.yml",
    "minio":       "compose.storage.yml",
    "postgres":    "compose.storage.yml",
    "redis":       "compose.auth.yml",
    "langfuse":    "compose.storage.yml",
    "prometheus":  "compose.monitoring.yml",
    "grafana":     "compose.monitoring.yml",
    "caddy":       "compose.caddy.yml",
}

# Maps UI service name → actual compose service name when they differ.
# Only needed when the UI name differs from the compose service key.
# whisper-stt and piper-tts are handled by SERVICE_MAP directly now.
COMPOSE_SERVICE_NAME = {
    "real-esrgan": "realesrgan",
}

# Services that are gated behind a compose profile — must pass --profile when starting
SERVICE_PROFILES = {
    "vllm-pair-b": "pair-b",
    "vllm-4gpu":   "large",
    "axolotl":     "training",
    "unsloth":     "training",
    "jupyterlab":  "notebook",
    "invokeai":    "studio",
    "real-esrgan": "studio",
}

GPU_ASSIGNMENT = {
    "vllm-pair-a": [0, 3],
    "vllm-pair-b": [1, 2],
    "vllm-4gpu": [0, 1, 2, 3],
    "axolotl": [0, 1, 2, 3],
    "kohya": [1, 2],
    "comfyui": [0],
    "invokeai": [0],
    "real-esrgan": [0],
    "whisper-stt": [0],
    "ollama": [0],
}

AFFECTS_MAP = {
    "POSTGRES_ADMIN_PASSWORD":  ["postgres", "langfuse", "n8n"],
    "LANGFUSE_DB_PASSWORD":     ["langfuse"],
    "LANGFUSE_NEXTAUTH_SECRET": ["langfuse"],
    "MINIO_ROOT_PASSWORD":      ["minio"],
    "AUTHENTIK_SECRET_KEY":     ["authentik"],
    "AUTHENTIK_REDIS_PASSWORD": ["authentik"],
    "N8N_ENCRYPTION_KEY":       ["n8n"],
    "DIFY_SECRET_KEY":          ["dify"],
    "GF_ADMIN_PASSWORD":        ["grafana"],
}

# Secrets that must be non-empty in docker/.env before a service can start.
SECRETS_REQUIRED = {
    "langfuse": ["LANGFUSE_DB_PASSWORD", "LANGFUSE_NEXTAUTH_SECRET"],
    "postgres": ["POSTGRES_ADMIN_PASSWORD"],
    "minio":    ["MINIO_ROOT_PASSWORD"],
    "grafana":  ["GF_ADMIN_PASSWORD"],
    # ghcr.io/bmaltais/kohya-ss is a public package — no GHCR auth needed.
    # Authentik (SSO) secrets required by caddy forward-auth.
    "caddy":    ["AUTHENTIK_SECRET_KEY"],
}

# Batch (run-to-completion) services — restart: no in compose.
# The post-start liveness check is skipped; they exit immediately by design.
BATCH_SERVICES = {"axolotl", "unsloth"}

# Host directories that must exist before the service can start.
REQUIRED_HOST_DIRS = {
    "comfyui":    ["/data/outputs/comfyui", "/data/models/comfyui/checkpoints"],
    "invokeai":   ["/data/outputs/invokeai", "/data/models/invokeai"],
    "real-esrgan": ["/data/outputs/upscaled"],
    "rembg":      ["/data/outputs/rembg"],
    "whisper-stt": ["/data/models/whisper", "/data/audio"],
    "piper-tts":  ["/data/models/piper", "/data/audio"],
    "kohya":      ["/data/datasets/images", "/data/models/comfyui/loras",
                   "/data/checkpoints/kohya", "/data/models/comfyui/checkpoints"],
    "axolotl":    ["/data/datasets/text", "/data/checkpoints/axolotl", "/data/models/vllm"],
}

# External service URLs
PROMETHEUS_URL = "http://localhost:9091"
LANGFUSE_URL = "http://localhost:3002"
OLLAMA_URL = "http://localhost:11434"
MINIO_URL = "http://localhost:9000"
QDRANT_URL = "http://localhost:6333"
AUTHENTIK_URL = "http://localhost:9000"

# Training engines
class TrainingEngine(str, Enum):
    AXOLOTL = "axolotl"
    KOHYA = "kohya"
    UNSLOTH = "unsloth"

class LogLevel(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
