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

# Verify docker is running
if ! docker info &>/dev/null; then
    log_error "Docker is not running"
    exit 1
fi

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
start_service "Storage stack (MinIO, Qdrant, PostgreSQL)" "compose.storage.yml" || exit 1
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
    $COMPOSE -f "$BASE/compose.training.yml" up -d
    sleep 3
fi

# 9. Start webui and agentic services
start_service "Web UI (Open WebUI, SearXNG)" "compose.webui.yml" || exit 1
log_step "Starting agentic services (n8n, MCP servers)..."
$COMPOSE -f "$BASE/compose.agentic.yml" up -d n8n mcp-filesystem mcp-fetch mcp-browser || echo "Agentic services failed (optional)"
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
