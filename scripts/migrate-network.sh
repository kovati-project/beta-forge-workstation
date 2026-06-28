#!/usr/bin/env bash
# Migrate workstation containers from docker_default to ai-workstation.
#
# Run this once after updating compose files to add the named network, or any
# time containers end up on docker_default instead of ai-workstation.
#
# Usage:
#   bash scripts/migrate-network.sh          # migrate and disconnect
#   bash scripts/migrate-network.sh --check  # report only, no changes
set -euo pipefail

TARGET="ai-workstation"
SOURCE="docker_default"
CHECK_ONLY=false

[[ "${1:-}" == "--check" ]] && CHECK_ONLY=true

# Create target network if it doesn't exist
if ! docker network inspect "$TARGET" &>/dev/null; then
    if [[ "$CHECK_ONLY" == true ]]; then
        echo "  MISSING  network $TARGET does not exist"
        exit 1
    fi
    echo "Creating $TARGET network..."
    docker network create "$TARGET"
    echo "  ✓ Created $TARGET"
fi

# Get containers currently on docker_default
CONTAINERS=$(docker network inspect "$SOURCE" \
    --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null || true)
CONTAINERS=$(echo "$CONTAINERS" | tr ' ' '\n' | grep -v '^$' | sort || true)

if [[ -z "$CONTAINERS" ]]; then
    echo "  ✓ No containers on $SOURCE — nothing to migrate"
    exit 0
fi

echo "Containers on $SOURCE:"
for c in $CONTAINERS; do
    echo "  - $c"
done
echo ""

if [[ "$CHECK_ONLY" == true ]]; then
    echo "Run without --check to migrate them."
    exit 1
fi

echo "Migrating to $TARGET..."
MIGRATED=0
FAILED=0
for c in $CONTAINERS; do
    # Connect to ai-workstation first (safe even if already connected)
    if docker network connect "$TARGET" "$c" 2>/dev/null; then
        docker network disconnect "$SOURCE" "$c" 2>/dev/null || true
        echo "  ✓ $c"
        (( MIGRATED++ )) || true
    else
        echo "  ⚠  $c — could not connect (may already be on $TARGET)"
        (( FAILED++ )) || true
    fi
done

echo ""
echo "Done: $MIGRATED migrated, $FAILED skipped"
