#!/bin/bash
# Phase 09 validation: Verify storage stack deployment
# Checks: MinIO, Qdrant, PostgreSQL, Langfuse, buckets, collections

set -e

echo "=== Phase 09 Validation ==="
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

# 1. MinIO API responding
if curl -sf http://localhost:9000/minio/health/live > /dev/null 2>&1; then
    check_pass "MinIO API responding on :9000"
else
    check_fail "MinIO API not responding on :9000"
fi

# 2. MinIO console responding
if curl -sf http://localhost:9001 > /dev/null 2>&1; then
    check_pass "MinIO Console responding on :9001"
else
    check_warn "MinIO Console not responding (takes time to initialize)"
fi

# 3. Qdrant REST API responding
if curl -sf http://localhost:6333/collections > /dev/null 2>&1; then
    check_pass "Qdrant REST API responding on :6333"
else
    check_fail "Qdrant REST API not responding on :6333"
fi

# 4. Qdrant health check
if curl -sf http://localhost:6333/health > /dev/null 2>&1; then
    check_pass "Qdrant health check passing"
else
    check_warn "Qdrant health check not available"
fi

# 5. PostgreSQL responding
if pg_isready -h localhost -p 5432 -U admin > /dev/null 2>&1; then
    check_pass "PostgreSQL responding on :5432"
else
    check_fail "PostgreSQL not responding on :5432"
fi

# 6. Langfuse responding
if curl -sf http://localhost:3002 > /dev/null 2>&1; then
    check_pass "Langfuse responding on :3002"
else
    check_warn "Langfuse not responding (might still be initializing)"
fi

# 7. Docker compose file valid
if docker compose -f docker/compose.storage.yml config > /dev/null 2>&1; then
    check_pass "docker/compose.storage.yml is valid"
else
    check_fail "docker/compose.storage.yml syntax error"
fi

# 8. All services defined in compose
for service in minio qdrant postgres langfuse; do
    if docker compose -f docker/compose.storage.yml config | grep -q "^    $service:"; then
        check_pass "Service defined: $service"
    else
        check_fail "Service not defined: $service"
    fi
done

# 9. Storage directories exist
for dir in /data/minio /data/documents/{research,code,security}; do
    if [ -d "$dir" ]; then
        check_pass "Directory exists: $dir"
    else
        check_fail "Directory missing: $dir"
    fi
done

# 10. Config files exist
for file in configs/postgres/init.sql scripts/sync-checkpoints.sh scripts/setup-qdrant.py scripts/ingest-documents.py; do
    if [ -f "$file" ]; then
        check_pass "File exists: $file"
    else
        check_fail "File missing: $file"
    fi
done

echo ""
echo "Automated checks: $PASSED passed, $FAILED failed"
echo ""

# ========== MANUAL CHECKS ==========
echo "Manual verification checklist:"
echo ""
echo "[ ] MinIO buckets created:"
echo "    - mc ls local/ (should show: models, loras, datasets, outputs, backups)"
echo ""
echo "[ ] PostgreSQL databases created:"
echo "    - psql -U admin -h localhost -d postgres -c '\\l' | grep -E 'langfuse|n8n|dify'"
echo ""
echo "[ ] Qdrant collections created:"
echo "    - curl http://localhost:6333/collections | jq"
echo "    - Should list: documents, code, research, security"
echo ""
echo "[ ] Langfuse accessible:"
echo "    - Open http://10.10.10.2:3002 in browser"
echo "    - Should show login/signup page"
echo ""
echo "[ ] Document ingestion working:"
echo "    - python3 scripts/setup-qdrant.py (initialize collections)"
echo "    - python3 scripts/ingest-documents.py (ingest sample docs)"
echo "    - curl http://localhost:6333/collections | jq '.collections[0].points_count'"
echo ""
echo "[ ] Checkpoint sync working:"
echo "    - bash scripts/sync-checkpoints.sh (should complete without errors)"
echo ""
echo "[ ] Open WebUI RAG integration:"
echo "    - Admin → Documents → Vector Database: Qdrant"
echo "    - URL: http://10.10.10.2:6333"
echo "    - Model: nomic-embed-text"
echo "    - Upload a test PDF and query it"
echo ""

# ========== RESULT ==========
echo ""
if [ $FAILED -eq 0 ]; then
    echo "Phase 09 READY ✓"
    exit 0
else
    echo "Phase 09 has $FAILED issue(s) — see above"
    exit 1
fi
