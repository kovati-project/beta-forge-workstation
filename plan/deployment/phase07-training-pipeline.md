# Phase 07 — Training Pipeline

**Services:** Label Studio (`:8081`), JupyterLab (`:8888`), Kohya (`:7860`), Axolotl, Unsloth  
**Compose file:** `docker/compose.training.yml`  
**Scripts:** `setup-storage-phase07.sh`, `deploy-phase07.sh`, `validate-phase07.sh`

---

## Prerequisites

- [ ] Phase 02 complete (driver, CUDA, Docker)
- [ ] Phase 06 deployed — Loadout Manager running at `:8800` (required before starting any training)
- [ ] Phase 04 deployed — SDXL checkpoint downloaded (required for image LoRA)
- [ ] Phase 03 deployed — Qwen2.5-32B downloaded (required for text fine-tuning)
- [ ] Files on workstation: `scp -r docker scripts configs kasemo@10.10.10.2:~/ai-workstation/`
- [ ] Disk space: ≥100GB free for datasets + checkpoints

Label Studio and JupyterLab run independently and do not require Phase 06. Kohya and Axolotl require Phase 06 to activate the correct GPU profile before starting.

---

## Step 1 — Create Storage Layout

```bash
ssh kasemo@10.10.10.2 "bash ~/ai-workstation/scripts/setup-storage-phase07.sh"
```

Creates:
- `/data/datasets/{images,text,audio}`
- `/data/datasets/images/{raw,tagged,rejected}`
- `/data/datasets/text/{raw,formatted,validation}`
- `/data/checkpoints/{kohya,axolotl,unsloth}`
- `/data/configs/kohya`

---

## Step 2 — Start Always-On Services

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/deploy-phase07.sh"
```

This starts Label Studio and JupyterLab only. Kohya, Axolotl, and Unsloth are started per-run via the Loadout Manager — do not start them here.

Expected output:
```
Services started:
  Label Studio  → http://10.10.10.2:8081  (admin@local.dev / changeme)
  JupyterLab    → http://10.10.10.2:8888  (token: changeme)
```

---

## Step 3 — Validate

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase07.sh"
```

Expected: 16 automated checks pass, 8 manual checks listed.

---

## Step 4 — Change Default Credentials

Label Studio and JupyterLab ship with placeholder credentials. Update them before exposing to the LAN.

```bash
# Label Studio — change password via the UI
# http://10.10.10.2:8081 → Account → Change Password

# JupyterLab — update JUPYTER_TOKEN in compose.training.yml
ssh kasemo@10.10.10.2 "nano ~/ai-workstation/docker/compose.training.yml"
# Replace: JUPYTER_TOKEN=changeme
# Then restart:
ssh kasemo@10.10.10.2 "docker compose -f ~/ai-workstation/docker/compose.training.yml \
  up -d jupyterlab"
```

---

## Image LoRA Training (Kohya)

### Prepare Dataset

```bash
# Copy 15–30 images (1024×1024) to the raw directory
scp my_images/*.jpg kasemo@10.10.10.2:/data/datasets/images/raw/
```

Tag images using Kohya's WD14 auto-tagger:
1. Open `http://10.10.10.2:7860` (after starting Kohya — see below)
2. Tools → WD14 Captioning → point at `/dataset/images/raw`
3. Review and correct tags
4. Move tagged images to `/data/datasets/images/tagged/`

Or annotate manually in Label Studio (`http://10.10.10.2:8081`).

### Activate GPU Profile + Start Kohya

```bash
# Stop inference services, reserve GPU1+2 for Kohya
ssh kasemo@10.10.10.2 "curl -sX POST http://localhost:8800/activate/training-lora-image"

# Wait for switching to complete
ssh kasemo@10.10.10.2 "curl -s http://localhost:8800/status | python3 -m json.tool"

# Start Kohya
ssh kasemo@10.10.10.2 "docker compose -f ~/ai-workstation/docker/compose.training.yml up -d kohya"
```

### Configure and Train

Edit the config template on the workstation:

```bash
ssh kasemo@10.10.10.2 "cp ~/ai-workstation/configs/kohya/sdxl_lora.toml \
  /data/configs/kohya/my_concept_v1.toml"
ssh kasemo@10.10.10.2 "nano /data/configs/kohya/my_concept_v1.toml"
```

Key values to update:
- `output_name = "my_concept_v1"`
- `max_train_epochs = 20` (adjust for dataset size)
- `learning_rate = 1e-4`

Open `http://10.10.10.2:7860`, load the TOML config, and start training.

Output LoRA saved to `/data/models/comfyui/loras/` — immediately usable in ComfyUI.

### Return to Inference

```bash
ssh kasemo@10.10.10.2 "docker stop kohya"
ssh kasemo@10.10.10.2 "curl -sX POST http://localhost:8800/activate/inference-small"
```

---

## Text Fine-Tuning (Axolotl)

### Prepare Dataset

```bash
# Option A: write Alpaca JSONL directly
cat > /tmp/train.jsonl << 'EOF'
{"instruction": "Summarise this document.", "input": "...", "output": "..."}
EOF
scp /tmp/train.jsonl kasemo@10.10.10.2:/data/datasets/text/formatted/train.jsonl

# Option B: export from Label Studio and convert
python3 scripts/convert_labelstudio_to_alpaca.py export.json \
  /data/datasets/text/formatted/train.jsonl
```

### Edit Config

```bash
ssh kasemo@10.10.10.2 "cp ~/ai-workstation/configs/axolotl/qlora_4gpu.yml \
  ~/ai-workstation/configs/axolotl/my_run.yml"
ssh kasemo@10.10.10.2 "nano ~/ai-workstation/configs/axolotl/my_run.yml"
```

Update:
- `output_dir: /workspace/outputs/my-run-001`
- `num_epochs: 3`
- `base_model: /workspace/models/qwen2.5-32b` (or another model path)

### Activate GPU Profile + Run Training

```bash
# Reserve all 4 GPUs for Axolotl FSDP
ssh kasemo@10.10.10.2 "curl -sX POST http://localhost:8800/activate/training-lora-text"

# Confirm switching complete
ssh kasemo@10.10.10.2 "curl -s http://localhost:8800/status | python3 -m json.tool"

# Start training (runs in foreground — use tmux)
ssh kasemo@10.10.10.2 "tmux new-session -d -s training"
ssh kasemo@10.10.10.2 "tmux send-keys -t training \
  'cd ~/ai-workstation && docker compose -f docker/compose.training.yml \
  --profile training run axolotl accelerate launch -m axolotl.cli.train \
  /workspace/configs/my_run.yml' Enter"

# Monitor
ssh kasemo@10.10.10.2 "docker logs -f axolotl"
ssh kasemo@10.10.10.2 "nvidia-smi dmon -s u -d 2"
```

Checkpoints saved to `/data/checkpoints/axolotl/my-run-001/`.

### Return to Inference

```bash
ssh kasemo@10.10.10.2 "curl -sX POST http://localhost:8800/stop"
ssh kasemo@10.10.10.2 "curl -sX POST http://localhost:8800/activate/inference-small"
```

---

## Dataset Format Converter

```bash
# Convert Label Studio JSON export to Alpaca JSONL
python3 scripts/convert_labelstudio_to_alpaca.py \
  /path/to/labelstudio-export.json \
  /data/datasets/text/formatted/train.jsonl
```

Input: Label Studio JSON export with `instruction` / `input` fields and `textarea` annotation results.  
Output: One `{"instruction": ..., "input": ..., "output": ...}` JSON object per line.

---

## Quick Reference

```bash
# Check always-on services
ssh kasemo@10.10.10.2 "docker ps --filter name=label-studio --filter name=jupyterlab"

# Get JupyterLab token from logs
ssh kasemo@10.10.10.2 "docker logs jupyterlab 2>&1 | grep token="

# Monitor GPU during training
ssh kasemo@10.10.10.2 "nvidia-smi dmon -s u -d 2"

# Check training output directory
ssh kasemo@10.10.10.2 "ls -lt /data/checkpoints/axolotl/"

# Check LoRA output directory (use in ComfyUI)
ssh kasemo@10.10.10.2 "ls -lt /data/models/comfyui/loras/"

# Stop all training services + return to idle
ssh kasemo@10.10.10.2 "docker stop kohya axolotl unsloth 2>/dev/null; \
  curl -sX POST http://localhost:8800/stop"
```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| CUDA OOM during Axolotl | Reduce `micro_batch_size` or `sequence_len` in the YAML config |
| NCCL timeout during training | Verify NVLink: `nvidia-smi topo -m`; confirm `ipc: host` is set in `compose.training.yml` |
| Kohya shows wrong GPU | `docker inspect kohya \| grep NVIDIA_VISIBLE_DEVICES` — should show `1,2` |
| Label Studio login fails | Reset volume: `docker volume rm label-studio-data && docker compose up -d label-studio` |
| JupyterLab no GPU | Check `docker logs jupyterlab` for CUDA errors; verify GPU0 is free (`nvidia-smi`) |
| Permission denied on `/data/datasets` | `ssh kasemo@10.10.10.2 "sudo chown -R kasemo:kasemo /data/datasets"` |
| Axolotl exits immediately | Config YAML error — run `docker compose run axolotl python -c "import axolotl"` to check import |
