#!/bin/bash
[ -n "${BASH_VERSION:-}" ] || { echo "ERROR: this script needs bash - run: bash $0" >&2; exit 1; }
# Phase 14 — Operations Runbook: Health Check Script
# Verifies all AI workstation services are operational
# Usage: bash scripts/healthcheck.sh

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
HEALTHY=0
UNHEALTHY=0
WARNINGS=0

# Locate the deployed tree and its deploy stamp. sync-and-deploy.ps1 writes
# scripts/.deployed-commit (key=value lines) into the synced tree.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
STAMP_FILE="$SCRIPT_DIR/.deployed-commit"

# status_matches CODE ALLOWED
# ALLOWED is a pipe-separated list of exact HTTP codes, e.g. "200|302".
# Exact matching only: no ranges and no blanket 3xx, so 000 (connection
# refused), 4xx and 5xx keep failing unless a check lists them explicitly.
status_matches() {
    local code=$1
    local allowed=$2
    case "|$allowed|" in
        *"|$code|"*) return 0 ;;
    esac
    return 1
}

# Check function
# Usage: check_service NAME URL [ALLOWED_CODES] [METHOD]
# ALLOWED_CODES is a single code or a pipe-separated set (default "200").
check_service() {
    local name=$1
    local url=$2
    local expected_code=${3:-200}
    local method=${4:-GET}

    local result=$(curl -sf -o /dev/null -w "%{http_code}" -X "$method" "$url" 2>/dev/null)
    # Normalise a missing code (e.g. curl itself absent) to curl's own "no response" value
    result=${result:-000}

    if status_matches "$result" "$expected_code"; then
        echo -e "  ${GREEN}✓${NC} $name"
        HEALTHY=$(( HEALTHY + 1 ))
        return 0
    else
        echo -e "  ${RED}✗${NC} $name (HTTP $result, expected $expected_code)"
        UNHEALTHY=$(( UNHEALTHY + 1 ))
        return 1
    fi
}

check_command() {
    local name=$1
    local cmd=$2
    
    if eval "$cmd" &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $name"
        HEALTHY=$(( HEALTHY + 1 ))
        return 0
    else
        echo -e "  ${RED}✗${NC} $name"
        UNHEALTHY=$(( UNHEALTHY + 1 ))
        return 1
    fi
}

# Print the deploy stamp and warn (never fail) if it is missing, stale or dirty.
# Stale = stamp commit differs from the local git HEAD; only checkable when a
# .git is present (rsync excludes .git/, so a synced host usually has none).
check_deploy_stamp() {
    echo -e "${BLUE}Deployment:${NC}"

    local head_full="" head_short="" head_branch=""
    if [ -e "$REPO_DIR/.git" ] && command -v git &>/dev/null; then
        head_full=$(git -C "$REPO_DIR" rev-parse HEAD 2>/dev/null)
        head_short=$(git -C "$REPO_DIR" rev-parse --short HEAD 2>/dev/null)
        head_branch=$(git -C "$REPO_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null)
    fi

    if [ ! -r "$STAMP_FILE" ]; then
        echo -e "  ${YELLOW}⚠${NC} No deploy stamp (${STAMP_FILE##*/}) — deployed version unknown; re-sync with sync-and-deploy.ps1"
        WARNINGS=$(( WARNINGS + 1 ))
        if [ -n "$head_full" ]; then
            echo "  Local git HEAD: $head_short ($head_branch)"
        fi
        return 0
    fi

    local s_short s_full s_branch s_time s_dirty
    s_short=$(sed -n 's/^short=//p' "$STAMP_FILE" | head -n1 | tr -d '\r')
    s_full=$(sed -n 's/^full=//p' "$STAMP_FILE" | head -n1 | tr -d '\r')
    s_branch=$(sed -n 's/^branch=//p' "$STAMP_FILE" | head -n1 | tr -d '\r')
    s_time=$(sed -n 's/^timestamp=//p' "$STAMP_FILE" | head -n1 | tr -d '\r')
    s_dirty=$(sed -n 's/^dirty=//p' "$STAMP_FILE" | head -n1 | tr -d '\r')

    echo "  Deployed: ${s_short:-unknown} (${s_branch:-unknown}) at ${s_time:-unknown}, dirty=${s_dirty:-unknown}"
    echo "  Full SHA: ${s_full:-unknown}"

    if [ "$s_dirty" = "true" ]; then
        echo -e "  ${YELLOW}⚠${NC} Deployed from a working tree with uncommitted changes — commit does not fully identify the code"
        WARNINGS=$(( WARNINGS + 1 ))
    fi

    if [ -z "$head_full" ]; then
        # No local .git (normal for an rsync deployment): nothing to compare against.
        return 0
    fi

    local match=""
    if [ -n "$s_full" ] && [ "$s_full" != "unknown" ]; then
        if [ "$s_full" = "$head_full" ]; then match=yes; else match=no; fi
    elif [ -n "$s_short" ] && [ "$s_short" != "unknown" ]; then
        case "$head_full" in
            "$s_short"*) match=yes ;;
            *) match=no ;;
        esac
    fi

    if [ "$match" = "yes" ]; then
        echo -e "  ${GREEN}✓${NC} Stamp matches local git HEAD ($head_short)"
    elif [ "$match" = "no" ]; then
        echo -e "  ${YELLOW}⚠${NC} Stamp (${s_short:-?}) differs from local git HEAD ($head_short) — deployment may be stale"
        WARNINGS=$(( WARNINGS + 1 ))
    else
        echo -e "  ${YELLOW}⚠${NC} Deploy stamp has no usable commit; cannot compare with local git HEAD ($head_short)"
        WARNINGS=$(( WARNINGS + 1 ))
    fi
}

echo -e "${BLUE}=== AI Workstation Health Check ===${NC}"
echo -e "Time: $(date)"
echo ""

# 0. Deployment stamp — is the code on this host the code in the repo?
# Warnings only: a stale or unstamped deployment does not fail the health check.
check_deploy_stamp
echo ""

# 1. Docker and basic infrastructure
echo -e "${BLUE}Infrastructure:${NC}"
check_command "Docker daemon" "docker info &>/dev/null"
check_command "Docker compose" "docker compose version &>/dev/null"

# 2. Storage services
echo ""
echo -e "${BLUE}Storage Services:${NC}"
check_service "MinIO (S3)" "http://localhost:9000/minio/health/live" "200"
# Console serves its login SPA with 200 unauthenticated; the former 403 expectation was
# wrong (TASK-120). Only 200 is accepted: 403 or a redirect would mean something changed.
check_service "MinIO Console" "http://localhost:9001" "200"
check_service "Qdrant (Vector DB)" "http://localhost:6333/" "200"
check_service "PostgreSQL (Primary)" "http://localhost:5432/heartbeat" "000"  # Not HTTP, but we can check container
check_command "PostgreSQL container" "docker inspect -f '{{.State.Running}}' postgres 2>/dev/null | grep -q true"

# 3. Monitoring services
echo ""
echo -e "${BLUE}Monitoring Services:${NC}"
check_service "Prometheus" "http://localhost:9091/-/healthy" "200"
check_service "Grafana" "http://localhost:3001/api/health" "200"
check_service "Node Exporter" "http://localhost:9100/metrics" "200"
# cAdvisor redirects / to /containers/ (307), so 307 is healthy; 200 kept in case that changes
check_service "cAdvisor" "http://localhost:8989/" "200|307"
check_command "DCGM Exporter" "docker ps | grep -q dcgm-exporter"

# 4. Authentication & Gateway
echo ""
echo -e "${BLUE}Authentication & Gateway:${NC}"
# Unauthenticated IdP redirects / to its login/flow page (302), which is correct behaviour
check_service "Authentik" "http://localhost:9080" "200|302"
check_command "Authentik PostgreSQL" "docker inspect -f '{{.State.Running}}' authentik-postgres 2>/dev/null | grep -q true"
check_command "Authentik Redis" "docker inspect -f '{{.State.Running}}' authentik-redis 2>/dev/null | grep -q true"

# 5. GPU Orchestration
echo ""
echo -e "${BLUE}GPU Orchestration:${NC}"
check_service "Loadout Manager" "http://localhost:8800/health" "200"

# 6. Inference services
echo ""
echo -e "${BLUE}Inference Services:${NC}"
check_service "Ollama" "http://localhost:11434/api/tags" "200"
check_service "vLLM Pair A (GPU 0+3)" "http://localhost:8000/health" "200"
check_service "ComfyUI" "http://localhost:8188/system_stats" "200"
check_service "Open WebUI" "http://localhost:3000" "200"
check_service "SearXNG" "http://localhost:8080" "200"

# 7. Training services (optional)
echo ""
echo -e "${BLUE}Training Services:${NC}"
if curl -sf http://localhost:7860 &>/dev/null; then
    check_service "Kohya" "http://localhost:7860" "200"
else
    echo -e "  ${YELLOW}◇${NC} Kohya (not running)"
fi

if curl -sf http://localhost:8081 &>/dev/null; then
    # Unauthenticated / redirects to the login page (302)
    check_service "Label Studio" "http://localhost:8081" "200|302"
else
    echo -e "  ${YELLOW}◇${NC} Label Studio (not running)"
fi

if curl -sf http://localhost:8888 &>/dev/null; then
    # Unauthenticated / redirects to /lab or the login page (302)
    check_service "JupyterLab" "http://localhost:8888" "200|302"
else
    echo -e "  ${YELLOW}◇${NC} JupyterLab (not running)"
fi

# 8. Agentic services
echo ""
echo -e "${BLUE}Agentic Services:${NC}"
check_service "n8n" "http://localhost:5678" "200"
if curl -sf http://localhost:3003 &>/dev/null; then
    check_service "OpenHands" "http://localhost:3003" "200"
else
    echo -e "  ${YELLOW}◇${NC} OpenHands (not running)"
fi

if curl -sf http://localhost:3010 &>/dev/null; then
    check_service "Dify" "http://localhost:3010" "200"
else
    echo -e "  ${YELLOW}◇${NC} Dify (not running)"
fi

check_command "MCP Filesystem Server" "docker ps | grep -q 'mcp-filesystem'"
check_command "MCP Fetch Server" "docker ps | grep -q 'mcp-fetch'"

# 9. Voice services
echo ""
echo -e "${BLUE}Voice Services:${NC}"
if curl -sf http://localhost:9099/health &>/dev/null; then
    check_service "Whisper (Speech-to-Text)" "http://localhost:9099/health" "200"
else
    echo -e "  ${YELLOW}◇${NC} Whisper (not running)"
fi

if curl -sf http://localhost:5000 &>/dev/null; then
    check_service "Piper (Text-to-Speech)" "http://localhost:5000/api/synthesize" "200" "POST"
else
    echo -e "  ${YELLOW}◇${NC} Piper (not running)"
fi

# 10. Observability
echo ""
echo -e "${BLUE}Observability:${NC}"
if curl -sf http://localhost:3002 &>/dev/null; then
    check_service "Langfuse" "http://localhost:3002" "200"
else
    echo -e "  ${YELLOW}◇${NC} Langfuse (not running)"
fi

# 11. GPU Status
echo ""
echo -e "${BLUE}GPU Status:${NC}"
if command -v nvidia-smi &>/dev/null; then
    echo "  GPU Summary:"
    nvidia-smi --query-gpu=index,name,temperature.gpu,utilization.gpu,memory.used,memory.free \
        --format=csv,noheader,nounits 2>/dev/null | \
        while read -r line; do
            echo "    $line" | awk -F', ' '{printf "    GPU%s: %.2f°C | %s%% util | %s/%sM\n", $1,$3,$4,$5,$6}'
        done || echo "    ${YELLOW}(nvidia-smi not available)${NC}"
    
    # Check for ECC errors
    if command -v nvidia-smi &>/dev/null; then
        ecc_errors=$(nvidia-smi -q -d ECC 2>/dev/null | grep -c "1 error" || true)
        if [ "$ecc_errors" -gt 0 ]; then
            echo -e "    ${RED}⚠ ECC errors detected${NC}"
            WARNINGS=$(( WARNINGS + 1 ))
        fi
    fi
else
    echo -e "  ${YELLOW}◇${NC} nvidia-smi not available"
fi

# 12. Active Loadout Profile
echo ""
echo -e "${BLUE}Active Loadout Profile:${NC}"
if profile=$(curl -sf http://localhost:8800/status 2>/dev/null); then
    active=$(echo "$profile" | grep -o '"active_profile":"[^"]*"' | cut -d'"' -f4)
    running=$(echo "$profile" | grep -o '"running_services":\[[^]]*\]')
    echo -e "  Profile: ${GREEN}$active${NC}"
    echo -e "  Services: $running"
else
    echo -e "  ${RED}(unable to reach Loadout Manager)${NC}"
fi

# 13. Storage and Resource Usage
echo ""
echo -e "${BLUE}Storage & Resources:${NC}"
if df /data &>/dev/null; then
    df_output=$(df -h /data | awk 'NR==2 {printf "  Data volume: %s used of %s (%s)\n", $3, $2, $5}')
    echo "$df_output"
    
    # Check if usage is high
    usage_pct=$(df /data | awk 'NR==2 {print $5}' | sed 's/%//')
    if [ "$usage_pct" -gt 85 ]; then
        echo -e "  ${YELLOW}⚠ Storage >85% full${NC}"
        WARNINGS=$(( WARNINGS + 1 ))
    fi
fi

# System RAM
if command -v free &>/dev/null; then
    ram_output=$(free -h | awk 'NR==2 {printf "  System RAM: %s used of %s (%.0f%%)\n", $3, $2, ($3/$2)*100}')
    echo "$ram_output"
fi

# Summary
echo ""
echo -e "${BLUE}Summary:${NC}"
total=$((HEALTHY + UNHEALTHY))
pct=$((HEALTHY * 100 / total))
if [ $UNHEALTHY -eq 0 ]; then
    echo -e "  ${GREEN}✓ All services healthy${NC} ($HEALTHY/$total running)"
elif [ $UNHEALTHY -le 3 ]; then
    echo -e "  ${YELLOW}⚠ Minor issues detected${NC} ($HEALTHY/$total healthy, $UNHEALTHY failed)"
else
    echo -e "  ${RED}✗ Multiple failures${NC} ($HEALTHY/$total healthy, $UNHEALTHY failed)"
fi

if [ $WARNINGS -gt 0 ]; then
    echo -e "  ${YELLOW}⚠ $WARNINGS warning(s)${NC}"
fi

echo ""
echo -e "Check Grafana dashboards at ${BLUE}http://10.10.10.2:3001${NC}"
echo -e "View Authentik admin at ${BLUE}http://10.10.10.2:9080/if/admin/${NC}"

# Exit with appropriate code
[ $UNHEALTHY -eq 0 ]
