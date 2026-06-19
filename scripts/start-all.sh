#!/bin/bash
# Phase 14 — Operations Runbook: Start All Services
# Starts AI workstation services in correct dependency order
# Usage: bash scripts/start-all.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_step() { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# Configuration
COMPOSE="docker compose"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="$(dirname "$SCRIPT_DIR")/docker"
export REPO_ROOT="$(dirname "$SCRIPT_DIR")"

# Verify docker is running
if ! docker info &>/dev/null; then
    log_error "Docker is not running"
    exit 1
fi

# ── Pre-flight: storage directories ──────────────────────────────────────────
log_step "Pre-flight: ensuring storage directories exist..."
bash "$SCRIPT_DIR/setup-storage-phase07.sh" 2>&1 | grep -E "(Creating|✓|Error)" || true

# ── Pre-flight: n8n encryption key cleanup ───────────────────────────────────
# N8N_ENCRYPTION_KEY is no longer managed via docker/.env — n8n self-manages
# its key in /data/n8n/config. If a stale env var is present, remove it to
# prevent the "mismatching encryption keys" crash loop.
if grep -q "^N8N_ENCRYPTION_KEY=" "$REPO_ROOT/docker/.env" 2>/dev/null; then
    log_step "Removing stale N8N_ENCRYPTION_KEY from docker/.env..."
    sed -i '/^N8N_ENCRYPTION_KEY=/d' "$REPO_ROOT/docker/.env"
    rm -f /data/n8n/config
    log_step "  → n8n will reinitialize with a self-managed key on next start"
fi

# ── Pre-flight: ghcr.io login for auth-gated images (e.g. kohya-ss) ─────────
if grep -q "^GHCR_TOKEN=" "$REPO_ROOT/docker/.env" 2>/dev/null; then
    GHCR_TOKEN=$(grep "^GHCR_TOKEN=" "$REPO_ROOT/docker/.env" | cut -d= -f2-)
    GHCR_USER=$(grep "^GHCR_USER=" "$REPO_ROOT/docker/.env" | cut -d= -f2-)
    if [[ -n "$GHCR_TOKEN" && -n "$GHCR_USER" ]]; then
        log_step "Logging into ghcr.io as $GHCR_USER..."
        echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
    fi
fi

# ── Pre-flight: remove containers whose images changed ───────────────────────
# docker compose up -d won't recreate a container whose image tag changed if
# the old container is still present. Force-remove known-changed containers.
for cname in kohya langfuse n8n; do
    old_image=$(docker inspect "$cname" --format '{{.Config.Image}}' 2>/dev/null || true)
    case "$cname" in
        kohya)   expected="bmaltais/kohya-ss" ;;
        langfuse) expected="langfuse/langfuse:2" ;;
        n8n)     expected="n8nio/n8n" ;;
    esac
    if [[ -n "$old_image" && "$old_image" != *"$expected"* ]]; then
        log_step "Removing stale $cname container (image: $old_image)..."
        docker rm -f "$cname" 2>/dev/null || true
    fi
done

log_step "=== Starting AI Workstation Services ==="
log_step "Base directory: $BASE"
echo ""

# Function to start service with error handling
start_service() {
    local name=$1
    local file=$2
    
    if [ ! -f "$BASE/$file" ]; then
        log_error "File not found: $BASE/$file"
        return 1
    fi
    
    log_step "Starting $name..."
    $COMPOSE -f "$BASE/$file" up -d || {
        log_error "Failed to start $name"
        return 1
    }
}

# 1. Storage layer (everything depends on this)
# --force-recreate langfuse so the :latest→:2 image change takes effect
log_step "Starting Storage stack (MinIO, Qdrant, PostgreSQL, Langfuse)..."
$COMPOSE -f "$BASE/compose.storage.yml" up -d --force-recreate langfuse || true
$COMPOSE -f "$BASE/compose.storage.yml" up -d || exit 1
sleep 5

# 2. Monitoring (start early to catch startup metrics)
start_service "Monitoring stack (Prometheus, Grafana, DCGM)" "compose.monitoring.yml" || exit 1
sleep 3

# 3. Authentication (before user-facing services)
start_service "Authentication (Authentik, Caddy)" "compose.auth.yml" || exit 1
sleep 5

# 4. Loadout Manager (GPU orchestrator)
log_step "Starting Loadout Manager (GPU orchestrator)..."
$COMPOSE -f "$BASE/compose.loadout.yml" up -d || {
    log_error "Failed to start Loadout Manager"
    exit 1
}
sleep 3

# 5. Verify Loadout Manager is ready
log_step "Waiting for Loadout Manager to be ready..."
for i in {1..30}; do
    if curl -sf http://localhost:8800/health &>/dev/null; then
        log_step "Loadout Manager is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        log_error "Loadout Manager failed to start"
        exit 1
    fi
    sleep 1
done

# 6. Activate default inference profile
log_step "Activating default inference profile (Ollama)..."
curl -sX POST http://localhost:8800/activate/inference-small || {
    log_error "Failed to activate default profile"
}
sleep 8  # Allow Ollama to load base model

# 7. Start inference services
start_service "Inference services (Ollama, vLLM, ComfyUI)" "compose.inference.yml" || exit 1
sleep 5

# 8. Start training services (if available)
if [ -f "$BASE/compose.training.yml" ]; then
    log_step "Starting training services (Kohya, Label Studio, JupyterLab)..."
    $COMPOSE -f "$BASE/compose.training.yml" up -d --force-recreate kohya || true
    $COMPOSE -f "$BASE/compose.training.yml" up -d label-studio || true
    sleep 3
fi

# 9. Start webui and agentic services
start_service "Web UI (Open WebUI, SearXNG)" "compose.webui.yml" || exit 1
log_step "Starting agentic services (n8n, MCP servers)..."
# --force-recreate on n8n ensures the volume binding change (named→bind) takes effect
$COMPOSE -f "$BASE/compose.agentic.yml" up -d --force-recreate n8n mcp-filesystem mcp-fetch mcp-browser || echo "Agentic services failed (optional)"
log_step "Starting code generation services (OpenHands)..."
$COMPOSE -f "$BASE/compose.codegen.yml" up -d || echo "Code generation services failed (optional)"
sleep 3

# 10. Start voice services
if [ -f "$BASE/compose.voice.yml" ]; then
    log_step "Starting voice services (Whisper, Piper)..."
    $COMPOSE -f "$BASE/compose.voice.yml" up -d
    sleep 2
fi

echo ""
log_step "=== Startup Complete ==="
echo ""
echo "Service URLs:"
echo "  Open WebUI:     http://10.10.10.2:3000"
echo "  Grafana:        http://10.10.10.2:3001"
echo "  n8n:            http://10.10.10.2:5678"
echo "  Loadout Status: http://10.10.10.2:8800/status"
echo ""
log_step "Running health check..."
if [ -f "./scripts/healthcheck.sh" ]; then
    bash ./scripts/healthcheck.sh || true
elif [ -f "$HOME/ai-workstation/scripts/healthcheck.sh" ]; then
    bash "$HOME/ai-workstation/scripts/healthcheck.sh" || true
fi

echo ""
log_step "Startup complete. Services may still be initializing — wait 30s before heavy use."
