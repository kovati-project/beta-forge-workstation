#!/usr/bin/env bash
# predeploy-check.sh: what would `docker compose up` do to the running host?
#
# Read-only. For every container that docker compose created, compares its
# config hash with the hash the checkout's compose files would produce now:
#
#   unchanged   `up` leaves the container alone
#   RECREATE    `up` replaces it (expected for services this deploy changes)
#   MISMATCH    it belongs to another compose project than the file declares;
#               `up` would fail on container_name or start a duplicate
#   NOT-IN-REPO no compose file defines the service any more
#
# The hash depends on the project directory: the same file run from
# /home/kasemo/share/... and from /srv/src/... resolves relative bind mounts to
# different paths and recreates the container. Each container is checked with
# its own project and working directory (its compose labels), which is also
# what the deploy must pass (see docs/runbooks/deploy-integration-2026-11.md).
#
# Exit status: 0 if no vLLM container would be recreated and nothing is in
# MISMATCH, 1 otherwise, 2 on usage errors.
#
# Usage: bash scripts/predeploy-check.sh [--env-file FILE] [--all]
#   --env-file  env file for interpolation (default docker/.env; must be
#               readable: run as the user who owns it)
#   --all       also list unchanged containers

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_DIR="$REPO_ROOT/docker"
ENV_FILE="$COMPOSE_DIR/.env"
SHOW_ALL=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env-file) ENV_FILE="$2"; shift 2 ;;
        --all)      SHOW_ALL=1; shift ;;
        -h|--help)  sed -n '2,27p' "$0"; exit 0 ;;
        *)          echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

if [[ ! -r "$ENV_FILE" ]]; then
    echo "cannot read env file $ENV_FILE (run as its owner, or pass --env-file)" >&2
    exit 2
fi
command -v docker >/dev/null || { echo "docker not found" >&2; exit 2; }

dc() { docker compose --env-file "$ENV_FILE" "$@"; }

# (project, service) -> compose file, service -> compose file (fallback), and
# compose file -> declared project. Service keys repeat across files (both
# compose.auth.yml and compose.storage.yml have a "postgres"), so a container
# is matched by its project first.
declare -A FILE_OF FILE_OF_PS PROJECT_OF
for f in "$COMPOSE_DIR"/compose.*.yml; do
    b="$(basename "$f")"
    if ! services="$(dc -f "$f" --profile '*' config --services 2>/dev/null)"; then
        echo "warning: $b does not render; its services are reported NOT-IN-REPO" >&2
        continue
    fi
    PROJECT_OF[$b]="$(dc -f "$f" config --format json 2>/dev/null \
        | python3 -c 'import json,sys; print(json.load(sys.stdin).get("name",""))')"
    while read -r s; do
        [[ -z "$s" ]] && continue
        FILE_OF[$s]="$b"
        FILE_OF_PS["${PROJECT_OF[$b]}/$s"]="$b"
    done <<<"$services"
done

bad=0
printf '%-12s %-22s %-16s %s\n' STATUS CONTAINER PROJECT NOTE
fmt='{{.Names}}|{{.Label "com.docker.compose.project"}}|{{.Label "com.docker.compose.service"}}|{{.Label "com.docker.compose.project.working_dir"}}|{{.Label "com.docker.compose.config-hash"}}|{{.State}}'
while IFS='|' read -r name project service wd hash cstate; do
    [[ -z "$project" || -z "$service" ]] && continue      # not a compose container
    file="${FILE_OF_PS[$project/$service]:-${FILE_OF[$service]:-}}"
    if [[ -z "$file" ]]; then
        printf '%-12s %-22s %-16s %s\n' NOT-IN-REPO "$name" "$project" "($cstate) no compose file defines '$service'"
        continue
    fi
    declared="${PROJECT_OF[$file]:-}"
    if [[ -n "$declared" && "$declared" != "$project" ]]; then
        printf '%-12s %-22s %-16s %s\n' MISMATCH "$name" "$project" "$file declares project '$declared'; remove this container before 'up'"
        bad=1
        continue
    fi
    if [[ ! -d "$wd" ]]; then
        printf '%-12s %-22s %-16s %s\n' RECREATE "$name" "$project" "working dir $wd no longer exists"
        [[ "$name" == vllm-* ]] && bad=1
        continue
    fi
    new="$(dc -p "$project" --project-directory "$wd" -f "$COMPOSE_DIR/$file" \
               --profile '*' config --hash "$service" 2>/dev/null | awk '{print $2}')"
    if [[ "$new" == "$hash" ]]; then
        [[ $SHOW_ALL == 1 ]] && printf '%-12s %-22s %-16s %s\n' unchanged "$name" "$project" "$file"
    else
        note="$file (--project-directory $wd)"
        if [[ "$name" == vllm-* ]]; then note="$note  <-- vLLM would restart"; bad=1; fi
        printf '%-12s %-22s %-16s %s\n' RECREATE "$name" "$project" "$note"
    fi
done < <(docker ps -a --format "$fmt" | sort -t'|' -k2,2 -k1,1)

echo
echo "Keys in docker/.env.example missing from $(basename "$ENV_FILE") (names only):"
missing="$(comm -23 \
    <(grep -oE '^#? ?[A-Z][A-Z0-9_]*=' "$COMPOSE_DIR/.env.example" | tr -d '# =' | sort -u) \
    <(grep -oE '^[A-Z][A-Z0-9_]*=' "$ENV_FILE" | tr -d '=' | sort -u))"
if [[ -n "$missing" ]]; then
    sed 's/^/  /' <<<"$missing"
    echo "  (commented keys in .env.example are optional)"
else
    echo "  none"
fi

exit "$bad"
