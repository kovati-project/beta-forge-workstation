#!/usr/bin/env bash
# Shared helper: remove a container if it exists under a different Compose project.
# Prevents "container name already in use" on re-runs where a previous deployment
# used a different project name or the container was started manually.
#
# Usage: remove_orphan <container_name> <expected_compose_project_name>
remove_orphan() {
    local cname="$1"
    local expected_project="$2"
    if docker inspect "$cname" &>/dev/null; then
        local proj
        proj=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' "$cname" 2>/dev/null || true)
        if [[ "$proj" != "$expected_project" ]]; then
            echo "  [idempotency] Removing orphaned container $cname (project: ${proj:-none})"
            docker rm -f "$cname"
        fi
    fi
}
