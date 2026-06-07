#!/usr/bin/env python3
"""
Ingest documents into Qdrant via Ollama embeddings.
Supports: PDF, Markdown, TXT, HTML, code files
"""
import sys
import hashlib
import uuid
from pathlib import Path
from typing import List

try:
    import requests
    from qdrant_client import QdrantClient
    from qdrant_client.models import PointStruct
except ImportError:
    print("ERROR: Required packages not installed. Install with:")
    print("  pip install requests qdrant-client")
    sys.exit(1)

# Configuration
OLLAMA_URL = "http://localhost:11434"
QDRANT_URL = "http://localhost:6333"
EMBED_MODEL = "nomic-embed-text"
CHUNK_SIZE = 512
CHUNK_OVERLAP = 64

def get_embedding(text: str) -> List[float]:
    """Get embedding from Ollama."""
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": EMBED_MODEL, "input": text},
            timeout=30
        )
        resp.raise_for_status()
        return resp.json()["embeddings"][0]
    except Exception as e:
        print(f"  ERROR getting embedding: {e}")
        return None

def chunk_text(text: str) -> List[str]:
    """Split text into overlapping chunks."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), CHUNK_SIZE - CHUNK_OVERLAP):
        chunk = " ".join(words[i:i + CHUNK_SIZE])
        if chunk.strip():
            chunks.append(chunk)
    return chunks

def ingest_file(filepath: Path, collection: str) -> int:
    """Ingest a single file into Qdrant."""
    client = QdrantClient(url=QDRANT_URL)
    
    # Read file with error handling
    try:
        text = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"  ERROR reading {filepath}: {e}")
        return 0
    
    if not text.strip():
        print(f"  SKIP empty file: {filepath}")
        return 0
    
    chunks = chunk_text(text)
    points = []
    
    for i, chunk in enumerate(chunks):
        embedding = get_embedding(chunk)
        if embedding is None:
            continue
        
        doc_hash = hashlib.md5(chunk.encode()).hexdigest()
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
    
    if points:
        try:
            client.upsert(collection_name=collection, points=points)
            print(f"  ✓ {filepath.name}: {len(chunks)} chunks")
            return len(chunks)
        except Exception as e:
            print(f"  ERROR upserting to Qdrant: {e}")
            return 0
    
    return 0

def ingest_directory(directory: str, collection: str, extensions: List[str]) -> int:
    """Ingest all matching files from directory."""
    dir_path = Path(directory)
    
    if not dir_path.exists():
        print(f"ERROR: Directory not found: {directory}")
        return 0
    
    total = 0
    print(f"\nIngesting from: {directory}")
    print(f"Collection: {collection}")
    print(f"Extensions: {extensions}\n")
    
    for ext in extensions:
        for filepath in sorted(dir_path.rglob(f"*{ext}")):
            chunk_count = ingest_file(filepath, collection)
            total += chunk_count
    
    if total > 0:
        print(f"\n✓ Total: {total} chunks ingested into '{collection}'")
    else:
        print(f"\n⊘ No documents ingested")
    
    return total

def main():
    """Main entry point."""
    print("=== Document Ingestion to Qdrant ===\n")
    
    # Verify Ollama is available
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        resp.raise_for_status()
    except Exception as e:
        print(f"ERROR: Ollama not available at {OLLAMA_URL}")
        print(f"  {e}")
        print("Start Ollama with: docker compose -f docker/compose.inference.yml up -d ollama")
        sys.exit(1)
    
    # Verify Qdrant is available
    try:
        resp = requests.get(f"{QDRANT_URL}/collections", timeout=5)
        resp.raise_for_status()
    except Exception as e:
        print(f"ERROR: Qdrant not available at {QDRANT_URL}")
        print(f"  {e}")
        print("Start Qdrant with: docker compose -f docker/compose.storage.yml up -d qdrant")
        sys.exit(1)
    
    print("✓ Ollama available")
    print("✓ Qdrant available\n")
    
    # Example ingestion patterns (customize as needed)
    ingest_patterns = [
        ("/data/documents/research", "research", [".pdf", ".md", ".txt", ".html"]),
        ("/data/documents/code", "code", [".py", ".js", ".ts", ".go", ".md"]),
        ("/data/documents/security", "security", [".md", ".txt"]),
    ]
    
    total_ingested = 0
    for directory, collection, extensions in ingest_patterns:
        count = ingest_directory(directory, collection, extensions)
        total_ingested += count
    
    print(f"\n=== Summary ===")
    print(f"Total documents ingested: {total_ingested} chunks")
    print("\nNext steps:")
    print("  1. Open WebUI: Admin → Documents → Qdrant configuration")
    print("  2. Create knowledge base and upload PDFs")
    print("  3. Query: Use # to reference knowledge base in chat")

if __name__ == "__main__":
    main()
