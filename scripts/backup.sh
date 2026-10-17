#!/bin/bash
[ -n "${BASH_VERSION:-}" ] || { echo "ERROR: this script needs bash - run: bash $0" >&2; exit 1; }
# Phase 14 — Operations Runbook: Backup Script
# Backs up critical Docker volumes and configurations
# Usage: bash scripts/backup.sh [all|volumes|configs|models]
#
# Exit codes: 0 = everything requested was backed up (or skipped because the
#                 source does not exist; skips are listed in the summary)
#             1 = at least one backup/verification step failed, or nothing was
#                 backed up at all
#             2 = bad usage / missing prerequisite (docker, free disk space)
#
# Environment:
#   DATA_ROOT            service data root           (default /data)
#   BACKUP_ROOT          destination root            (default $DATA_ROOT/backups)
#   BACKUP_MIN_FREE_GB   abort if less free space    (default 20, 0 = no check)

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_ROOT="${DATA_ROOT:-/data}"
BACKUP_ROOT="${BACKUP_ROOT:-$DATA_ROOT/backups}"
BACKUP_MIN_FREE_GB="${BACKUP_MIN_FREE_GB:-20}"
BACKUP_MODE="${1:-all}"
DATE=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="$BACKUP_ROOT/$DATE"

# Results, reported in the summary and reflected in the exit code
FAILED=()
SKIPPED=()
CREATED=0

log_step() { echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

case "$BACKUP_MODE" in
    all|volumes|configs|models) ;;
    *)
        log_error "Unknown mode: $BACKUP_MODE (expected: all|volumes|configs|models)"
        exit 2
        ;;
esac

# Prerequisites
if [ "$BACKUP_MODE" = "all" ] || [ "$BACKUP_MODE" = "volumes" ]; then
    if ! command -v docker &>/dev/null || ! docker info &>/dev/null; then
        log_error "docker is not installed or the daemon is not reachable (is the user in the docker group?)"
        exit 2
    fi
fi

# Backups contain credentials (n8n, Authentik, databases) — keep them private
umask 077

# Create backup directory
mkdir -p "$BACKUP_DIR" || {
    log_error "Failed to create backup directory: $BACKUP_DIR"
    exit 1
}

if [ "$BACKUP_MIN_FREE_GB" -gt 0 ]; then
    free_kb=$(df -Pk "$BACKUP_DIR" | awk 'NR==2 {print $4}')
    if [ "$((free_kb / 1024 / 1024))" -lt "$BACKUP_MIN_FREE_GB" ]; then
        log_error "Less than ${BACKUP_MIN_FREE_GB} GB free on $BACKUP_ROOT ($((free_kb / 1024 / 1024)) GB) — aborting"
        rmdir "$BACKUP_DIR" 2>/dev/null || true
        exit 2
    fi
fi

log_step "=== AI Workstation Backup ==="
log_step "Backup directory: $BACKUP_DIR"
log_step "Backup mode: $BACKUP_MODE"
echo ""

# Verify a freshly written archive is a readable gzip stream; drop it if not,
# so a truncated file (disk full, killed tar) never looks like a good backup.
finish_archive() {
    local file=$1
    local name=$2
    local size

    if ! gzip -t "$file" 2>/dev/null; then
        log_error "Archive failed integrity check: $name"
        rm -f "$file"
        FAILED+=("$name")
        return 0
    fi

    size=$(du -sh "$file" | cut -f1)
    log_step "  → $(basename "$file") ($size)"
    CREATED=$((CREATED + 1))
}

# Resolve a compose volume to its real Docker name. Compose prefixes volumes
# with the project name (e.g. open-webui-data -> ai-webui_open-webui-data), so
# fall back to a unique "<project>_<name>" match. Several matches (leftovers
# from an older project name, e.g. docker_postgres-data) are narrowed to the
# ones a container, running or stopped, actually mounts.
# Prints the name; returns 1 if absent, 2 if ambiguous.
resolve_volume() {
    local base=$1
    local matches

    if docker volume inspect "$base" &>/dev/null; then
        echo "$base"
        return 0
    fi

    matches=$(docker volume ls -q | grep -E -- "_${base}\$" || true)
    if [ -z "$matches" ]; then
        return 1
    fi
    if [ "$(printf '%s\n' "$matches" | wc -l)" -gt 1 ]; then
        local m in_use=""
        for m in $matches; do
            if [ -n "$(docker ps -aq --filter "volume=$m")" ]; then
                in_use+="$m"$'\n'
            fi
        done
        matches=${in_use%$'\n'}
        if [ -z "$matches" ] || [ "$(printf '%s\n' "$matches" | wc -l)" -gt 1 ]; then
            return 2
        fi
    fi
    echo "$matches"
}

# Tar a Docker volume or an absolute host path from inside a root container
# (bind-mounted service data such as /data/authentik/postgres is not readable
# by the invoking user).
tar_in_container() {
    local source=$1
    local name=$2
    local file="$BACKUP_DIR/${name}.tar.gz"

    log_step "Backing up: $name..."
    if ! docker run --rm \
        -v "$source":/source:ro \
        -v "$BACKUP_DIR":/backup \
        alpine tar czf "/backup/${name}.tar.gz" -C /source .; then
        log_error "Failed to backup: $name"
        rm -f "$file"
        FAILED+=("$name")
        return 0
    fi

    finish_archive "$file" "$name"
}

# Function to backup Docker volume
backup_volume() {
    local vol=$1
    local name=$2
    local resolved rc=0

    resolved=$(resolve_volume "$vol") || rc=$?
    if [ "$rc" -eq 1 ]; then
        log_warn "Volume not found: $vol (skipping)"
        SKIPPED+=("$name")
        return 0
    elif [ "$rc" -ne 0 ]; then
        log_error "Volume name is ambiguous: $vol matches several volumes"
        FAILED+=("$name")
        return 0
    fi

    tar_in_container "$resolved" "$name"
}

# Function to backup a bind-mounted service directory (read as root)
backup_service_dir() {
    local source=$1
    local name=$2

    if [ ! -d "$source" ]; then
        log_warn "Directory not found: $source (skipping)"
        SKIPPED+=("$name")
        return 0
    fi

    tar_in_container "$source" "$name"
}

# Function to backup directory (extra args are passed to tar, e.g. --exclude)
backup_directory() {
    local source=$1
    local name=$2
    shift 2
    local file="$BACKUP_DIR/${name}.tar.gz"
    local rc=0

    if [ ! -d "$source" ]; then
        log_warn "Directory not found: $source (skipping)"
        SKIPPED+=("$name")
        return 0
    fi

    log_step "Backing up directory: $name..."
    tar czf "$file" "$@" -C "$(dirname "$source")" "$(basename "$source")" || rc=$?
    # tar exit 1 = "file changed as we read it": archive is usable
    if [ "$rc" -eq 1 ]; then
        log_warn "Files changed while archiving $name"
    elif [ "$rc" -ne 0 ]; then
        log_error "Failed to backup directory: $name"
        rm -f "$file"
        FAILED+=("$name")
        return 0
    fi

    finish_archive "$file" "$name"
}

# Consistent logical dump of a running PostgreSQL container. A file-level copy
# of a live data directory is not guaranteed to be restorable on its own.
backup_postgres() {
    local container=$1
    local pguser=$2
    local name=$3
    local file="$BACKUP_DIR/${name}.sql.gz"

    if [ "$(docker inspect -f '{{.State.Running}}' "$container" 2>/dev/null || true)" != "true" ]; then
        log_warn "Container not running: $container (skipping SQL dump)"
        SKIPPED+=("$name")
        return 0
    fi

    log_step "Dumping PostgreSQL: $container..."
    if ! docker exec "$container" pg_dumpall -U "$pguser" | gzip > "$file"; then
        log_error "Failed to dump PostgreSQL: $container"
        rm -f "$file"
        FAILED+=("$name")
        return 0
    fi

    finish_archive "$file" "$name"
}

# Backup critical Docker volumes
if [ "$BACKUP_MODE" = "all" ] || [ "$BACKUP_MODE" = "volumes" ]; then
    echo -e "${BLUE}Docker Volumes:${NC}"

    # Application data
    backup_volume "open-webui-data" "open-webui"
    backup_volume "label-studio-data" "label-studio"
    # Bind mounts, not Docker volumes (docker/compose.agentic.yml, compose.auth.yml)
    backup_service_dir "$DATA_ROOT/n8n" "n8n"
    backup_service_dir "$DATA_ROOT/authentik" "authentik"
    # Shared Postgres (Langfuse, Dify): volume copy plus logical dump
    backup_volume "postgres-data" "postgres"
    backup_postgres "postgres" "admin" "postgres-dump"
    backup_postgres "authentik-postgres" "authentik" "authentik-db-dump"

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

    # Project configs (resolved from the script location, not the caller's cwd).
    # .env files are excluded: init-secrets.sh keeps plaintext secrets out of backups.
    backup_directory "$REPO_ROOT/configs" "project-configs" --exclude=.env

    # Training configs in /data
    backup_directory "$DATA_ROOT/configs" "training-configs"

    # LoRA adapters
    backup_directory "$DATA_ROOT/models/comfyui/loras" "lora-adapters"

    # Training checkpoints (selective — last 7 days only)
    if [ -d "$DATA_ROOT/checkpoints" ]; then
        if [ -n "$(find "$DATA_ROOT/checkpoints" -type f -mtime -7 -print -quit 2>/dev/null)" ]; then
            log_step "Backing up recent training checkpoints..."
            if find "$DATA_ROOT/checkpoints" -type f -mtime -7 -print0 | tar czf "$BACKUP_DIR/recent-checkpoints.tar.gz" --null -T -; then
                finish_archive "$BACKUP_DIR/recent-checkpoints.tar.gz" "recent-checkpoints"
            else
                log_error "Failed to backup checkpoints (they may be large)"
                rm -f "$BACKUP_DIR/recent-checkpoints.tar.gz"
                FAILED+=("recent-checkpoints")
            fi
        else
            log_warn "No checkpoints modified in the last 7 days (skipping)"
            SKIPPED+=("recent-checkpoints")
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
        if [ -d "$DATA_ROOT/models/vllm" ]; then
            log_step "Backing up vLLM models..."
            if find "$DATA_ROOT/models/vllm" -maxdepth 1 -type d -print0 | tar czf "$BACKUP_DIR/vllm-models.tar.gz" --null -T -; then
                finish_archive "$BACKUP_DIR/vllm-models.tar.gz" "vllm-models"
            else
                log_error "vLLM models too large to backup (archive would exceed disk)"
                rm -f "$BACKUP_DIR/vllm-models.tar.gz"
                FAILED+=("vllm-models")
            fi
        else
            log_warn "Directory not found: $DATA_ROOT/models/vllm (skipping)"
            SKIPPED+=("vllm-models")
        fi
    fi
    echo ""
fi

if [ "$CREATED" -eq 0 ] && [ "${#FAILED[@]}" -eq 0 ]; then
    log_error "Nothing was backed up (mode: $BACKUP_MODE) — every source was missing"
    FAILED+=("nothing-backed-up")
fi

# Generate backup manifest (before the MinIO sync so it is mirrored too)
manifest="$BACKUP_DIR/MANIFEST.txt"
{
    echo "# Backup Manifest"
    echo "Date: $(date)"
    echo "Mode: $BACKUP_MODE"
    echo ""
    echo "## Files"
    (cd "$BACKUP_DIR" && ls -lh | awk 'NR>1 {printf "%s  %s\n", $5, $9}')
    if [ "${#SKIPPED[@]}" -gt 0 ]; then
        echo ""
        echo "## Skipped (source not present)"
        printf '%s\n' "${SKIPPED[@]}"
    fi
    if [ "${#FAILED[@]}" -gt 0 ]; then
        echo ""
        echo "## FAILED"
        printf '%s\n' "${FAILED[@]}"
    fi
    echo ""
    echo "## Restore Instructions"
    echo "# To restore a volume (name is the real Docker volume, see 'docker volume ls'):"
    echo "docker volume create <volume-name>"
    echo "docker run --rm -v <volume-name>:/target -v \$(pwd):/source alpine tar xzf /source/<file>.tar.gz -C /target"
    echo ""
    echo "# To restore n8n / authentik (bind-mounted dirs; stop the containers first):"
    echo "docker run --rm -v /data/<n8n|authentik>:/target -v \$(pwd):/source alpine tar xzf /source/<file>.tar.gz -C /target"
    echo ""
    echo "# To restore a PostgreSQL dump into a fresh, running container:"
    echo "gunzip -c <file>.sql.gz | docker exec -i <container> psql -U <user> -d postgres"
    echo ""
    echo "# To restore a directory:"
    echo "tar xzf <file>.tar.gz -C <target-directory>"
} > "$manifest"

# Sync backups to MinIO (if available)
echo -e "${BLUE}MinIO Sync:${NC}"
if command -v mc &>/dev/null && mc ls local &>/dev/null; then
    log_step "Syncing backup to MinIO..."
    if mc mirror --overwrite "$BACKUP_DIR/" "local/backups/$DATE/"; then
        log_step "  → Synced to MinIO: local/backups/$DATE/"
    else
        # mc is configured, so a failed mirror means no offsite copy: not a silent warning
        log_error "MinIO sync failed (local backup is intact)"
        FAILED+=("minio-sync")
    fi
else
    log_warn "MinIO client not configured (skipping sync)"
fi

echo ""

# Cleanup old local backups (keep last 30 days). Only timestamped run
# directories directly under BACKUP_ROOT are eligible, and nothing is pruned
# when this run failed (don't trade good old backups for a bad new one).
echo -e "${BLUE}Cleanup:${NC}"
if [ "${#FAILED[@]}" -eq 0 ]; then
    log_step "Removing backups older than 30 days..."
    old_count=$(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d \
        -name '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9]' \
        -mtime +30 2>/dev/null | wc -l)
    find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d \
        -name '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9][0-9][0-9]' \
        -mtime +30 -exec rm -rf {} + || log_warn "Some old backups could not be removed"

    if [ "$old_count" -gt 0 ]; then
        log_step "  → Removed $old_count old backup(s)"
    else
        log_step "  → No old backups to remove"
    fi
else
    log_warn "Skipping cleanup because this run had failures"
fi

echo ""

# Summary
total_size=$(du -sh "$BACKUP_DIR" | cut -f1)
file_count=$(ls -1 "$BACKUP_DIR" | wc -l)

if [ "${#FAILED[@]}" -eq 0 ]; then
    echo -e "${GREEN}=== Backup Complete ===${NC}"
else
    echo -e "${RED}=== Backup FAILED ===${NC}"
    printf '  failed: %s\n' "${FAILED[@]}"
fi
echo "Location:   $BACKUP_DIR"
echo "Size:       $total_size"
echo "Files:      $file_count"
echo "Skipped:    ${#SKIPPED[@]}"
echo "Manifest:   $manifest"
echo ""
echo "Schedule with cron:"
echo "  0 2 * * * $SCRIPT_DIR/backup.sh >> /var/log/ai-backup.log 2>&1"

if [ "${#FAILED[@]}" -gt 0 ]; then
    exit 1
fi
