#!/bin/bash
# Phase 14 — Operations Runbook: Update System Script
# Manages NVIDIA driver, Docker image, and model updates
# Usage: bash scripts/update-system.sh [driver|images|model-add] [args]

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_step() { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

COMMAND="${1:-help}"

# Show usage
show_usage() {
    cat <<EOF
${BLUE}Phase 14 — Update System Manager${NC}

${YELLOW}Usage:${NC}
  bash scripts/update-system.sh <command> [args]

${YELLOW}Commands:${NC}
  driver [VERSION]       Update NVIDIA driver (e.g., 560, 555, or latest)
  images [SERVICE]       Update Docker images (all or specific service)
  model-add <MODEL>      Add new inference model
  model-remove <MODEL>   Remove inference model
  check                  Check for available updates
  help                   Show this message

${YELLOW}Examples:${NC}
  bash scripts/update-system.sh driver latest
  bash scripts/update-system.sh images
  bash scripts/update-system.sh images compose.inference.yml
  bash scripts/update-system.sh model-add mistral:7b
  bash scripts/update-system.sh check

EOF
}

# Check for available updates
cmd_check() {
    echo -e "${BLUE}=== Checking for Updates ===${NC}"
    echo ""
    
    # NVIDIA driver
    echo -e "${BLUE}NVIDIA Driver:${NC}"
    if command -v nvidia-smi &>/dev/null; then
        current=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader | head -1)
        echo "  Current: $current"
        
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            if [ "$ID" = "ubuntu" ]; then
                available=$(apt list --upgradable 2>/dev/null | grep nvidia-driver | cut -d/ -f1 | head -1)
                if [ -n "$available" ]; then
                    echo "  Available: $available"
                else
                    echo "  Status: ${GREEN}Up to date${NC}"
                fi
            fi
        fi
    else
        echo "  ${RED}nvidia-smi not available${NC}"
    fi
    
    # Docker images
    echo ""
    echo -e "${BLUE}Docker Images:${NC}"
    log_step "Checking for image updates (this may take a minute)..."
    
    # Pull latest manifests without pulling the images
    docker compose -f ./docker/compose.inference.yml pull --dry-run 2>/dev/null | grep -E "^Pulling|Image|already|up to date" || {
        log_warn "Could not check image updates (requires network)"
    }
    
    # Python packages
    echo ""
    echo -e "${BLUE}Python Packages:${NC}"
    if [ -f "requirements.txt" ]; then
        log_step "Checking pip packages..."
        pip list --outdated 2>/dev/null | head -10 || echo "  (pip not available or no updates)"
    fi
}

# Update NVIDIA driver
cmd_driver() {
    local version="${1:-latest}"
    
    echo -e "${BLUE}=== NVIDIA Driver Update ===${NC}"
    
    if [ "$version" = "latest" ]; then
        log_step "Finding latest NVIDIA driver..."
        version=$(apt list --upgradable 2>/dev/null | grep nvidia-driver | grep -oE '[0-9]+$' | head -1)
        if [ -z "$version" ]; then
            log_warn "Already on latest driver"
            return 0
        fi
    fi
    
    log_warn "This will stop all GPU services and reboot the system"
    echo -n "Continue? (yes/no): "
    read -r confirm
    if [ "$confirm" != "yes" ]; then
        log_step "Cancelled"
        return 0
    fi
    
    # Backup first
    log_step "Creating backup before driver update..."
    bash ./scripts/backup.sh volumes &>/dev/null || {
        log_error "Backup failed (aborting)"
        return 1
    }
    
    # Stop GPU workloads
    log_step "Stopping GPU workloads..."
    curl -sX POST http://localhost:8800/stop || log_warn "Loadout Manager not reachable"
    sleep 5
    
    # Stop inference services
    log_step "Stopping inference services..."
    docker compose -f ./docker/compose.inference.yml down || true
    docker compose -f ./docker/compose.training.yml down 2>/dev/null || true
    sleep 3
    
    # Update driver
    log_step "Updating NVIDIA driver to version $version..."
    sudo apt update
    sudo apt install -y "nvidia-driver-$version" || {
        log_error "Driver installation failed"
        return 1
    }
    
    log_step "Driver updated. System will reboot in 30 seconds..."
    log_step "After reboot, run: bash scripts/start-all.sh"
    sleep 5
    
    sudo reboot
}

# Update Docker images
cmd_images() {
    local service="${1:-all}"
    
    echo -e "${BLUE}=== Docker Image Update ===${NC}"
    
    # Determine which compose files to update
    local files=()
    if [ "$service" = "all" ]; then
        files=(
            "docker/compose.storage.yml"
            "docker/compose.monitoring.yml"
            "docker/compose.auth.yml"
            "docker/compose.loadout.yml"
            "docker/compose.inference.yml"
            "docker/compose.training.yml"
            "docker/compose.webui.yml"
            "docker/compose.agentic.yml"
            "docker/compose.voice.yml"
        )
    else
        files=("docker/$service")
    fi
    
    # Pull latest images
    log_step "Pulling latest images..."
    for file in "${files[@]}"; do
        if [ -f "$file" ]; then
            log_step "  Updating from $file..."
            docker compose -f "$file" pull || log_warn "Pull failed for $file (continuing)"
        fi
    done
    
    log_step "Images pulled. To apply updates, restart services:"
    echo "  docker compose -f docker/compose.inference.yml up -d --force-recreate"
    
    # Cleanup old images
    log_step "Cleaning up old images..."
    docker image prune -f
}

# Add new model via Ollama
cmd_model_add() {
    local model="${1:-}"
    
    if [ -z "$model" ]; then
        log_error "Model name required: bash scripts/update-system.sh model-add <model>"
        exit 1
    fi
    
    echo -e "${BLUE}=== Adding Model: $model ===${NC}"
    
    # Check if Ollama is running
    if ! curl -sf http://localhost:11434/api/tags &>/dev/null; then
        log_error "Ollama is not running"
        exit 1
    fi
    
    log_step "Pulling model: $model (this may take several minutes)..."
    if docker exec ollama ollama pull "$model"; then
        log_step "${GREEN}✓${NC} Model '$model' added successfully"
        
        # List available models
        log_step "Available models:"
        docker exec ollama ollama list | awk 'NR>1 {printf "  %s\n", $1}'
    else
        log_error "Failed to pull model: $model"
        return 1
    fi
}

# Remove model via Ollama
cmd_model_remove() {
    local model="${1:-}"
    
    if [ -z "$model" ]; then
        log_error "Model name required: bash scripts/update-system.sh model-remove <model>"
        exit 1
    fi
    
    echo -e "${BLUE}=== Removing Model: $model ===${NC}"
    
    echo -n "Remove '$model'? (yes/no): "
    read -r confirm
    if [ "$confirm" != "yes" ]; then
        log_step "Cancelled"
        return 0
    fi
    
    if docker exec ollama ollama rm "$model"; then
        log_step "${GREEN}✓${NC} Model '$model' removed"
    else
        log_error "Failed to remove model: $model"
        return 1
    fi
}

# Route to appropriate command
case "$COMMAND" in
    driver)
        cmd_driver "$2"
        ;;
    images)
        cmd_images "$2"
        ;;
    model-add)
        cmd_model_add "$2"
        ;;
    model-remove)
        cmd_model_remove "$2"
        ;;
    check)
        cmd_check
        ;;
    help|--help|-h)
        show_usage
        ;;
    *)
        log_error "Unknown command: $COMMAND"
        echo ""
        show_usage
        exit 1
        ;;
esac
