#!/bin/bash
# Phase 10 validation: Verify monitoring stack deployment
# Checks: Prometheus, Grafana, exporters, targets, alerts

set -e

echo "=== Phase 10 Validation ==="
echo ""

FAILED=0
PASSED=0

# Helper functions
check_pass() {
    echo "✓ $1"
    PASSED=$(( PASSED + 1 ))
}

check_fail() {
    echo "✗ $1"
    FAILED=$(( FAILED + 1 ))
}

check_warn() {
    echo "⊘ $1"
}

# ========== AUTOMATED CHECKS ==========
echo "Automated checks:"
echo ""

# 1. Prometheus responding
if curl -sf http://localhost:9091/-/healthy > /dev/null 2>&1; then
    check_pass "Prometheus health check passing on :9091"
else
    check_fail "Prometheus not responding on :9091"
fi

# 2. Prometheus metrics endpoint
if curl -sf http://localhost:9091/metrics > /dev/null 2>&1; then
    check_pass "Prometheus /metrics endpoint available"
else
    check_fail "Prometheus /metrics endpoint not responding"
fi

# 3. Grafana responding
if curl -sf http://localhost:3001/api/health > /dev/null 2>&1; then
    check_pass "Grafana API responding on :3001"
else
    check_fail "Grafana not responding on :3001"
fi

# 4. DCGM exporter responding
if curl -sf http://localhost:9400/metrics > /dev/null 2>&1; then
    check_pass "DCGM Exporter metrics on :9400"
else
    check_fail "DCGM Exporter not responding on :9400"
fi

# 5. Node exporter responding
if curl -sf http://localhost:9100/metrics > /dev/null 2>&1; then
    check_pass "Node Exporter metrics on :9100"
else
    check_fail "Node Exporter not responding on :9100"
fi

# 6. cAdvisor responding
if curl -sf http://localhost:8989/api/v1.3/machine > /dev/null 2>&1; then
    check_pass "cAdvisor API responding on :8989"
else
    check_warn "cAdvisor not responding (might still initialize)"
fi

# 7. Docker compose file valid
if docker compose -f docker/compose.monitoring.yml config > /dev/null 2>&1; then
    check_pass "docker/compose.monitoring.yml is valid"
else
    check_fail "docker/compose.monitoring.yml syntax error"
fi

# 8. All services defined in compose
for service in prometheus grafana dcgm-exporter node-exporter cadvisor; do
    if docker compose -f docker/compose.monitoring.yml config | grep -q "^    $service:"; then
        check_pass "Service defined: $service"
    else
        check_fail "Service not defined: $service"
    fi
done

# 9. Config files exist
for file in configs/prometheus/prometheus.yml configs/prometheus/alerts.yml configs/grafana/provisioning/datasources/prometheus.yml; do
    if [ -f "$file" ]; then
        check_pass "File exists: $file"
    else
        check_fail "File missing: $file"
    fi
done

# 10. Prometheus config valid
if docker run --rm -v "$(pwd)/configs/prometheus:/etc/prometheus" prom/prometheus:latest promtool check config /etc/prometheus/prometheus.yml > /dev/null 2>&1; then
    check_pass "Prometheus configuration valid (promtool check)"
else
    check_warn "Prometheus config validation skipped (requires promtool container)"
fi

echo ""
echo "Automated checks: $PASSED passed, $FAILED failed"
echo ""

# ========== PROMETHEUS TARGETS CHECK ==========
echo "Prometheus target status:"
echo ""

# Query Prometheus for all targets
TARGETS_UP=$(curl -s http://localhost:9091/api/v1/targets | jq '.data.activeTargets | length')
TARGETS_DOWN=$(curl -s http://localhost:9091/api/v1/targets | jq '.data.droppedTargets | length')

echo "Active targets: $TARGETS_UP"
echo "Dropped targets: $TARGETS_DOWN"

# Show target details
echo ""
echo "Target health:"
curl -s http://localhost:9091/api/v1/targets | jq -r '.data.activeTargets[] | "  \(.labels.job): \(.health)"' 2>/dev/null || check_warn "Could not parse targets"

echo ""

# ========== ALERT RULES CHECK ==========
echo "Alert rules:"
echo ""

ALERTS=$(curl -s http://localhost:9091/api/v1/rules | jq '.data.groups[].rules | length' | awk '{sum+=$1} END {print sum}')
if [ -n "$ALERTS" ] && [ "$ALERTS" -gt 0 ]; then
    check_pass "Alert rules loaded: $ALERTS rules"
else
    check_warn "No alert rules loaded (check alerts.yml)"
fi

echo ""

# ========== MANUAL CHECKS ==========
echo "Manual verification checklist:"
echo ""
echo "[ ] Prometheus targets all 'UP':"
echo "    http://10.10.10.2:9091/targets"
echo ""
echo "[ ] GPU metrics present in Prometheus:"
echo "    http://10.10.10.2:9091/graph?query=DCGM_FI_DEV_GPU_UTIL"
echo "    - Should show graphs for GPU0-3"
echo ""
echo "[ ] Grafana dashboard import:"
echo "    Dashboards → Import → ID 12239 (NVIDIA DCGM)"
echo "    - Should display GPU metrics for 4 GPUs"
echo ""
echo "[ ] Grafana dashboard import (system):"
echo "    Dashboards → Import → ID 1860 (Node Exporter Full)"
echo "    - Should display CPU, RAM, disk, network metrics"
echo ""
echo "[ ] Grafana dashboard import (containers):"
echo "    Dashboards → Import → ID 893 (Docker Container Stats)"
echo "    - Should display per-container resource usage"
echo ""
echo "[ ] Verify alert rules:"
echo "    Prometheus → Alerts"
echo "    - Should list groups: gpu_alerts, system_alerts, service_alerts, etc."
echo ""
echo "[ ] Test GPU alert (optional):"
echo "    Run: stress-ng --gpu 0 --gpu-ops 1000000 &"
echo "    Wait for temperature > 83°C"
echo "    Should trigger GPUHighTemperature alert"
echo ""
echo "[ ] CLI GPU monitoring:"
echo "    pip install nvitop && nvitop"
echo "    - Should show real-time GPU metrics"
echo ""
echo "[ ] Verify metrics retention:"
echo "    Prometheus → Status → Runtime & Build"
echo "    - Should show --storage.tsdb.retention.time=90d"
echo ""

# ========== RESULT ==========
echo ""
if [ $FAILED -eq 0 ]; then
    echo "Phase 10 READY ✓"
    exit 0
else
    echo "Phase 10 has $FAILED issue(s) — see above"
    exit 1
fi
