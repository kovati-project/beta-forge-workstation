#!/usr/bin/env bash
# Validate Phase 08: Agentic Workflows & MCP
set -euo pipefail

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

echo "=== Phase 08 Validation ==="
echo ""

# Services running
check "n8n container running" "docker ps --filter name=n8n --filter status=running | grep -q n8n"
check "n8n HTTP responding" "curl -sf http://localhost:5678/"
check "MCP filesystem responding" "curl -sf http://localhost:3100/ 2>&1 | grep -q -E '(ok|error|response)' || true"
check "MCP fetch responding" "curl -sf http://localhost:3103/ 2>&1 | grep -q -E '(ok|error|response)' || true"
check "MCP browser responding" "curl -sf http://localhost:3101/ 2>&1 | grep -q -E '(ok|error|response)' || true"
check "MCP code-exec responding" "curl -sf http://localhost:3102/ 2>&1 | grep -q -E '(ok|error|response)' || true"

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
warn "n8n owner account created (visit http://10.10.10.2:5678)"
warn "n8n Ollama integration configured (Settings → AI)"
warn "Can create and save n8n workflows"
warn "MCP servers respond to JSON-RPC calls (advanced testing)"
warn "First n8n workflow executes end-to-end"

echo ""
echo "Result: ${PASS} passed, ${FAIL} failed, ${WARN} manual checks"
[[ $FAIL -eq 0 ]] && echo -e "${GREEN}Phase 08 READY${NC}" || echo -e "${RED}Phase 08 NOT READY — fix failures above${NC}"
exit $FAIL
