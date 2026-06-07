#!/usr/bin/env python3
"""
Initialize Qdrant collections for RAG workloads.
Creates semantic search collections for documents, code, research, and security.
"""
import sys
import time

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams
except ImportError:
    print("ERROR: qdrant-client not installed. Install with:")
    print("  pip install qdrant-client")
    sys.exit(1)

QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
EMBEDDING_DIM = 768  # nomic-embed-text vector dimension

# Collections to create: (name, description)
COLLECTIONS = [
    ("documents", "General document knowledge base"),
    ("code", "Code repository, documentation, and snippets"),
    ("research", "Research papers, technical content, whitepapers"),
    ("security", "Security research, CVEs, threat intelligence"),
]

def wait_for_qdrant(host, port, timeout=30):
    """Wait for Qdrant to become available."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            client = QdrantClient(host=host, port=port)
            client.get_collections()
            return client
        except Exception as e:
            print(f"  Waiting for Qdrant... ({int(time.time() - start)}s)")
            time.sleep(2)
    raise TimeoutError(f"Qdrant not available after {timeout}s")

def setup_collections():
    """Create all collections."""
    print("=== Qdrant Collection Setup ===")
    print(f"Connecting to Qdrant at {QDRANT_HOST}:{QDRANT_PORT}...")
    
    try:
        client = wait_for_qdrant(QDRANT_HOST, QDRANT_PORT)
    except TimeoutError as e:
        print(f"ERROR: {e}")
        print("Ensure Qdrant is running: docker compose -f docker/compose.storage.yml up -d qdrant")
        sys.exit(1)
    
    print("✓ Connected to Qdrant\n")
    
    created_count = 0
    existing_count = 0
    
    for collection_name, description in COLLECTIONS:
        try:
            if client.collection_exists(collection_name):
                info = client.get_collection(collection_name)
                print(f"✓ Collection exists: {collection_name}")
                print(f"  Description: {description}")
                print(f"  Vectors: {info.points_count}")
                existing_count += 1
            else:
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=EMBEDDING_DIM,
                        distance=Distance.COSINE
                    )
                )
                print(f"✓ Created collection: {collection_name}")
                print(f"  Description: {description}")
                print(f"  Vector dimension: {EMBEDDING_DIM} (nomic-embed-text)")
                created_count += 1
        except Exception as e:
            print(f"✗ ERROR creating/checking {collection_name}: {e}")
            sys.exit(1)
    
    print("\n=== Summary ===")
    print(f"Created: {created_count} new collections")
    print(f"Existing: {existing_count} collections")
    print(f"Total: {created_count + existing_count} collections")
    
    print("\nQdrant collections ready for RAG ingestion:")
    for col in client.get_collections().collections:
        info = client.get_collection(col.name)
        print(f"  • {col.name}: {info.points_count} vectors")
    
    print("\nNext steps:")
    print("  1. Ingest documents: python3 scripts/ingest-documents.py")
    print("  2. Configure Open WebUI: Admin → Documents → Qdrant")
    print("  3. Test RAG: Create knowledge base and upload PDFs")

if __name__ == "__main__":
    setup_collections()
