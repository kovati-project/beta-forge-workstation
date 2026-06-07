# Phase 07 — Training & Fine-Tuning Pipeline
[← Loadout Manager](06-loadout-manager.md) | [Next: Agentic Workflows →](08-agentic-mcp.md)

---

## Objective
Deploy the full LoRA and fine-tuning stack: Kohya_ss for image LoRA training, Axolotl for text model fine-tuning, Unsloth for fast single/dual GPU LoRA, and Label Studio for training data tagging. Wire checkpoint and dataset storage to MinIO (Phase 09).

---

## GPU Assignment for Training

| Workload | GPUs | Strategy | Notes |
|----------|------|----------|-------|
| Image LoRA (Kohya) | [1, 2] | DDP | NVLink pair B, leaves GPU0 for ComfyUI test |
| Text LoRA (Unsloth) | [0, 3] | Single/dual | NVLink pair A |
| Full fine-tune (Axolotl) | [0,1,2,3] | FSDP | All GPUs, inference must be stopped |

---

## Step 1 — Docker Compose: Training Stack

```bash
cat <<'EOF' > ~/ai-workstation/docker/compose.training.yml
version: '3.8'

services:

  # ── Kohya_ss: image LoRA and Dreambooth ───────────────────────────────────
  kohya:
    image: ghcr.io/bmaltais/kohya-ss:latest
    container_name: kohya
    restart: unless-stopped
    ports:
      - "7860:7860"
    volumes:
      - /data/datasets/images:/dataset
      - /data/models/comfyui/loras:/output/loras
      - /data/checkpoints/kohya:/output/checkpoints
      - /data/models/comfyui/checkpoints:/models/checkpoints
    environment:
      - NVIDIA_VISIBLE_DEVICES=1,2
      - KOHYA_LOG_LEVEL=INFO
    command: >
      --listen 0.0.0.0
      --server_port 7860
      --headless
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['1', '2']
              capabilities: [gpu]

  # ── Axolotl: text model fine-tuning ───────────────────────────────────────
  axolotl:
    image: winglian/axolotl:main-latest
    container_name: axolotl
    restart: no            # training jobs are one-shot
    volumes:
      - /data/datasets/text:/workspace/datasets
      - /data/checkpoints/axolotl:/workspace/outputs
      - /data/models/vllm:/workspace/models
      - ./configs/axolotl:/workspace/configs
    environment:
      - NVIDIA_VISIBLE_DEVICES=0,1,2,3
      - NCCL_P2P_LEVEL=NVL
      - NCCL_SHM_DISABLE=0
      - WANDB_DISABLED=true    # use Langfuse instead
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0', '1', '2', '3']
              capabilities: [gpu]
    profiles:
      - training     # started manually per run

  # ── Unsloth: fast LoRA (1-2 GPU) ─────────────────────────────────────────
  unsloth:
    image: unslothai/unsloth:latest
    container_name: unsloth
    restart: no
    ports:
      - "8501:8501"    # Streamlit UI if available
    volumes:
      - /data/datasets/text:/workspace/datasets
      - /data/checkpoints/unsloth:/workspace/outputs
      - /data/models/vllm:/workspace/models
    environment:
      - NVIDIA_VISIBLE_DEVICES=0,3
      - NCCL_P2P_LEVEL=NVL
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0', '3']
              capabilities: [gpu]
    profiles:
      - training

  # ── Label Studio: training data annotation ────────────────────────────────
  label-studio:
    image: heartexlabs/label-studio:latest
    container_name: label-studio
    restart: unless-stopped
    ports:
      - "8081:8080"
    volumes:
      - label-studio-data:/label-studio/data
      - /data/datasets:/label-studio/files
    environment:
      - LABEL_STUDIO_LOCAL_FILES_SERVING_ENABLED=true
      - LABEL_STUDIO_LOCAL_FILES_DOCUMENT_ROOT=/label-studio/files
      - LABEL_STUDIO_USERNAME=admin@local.dev
      - LABEL_STUDIO_PASSWORD=changeme

  # ── JupyterLab: experimentation ───────────────────────────────────────────
  jupyterlab:
    image: quay.io/jupyter/pytorch-notebook:cuda12-pytorch-2.4.0
    container_name: jupyterlab
    restart: unless-stopped
    ports:
      - "8888:8888"
    volumes:
      - /data/notebooks:/home/jovyan/work
      - /data/models:/home/jovyan/models
      - /data/datasets:/home/jovyan/datasets
    environment:
      - NVIDIA_VISIBLE_DEVICES=0
      - JUPYTER_ENABLE_LAB=yes
      - JUPYTER_TOKEN=changeme
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']
              capabilities: [gpu]

volumes:
  label-studio-data:

EOF
```

---

## Step 2 — Dataset Directory Structure

```bash
sudo mkdir -p /data/datasets/{images,text,audio}
sudo mkdir -p /data/datasets/images/{raw,tagged,rejected}
sudo mkdir -p /data/datasets/text/{raw,formatted,validation}
sudo mkdir -p /data/checkpoints/{kohya,axolotl,unsloth}
sudo chown -R $USER:$USER /data/datasets /data/checkpoints
```

---

## Step 3 — Image LoRA Training Workflow

### Data Preparation
```bash
# Recommended: 15-30 images per concept for Dreambooth LoRA
# Crop to 1024×1024 for SDXL

# Tag images using WD14 tagger via Kohya UI:
# 1. Open Kohya at http://10.10.10.2:7860
# 2. Tools → WD14 Captioning
# 3. Point at /dataset/images/raw/
# 4. Run auto-tagging (BLIP2 + WD14)
# 5. Review and edit tags in Label Studio

# Or use Label Studio for manual annotation:
# http://10.10.10.2:8081
# Create project → Image Captioning template
# Import images from /data/datasets/images/raw/
```

### Kohya Training Config (SDXL LoRA)
```toml
# /data/configs/kohya/sdxl_lora.toml
[model_arguments]
pretrained_model_name_or_path = "/models/checkpoints/sdxl-base/sd_xl_base_1.0.safetensors"
v_parameterization = false

[dataset_arguments]
train_data_dir = "/dataset/images/tagged"
resolution = "1024,1024"
batch_size = 2
enable_bucket = true

[training_arguments]
output_dir = "/output/loras"
output_name = "my_lora_v1"
save_every_n_epochs = 1
max_train_epochs = 20
learning_rate = 1e-4
lr_scheduler = "cosine_with_restarts"
optimizer_type = "AdamW8bit"
mixed_precision = "bf16"
gradient_checkpointing = true
network_dim = 32
network_alpha = 16

[logging_arguments]
log_with = "tensorboard"
logging_dir = "/output/checkpoints/logs"
```

---

## Step 4 — Text LoRA Training (Axolotl)

### Config Template
```yaml
# ~/ai-workstation/configs/axolotl/qlora_4gpu.yml
base_model: /workspace/models/qwen2.5-32b
model_type: AutoModelForCausalLM
tokenizer_type: AutoTokenizer

load_in_4bit: false
bf16: true
tf32: true

fsdp:
  - full_shard
  - auto_wrap
fsdp_config:
  fsdp_offload_params: false
  fsdp_state_dict_type: FULL_STATE_DICT
  fsdp_transformer_layer_cls_to_wrap: Qwen2DecoderLayer

datasets:
  - path: /workspace/datasets/text/formatted
    type: alpaca
    data_files:
      - train.jsonl

dataset_prepared_path: /workspace/datasets/.cache
val_set_size: 0.02

output_dir: /workspace/outputs/qlora-run-001
sequence_len: 8192
sample_packing: true

micro_batch_size: 2
gradient_accumulation_steps: 4
num_epochs: 3
learning_rate: 2e-5
lr_scheduler: cosine
warmup_ratio: 0.05
optimizer: adamw_torch_fused

lora_r: 64
lora_alpha: 128
lora_dropout: 0.05
lora_target_modules:
  - q_proj
  - v_proj
  - k_proj
  - o_proj
  - gate_proj
  - up_proj
  - down_proj

saves_per_epoch: 2
logging_steps: 10
```

### Run Training
```bash
# Activate training loadout first
curl -X POST http://localhost:8800/activate/training-lora-text

# Start training
docker compose -f ~/ai-workstation/docker/compose.training.yml \
  --profile training run axolotl \
  accelerate launch -m axolotl.cli.train /workspace/configs/qlora_4gpu.yml

# Monitor
docker logs -f axolotl
nvidia-smi dmon -s u -d 2
```

---

## Step 5 — Label Studio for Dataset Management

```bash
docker compose -f ~/ai-workstation/docker/compose.training.yml up -d label-studio

# Access at http://10.10.10.2:8081
# Default login: admin@local.dev / changeme
```

**Recommended Label Studio project templates:**

| Project Type | Template | Use Case |
|-------------|----------|----------|
| Image captioning | Image Captioning | SDXL/FLUX training captions |
| Preference data | Text Pairwise | RLHF / DPO datasets |
| NER/Classification | Named Entity Recognition | Domain-specific text extraction |
| Conversation | Conversational AI | Chat instruction fine-tuning |

**Export formats:**
- For Kohya: export as JSON, convert captions to `.txt` sidecar files
- For Axolotl: export as JSONL in Alpaca or ShareGPT format

---

## Step 6 — Dataset Format Conversion Scripts

```python
# ~/ai-workstation/scripts/convert_labelstudio_to_alpaca.py
"""Convert Label Studio conversational export to Alpaca JSONL for Axolotl."""
import json, sys
from pathlib import Path

def convert(input_path: str, output_path: str):
    with open(input_path) as f:
        tasks = json.load(f)
    
    records = []
    for task in tasks:
        ann = task.get("annotations", [{}])[0]
        result = ann.get("result", [])
        
        instruction = task["data"].get("instruction", "")
        input_text = task["data"].get("input", "")
        output_text = ""
        
        for r in result:
            if r.get("type") == "textarea":
                output_text = r["value"]["text"][0]
        
        if instruction and output_text:
            records.append({
                "instruction": instruction,
                "input": input_text,
                "output": output_text
            })
    
    with open(output_path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    
    print(f"Converted {len(records)} records → {output_path}")

if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
```

---

## Validation Checklist

- [ ] Kohya_ss web UI accessible at `:7860`
- [ ] Label Studio accessible at `:8081`, login works
- [ ] JupyterLab accessible at `:8888`
- [ ] Sample image LoRA training run completes (even 5 steps to verify setup)
- [ ] Output LoRA file appears in `/data/models/comfyui/loras/`
- [ ] LoRA loads in ComfyUI without errors
- [ ] Axolotl config parses without error: `docker compose run axolotl python -c "import axolotl"`
- [ ] NCCL initializes across all 4 GPUs in training container

---

## Notes
- Never run training and inference on the same GPUs — the loadout manager enforces this but double-check before long training runs
- Save Kohya configs as `.toml` files in version control — they are the reproducibility artifact for each LoRA
- Axolotl FSDP requires all GPUs to have identical VRAM — confirmed on your 4x A5500
- Checkpoint every epoch minimum — training on 4 GPUs at this scale is expensive to restart from scratch
- Label Studio data lives in a Docker volume — include it in backup strategy (Phase 14)
