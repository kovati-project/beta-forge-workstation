#!/bin/bash
# Phase 10 deployment: Monitoring & Observability
# Deploys Prometheus, Grafana, DCGM exporter, node exporter, cAdvisor

set -e

echo "=== Phase 10: Monitoring & Observability ==="
echo ""

# Verify Phase 06 (Loadout Manager) is running
echo "Checking Phase 06 (Loadout Manager)..."
if ! curl -sf http://localhost:8800/health > /dev/null 2>&1; then
    echo "WARNING: Loadout Manager not running on :8800"
    echo "Monitoring will work but GPU orchestrator metrics unavailable"
fi
echo ""

# Verify docker compose file exists
if [ ! -f "docker/compose.monitoring.yml" ]; then
    echo "ERROR: docker/compose.monitoring.yml not found"
    exit 1
fi

# Verify prometheus config exists
if [ ! -f "configs/prometheus/prometheus.yml" ]; then
    echo "ERROR: configs/prometheus/prometheus.yml not found"
    exit 1
fi

# Verify alert rules exist
if [ ! -f "configs/prometheus/alerts.yml" ]; then
    echo "ERROR: configs/prometheus/alerts.yml not found"
    exit 1
fi

# Create monitoring directories
echo "Creating monitoring directories..."
mkdir -p configs/prometheus
mkdir -p configs/grafana/provisioning/datasources
mkdir -p configs/grafana/provisioning/dashboards
echo "✓ Directories created"
echo ""

# Start services
echo "Starting monitoring stack..."
docker compose -f docker/compose.monitoring.yml up -d prometheus grafana dcgm-exporter node-exporter cadvisor
echo "✓ Containers started"
echo ""

# Wait for services to be ready
echo "Waiting for services to initialize..."
for i in {1..30}; do
    if curl -sf http://localhost:9091/-/healthy > /dev/null 2>&1; then
        break
    fi
    if [ $i -eq 30 ]; then
        echo "WARNING: Prometheus still initializing"
    fi
    sleep 1
done

# Verify services are responding
echo ""
echo "Verifying services..."
FAILED=0

if curl -sf http://localhost:9091/-/healthy > /dev/null 2>&1; then
    echo "✓ Prometheus running on :9091"
else
    echo "✗ Prometheus not responding"
    FAILED=1
fi

if curl -sf http://localhost:3001/api/health > /dev/null 2>&1; then
    echo "✓ Grafana running on :3001"
else
    echo "⊘ Grafana initializing (might take a moment)"
fi

if curl -sf http://localhost:9400/metrics > /dev/null 2>&1; then
    echo "✓ DCGM Exporter running on :9400"
else
    echo "⊘ DCGM Exporter not responding (check: docker logs dcgm-exporter)"
    echo "  Common fix: nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker"
fi

if curl -sf http://localhost:9100/metrics > /dev/null 2>&1; then
    echo "✓ Node Exporter running on :9100"
else
    echo "✗ Node Exporter not responding"
    FAILED=1
fi

if curl -sf http://localhost:8989/api/v1.3/machine > /dev/null 2>&1; then
    echo "✓ cAdvisor running on :8989"
else
    echo "⊘ cAdvisor initializing"
fi

# Wait a bit longer for Grafana
sleep 5
if curl -sf http://localhost:3001/api/health > /dev/null 2>&1; then
    echo "✓ Grafana ready"
else
    echo "⊘ Grafana still initializing (safe to continue — it will be ready in ~30s)"
fi

if [ $FAILED -eq 1 ]; then
    echo ""
    echo "Failed services:"
    for svc in prometheus node-exporter; do
        if ! docker ps --filter name=$svc --filter status=running | grep -q $svc; then
            echo "  $svc logs:"
            docker logs --tail 20 $svc 2>&1 | sed 's/^/    /'
        fi
    done
    exit 1
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Monitoring stack deployed:"
echo ""
echo "  Prometheus (metrics DB):   http://10.10.10.2:9091"
echo "  Grafana (dashboards):      http://10.10.10.2:3001 (admin/changeme)"
echo "  DCGM Exporter (GPU):       http://10.10.10.2:9400/metrics"
echo "  Node Exporter (system):    http://10.10.10.2:9100/metrics"
echo "  cAdvisor (containers):     http://10.10.10.2:8989"
echo ""
echo "Next steps:"
echo ""
echo "1. Access Grafana:"
echo "   http://10.10.10.2:3001"
echo "   Login: admin / changeme"
echo ""
echo "2. Import official dashboards:"
echo "   Dashboards → Import:"
echo "   - ID 12239: NVIDIA DCGM Exporter (GPU metrics)"
echo "   - ID 1860:  Node Exporter Full (system metrics)"
echo "   - ID 893:   Docker Container Stats"
echo ""
echo "3. Verify metrics collection:"
echo "   Prometheus → Status → Targets"
echo "   All targets should show 'UP'"
echo ""
echo "4. View metrics queries:"
echo "   Prometheus → Graph or Alerts"
echo ""
echo "5. Test alerts (optional):"
echo "   Prometheus → Alerts"
echo ""
echo "6. CLI monitoring (on host):"
echo "   nvitop                    # Rich GPU monitor"
echo "   watch -n 1 nvidia-smi     # Simple GPU watch"
echo ""
echo "7. Run validation:"
echo "   bash scripts/validate-phase10.sh"
