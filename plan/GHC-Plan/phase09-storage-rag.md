# GHC Task: Phase 09 — Storage, Vector DB & RAG
**Brief ID:** P09-001  
**Source doc:** `/plan/steps/09-storage-rag.md`  
**Write feedback to:** `/plan/ghc-feedback/phase09-storage-rag.md`

---

## Context

Phases 01–08 are complete. The workstation has:
- Ubuntu 26.04 LTS, driver 595.71.05, CUDA 13.3
- Ollama at `:11434` with `nomic-embed-text` pulled (768-dim embeddings)
- Open WebUI at `:3000` (RAG settings need updating after this phase)
- n8n at `:5678` (checkpoint sync can hook into n8n workflows)
- Training checkpoints at `/data/checkpoints/{kohya,axolotl,unsloth}`
- LoRA outputs at `/data/models/comfyui/loras/`

This phase deploys MinIO (S3-compatible artifact store), Qdrant (vector database), and a shared Postgres instance (used by Langfuse, Dify, n8n). It also creates scripts to initialize Qdrant collections, ingest documents, and sync training checkpoints to MinIO. Langfuse (prompt observability) is included behind a `langfuse` profile.

---

## Scope

Create:
1. **`docker/compose.storage.yml`** — MinIO, Qdrant, Postgres, and Langfuse (profile: `langfuse`)
2. **`configs/postgres/init.sql`** — multi-database init script (langfuse, n8n, dify databases)
3. **`scripts/setup-storage-phase09.sh`** — create `/data/minio` host directory
4. **`scripts/deploy-phase09.sh`** — start storage stack, run MinIO bucket setup, run Qdrant init
5. **`scripts/validate-phase09.sh`** — endpoint and data checks; exits non-zero on failure
6. **`scripts/setup-qdrant.py`** — initialize Qdrant collections for RAG
7. **`scripts/ingest-documents.py`** — document ingestion pipeline (PDF, Markdown, TXT, HTML)
8. **`scripts/sync-checkpoints.sh`** — sync training checkpoints and LoRAs to MinIO

**Not in scope:** Open WebUI RAG reconfiguration to use Qdrant (manual — done in browser), Langfuse project and API key setup (done in browser), n8n MinIO integration (Phase 08 n8n workflow).

---

## Step 1 — `configs/postgres/init.sql`

```sql
CREATE USER langfuse WITH PASSWORD 'langfuse_pass';
CREATE DATABASE langfuse OWNER langfuse;

CREATE USER n8n WITH PASSWORD 'n8n_pass';
CREATE DATABASE n8n OWNER n8n;

CREATE USER dify WITH PASSWORD 'dify_pass';
CREATE DATABASE dify OWNER dify;
```

This runs automatically on Postgres first start via the `docker-entrypoint-initdb.d/` mount. It only runs once; recreating the container without deleting the volume will not re-run it.

---

## Step 2 — `docker/compose.storage.yml`

**minio service:**
- Image: `minio/minio:latest`
- Ports: `9000:9000` (S3 API), `9001:9001` (web console)
- `restart: unless-stopped`
- Volume: `/data/minio:/data`
- Environment:
  - `MINIO_ROOT_USER=admin`
  - `MINIO_ROOT_PASSWORD=changeme-strong-password` ← placeholder; add comment to change before use
  - `MINIO_VOLUMES=/data`
- Command: `server /data --console-address ":9001"`
- Healthcheck: `curl -f http://localhost:9000/minio/health/live` every 30s

**qdrant service:**
- Image: `qdrant/qdrant:latest`
- Ports: `6333:6333` (REST), `6334:6334` (gRPC)
- `restart: unless-stopped`
- Volume: `qdrant-data:/qdrant/storage`
- Environment: `QDRANT__SERVICE__HTTP_PORT=6333`, `QDRANT__SERVICE__GRPC_PORT=6334`, `QDRANT__LOG_LEVEL=INFO`

**postgres service:**
- Image: `postgres:16-alpine`
- Port: `5432:5432`
- `restart: unless-stopped`
- Volumes: `postgres-data:/var/lib/postgresql/data`, `./configs/postgres/init.sql:/docker-entrypoint-initdb.d/init.sql`
- Environment:
  - `POSTGRES_USER=admin`
  - `POSTGRES_PASSWORD=changeme` ← placeholder; add comment to change before use
  - **Do NOT add `POSTGRES_MULTIPLE_DATABASES`** — this is not a native Postgres env var; multi-db creation is handled entirely by `init.sql`

**langfuse service** (behind `langfuse` profile):
- Image: `langfuse/langfuse:latest`
- Port: `3002:3000`
- `restart: unless-stopped`
- Profile: `langfuse`
- Environment:
  - `DATABASE_URL=postgresql://langfuse:langfuse_pass@postgres:5432/langfuse`
  - `NEXTAUTH_SECRET=change-this-to-a-random-secret` ← placeholder; add comment
  - `NEXTAUTH_URL=http://10.10.10.2:3002`
  - `LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES=true`
- `depends_on: [postgres]`

**Volumes:** `qdrant-data`, `postgres-data`  
**Do not include `version: '3.8'`** — deprecated.

The compose file path for `init.sql` is `./configs/postgres/init.sql` — relative to the compose file's location in `docker/`. The actual file is at `configs/postgres/init.sql` in the repo root. Since Compose resolves relative paths from the file's directory, use `../configs/postgres/init.sql`.

---

## Step 3 — `scripts/setup-storage-phase09.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

sudo mkdir -p /data/minio
sudo mkdir -p /data/documents/{research,code,general,security}
sudo chown -R "$USER:$USER" /data/minio /data/documents

echo "Phase 09 storage layout created."
echo "  /data/minio             → MinIO object store"
echo "  /data/documents/        → Document ingestion source directories"
```

---

## Step 4 — `scripts/deploy-phase09.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Phase 09: Storage, Vector DB & RAG ==="

# Storage layout
bash "$REPO_ROOT/scripts/setup-storage-phase09.sh"

# Start MinIO, Qdrant, Postgres
docker compose -f "$REPO_ROOT/docker/compose.storage.yml" up -d minio qdrant postgres

# Wait for MinIO
echo "Waiting for MinIO..."
for i in $(seq 1 15); do
    if curl -sf http://localhost:9000/minio/health/live >/dev/null 2>&1; then
        echo "MinIO ready"
        break
    fi
    sleep 3
done

# Install MinIO client and create buckets
if ! command -v mc &>/dev/null; then
    wget -q https://dl.min.io/client/mc/release/linux-amd64/mc -O /tmp/mc
    chmod +x /tmp/mc
    sudo mv /tmp/mc /usr/local/bin/mc
fi
mc alias set local http://localhost:9000 admin changeme-strong-password
mc mb --ignore-existing local/models
mc mb --ignore-existing local/loras
mc mb --ignore-existing local/datasets
mc mb --ignore-existing local/outputs
mc mb --ignore-existing local/backups
mc ilm rule add --expiry-days 90 local/outputs 2>/dev/null || true

# Wait for Qdrant
echo "Waiting for Qdrant..."
for i in $(seq 1 10); do
    if curl -sf http://localhost:6333/collections >/dev/null 2>&1; then
        echo "Qdrant ready"
        break
    fi
    sleep 2
done

# Initialize Qdrant collections
pip3 install -q qdrant-client
python3 "$REPO_ROOT/scripts/setup-qdrant.py"

echo ""
echo "Services running:"
echo "  MinIO console  → http://10.10.10.2:9001  (admin / changeme-strong-password)"
echo "  MinIO S3 API   → http://10.10.10.2:9000"
echo "  Qdrant         → http://10.10.10.2:6333"
echo "  Postgres       → 10.10.10.2:5432"
echo ""
echo "Update passwords in docker/compose.storage.yml before production use."
echo ""
echo "Optional Langfuse:"
echo "  docker compose -f docker/compose.storage.yml --profile langfuse up -d"
```

---

## Step 5 — `scripts/validate-phase09.sh`

Automated checks:

| Check | Command |
|-------|---------|
| MinIO running | `docker ps --filter name=minio --filter status=running \| grep -q minio` |
| MinIO health | `curl -sf http://localhost:9000/minio/health/live` |
| Qdrant running | `docker ps --filter name=qdrant --filter status=running \| grep -q qdrant` |
| Qdrant API | `curl -sf http://localhost:6333/collections` |
| Postgres running | `docker ps --filter name=postgres --filter status=running \| grep -q postgres` |
| Postgres port | `nc -z localhost 5432` |
| MinIO buckets created | `mc ls local/ 2>/dev/null \| grep -q models` |
| Qdrant has collections | `curl -sf http://localhost:6333/collections \| grep -q 'documents'` |
| MinIO password not default | `docker inspect minio \| grep MINIO_ROOT_PASSWORD \| grep -v 'changeme-strong-password'` |
| Postgres password not default | `docker inspect postgres \| grep POSTGRES_PASSWORD \| grep -v "'changeme'"` |
| setup-qdrant.py exists | `test -f scripts/setup-qdrant.py` |
| ingest-documents.py exists | `test -f scripts/ingest-documents.py` |
| sync-checkpoints.sh exists | `test -f scripts/sync-checkpoints.sh` |
| init.sql exists | `test -f configs/postgres/init.sql` |
| /data/minio exists | `test -d /data/minio` |

Manual checks (warn only):
- Open MinIO console at `http://10.10.10.2:9001`, confirm all 5 buckets visible
- Run `curl http://localhost:6333/collections` and confirm 4 collections (documents, code, research, security)
- Test document ingestion: `python3 scripts/ingest-documents.py` with a test file
- Update Open WebUI RAG: Admin Panel → Settings → Documents → set Qdrant URL to `http://10.10.10.2:6333`

Use the same `check()` / `warn()` pattern as prior validate scripts. Exit with `$FAIL` count.

---

## Step 6 — `scripts/setup-qdrant.py`

Use exact implementation from source doc. Key details:
- `EMBEDDING_DIM = 768` — must match `nomic-embed-text` output dimension exactly. If dimension mismatches, Open WebUI RAG will silently fail or error on insert.
- Four collections: `documents`, `code`, `research`, `security`
- Skip creation if collection already exists (`client.collection_exists()`)
- Print collection list with point counts after setup

---

## Step 7 — `scripts/ingest-documents.py`

Use exact implementation from source doc. Key details:
- `EMBED_MODEL = "nomic-embed-text"` — uses Ollama `/api/embed` endpoint, not `/api/embeddings`
- `CHUNK_SIZE = 512`, `CHUNK_OVERLAP = 64`
- Supported extensions: `.pdf`, `.md`, `.txt`, `.html`
- Payload includes: `text`, `source`, `filename`, `chunk_index`, `total_chunks`, `hash`
- Upsert (not insert) — safe to re-run on same files
- The `if __name__ == "__main__":` block ingests from `/data/documents/research` into the `research` collection as an example

---

## Step 8 — `scripts/sync-checkpoints.sh`

Use exact implementation from source doc. Key details:
- Source: `/data/checkpoints/axolotl/` and `/data/models/comfyui/loras/`
- Destination: `local/models/axolotl/$TIMESTAMP/` and `local/models/loras/$TIMESTAMP/`
- Uses `mc mirror --overwrite`
- Requires `mc` alias `local` to be configured (done by deploy script)
- Add a note at the top: "Run after training completes, or hook into n8n training completion workflow"

---

## Constraints

1. **`POSTGRES_MULTIPLE_DATABASES` must not be included** in the postgres service env. The source doc includes a comment flagging it as non-native — it was already caught. Do not include it in the compose file.

2. **`init.sql` volume mount path** — the compose file is in `docker/`, so `./configs/postgres/init.sql` resolves to `docker/configs/postgres/init.sql`, which is wrong. Use `../configs/postgres/init.sql` to resolve from the repo root.

3. **MinIO bucket creation is idempotent** — use `mc mb --ignore-existing` so the deploy script is safe to re-run.

4. **Qdrant collection creation is idempotent** — `setup-qdrant.py` must check `client.collection_exists()` before creating. Re-running must not fail or corrupt existing data.

5. **`nomic-embed-text` dimension is 768** — this is fixed by the model. If you change the embedding model later, you must delete and recreate the Qdrant collections. Document this clearly in a comment in `setup-qdrant.py`.

6. **Langfuse requires Postgres to be running** — Langfuse is behind the `langfuse` profile. Its `depends_on: [postgres]` ensures ordering, but the user must start Postgres first (the deploy script does this). Document that `--profile langfuse up -d` requires Postgres to already be running.

7. **MinIO password and Postgres password are placeholders** — the validate script checks for default passwords and fails if unchanged. Include clear comments in compose.storage.yml.

8. **Qdrant data volume** — use a Docker named volume (`qdrant-data`), not a bind mount. Named volumes survive container recreation; bind mounts require manual permission management.

---

## Feedback Template

Write to `/plan/ghc-feedback/phase09-storage-rag.md`:

```markdown
# GHC Feedback: Phase 09 — Storage, Vector DB & RAG
**Brief:** P09-001 | **Status:** Complete / Partial / Blocked

## Files Created
- [ ] docker/compose.storage.yml
- [ ] configs/postgres/init.sql
- [ ] scripts/setup-storage-phase09.sh
- [ ] scripts/deploy-phase09.sh
- [ ] scripts/validate-phase09.sh
- [ ] scripts/setup-qdrant.py
- [ ] scripts/ingest-documents.py
- [ ] scripts/sync-checkpoints.sh

## Deviations from Brief
| Item | Plan | Actual | Reason |

## Validation Results
[paste validate-phase09.sh output]

## Notes
```
