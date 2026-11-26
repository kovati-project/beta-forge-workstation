#!/usr/bin/env bash
[ -n "${BASH_VERSION:-}" ] || { echo "ERROR: this script needs bash - run: bash $0" >&2; exit 1; }
# Validate Phase 08: Agentic Workflows & MCP
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib/workstation-host.sh"  # WORKSTATION_HOST (#51)

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
PASS=0; FAIL=0; WARN=0

check() {
    local desc="$1"; shift
    if eval "$@" &>/dev/null; then
        echo -e "${GREEN}✓${NC} $desc"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} $desc"
        ((FAIL++))
    fi
}

warn() {
    echo -e "${YELLOW}?${NC} $1 — manual verification needed"
    ((WARN++))
}

# MCP streamable-HTTP handshake: POST initialize to /mcp, expect a serverInfo.
mcp_init() {
    curl -sf -m 10 -X POST "http://localhost:$1/mcp" \
        -H 'Content-Type: application/json' \
        -H 'Accept: application/json, text/event-stream' \
        -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"validate-phase08","version":"1"}}}' \
        | grep -q '"serverInfo"'
}

echo "=== Phase 08 Validation ==="
echo ""

# Services running
check "n8n container running" "docker ps --filter name=n8n --filter status=running | grep -q n8n"
check "n8n HTTP responding" "curl -sf http://localhost:5678/"
check "MCP filesystem answers initialize on :3100/mcp" "mcp_init 3100"
check "MCP fetch answers initialize on :3103/mcp" "mcp_init 3103"
check "MCP browser answers initialize on :3101/mcp" "mcp_init 3101"
if docker ps --format '{{.Names}}' | grep -qx mcp-code-exec; then
    check "MCP code-exec answers initialize on :3102/mcp" "mcp_init 3102"
else
    echo "  - MCP code-exec disabled (compose profile code-exec), not checked"
fi

# Docker compose validation
echo ""
check "compose.agentic.yml is valid" "docker compose -f docker/compose.agentic.yml config > /dev/null"
check "n8n service defined" "docker compose -f docker/compose.agentic.yml config | grep -q 'n8n'"
check "MCP services defined" "docker compose -f docker/compose.agentic.yml config | grep -q 'mcp-filesystem'"

# Configuration files
echo ""
check "n8n data volume mounted" "docker inspect n8n | grep -q n8n-data"
check "n8n files directory exists" "[[ -d /data/n8n-files ]]"

# Manual checks
echo ""
warn "n8n owner account created (visit http://${WORKSTATION_HOST}:5678)"
warn "n8n LLM integration configured (Settings → AI, http://vllm-4gpu:8000/v1)"
warn "Can create and save n8n workflows"
warn "MCP tool calls work (docs/validation/TASK-101-mcp-filesystem.md, re-run section)"
warn "First n8n workflow executes end-to-end"

echo ""
echo "Result: ${PASS} passed, ${FAIL} failed, ${WARN} manual checks"
[[ $FAIL -eq 0 ]] && echo -e "${GREEN}Phase 08 READY${NC}" || echo -e "${RED}Phase 08 NOT READY — fix failures above${NC}"
exit $FAIL
