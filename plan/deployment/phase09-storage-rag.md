# Phase 09 — Storage, Vector DB & RAG

**Services:** MinIO S3 API (`:9000`), MinIO Console (`:9001`), Qdrant (`:6333`/`:6334`), PostgreSQL (`:5432`), Langfuse (`:3002`)  
**Compose file:** `docker/compose.storage.yml`  
**Scripts:** `setup-storage-phase09.sh`, `deploy-phase09.sh`, `validate-phase09.sh`, `setup-qdrant.py`, `ingest-documents.py`, `sync-checkpoints.sh`

---

## Prerequisites

- [ ] Phase 03 deployed — Ollama running with `nomic-embed-text` pulled (required for embedding)
- [ ] Phase 06 deployed — Loadout Manager running at `:8800`
- [ ] Files on workstation: `scp -r docker scripts configs kasemo@10.10.10.2:~/ai-workstation/`
- [ ] ≥20GB free disk space for MinIO data and Qdrant vectors

---

## Step 1 — Update Secrets

Three placeholder secrets ship in the compose file. Update them before starting services.

```bash
# Generate secrets
openssl rand -hex 32   # for MinIO password
openssl rand -hex 32   # for Postgres password
openssl rand -hex 32   # for Langfuse NEXTAUTH_SECRET

ssh kasemo@10.10.10.2 "nano ~/ai-workstation/docker/compose.storage.yml"
```

Replace:
- `MINIO_ROOT_PASSWORD=changeme-strong-password`
- `POSTGRES_PASSWORD=changeme`
- `NEXTAUTH_SECRET=change-this-secret-key-randomly`

**Record these somewhere safe.** The Postgres password is also embedded in `DATABASE_URL` for Langfuse — update both if you change it:
```
DATABASE_URL=postgresql://langfuse:langfuse_pass@postgres:5432/langfuse
```

---

## Step 2 — Deploy

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/deploy-phase09.sh"
```

The script:
1. Creates `/data/minio/` and `/data/documents/` directories
2. Starts MinIO, Qdrant, and Postgres
3. Installs the MinIO client (`mc`) and creates the 5 buckets
4. Runs `setup-qdrant.py` to initialize the 4 Qdrant collections
5. Starts Langfuse

---

## Step 3 — Verify MinIO

```bash
# List buckets
ssh kasemo@10.10.10.2 "mc ls local/"
```

Expected output:
```
[...] models/
[...] loras/
[...] datasets/
[...] outputs/
[...] backups/
```

Open the console at `http://10.10.10.2:9001` to confirm.

---

## Step 4 — Verify Qdrant Collections

```bash
ssh kasemo@10.10.10.2 "curl -s http://localhost:6333/collections | python3 -m json.tool"
```

Expected: four collections — `documents`, `code`, `research`, `security`. All at 0 vectors (empty until documents are ingested).

---

## Step 5 — Verify Postgres Databases

```bash
ssh kasemo@10.10.10.2 "docker exec postgres psql -U admin -c '\l'"
```

Expected: `langfuse`, `n8n`, and `dify` databases listed alongside the default `postgres` database.

---

## Step 6 — Set Up Langfuse

Open `http://10.10.10.2:3002` in a browser and create an admin account.

Once logged in:
1. **Settings → API Keys → Create API Key**
2. Copy the public and secret keys — you'll need them to instrument n8n workflows

---

## Step 7 — Ingest Documents (Optional)

Place documents in `/data/documents/{research,code,security}` on the workstation, then run:

```bash
ssh kasemo@10.10.10.2 "pip3 install -q qdrant-client requests"
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && python3 scripts/ingest-documents.py"
```

The script chunks and embeds every `.pdf`, `.md`, `.txt`, and `.html` file it finds into Qdrant via `nomic-embed-text`. Re-running is safe (upsert, not insert).

Verify a collection has vectors:
```bash
ssh kasemo@10.10.10.2 "curl -s http://localhost:6333/collections/documents \
  | python3 -m json.tool | grep points_count"
```

---

## Step 8 — Configure Open WebUI RAG

In Open WebUI: **Admin Panel → Settings → Documents**

| Setting | Value |
|---------|-------|
| Vector Database | Qdrant |
| Qdrant Server URL | `http://10.10.10.2:6333` |
| Chunk Size | 512 |
| Chunk Overlap | 64 |
| Embedding Model | `nomic-embed-text` (Ollama) |
| Top K Results | 5 |

Test: create a Knowledge Base in Workspace → Knowledge, upload a PDF, then query it in chat using `#knowledge-base-name`.

---

## Step 9 — Validate

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase09.sh"
```

Expected: 10 automated checks pass, 6 manual checks listed.

---

## Syncing Checkpoints to MinIO

Run after any training job completes (Phase 07):

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/sync-checkpoints.sh"
```

Syncs from local `/data/checkpoints/` and `/data/models/comfyui/loras/` to timestamped MinIO paths. To automate, add a webhook call to this script at the end of your n8n training pipeline workflow.

---

## Quick Reference

```bash
# MinIO — list all buckets and sizes
ssh kasemo@10.10.10.2 "mc du local/"

# MinIO — upload a file manually
ssh kasemo@10.10.10.2 "mc cp /data/checkpoints/axolotl/latest.safetensors local/models/"

# Qdrant — collection stats
ssh kasemo@10.10.10.2 "curl -s http://localhost:6333/collections | python3 -m json.tool"

# Qdrant — delete and recreate a collection (if switching embedding model)
ssh kasemo@10.10.10.2 "curl -sX DELETE http://localhost:6333/collections/documents"
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && python3 scripts/setup-qdrant.py"

# Postgres — connect as admin
ssh kasemo@10.10.10.2 "docker exec -it postgres psql -U admin"

# Langfuse logs
ssh kasemo@10.10.10.2 "docker logs -f langfuse"

# Restart all storage services
ssh kasemo@10.10.10.2 "docker compose -f ~/ai-workstation/docker/compose.storage.yml \
  up -d"
```

---

## Qdrant + Embedding Model Note

The 4 collections are initialised with **768-dimensional vectors** to match `nomic-embed-text`. If you ever switch embedding models, the dimensions must match or all queries will error. Procedure:

```bash
# Delete existing collections
curl -X DELETE http://localhost:6333/collections/documents
# (repeat for code, research, security)

# Edit setup-qdrant.py: change EMBEDDING_DIM to match new model
# Re-run to recreate collections
python3 scripts/setup-qdrant.py

# Re-ingest all documents
python3 scripts/ingest-documents.py
```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| MinIO bucket creation fails | `mc alias set` may not be configured — re-run `deploy-phase09.sh` |
| Qdrant ingestion hangs | Ollama not running or `nomic-embed-text` not pulled: `docker exec ollama ollama list` |
| Postgres `init.sql` not run | Volume already exists with old state — `docker volume rm postgres-data` then restart (destroys all data) |
| Langfuse login fails | Postgres not yet initialised — `docker logs postgres` to confirm init.sql ran |
| Open WebUI RAG returns no results | Collections empty — run `ingest-documents.py` and confirm `points_count > 0` |
| Qdrant dimension mismatch error | Embedding model changed — delete and recreate collections (see note above) |
| MinIO console inaccessible | Container still starting — `docker logs minio`; first start can take 10–15s |
