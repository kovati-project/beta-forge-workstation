# KOVATI OS — Component Spec 06
## Resources Panel
*Models · Datasets · Checkpoints · Vectors · Storage*

---

## 1. Purpose

The Resources panel is the operator's file manager and artifact browser for everything stored in the stack: AI models loaded into Ollama/vLLM, training datasets in MinIO, fine-tuned LoRA checkpoints, Qdrant vector collections, and raw storage usage. All actions are non-destructive reads or explicitly confirmed deletes/loads.

---

## 2. Layout

```
┌─────────────────────────────────────────────────────────┐
│ PANEL HEADER: "Resources"                               │
├─────────────────────────────────────────────────────────┤
│ [Models] [Datasets] [Checkpoints] [Vectors] [Storage]  │  ← tab bar
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Tab content area (varies by active tab)                │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

Tab bar: horizontal, border-bottom only on active tab (`--cyan`), 10px text.

URL state: `/#/resources?tab=models` (or datasets, checkpoints, vectors, storage) — tabs are URL-addressable.

---

## 3. Models Tab

Source: `GET /api/models` — merged from Ollama API (`GET :11434/api/tags`) and vLLM loaded models.

### Ollama Models Table

```
┌──────────────────────────────────────────────────────────────┐
│ Name                    │ Size   │ Quant    │ Last Used │ Act │
├──────────────────────────────────────────────────────────────┤
│ qwen2.5-32b-instruct    │ 65 GB  │ Q4_K_M   │ 2h ago    │[▼] │
│ qwen2.5-7b-instruct     │ 4.1 GB │ Q4_K_M   │ 1d ago    │[▼] │
│ nomic-embed-text-v1.5   │ 274 MB │ F32      │ 3d ago    │[▼] │
│ sdxl-1.0-base           │ 6.9 GB │ FP16     │ 5d ago    │[▼] │
└──────────────────────────────────────────────────────────────┘
```

**Actions (in `[▼]` dropdown per row):**
- Set Default (marks this model for default use in Open WebUI)
- Pull Update (runs `ollama pull {name}`)
- Delete (confirms → `DELETE /api/models/{name}`)
- Copy model ID to clipboard

**Name color:** `--cyan` for currently-loaded models, `--text` for others.

**"Pull New Model" button** (top of section): text input + "Pull" button → `POST /api/models/pull {name}`. Shows streaming pull progress.

### vLLM Loaded Models Table

```
Endpoint    │ Model ID              │ TP Config    │ VRAM
:8000/v1    │ qwen2.5-32b-instruct  │ GPU 0+3      │ 42.1 GB
:8001/v1    │ (stopped)             │ GPU 1+2      │ —
```

Read-only. Source: `GET :8000/v1/models` and `GET :8001/v1/models` (proxied through `/api/models/vllm`).

### Custom LoRA Adapters (MinIO)

```
Name                    │ Base Model    │ Date     │ Size   │ Act
qwen25-32b-20250115.bin │ qwen2.5-32b  │ Jan 15   │ 1.8 GB │ [Load] [Delete]
char-lora-v3.safetensors│ sdxl-1.0     │ Jan 10   │ 380 MB │ [Load] [Delete]
```

"Load" action: `POST /api/models/load-lora` → triggers Ollama modelfile creation or vLLM adapter load.

---

## 4. Datasets Tab

Source: `GET /api/storage/buckets/training` (MinIO bucket listing).

### Upload Zone

```
┌──────────────────────────────────────────────────────────┐
│  ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐   │
│  │  Drop .jsonl or .zip here to upload             │   │
│  │  → /data/training/text/formatted/ or /images/   │   │
│   ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─    │
└──────────────────────────────────────────────────────────┘
```

`border: 2px dashed --border2`, `border-radius: 6px`. Drag-over state: `border-color: --cyan`, `background: --cyan-dim`.

Upload uses multipart form to `POST /api/storage/upload` with a `path` parameter (user selects destination: text/formatted or images).

Progress bar shown per file: `VBar` component at 0-100% driven by XHR `upload.onprogress`.

### File Browser

Three sub-sections, collapsible:

**text/raw/** — raw scraped/collected text, not yet formatted  
**text/formatted/** — JSONL files ready for training  
**images/** — image zip archives or folders

Per-section table:

| Name | Size | Modified | Actions |
|------|------|----------|---------|
| alpaca-52k.jsonl | 84 MB | 2d ago | Preview · Download · Delete |
| custom-instruct-3k.jsonl | 12 MB | 12d ago | Preview · Download · Delete |

**Preview action:** Fetches first 5 lines from `/api/storage/preview?path={path}&n=5`. Displays in a modal with JSONL → formatted table (instruction/input/output columns).

**Delete action:** Confirmation dialog → `DELETE /api/storage/file?path={path}`.

---

## 5. Checkpoints Tab

Source: `GET /api/storage/buckets/checkpoints` — grouped by run name.

```
┌──────────────────────────────────────────────────────────────┐
│ ▾ qwen25-32b-20250115         (text LoRA)         Jan 15     │
│   checkpoint-step-800.bin     1.2 GB   [Load into Ollama]   │
│   checkpoint-final.bin        1.8 GB   [Load into Ollama]   │
│   adapter_config.json         2 KB     [View]                │
│                                                              │
│ ▾ char-lora-v3                (image LoRA)        Jan 10     │
│   char-lora-v3.safetensors    380 MB   [Load into ComfyUI]  │
└──────────────────────────────────────────────────────────────┘
```

**Grouping:** By top-level folder name in `/data/checkpoints/`. Sub-folders are step checkpoints.

**Load action:**
- Text LoRA: `POST /api/models/load-lora {path, base_model}` — creates an Ollama modelfile merging base + adapter
- Image LoRA: Opens a dialog asking which ComfyUI workflow to attach to, or copies the safetensors path

**One-click merge (text LoRA):** "Merge & Pull" button — calls backend to run `ollama create {name} -f {modelfile}` and stream output.

---

## 6. Vectors Tab

Source: `GET /api/vectors/collections` (Qdrant REST API proxied).

```
┌──────────────────────────────────────────────────────────────┐
│ Collection              │ Vectors  │ Dim │ Disk    │ Actions │
├──────────────────────────────────────────────────────────────┤
│ codebase-embeddings     │ 142,880  │ 768 │ 1.1 GB  │[Re-embed][Delete]│
│ docs-nomic              │ 28,441   │ 768 │ 218 MB  │[Re-embed][Delete]│
└──────────────────────────────────────────────────────────────┘
```

**Vector counts:** Formatted with `toLocaleString()`.

**Re-embed action:** `POST /api/vectors/re-embed {collection}` — triggers re-ingestion pipeline (runs nomic-embed-text via Ollama, re-populates Qdrant). Shows progress indicator.

**Delete action:** Two-step confirmation (type collection name to confirm) → `DELETE /api/vectors/collections/{name}`.

**Create new collection button:** Form: name, dimension (default 768), distance metric (cosine/dot/euclidean). `POST /api/vectors/collections`.

---

## 7. Storage Tab

Source: `GET /api/storage/summary` (MinIO + PostgreSQL + disk).

### Disk Usage

```
/data/ partition — 14.8 TB / 20 TB
[████████████████████████████░░░░░░░░] 74%
```

`VBar variant="amber"` (amber at >70%, red at >90%).

### MinIO Bucket Breakdown

Horizontal stacked bar, then per-bucket breakdown:

| Bucket | Used | Bar |
|--------|------|-----|
| models/ | 10.1 TB | cyan fill |
| training/ | 2.7 TB | amber fill |
| checkpoints/ | 1.2 TB | purple fill |
| backups/ | 0.8 TB | green fill |

### PostgreSQL Sizes

```
Database      │ Size
langfuse       │ 2.4 GB
n8n            │ 890 MB
dify           │ 1.1 GB
```

Source: `GET /api/storage/postgres-sizes` (query via `pg_database_size`).

### Backup Controls

```
Last backup:    06:00 today · 42 GB · ✓ success
Schedule:       0 6 * * *   (daily at 06:00)
                [edit cron expression]

[Run Backup Now]
```

"Run Backup Now" → `POST /api/backup/run` → shows progress banner → records to backup history.

**Backup history** (last 10):

| Date | Size | Status | Action |
|------|------|--------|--------|
| 2026-06-05 06:00 | 42 GB | ✓ success | [Delete] |
| 2026-06-04 06:00 | 41 GB | ✓ success | [Delete] |

---

## 8. API Dependencies

| Data | Endpoint | Notes |
|------|----------|-------|
| Ollama models | `GET /api/models` | Merged from Ollama + vLLM |
| MinIO datasets | `GET /api/storage/buckets/training` | File listing |
| File preview | `GET /api/storage/preview?path=&n=` | First N lines |
| Checkpoints | `GET /api/storage/buckets/checkpoints` | Grouped |
| Vector collections | `GET /api/vectors/collections` | Qdrant proxy |
| Storage summary | `GET /api/storage/summary` | MinIO + PG + disk |
| Backup history | `GET /api/backup/history` | Last 10 |
| Upload | `POST /api/storage/upload` | Multipart |
| Pull model | `POST /api/models/pull` | Ollama pull |
| Load LoRA | `POST /api/models/load-lora` | Merge adapter |
| Re-embed | `POST /api/vectors/re-embed` | Trigger pipeline |
| Run backup | `POST /api/backup/run` | Returns job ID |
