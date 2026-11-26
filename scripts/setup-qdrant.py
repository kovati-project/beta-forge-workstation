#!/usr/bin/env python3
"""
Create the Qdrant collections used for RAG (documents, code, research, security).

Idempotent: existing collections are left alone (their vector size is checked),
so deploy-phase09.sh runs it on every deploy. Uses only the standard library
and Qdrant's REST API, so it runs on the host without `pip install`.

Usage: python3 scripts/setup-qdrant.py [--check] [--url URL]
  --check   report missing collections and exit 1 if any; change nothing
  --url     Qdrant REST URL (default $QDRANT_URL or http://localhost:6333)

Exit: 0 ok, 1 missing (--check), a failed create or a vector-size mismatch,
      2 usage, 3 Qdrant unreachable
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

EMBEDDING_DIM = 768  # nomic-embed-text
DISTANCE = "Cosine"

# (name, description)
COLLECTIONS = [
    ("documents", "General document knowledge base"),
    ("code", "Code repository, documentation, and snippets"),
    ("research", "Research papers, technical content, whitepapers"),
    ("security", "Security research, CVEs, threat intelligence"),
]


def request(method, url, body=None, timeout=10):
    """(status, parsed JSON or None). Raises URLError when unreachable."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except ValueError:
            return e.code, None


def wait_for_qdrant(base, timeout):
    deadline = time.time() + timeout
    while True:
        try:
            status, _ = request("GET", f"{base}/collections", timeout=5)
            if status == 200:
                return True
        except (urllib.error.URLError, OSError):
            pass
        if time.time() >= deadline:
            return False
        time.sleep(2)


def vector_size(info):
    """Vector size from a GET /collections/{name} result (single unnamed vector)."""
    result = (info or {}).get("result") or {}
    vectors = ((result.get("config") or {}).get("params") or {}).get("vectors")
    if isinstance(vectors, dict) and "size" in vectors:
        return vectors["size"]
    return None  # named vectors or unknown layout


def main(argv=None):
    ap = argparse.ArgumentParser(description="Create the Qdrant RAG collections.")
    ap.add_argument("--check", action="store_true", help="report only, change nothing")
    ap.add_argument("--url", default=os.environ.get("QDRANT_URL", "http://localhost:6333"))
    ap.add_argument("--wait", type=int, default=30, help="seconds to wait for Qdrant")
    args = ap.parse_args(argv)
    base = args.url.rstrip("/")

    print(f"Qdrant collections ({base}):")
    if not wait_for_qdrant(base, args.wait):
        print(f"ERROR: Qdrant not reachable at {base} after {args.wait}s", file=sys.stderr)
        print("Start it with: docker compose -f docker/compose.storage.yml up -d qdrant", file=sys.stderr)
        return 3

    rc = 0
    for name, description in COLLECTIONS:
        status, info = request("GET", f"{base}/collections/{name}")
        if status == 200:
            size = vector_size(info)
            if size not in (None, EMBEDDING_DIM):
                print(f"  MISMATCH {name}: vector size {size}, expected {EMBEDDING_DIM}")
                rc = 1
            else:
                points = ((info or {}).get("result") or {}).get("points_count")
                print(f"  ok       {name} ({points} points)")
        elif status != 404:
            print(f"  FAILED   {name}: GET returned {status} {info}")
            rc = 1
        elif args.check:
            print(f"  MISSING  {name}")
            rc = 1
        else:
            status, body = request("PUT", f"{base}/collections/{name}",
                                   {"vectors": {"size": EMBEDDING_DIM, "distance": DISTANCE}})
            if status == 200:
                print(f"  created  {name} - {description}")
            else:
                print(f"  FAILED   {name}: PUT returned {status} {body}")
                rc = 1

    if rc == 0:
        print("Qdrant collections: OK")
    elif args.check:
        print("Qdrant collections: missing or mismatched (run without --check to create)")
    return rc


if __name__ == "__main__":
    sys.exit(main())
