#!/usr/bin/env bash
# Validate Phase 05: Open WebUI + SearXNG
# Run on the workstation after deploy-phase05.sh completes.
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
    echo -e "${YELLOW}?${NC} $1 — check manually"
    ((WARN++))
}

echo "=== Phase 05 Validation ==="
echo ""

# Services
check "Open WebUI container running"  "docker ps --filter name=open-webui --filter status=running | grep -q open-webui"
check "Open WebUI HTTP responding"    "curl -sf http://localhost:3000/"
check "SearXNG container running"     "docker ps --filter name=searxng --filter status=running | grep -q searxng"
check "SearXNG API responding"        "curl -sf 'http://localhost:8080/search?q=test&format=json'"

# Backends reachable from Open WebUI's perspective
echo ""
check "Ollama reachable at :11434"    "curl -sf http://localhost:11434/v1/models"
check "nomic-embed-text in Ollama"    "curl -sf http://localhost:11434/v1/models | grep -q nomic-embed-text"
check "ComfyUI reachable at :8188"    "curl -sf http://localhost:8188/system_stats"

# Config
echo ""
check "WEBUI_SECRET_KEY not default"       "docker inspect open-webui | grep WEBUI_SECRET_KEY | grep -v 'change-this'"
check "ENABLE_SIGNUP=false set"            "docker inspect open-webui | grep -q 'ENABLE_SIGNUP=false'"
check "SearXNG secret_key not placeholder" "! grep -q 'change-this-to-a-random-32-char-string' configs/searxng/settings.yml"

# Manual checks
echo ""
warn "Admin account created and signup disabled — verify in browser"
warn "Ollama models visible in model selector — check http://10.10.10.2:3000"
warn "Chat response from mistral:7b works end-to-end"
warn "/image command produces output via ComfyUI (requires checkpoint downloaded)"
warn "Web search returns results in chat"
warn "RAG document upload works — try uploading a PDF and querying it"

echo ""
echo "Result: ${PASS} passed, ${FAIL} failed, ${WARN} manual checks"
[[ $FAIL -eq 0 ]] && echo -e "${GREEN}Phase 05 READY${NC}" || echo -e "${RED}Phase 05 NOT READY — fix failures above${NC}"
exit $FAIL
