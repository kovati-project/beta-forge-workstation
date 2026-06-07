# Phase 09 — Storage, Vector DB & RAG
[← Agentic Workflows](08-agentic-mcp.md) | [Next: Monitoring →](10-monitoring.md)

---

## Objective
Deploy MinIO (S3-compatible artifact store for model checkpoints and LoRA adapters), Qdrant (vector database for RAG and semantic search), and wire the full RAG ingestion pipeline into Open WebUI and n8n.

---

## Step 1 — Docker Compose: Storage Stack

```bash
cat <<'EOF' > ~/ai-workstation/docker/compose.storage.yml
version: '3.8'

services:

  # ── MinIO: S3-compatible model and artifact store ─────────────────────────
  minio:
    image: minio/minio:latest
    container_name: minio
    restart: unless-stopped
    ports:
      - "9000:9000"      # S3 API
      - "9001:9001"      # Web console
    volumes:
      - /data/minio:/data
    environment:
      - MINIO_ROOT_USER=admin
      - MINIO_ROOT_PASSWORD=changeme-strong-password
      - MINIO_VOLUMES=/data
    command: server /data --console-address ":9001"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 30s
      timeout: 10s
      retries: 3

  # ── Qdrant: vector database ────────────────────────────────────────────────
  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant
    restart: unless-stopped
    ports:
      - "6333:6333"      # REST API
      - "6334:6334"      # gRPC
    volumes:
      - qdrant-data:/qdrant/storage
    environment:
      - QDRANT__SERVICE__HTTP_PORT=6333
      - QDRANT__SERVICE__GRPC_PORT=6334
      - QDRANT__LOG_LEVEL=INFO

  # ── Postgres: shared relational store (Dify, Langfuse, n8n) ───────────────
  postgres:
    image: postgres:16-alpine
    container_name: postgres
    restart: unless-stopped
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./configs/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql
    environment:
      - POSTGRES_USER=admin
      - POSTGRES_PASSWORD=changeme
      # NOTE: POSTGRES_MULTIPLE_DATABASES is NOT a native postgres env var.
      # Multi-database creation is handled entirely by init.sql above — remove
      # this env var if your image does not ship a custom entrypoint that reads it.

volumes:
  qdrant-data:
  postgres-data:

EOF

docker compose -f ~/ai-workstation/docker/compose.storage.yml up -d
```

---

## Step 2 — Postgres Multi-DB Init Script

```sql
-- ~/ai-workstation/configs/postgres/init.sql
CREATE USER langfuse WITH PASSWORD 'langfuse_pass';
CREATE DATABASE langfuse OWNER langfuse;

CREATE USER n8n WITH PASSWORD 'n8n_pass';
CREATE DATABASE n8n OWNER n8n;

CREATE USER dify WITH PASSWORD 'dify_pass';
CREATE DATABASE dify OWNER dify;
```

---

## Step 3 — MinIO Bucket Setup

```bash
# Install MinIO client
wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc && sudo mv mc /usr/local/bin/

# Configure alias
mc alias set local http://localhost:9000 admin changeme-strong-password

# Create buckets
mc mb local/models          # model weights and checkpoints
mc mb local/loras           # LoRA adapters
mc mb local/datasets        # training datasets
mc mb local/outputs         # generation outputs
mc mb local/backups         # system backups

# Set lifecycle: auto-delete outputs older than 90 days
mc ilm rule add --expiry-days 90 local/outputs

# Verify
mc ls local/
```

---

## Step 4 — Checkpoint Sync to MinIO

```bash
# ~/ai-workstation/scripts/sync-checkpoints.sh
#!/bin/bash
# Sync training checkpoints to MinIO after each training run

CHECKPOINT_DIR="/data/checkpoints"
MINIO_BUCKET="local/models"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

echo "Syncing checkpoints to MinIO at $TIMESTAMP..."

# Axolotl checkpoints
mc mirror --overwrite "$CHECKPOINT_DIR/axolotl/" "$MINIO_BUCKET/axolotl/$TIMESTAMP/"

# Kohya LoRAs
mc mirror --overwrite /data/models/comfyui/loras/ "$MINIO_BUCKET/loras/$TIMESTAMP/"

echo "Sync complete."
```

```bash
sudo chmod +x ~/ai-workstation/scripts/sync-checkpoints.sh

# Hook into n8n training completion workflow or run manually
```

---

## Step 5 — Qdrant Collection Setup

```python
# ~/ai-workstation/scripts/setup-qdrant.py
"""Initialize Qdrant collections for RAG workloads."""
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

client = QdrantClient(host="localhost", port=6333)

EMBEDDING_DIM = 768  # nomic-embed-text dimension

collections = [
    {
        "name": "documents",
        "description": "General document knowledge base"
    },
    {
        "name": "code",
        "description": "Code repository and documentation"
    },
    {
        "name": "research",
        "description": "Research papers and technical content"
    },
    {
        "name": "security",
        "description": "Security research, CVEs, threat intel"
    }
]

for col in collections:
    if not client.collection_exists(col["name"]):
        client.create_collection(
            collection_name=col["name"],
            vectors_config=VectorParams(
                size=EMBEDDING_DIM,
                distance=Distance.COSINE
            )
        )
        print(f"Created collection: {col['name']}")
    else:
        print(f"Collection exists: {col['name']}")

print("\nQdrant collections:")
for col in client.get_collections().collections:
    info = client.get_collection(col.name)
    print(f"  {col.name}: {info.points_count} vectors")
```

```bash
pip3 install qdrant-client
python3 ~/ai-workstation/scripts/setup-qdrant.py
```

---

## Step 6 — RAG Ingestion Pipeline

```python
# ~/ai-workstation/scripts/ingest-documents.py
"""
Ingest documents into Qdrant via Ollama embeddings.
Supports: PDF, Markdown, TXT, HTML, code files
"""
import sys
import hashlib
import requests
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import uuid

OLLAMA_URL = "http://localhost:11434"
QDRANT_URL = "http://localhost:6333"
EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64

def get_embedding(text: str) -> list[float]:
    resp = requests.post(f"{OLLAMA_URL}/api/embed",
        json={"model": EMBED_MODEL, "input": text})
    return resp.json()["embeddings"][0]

def chunk_text(text: str) -> list[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), CHUNK_SIZE - CHUNK_OVERLAP):
        chunk = " ".join(words[i:i + CHUNK_SIZE])
        if chunk:
            chunks.append(chunk)
    return chunks

def ingest_file(filepath: Path, collection: str):
    client = QdrantClient(url=QDRANT_URL)
    
    # Read file
    try:
        text = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"  Error reading {filepath}: {e}")
        return 0
    
    chunks = chunk_text(text)
    points = []
    
    for i, chunk in enumerate(chunks):
        doc_hash = hashlib.md5(chunk.encode()).hexdigest()
        embedding = get_embedding(chunk)
        
        points.append(PointStruct(
            id=str(uuid.uuid4()),
            vector=embedding,
            payload={
                "text": chunk,
                "source": str(filepath),
                "filename": filepath.name,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "hash": doc_hash
            }
        ))
    
    client.upsert(collection_name=collection, points=points)
    print(f"  Ingested {filepath.name}: {len(chunks)} chunks")
    return len(chunks)

def ingest_directory(directory: str, collection: str, extensions: list[str]):
    dir_path = Path(directory)
    total = 0
    for ext in extensions:
        for filepath in dir_path.rglob(f"*{ext}"):
            total += ingest_file(filepath, collection)
    print(f"\nTotal: {total} chunks ingested into '{collection}'")

if __name__ == "__main__":
    # Example usage:
    ingest_directory(
        directory="/data/documents/research",
        collection="research",
        extensions=[".pdf", ".md", ".txt", ".html"]
    )
```

---

## Step 7 — Open WebUI RAG Configuration

In Open WebUI Admin settings:

```
Settings → Documents:
  Vector Database: Qdrant
  Qdrant URL: http://10.10.10.2:6333
  Embedding Model: nomic-embed-text (Ollama)
  Chunk Size: 512
  Chunk Overlap: 64
  Top K Results: 5
```

Test RAG:
1. Create a knowledge base in Workspace → Knowledge
2. Upload a PDF
3. In chat, use `#` to reference the knowledge base
4. Query: "What does this document say about X?"

---

## Step 8 — Langfuse: Prompt Versioning and Eval

```bash
cat <<'EOF' >> ~/ai-workstation/docker/compose.storage.yml

  langfuse:
    image: langfuse/langfuse:latest
    container_name: langfuse
    restart: unless-stopped
    ports:
      - "3002:3000"
    environment:
      - DATABASE_URL=postgresql://langfuse:langfuse_pass@postgres:5432/langfuse
      - NEXTAUTH_SECRET=change-this-secret
      - NEXTAUTH_URL=http://10.10.10.2:3002
      - LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES=true
    depends_on:
      - postgres

EOF

docker compose -f ~/ai-workstation/docker/compose.storage.yml up -d langfuse
```

Use Langfuse for:
- Version-controlling system prompts across models
- Tracking token usage and latency per model/workflow
- Running offline evals against labeled test sets
- Comparing LoRA fine-tuned vs base model outputs

---

## Validation Checklist

- [ ] MinIO console accessible at `:9001`, buckets created
- [ ] `mc ls local/` shows all 5 buckets
- [ ] Qdrant API responding at `:6333/collections`
- [ ] Qdrant collections created (documents, code, research, security)
- [ ] Test document ingested and retrievable via Qdrant API
- [ ] Open WebUI RAG query returns relevant chunks from test document
- [ ] Langfuse accessible at `:3002`, connected to Postgres
- [ ] Checkpoint sync script runs without error

---

## Notes
- Qdrant stores vectors on disk — `/qdrant/storage` should be on NVMe for fast similarity search
- nomic-embed-text produces 768-dim vectors; if you switch embedding models, you must recreate collections (dimensions must match)
- MinIO is not a backup destination — it's a versioned artifact store. Back up MinIO data itself to external storage (Phase 14)
- Langfuse tracing adds ~5-10ms latency per LLM call — acceptable for research, consider disabling for latency-sensitive production workflows
