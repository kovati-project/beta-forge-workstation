#!/bin/bash
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

# Check function
check_service() {
    local name=$1
    local url=$2
    local expected_code=${3:-200}
    local method=${4:-GET}
    
    local result=$(curl -sf -o /dev/null -w "%{http_code}" -X "$method" "$url" 2>/dev/null)
    
    if [ "$result" = "$expected_code" ]; then
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

echo -e "${BLUE}=== AI Workstation Health Check ===${NC}"
echo -e "Time: $(date)"
echo ""

# 1. Docker and basic infrastructure
echo -e "${BLUE}Infrastructure:${NC}"
check_command "Docker daemon" "docker info &>/dev/null"
check_command "Docker compose" "docker compose version &>/dev/null"

# 2. Storage services
echo ""
echo -e "${BLUE}Storage Services:${NC}"
check_service "MinIO (S3)" "http://localhost:9000/minio/health/live" "200"
check_service "MinIO Console" "http://localhost:9001" "403"  # 403 expected without auth
check_service "Qdrant (Vector DB)" "http://localhost:6333/" "200"
check_service "PostgreSQL (Primary)" "http://localhost:5432/heartbeat" "000"  # Not HTTP, but we can check container
check_command "PostgreSQL container" "docker inspect -f '{{.State.Running}}' postgres 2>/dev/null | grep -q true"

# 3. Monitoring services
echo ""
echo -e "${BLUE}Monitoring Services:${NC}"
check_service "Prometheus" "http://localhost:9091/-/healthy" "200"
check_service "Grafana" "http://localhost:3001/api/health" "200"
check_service "Node Exporter" "http://localhost:9100/metrics" "200"
check_service "cAdvisor" "http://localhost:8989/" "200"
check_command "DCGM Exporter" "docker ps | grep -q dcgm-exporter"

# 4. Authentication & Gateway
echo ""
echo -e "${BLUE}Authentication & Gateway:${NC}"
check_service "Authentik" "http://localhost:9080" "200"
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
    check_service "Label Studio" "http://localhost:8081" "200"
else
    echo -e "  ${YELLOW}◇${NC} Label Studio (not running)"
fi

if curl -sf http://localhost:8888 &>/dev/null; then
    check_service "JupyterLab" "http://localhost:8888" "200"
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
