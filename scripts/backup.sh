#!/bin/bash
# Phase 14 — Operations Runbook: Backup Script
# Backs up critical Docker volumes and configurations
# Usage: bash scripts/backup.sh [all|volumes|configs|models]

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
BACKUP_ROOT="${BACKUP_ROOT:-/data/backups}"
BACKUP_MODE="${1:-all}"
DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="$BACKUP_ROOT/$DATE"

log_step() { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# Create backup directory
mkdir -p "$BACKUP_DIR" || {
    log_error "Failed to create backup directory: $BACKUP_DIR"
    exit 1
}

log_step "=== AI Workstation Backup ==="
log_step "Backup directory: $BACKUP_DIR"
log_step "Backup mode: $BACKUP_MODE"
echo ""

# Function to backup Docker volume
backup_volume() {
    local vol=$1
    local name=$2
    
    if ! docker volume inspect "$vol" &>/dev/null; then
        log_warn "Volume not found: $vol (skipping)"
        return 0
    fi
    
    log_step "Backing up volume: $name..."
    docker run --rm \
        -v "$vol":/source:ro \
        -v "$BACKUP_DIR":/backup \
        alpine tar czf "/backup/${name}.tar.gz" -C /source . 2>/dev/null || {
        log_error "Failed to backup volume: $name"
        return 1
    }
    
    size=$(du -sh "$BACKUP_DIR/${name}.tar.gz" | cut -f1)
    log_step "  → ${name}.tar.gz ($size)"
}

# Function to backup directory
backup_directory() {
    local source=$1
    local name=$2
    
    if [ ! -d "$source" ]; then
        log_warn "Directory not found: $source (skipping)"
        return 0
    fi
    
    log_step "Backing up directory: $name..."
    tar czf "$BACKUP_DIR/${name}.tar.gz" -C "$(dirname "$source")" "$(basename "$source")" 2>/dev/null || {
        log_error "Failed to backup directory: $name"
        return 1
    }
    
    size=$(du -sh "$BACKUP_DIR/${name}.tar.gz" | cut -f1)
    log_step "  → ${name}.tar.gz ($size)"
}

# Backup critical Docker volumes
if [ "$BACKUP_MODE" = "all" ] || [ "$BACKUP_MODE" = "volumes" ]; then
    echo -e "${BLUE}Docker Volumes:${NC}"
    
    # Application data
    backup_volume "open-webui-data" "open-webui"
    backup_volume "n8n-data" "n8n"
    backup_volume "authentik-postgres" "authentik-db"
    backup_volume "label-studio-data" "label-studio"
    backup_volume "langfuse-data" "langfuse"
    
    # Observability data (can be regenerated but useful)
    backup_volume "prometheus-data" "prometheus"
    backup_volume "grafana-data" "grafana"
    
    # Vector DB (high value, slow to repopulate)
    backup_volume "qdrant-data" "qdrant"
    
    echo ""
fi

# Backup configurations and training artifacts
if [ "$BACKUP_MODE" = "all" ] || [ "$BACKUP_MODE" = "configs" ]; then
    echo -e "${BLUE}Configuration & Artifacts:${NC}"
    
    # Project configs
    if [ -d "./configs" ]; then
        backup_directory "./configs" "project-configs"
    fi
    
    # Training configs in /data
    if [ -d "/data/configs" ]; then
        backup_directory "/data/configs" "training-configs"
    fi
    
    # LoRA adapters
    if [ -d "/data/models/comfyui/loras" ]; then
        backup_directory "/data/models/comfyui/loras" "lora-adapters"
    fi
    
    # Training checkpoints (selective — last 7 days only)
    if [ -d "/data/checkpoints" ]; then
        log_step "Backing up recent training checkpoints..."
        find /data/checkpoints -type f -mtime -7 2>/dev/null | tar czf "$BACKUP_DIR/recent-checkpoints.tar.gz" -T - 2>/dev/null || {
            log_warn "Failed to backup checkpoints (they may be large)"
        }
        if [ -f "$BACKUP_DIR/recent-checkpoints.tar.gz" ]; then
            size=$(du -sh "$BACKUP_DIR/recent-checkpoints.tar.gz" | cut -f1)
            log_step "  → recent-checkpoints.tar.gz ($size)"
        fi
    fi
    
    echo ""
fi

# Backup model weights (large, but redownloadable)
if [ "$BACKUP_MODE" = "all" ] || [ "$BACKUP_MODE" = "models" ]; then
    echo -e "${BLUE}Model Weights (Large):${NC}"
    log_warn "Model backups are large. Consider using MinIO instead for long-term storage."
    
    # Only backup if explicitly requested
    if [ "$BACKUP_MODE" = "models" ]; then
        if [ -d "/data/models/vllm" ]; then
            log_step "Backing up vLLM models..."
            find /data/models/vllm -maxdepth 1 -type d | tar czf "$BACKUP_DIR/vllm-models.tar.gz" -T - 2>/dev/null || {
                log_warn "vLLM models too large to backup (archive would exceed disk)"
            }
        fi
    fi
    echo ""
fi

# Sync backups to MinIO (if available)
echo -e "${BLUE}MinIO Sync:${NC}"
if command -v mc &>/dev/null && mc ls local &>/dev/null 2>&1; then
    log_step "Syncing backup to MinIO..."
    if mc mirror --overwrite "$BACKUP_DIR/" "local/backups/$DATE/" 2>/dev/null; then
        log_step "  → Synced to MinIO: local/backups/$DATE/"
    else
        log_warn "MinIO sync failed (continuing with local backup)"
    fi
else
    log_warn "MinIO client not configured (skipping sync)"
fi

echo ""

# Generate backup manifest
manifest="$BACKUP_DIR/MANIFEST.txt"
{
    echo "# Backup Manifest"
    echo "Date: $(date)"
    echo "Mode: $BACKUP_MODE"
    echo ""
    echo "## Files"
    cd "$BACKUP_DIR"
    ls -lh | awk 'NR>1 {printf "%s  %s\n", $5, $9}'
    echo ""
    echo "## Restore Instructions"
    echo "# To restore a volume:"
    echo "docker volume create <volume-name>"
    echo "docker run --rm -v <volume-name>:/target -v \$(pwd):/source alpine tar xzf /source/<file>.tar.gz -C /target"
    echo ""
    echo "# To restore a directory:"
    echo "tar xzf <file>.tar.gz -C <target-directory>"
} > "$manifest"

# Cleanup old local backups (keep last 30 days)
echo -e "${BLUE}Cleanup:${NC}"
log_step "Removing backups older than 30 days..."
old_count=$(find "$BACKUP_ROOT" -maxdepth 1 -type d -mtime +30 2>/dev/null | wc -l)
find "$BACKUP_ROOT" -maxdepth 1 -type d -mtime +30 -exec rm -rf {} + 2>/dev/null || true

if [ "$old_count" -gt 0 ]; then
    log_step "  → Removed $old_count old backup(s)"
else
    log_step "  → No old backups to remove"
fi

echo ""

# Summary
total_size=$(du -sh "$BACKUP_DIR" | cut -f1)
file_count=$(ls -1 "$BACKUP_DIR" | wc -l)

echo -e "${GREEN}=== Backup Complete ===${NC}"
echo "Location:   $BACKUP_DIR"
echo "Size:       $total_size"
echo "Files:      $file_count"
echo "Manifest:   $(cat "$manifest" | head -1)"
echo ""
echo "Schedule with cron:"
echo "  0 2 * * * $HOME/ai-workstation/scripts/backup.sh >> /var/log/ai-backup.log 2>&1"
