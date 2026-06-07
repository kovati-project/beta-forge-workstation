# GHC Task: Phase 07 — Training & Fine-Tuning Pipeline
**Brief ID:** P07-001  
**Source doc:** `/plan/steps/07-training-pipeline.md`  
**Write feedback to:** `/plan/ghc-feedback/phase07-training-pipeline.md`

---

## Context

Phases 01–06 are complete. The workstation has:
- Ubuntu 26.04 LTS, driver 595.71.05, CUDA 13.3
- Loadout Manager running at `:8800` — **use it to switch profiles before training**
- NVLink pair A: GPU0↔GPU3 | pair B: GPU1↔GPU2
- NCCL config at `configs/nccl/nccl.conf` (already deployed in Phase 03)
- `/data/models/comfyui/` layout exists from Phase 04 (checkpoints, loras, vae, etc.)

**GPU assignment for training:**

| Workload | GPUs | Strategy |
|----------|------|----------|
| Image LoRA (Kohya_ss) | [1, 2] | DDP, NVLink pair B |
| Text LoRA (Unsloth) | [0, 3] | NVLink pair A |
| Full fine-tune (Axolotl) | [0,1,2,3] | FSDP, all GPUs |

Training and inference cannot share GPUs. The loadout manager `training-lora-image` and `training-lora-text` profiles enforce this — but scripts must call the loadout manager before starting training containers.

---

## Scope

Create:
1. **`docker/compose.training.yml`** — Kohya_ss, Axolotl, Unsloth, Label Studio, JupyterLab
2. **`configs/axolotl/qlora_4gpu.yml`** — Axolotl FSDP config template for Qwen2.5-32B
3. **`scripts/setup-storage-phase07.sh`** — create dataset and checkpoint directories
4. **`scripts/deploy-phase07.sh`** — start Label Studio and JupyterLab (always-on services); Kohya/Axolotl/Unsloth are started per-run, not auto-started
5. **`scripts/validate-phase07.sh`** — smoke tests for always-on services and import checks for training containers
6. **`scripts/convert_labelstudio_to_alpaca.py`** — Label Studio export → Alpaca JSONL converter

**Not in scope:** MinIO integration for checkpoint storage (Phase 09), Langfuse training metrics (Phase 10), actual training run execution.

---

## Step 1 — `scripts/setup-storage-phase07.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

sudo mkdir -p /data/datasets/{images,text,audio}
sudo mkdir -p /data/datasets/images/{raw,tagged,rejected}
sudo mkdir -p /data/datasets/text/{raw,formatted,validation}
sudo mkdir -p /data/checkpoints/{kohya,axolotl,unsloth}
sudo mkdir -p /data/configs/kohya
sudo chown -R "$USER:$USER" /data/datasets /data/checkpoints /data/configs

echo "Phase 07 storage layout created."
```

---

## Step 2 — `docker/compose.training.yml`

Five services:

**kohya** — image LoRA training:
- Image: `ghcr.io/bmaltais/kohya-ss:latest`
- Port: `7860:7860`
- GPUs: `['1', '2']` (NVLink pair B)
- Volumes: `/data/datasets/images:/dataset`, `/data/models/comfyui/loras:/output/loras`, `/data/checkpoints/kohya:/output/checkpoints`, `/data/models/comfyui/checkpoints:/models/checkpoints`
- Command: `--listen 0.0.0.0 --server_port 7860 --headless`
- No profile — started manually, not auto-started by deploy script

**axolotl** — text fine-tuning:
- Image: `winglian/axolotl:main-latest`
- No ports (run as one-shot jobs via `docker compose run`)
- `restart: no`
- GPUs: `['0', '1', '2', '3']`
- Volumes: `/data/datasets/text:/workspace/datasets`, `/data/checkpoints/axolotl:/workspace/outputs`, `/data/models/vllm:/workspace/models`, `./configs/axolotl:/workspace/configs`
- Env: `NCCL_P2P_LEVEL=NVL`, `NCCL_SHM_DISABLE=0`, `WANDB_DISABLED=true`
- `ipc: host` — required for NCCL shared memory across GPUs (same constraint as vLLM)
- Profile: `training`

**unsloth** — fast LoRA (1–2 GPU):
- Image: `unslothai/unsloth:latest`
- Port: `8501:8501`
- `restart: no`
- GPUs: `['0', '3']` (NVLink pair A)
- Volumes: `/data/datasets/text:/workspace/datasets`, `/data/checkpoints/unsloth:/workspace/outputs`, `/data/models/vllm:/workspace/models`
- Env: `NCCL_P2P_LEVEL=NVL`
- Profile: `training`

**label-studio** — annotation UI:
- Image: `heartexlabs/label-studio:latest`
- Port: `8081:8080`
- `restart: unless-stopped`
- No GPU reservation
- Volume: named volume `label-studio-data:/label-studio/data`, `/data/datasets:/label-studio/files`
- Env: `LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true`, `LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=/label-studio/files`, `LABEL_STUDIO_USERNAME=admin@local.dev`, `LABEL_STUDIO_PASSWORD=changeme`

**jupyterlab** — notebook environment:
- Image: `quay.io/jupyter/pytorch-notebook:cuda12-pytorch-2.4.0`
- Port: `8888:8888`
- `restart: unless-stopped`
- GPU: `['0']` only
- Volumes: `/data/notebooks:/home/jovyan/work`, `/data/models:/home/jovyan/models`, `/data/datasets:/home/jovyan/datasets`
- Env: `NVIDIA_VISIBLE_DEVICES=0`, `JUPYTER_ENABLE_LAB=yes`, `JUPYTER_TOKEN=changeme`

Declare named volume `label-studio-data:` at the bottom.

**Critical:** `version: '3.8'` is deprecated — omit it.

---

## Step 3 — `configs/axolotl/qlora_4gpu.yml`

FSDP config for Qwen2.5-32B fine-tuning on all 4 GPUs. Key fields:
- `base_model: /workspace/models/qwen2.5-32b`
- `bf16: true`, `tf32: true`
- FSDP: `full_shard`, `auto_wrap`, `fsdp_transformer_layer_cls_to_wrap: Qwen2DecoderLayer`
- Dataset path: `/workspace/datasets/text/formatted`, type `alpaca`, file `train.jsonl`
- `sequence_len: 8192`, `sample_packing: true`
- LoRA: `lora_r: 64`, `lora_alpha: 128`, targets `q_proj v_proj k_proj o_proj gate_proj up_proj down_proj`
- `saves_per_epoch: 2`, `output_dir: /workspace/outputs/qlora-run-001`

Use exact structure from source doc — this is a reproducibility artifact.

---

## Step 4 — `scripts/deploy-phase07.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Phase 07: Training Pipeline ==="

# Run storage setup if directories don't exist
if [[ ! -d /data/datasets ]]; then
    bash "$REPO_ROOT/scripts/setup-storage-phase07.sh"
fi

# Start always-on services only (Label Studio + JupyterLab)
docker compose -f "$REPO_ROOT/docker/compose.training.yml" up -d label-studio jupyterlab

echo ""
echo "Services started:"
echo "  Label Studio  → http://10.10.10.2:8081  (admin@local.dev / changeme)"
echo "  JupyterLab    → http://10.10.10.2:8888  (token: changeme)"
echo ""
echo "Training services (Kohya, Axolotl, Unsloth) are started per-run."
echo "Use the loadout manager before starting training:"
echo "  curl -X POST http://localhost:8800/activate/training-lora-image   # Kohya on GPU1+2"
echo "  curl -X POST http://localhost:8800/activate/training-lora-text    # Axolotl on all GPUs"
```

**Do not auto-start Kohya, Axolotl, or Unsloth.** They claim GPUs and must only run when inference is stopped. The deploy script starts only Label Studio and JupyterLab.

---

## Step 5 — `scripts/validate-phase07.sh`

Automated checks:

| Check | Command |
|-------|---------|
| Label Studio running | `docker ps --filter name=label-studio --filter status=running \| grep -q label-studio` |
| Label Studio HTTP | `curl -sf http://localhost:8081/` |
| JupyterLab running | `docker ps --filter name=jupyterlab --filter status=running \| grep -q jupyterlab` |
| JupyterLab HTTP | `curl -sf http://localhost:8888/` |
| Dataset dirs exist | `test -d /data/datasets/images && test -d /data/datasets/text` |
| Checkpoint dirs exist | `test -d /data/checkpoints/kohya && test -d /data/checkpoints/axolotl` |
| Axolotl config exists | `test -f configs/axolotl/qlora_4gpu.yml` |
| Convert script exists | `test -f scripts/convert_labelstudio_to_alpaca.py` |
| Axolotl import check | `docker compose -f docker/compose.training.yml --profile training run --rm axolotl python -c "import axolotl; print('axolotl ok')"` |

Manual checks (warn only):
- Open Label Studio at `:8081`, confirm login works with `admin@local.dev` / `changeme`
- Open JupyterLab at `:8888`, confirm notebook with `import torch; torch.cuda.device_count()` returns 4
- Verify Kohya UI accessible at `:7860` after manually starting with `docker compose ... up -d kohya`

Use the same `check()` / `warn()` pattern as prior validate scripts. Exit with `$FAIL` count.

---

## Step 6 — `scripts/convert_labelstudio_to_alpaca.py`

Converts Label Studio conversational export JSON to Alpaca JSONL for Axolotl. CLI usage: `python3 convert_labelstudio_to_alpaca.py input.json output.jsonl`.

Logic:
- Read Label Studio JSON export (list of tasks)
- For each task: extract `data.instruction`, `data.input`, and the first `textarea` annotation result as `output`
- Skip records where `instruction` or `output` is empty
- Write one JSON object per line: `{"instruction": ..., "input": ..., "output": ...}`
- Print count of converted records

Use exact implementation from source doc.

---

## Constraints

- **`ipc: host`** is required on `axolotl` — NCCL inter-GPU shared memory requires it, same as vLLM. Missing this causes training to hang at NCCL init.
- **Axolotl and Unsloth behind `training` profile** — they must not start with `docker compose up -d` without `--profile training`. This is intentional.
- **Kohya has no profile** but is also not started by the deploy script — only named explicitly via `docker compose up -d kohya`. Add a comment in compose.training.yml explaining this.
- **JUPYTER_TOKEN=changeme** is a placeholder — add a comment in the compose file to change it before LAN exposure
- **Label Studio password** `changeme` — same, add a comment. These are not flagged in validation because Label Studio doesn't expose an API to check auth state easily.
- The Axolotl image tag `main-latest` is a floating tag — it may break on future pulls. Note this in the compose file comment.
- Do not mount `configs/nccl/nccl.conf` into training containers — the NCCL env vars (`NCCL_P2P_LEVEL=NVL`, `NCCL_SHM_DISABLE=0`) in the compose file are sufficient. The conf file is only needed for vLLM.

---

## Feedback Template

Write to `/plan/ghc-feedback/phase07-training-pipeline.md`:

```markdown
# GHC Feedback: Phase 07 — Training & Fine-Tuning Pipeline
**Brief:** P07-001 | **Status:** Complete / Partial / Blocked

## Files Created
- [ ] docker/compose.training.yml
- [ ] configs/axolotl/qlora_4gpu.yml
- [ ] scripts/setup-storage-phase07.sh
- [ ] scripts/deploy-phase07.sh
- [ ] scripts/validate-phase07.sh
- [ ] scripts/convert_labelstudio_to_alpaca.py

## Deviations from Brief
| Item | Plan | Actual | Reason |

## Validation Results
[paste validate-phase07.sh output]

## Notes
```
