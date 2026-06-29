#!/bin/bash
# Phase 09 deployment: Storage stack (MinIO, Qdrant, PostgreSQL, Langfuse)
# Deploys S3-compatible artifact storage, vector database, and prompt tracking

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/container-helpers.sh
source "$REPO_ROOT/scripts/lib/container-helpers.sh"

echo "=== Phase 09: Storage, Vector DB & RAG ==="
echo ""

# Verify Phase 06 (Loadout Manager) is running
echo "Checking Phase 06 (Loadout Manager)..."
if ! curl -sf http://localhost:8800/health > /dev/null 2>&1; then
    echo "ERROR: Loadout Manager not running on :8800"
    echo "Deploy Phase 06 first: bash scripts/deploy-phase06.sh"
    exit 1
fi
echo "✓ Loadout Manager running"
echo ""

# Verify docker compose file exists
if [ ! -f "docker/compose.storage.yml" ]; then
    echo "ERROR: docker/compose.storage.yml not found"
    exit 1
fi

# Verify postgres init script exists
if [ ! -f "configs/postgres/init.sql" ]; then
    echo "ERROR: configs/postgres/init.sql not found"
    exit 1
fi

# Create storage directories
echo "Creating storage directories..."
sudo mkdir -p /data/minio
sudo mkdir -p /data/documents/{research,code,security,inbox,processed}
sudo chmod -R 755 /data/documents
echo "✓ Storage directories ready"
echo ""

# Start services
echo "Starting services..."
for _c in minio qdrant postgres langfuse; do
    remove_orphan "$_c" ai-storage
done
docker compose -f docker/compose.storage.yml up -d minio qdrant postgres langfuse
echo "✓ Containers started"
echo ""

# Wait for services to be ready
echo "Waiting for services to initialize..."
for i in {1..30}; do
    if curl -sf http://localhost:9000/minio/health/live > /dev/null 2>&1; then
        break
    fi
    if [ $i -eq 30 ]; then
        echo "WARNING: MinIO still initializing (might take a moment)"
    fi
    sleep 1
done

# Verify services are responding
echo ""
echo "Verifying services..."
FAILED=0

if curl -sf http://localhost:9000/minio/health/live > /dev/null 2>&1; then
    echo "✓ MinIO running (S3 API on :9000)"
else
    echo "✗ MinIO not responding"
    FAILED=1
fi

if curl -sf http://localhost:9001 > /dev/null 2>&1; then
    echo "✓ MinIO Console on :9001"
else
    echo "⊘ MinIO Console (might need time to start)"
fi

if curl -sf http://localhost:6333/collections > /dev/null 2>&1; then
    echo "✓ Qdrant running (REST API on :6333, gRPC on :6334)"
else
    echo "✗ Qdrant not responding"
    FAILED=1
fi

if pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo "✓ PostgreSQL running on :5432"
else
    echo "⊘ PostgreSQL initializing..."
    sleep 5
fi

if curl -sf http://localhost:3002 > /dev/null 2>&1; then
    echo "✓ Langfuse running on :3002"
else
    echo "⊘ Langfuse initializing..."
fi

if [ $FAILED -eq 1 ]; then
    echo ""
    echo "ERROR: Some services failed to start"
    docker compose -f docker/compose.storage.yml logs
    exit 1
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo ""
echo "1. Configure MinIO client (one-time):"
echo "   wget https://dl.min.io/client/mc/release/linux-amd64/mc"
echo "   chmod +x mc && sudo mv mc /usr/local/bin/"
echo "   mc alias set local http://localhost:9000 admin 5c6eb4508af1de3f08b4acdea9d29934"
echo ""
echo "2. Create MinIO buckets:"
echo "   mc mb local/models local/loras local/datasets local/outputs local/backups"
echo "   mc ilm rule add --expiry-days 90 local/outputs"
echo ""
echo "3. Initialize Qdrant collections:"
echo "   python3 scripts/setup-qdrant.py"
echo ""
echo "4. Ingest documents:"
echo "   python3 scripts/ingest-documents.py"
echo ""
echo "5. Configure Open WebUI RAG:"
echo "   Admin → Documents → Vector Database"
echo "   URL: http://10.10.10.2:6333"
echo "   Model: nomic-embed-text"
echo ""
echo "6. Access services:"
echo "   MinIO Console: http://10.10.10.2:9001 (admin / see docker/.env MINIO_ROOT_PASSWORD)"
echo "   Qdrant API: http://10.10.10.2:6333/docs"
echo "   Langfuse: http://10.10.10.2:3002"
echo ""
echo "7. Run validation:"
echo "   bash scripts/validate-phase09.sh"
