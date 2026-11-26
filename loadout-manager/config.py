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
    "vllm-embed": "vllm-embed",
    "vllm-huihui": "vllm-huihui",
    "vllm-huihui-coder": "vllm-huihui-coder",
    "open-webui": "open-webui",
    "axolotl": "axolotl",
    "kohya": "kohya",
    "comfyui": "comfyui",
    "invokeai": "invokeai",
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
    "authentik": "authentik",
    "caddy": "caddy",
}

PORT_MAP = {
    "vllm-pair-a": 8000,
    "vllm-pair-b": 8001,
    "vllm-4gpu": 8002,
    "vllm-embed": 8003,
    "vllm-huihui": 8004,
    "vllm-huihui-coder": 8005,
    "open-webui": 3000,
    "axolotl": None,
    "kohya": 7860,
    "comfyui": 8188,
    "invokeai": 9090,
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
    "authentik": 9080,     # host port (mapped 9080→9000 inside container)
    "caddy": 80,
}

COMPOSE_FILES = {
    "vllm-pair-a": "compose.inference.yml",
    "vllm-pair-b": "compose.inference.yml",
    "vllm-4gpu":   "compose.inference.yml",
    "vllm-embed":  "compose.inference.yml",
    "vllm-huihui": "compose.inference.yml",
    "vllm-huihui-coder": "compose.inference.yml",
    "open-webui":  "compose.webui.yml",
    "axolotl":     "compose.training.yml",
    "kohya":       "compose.training.yml",
    "comfyui":     "compose.studio.yml",
    "invokeai":    "compose.studio.yml",
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
    "authentik":   "compose.auth.yml",
    "caddy":       "compose.caddy.yml",
}

# Maps UI service name → actual compose service name when they differ.
# Only needed when the UI name differs from the compose service key.
# whisper-stt and piper-tts are handled by SERVICE_MAP directly now.
COMPOSE_SERVICE_NAME: dict[str, str] = {}

# Services that are gated behind a compose profile — must pass --profile when starting
SERVICE_PROFILES = {
    # vllm-4gpu and vllm-embed are the default stack (no profile).
    "vllm-pair-a": "pair-a",
    "vllm-pair-b": "pair-b",
    "vllm-huihui": "huihui",
    "vllm-huihui-coder": "huihui",
    "axolotl":     "training",
    "unsloth":     "training",
    "jupyterlab":  "notebook",
    "invokeai":    "studio",
}

GPU_ASSIGNMENT = {
    "vllm-pair-a": [0, 3],
    "vllm-pair-b": [1, 2],
    "vllm-4gpu": [0, 1, 2, 3],
    "vllm-embed": [1],
    "vllm-huihui": [0, 3],
    "vllm-huihui-coder": [1, 2],
    "axolotl": [0, 1, 2, 3],
    "kohya": [1, 2],
    "comfyui": [0],
    "invokeai": [0],
    "whisper-stt": [0],
}

# Secrets the platform generates and owns. scripts/init-secrets.sh is the
# reference generator; keep the two in step. Everything else in docker/.env
# (GHCR_TOKEN, HUGGINGFACE_TOKEN, WANDB_API_KEY, ...) is a credential the user
# brings and is never generated or rotated by the API. N8N_ENCRYPTION_KEY is
# deliberately absent: n8n generates and persists its own, and injecting one
# later breaks every stored credential.
#
#   db_roles  (container, admin user, database, role) whose password IS the
#             value. Postgres reads POSTGRES_PASSWORD only on first init, so
#             rotation runs ALTER ROLE there before docker/.env is touched.
#   recreate  (compose file, service) that read the value from the environment.
#             They are recreated, not restarted: `restart` does not re-read .env.
#   rotate    None when rotatable; otherwise why it must not be rotated here.
# See docs/runbooks/rotate-postgres-passwords.md.
MANAGED_SECRETS = {
    "POSTGRES_ADMIN_PASSWORD": {
        "db_roles": [("postgres", "admin", "postgres", "admin")],
        "recreate": [], "rotate": None},
    "LANGFUSE_DB_PASSWORD": {
        "db_roles": [("postgres", "admin", "postgres", "langfuse")],
        "recreate": [("compose.storage.yml", "langfuse")], "rotate": None},
    "N8N_DB_PASSWORD": {
        # n8n runs on SQLite; only the unused shared-postgres role holds it.
        "db_roles": [("postgres", "admin", "postgres", "n8n")],
        "recreate": [], "rotate": None},
    "DIFY_DB_PASSWORD": {
        # Same value is the shared-postgres `dify` role AND the dify-db superuser.
        "db_roles": [("postgres", "admin", "postgres", "dify"),
                     ("dify-db", "dify", "dify", "dify")],
        "recreate": [("compose.agentic.yml", "dify-api")], "rotate": None},
    "AUTHENTIK_PG_PASSWORD": {
        "db_roles": [("authentik-postgres", "authentik", "authentik", "authentik")],
        "recreate": [("compose.auth.yml", "authentik"),
                     ("compose.auth.yml", "authentik-worker")], "rotate": None},
    "AUTHENTIK_REDIS_PASSWORD": {
        "db_roles": [],
        "recreate": [("compose.auth.yml", "redis"),
                     ("compose.auth.yml", "authentik"),
                     ("compose.auth.yml", "authentik-worker")], "rotate": None},
    "MINIO_ROOT_PASSWORD": {
        "db_roles": [], "recreate": [("compose.storage.yml", "minio")], "rotate": None},
    "LANGFUSE_NEXTAUTH_SECRET": {
        "db_roles": [], "recreate": [("compose.storage.yml", "langfuse")], "rotate": None},
    "WEBUI_SECRET_KEY": {
        "db_roles": [], "recreate": [("compose.webui.yml", "open-webui")], "rotate": None},
    "AUTHENTIK_SECRET_KEY": {
        "db_roles": [], "recreate": [],
        "rotate": "Authentik must keep the secret key it was installed with."},
    "DIFY_SECRET_KEY": {
        "db_roles": [], "recreate": [],
        "rotate": "Dify encrypts stored credentials with this key; changing it loses them."},
    "GF_ADMIN_PASSWORD": {
        "db_roles": [], "recreate": [],
        "rotate": "Grafana applies this only on first start; change the password in "
                  "Grafana (grafana cli admin reset-admin-password) instead."},
}

# Generated once by the setup wizard alongside MANAGED_SECRETS. These two are
# user-editable afterwards via the Settings page (CONFIG_SCHEMA), not rotated.
GENERATED_SECRETS = list(MANAGED_SECRETS) + [
    "JUPYTER_TOKEN", "LABEL_STUDIO_PASSWORD",
    "UNSLOTH_STUDIO_PASSWORD", "UNSLOTH_JUPYTER_PASSWORD",
]

# Secrets that must be non-empty in docker/.env before a service can start.
SECRETS_REQUIRED = {
    "langfuse": ["LANGFUSE_DB_PASSWORD", "LANGFUSE_NEXTAUTH_SECRET"],
    "postgres": ["POSTGRES_ADMIN_PASSWORD"],
    "minio":    ["MINIO_ROOT_PASSWORD"],
    "grafana":  ["GF_ADMIN_PASSWORD"],
    # ghcr.io/bmaltais/kohya-ss is a public package — no GHCR auth needed.
    "authentik": ["AUTHENTIK_SECRET_KEY", "AUTHENTIK_REDIS_PASSWORD", "AUTHENTIK_PG_PASSWORD"],
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
    "rembg":      ["/data/outputs/rembg"],
    "whisper-stt": ["/data/models/whisper", "/data/audio"],
    "piper-tts":  ["/data/models/piper", "/data/audio"],
    "kohya":      ["/data/datasets/images", "/data/models/comfyui/loras",
                   "/data/checkpoints/kohya", "/data/models/comfyui/checkpoints"],
    "axolotl":    ["/data/datasets/text", "/data/checkpoints/axolotl", "/data/models/vllm"],
    "unsloth":    ["/data/datasets/text", "/data/checkpoints/unsloth", "/data/models/vllm",
                   "/data/unsloth/workspace", "/data/unsloth/studio"],
}

# External services, as seen from inside the loadout-manager container.
# "localhost" there is the container itself, so services on the shared
# ai-workstation network are reached by container name and container-internal
# port (not the host-published port). Each can be overridden with an
# environment variable of the same name.
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus:9090")
LANGFUSE_URL = os.getenv("LANGFUSE_URL", "http://langfuse:3000")
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")   # host:port, no scheme
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
# vLLM servers, by container name. Every vLLM container listens on 8000 inside
# the network; the 8000-8003 numbers in PORT_MAP are host-published ports.
VLLM_PAIR_A_URL = os.getenv("VLLM_PAIR_A_URL", "http://vllm-pair-a:8000")
VLLM_PAIR_B_URL = os.getenv("VLLM_PAIR_B_URL", "http://vllm-pair-b:8000")
VLLM_4GPU_URL = os.getenv("VLLM_4GPU_URL", "http://vllm-4gpu:8000")
VLLM_EMBED_URL = os.getenv("VLLM_EMBED_URL", "http://vllm-embed:8000")
VLLM_HUIHUI_URL = os.getenv("VLLM_HUIHUI_URL", "http://vllm-huihui:8000")
VLLM_HUIHUI_CODER_URL = os.getenv("VLLM_HUIHUI_CODER_URL", "http://vllm-huihui-coder:8000")
VLLM_URLS = {
    "vllm-pair-a": VLLM_PAIR_A_URL,
    "vllm-pair-b": VLLM_PAIR_B_URL,
    "vllm-4gpu": VLLM_4GPU_URL,
    "vllm-embed": VLLM_EMBED_URL,
    "vllm-huihui": VLLM_HUIHUI_URL,
    "vllm-huihui-coder": VLLM_HUIHUI_CODER_URL,
}
# Authentik is on its own ai-auth network, so it is reached through its
# published port on the host (compose maps host.docker.internal to the host).
AUTHENTIK_URL = os.getenv("AUTHENTIK_URL", "http://host.docker.internal:9080")

# User-configurable settings exposed in the Settings UI.
# Tuple: (category, key, description, sensitive, affects)
# sensitive=True → value is masked in API responses; never returned in plaintext.
# affects → list of service names to restart after an update.
CONFIG_SCHEMA = [
    ("Registry Access", "GHCR_USER",            "GitHub Container Registry username",                    False, []),
    ("Registry Access", "GHCR_TOKEN",           "GitHub Container Registry PAT (scope: read:packages)",  True,  []),
    ("AI Providers",    "HUGGINGFACE_TOKEN",     "HuggingFace API token for downloading gated models",   True,  ["axolotl", "unsloth"]),
    ("AI Providers",    "WANDB_API_KEY",         "Weights & Biases API key for training run logging",    True,  ["axolotl", "unsloth"]),
    ("Training",        "LABEL_STUDIO_PASSWORD", "Label Studio admin password",                           True,  ["label-studio"]),
    ("Training",        "JUPYTER_TOKEN",         "JupyterLab access token",                               True,  ["jupyterlab"]),
    ("Training",        "UNSLOTH_STUDIO_PASSWORD", "Unsloth Studio login password",                       True,  ["unsloth"]),
    ("Training",        "UNSLOTH_JUPYTER_PASSWORD", "Unsloth JupyterLab password",                        True,  ["unsloth"]),
    ("Training",        "AXOLOTL_CONFIG",        "Axolotl training config filename (e.g. qlora_4gpu.yml)", False, []),
    ("Access",          "AUTHENTIK_TOKEN",       "Authentik API token (Directory > Tokens, intent API) for user and group management", True, []),
    ("System",          "KOVATI_OS_MODE",        "System mode: workstation or appliance",                 False, []),
]

CONFIG_SCHEMA_MAP = {
    key: {"category": cat, "description": desc, "sensitive": sensitive, "affects": affects}
    for cat, key, desc, sensitive, affects in CONFIG_SCHEMA
}

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
