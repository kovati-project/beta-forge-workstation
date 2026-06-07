#!/usr/bin/env bash
# Validate Phase 06: Loadout Manager
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
PASS=0; FAIL=0

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

echo "=== Phase 06 Validation ==="
echo ""

# Service
check "Loadout Manager container running" "docker ps --filter name=loadout-manager | grep -q loadout-manager"
check "API responding at :8800" "curl -sf http://localhost:8800/health"

# Endpoints
check "GET /loadouts lists all profiles" "curl -sf http://localhost:8800/loadouts | jq -e '.inference-small' > /dev/null"
check "GET /status returns GPU info" "curl -sf http://localhost:8800/status | jq -e '.gpus[0]' > /dev/null"
check "Web UI loads" "curl -sf http://localhost:8800/ | grep -q 'Loadout Manager'"

# Profiles validation
echo ""
check "8 profiles defined" "curl -sf http://localhost:8800/loadouts | jq 'length' | grep -q 8"
check "inference-small profile exists" "curl -sf http://localhost:8800/loadouts | jq -e '.\"inference-small\"' > /dev/null"
check "training-lora-text profile exists" "curl -sf http://localhost:8800/loadouts | jq -e '.\"training-lora-text\"' > /dev/null"

# Docker socket access
echo ""
check "Docker socket accessible" "docker ps --filter name=ollama 2>/dev/null | head -1"

echo ""
echo "Result: ${PASS} passed, ${FAIL} failed"
[[ $FAIL -eq 0 ]] && echo -e "${GREEN}Phase 06 READY${NC}" || echo -e "${RED}Phase 06 NOT READY${NC}"
exit $FAIL
