#!/usr/bin/env bash
# Shared helper: resolve WORKSTATION_HOST, the address browsers and clients use
# to reach this workstation (an IP or a hostname such as kovati.lan).
#
# Order: an already-exported WORKSTATION_HOST, then WORKSTATION_HOST= in
# docker/.env, then 10.10.10.2 (the same fallback the compose files use).
# Change the host in docker/.env only; see README "Changing the workstation host".
#
# Usage: source "$REPO_ROOT/scripts/lib/workstation-host.sh"
#        echo "Open WebUI: http://${WORKSTATION_HOST}:3000"
if [[ -z "${WORKSTATION_HOST:-}" ]]; then
    _wh_env="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/docker/.env"
    if [[ -r "$_wh_env" ]]; then
        WORKSTATION_HOST="$(sed -n 's/^WORKSTATION_HOST=//p' "$_wh_env" | tail -n 1 | tr -d '\r"'"'"' ')"
    fi
    unset _wh_env
fi
WORKSTATION_HOST="${WORKSTATION_HOST:-10.10.10.2}"
export WORKSTATION_HOST
