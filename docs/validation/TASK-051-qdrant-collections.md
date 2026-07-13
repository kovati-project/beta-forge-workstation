# TASK-051 — Validate Qdrant collections and embedding pipeline

**Issue:** #26
**Result: FAIL** — Qdrant is healthy but holds **zero** collections. None of the four
required collections has ever been created.

## Evidence

`GET http://localhost:6333/collections`:

```json
{"result":{"collections":[]},"status":"ok","time":0.000016101}
```

Qdrant itself is up and answering on both 6333 (HTTP) and 6334 (gRPC).

## Expected

`scripts/setup-qdrant.py:22-27` defines four collections, each 768-dimensional for
`nomic-embed-text`: `documents`, `code`, `research`, `security`. None exist.

The embedding model itself *is* present — `GET /api/tags` on Ollama returns
`nomic-embed-text:latest` — so the dependency is satisfied and only the collection
creation step is missing. `scripts/setup-qdrant.py` has evidently never been run
against this deployment.

## Not covered

The ingestion half of the task (embed a document, confirm it lands and is
searchable) writes to Qdrant and is outside the read-only remit. It is also moot
until the collections exist.

## Verdict

Fails at the first step. Run `scripts/setup-qdrant.py`, then re-run this validation
to exercise ingestion.
