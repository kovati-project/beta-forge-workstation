#!/usr/bin/env bash
# Sync project files from this repo to the workstation.
# Run from the repo root on Windows (Git Bash / WSL) or any Linux/Mac.
#
# Usage:
#   bash scripts/sync-to-workstation.sh             # sync
#   bash scripts/sync-to-workstation.sh --dry-run   # preview what would change
#
# After sync, scripts are chmod +x'd on the workstation automatically.

set -euo pipefail

HOST="kasemo@10.10.10.2"
REMOTE_DIR="~/ai-workstation-project"
DRY_RUN=""

for arg in "$@"; do
    case "$arg" in
        --dry-run|-n) DRY_RUN="--dry-run" ;;
        --help|-h)
            echo "Usage: bash scripts/sync-to-workstation.sh [--dry-run]"
            exit 0
            ;;
    esac
done

# Resolve repo root regardless of where the script is called from
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Sync to workstation ==="
echo "Source:      $REPO_ROOT"
echo "Destination: $HOST:$REMOTE_DIR"
[[ -n "$DRY_RUN" ]] && echo "Mode:        DRY RUN (no files transferred)"
echo ""

# ── Prefer rsync (available in Git for Windows, WSL, macOS) ──────────────────
if command -v rsync &>/dev/null; then
    echo "Using rsync..."
    rsync -avz \
        $DRY_RUN \
        --exclude='.git/' \
        --exclude='*.pyc' \
        --exclude='__pycache__/' \
        --exclude='.env' \
        --exclude='*.env' \
        --exclude='docker/.env' \
        --exclude='plan/' \
        --exclude='distro/' \
        --exclude='*.ps1' \
        --exclude='node_modules/' \
        --exclude='.pytest_cache/' \
        --exclude='*.egg-info/' \
        "$REPO_ROOT/" "$HOST:$REMOTE_DIR/"
# ── Fallback: scp ─────────────────────────────────────────────────────────────
elif command -v scp &>/dev/null; then
    if [[ -n "$DRY_RUN" ]]; then
        echo "[dry-run] Would run: scp -r docker scripts configs loadout-manager $HOST:$REMOTE_DIR/"
        exit 0
    fi
    echo "rsync not found — using scp..."
    scp -r docker scripts configs loadout-manager "$HOST:$REMOTE_DIR/"
else
    echo "ERROR: Neither rsync nor scp found. Install OpenSSH or Git for Windows."
    exit 1
fi

if [[ -n "$DRY_RUN" ]]; then
    echo ""
    echo "Dry run complete. Remove --dry-run to transfer."
    exit 0
fi

# ── Make scripts executable on workstation ────────────────────────────────────
echo ""
echo "Setting script permissions..."
ssh "$HOST" "chmod +x $REMOTE_DIR/scripts/*.sh $REMOTE_DIR/scripts/*.py 2>/dev/null; echo '  ✓ chmod +x scripts/*'"

# ── Ensure project directories exist on workstation ──────────────────────────
echo "Ensuring workstation directories exist..."
ssh "$HOST" "mkdir -p $REMOTE_DIR/{docker,scripts,configs,loadout-manager}"

echo ""
echo "=== Sync complete ==="
echo ""
echo "Next: deploy from workstation"
echo "  ssh $HOST"
echo "  cd ai-workstation"
echo "  bash scripts/deploy-all.sh"
echo ""
echo "Or deploy directly from here:"
echo "  bash scripts/sync-to-workstation.sh && ssh $HOST 'cd ~/ai-workstation && bash scripts/deploy-all.sh --from 03'"
