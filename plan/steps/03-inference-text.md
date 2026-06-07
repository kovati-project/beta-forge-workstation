# Phase 03 — Text Inference Stack
[← Host Baseline](02-host-baseline.md) | [Next: Image Inference →](04-inference-image.md)

---

## Objective
Deploy Ollama and vLLM for text model serving, configured for the confirmed NVLink topology (GPU0↔GPU3 and GPU1↔GPU2). Establish the OpenAI-compatible API endpoints that all upstream services consume.

---

## NVLink Topology Reference
```
Bridge A: GPU0 (bus 0x21) ←—NV4—→ GPU3 (bus 0x43)  [CUDA_VISIBLE_DEVICES=0,3]
Bridge B: GPU1 (bus 0x22) ←—NV4—→ GPU2 (bus 0x41)  [CUDA_VISIBLE_DEVICES=1,2]
Full mesh: all 4 GPUs valid for TP=4 up to ~70B fp16
```

---

## Services Deployed

| Service | Port | Role |
|---------|------|------|
| Ollama | 11434 | OpenAI-compatible, model management, hot-swap |
| vLLM (pair A) | 8000 | High-throughput, NVLink pair [0,3] |
| vLLM (pair B) | 8001 | Second model, NVLink pair [1,2] |
| vLLM (4-GPU) | 8002 | 70B+ models, full mesh TP=4 |

---

## Step 1 — Docker Compose: Text Inference

```bash
mkdir -p ~/ai-workstation/docker
cat <<'EOF' > ~/ai-workstation/docker/compose.inference.yml
version: '3.8'

services:

  # ── Ollama: lightweight model management and hot-swap ──────────────────────
  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - /data/models/ollama:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0
      - OLLAMA_NUM_PARALLEL=4
      - OLLAMA_MAX_LOADED_MODELS=2
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0']      # default single GPU; override per loadout
              capabilities: [gpu]

  # ── vLLM: NVLink pair A [GPU0, GPU3] ──────────────────────────────────────
  vllm-pair-a:
    image: vllm/vllm-openai:latest
    container_name: vllm-pair-a
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - /data/models/vllm:/models
    environment:
      - CUDA_VISIBLE_DEVICES=0,3
      - NCCL_P2P_LEVEL=NVL
      - NCCL_SHM_DISABLE=0
    command: >
      --model /models/current
      --tensor-parallel-size 2
      --max-model-len 32768
      --gpu-memory-utilization 0.92
      --host 0.0.0.0
      --port 8000
      --served-model-name current-model
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0', '3']
              capabilities: [gpu]

  # ── vLLM: NVLink pair B [GPU1, GPU2] ──────────────────────────────────────
  vllm-pair-b:
    image: vllm/vllm-openai:latest
    container_name: vllm-pair-b
    restart: unless-stopped
    ports:
      - "8001:8000"
    volumes:
      - /data/models/vllm:/models
    environment:
      - CUDA_VISIBLE_DEVICES=1,2
      - NCCL_P2P_LEVEL=NVL
      - NCCL_SHM_DISABLE=0
    command: >
      --model /models/current-b
      --tensor-parallel-size 2
      --max-model-len 32768
      --gpu-memory-utilization 0.92
      --host 0.0.0.0
      --port 8000
      --served-model-name current-model-b
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['1', '2']
              capabilities: [gpu]

  # ── vLLM: Full 4-GPU for 70B+ models ─────────────────────────────────────
  vllm-4gpu:
    image: vllm/vllm-openai:latest
    container_name: vllm-4gpu
    restart: unless-stopped
    ports:
      - "8002:8000"
    volumes:
      - /data/models/vllm:/models
    environment:
      - CUDA_VISIBLE_DEVICES=0,1,2,3
      - NCCL_P2P_LEVEL=NVL
      - NCCL_SHM_DISABLE=0
    command: >
      --model /models/large
      --tensor-parallel-size 4
      --max-model-len 32768
      --gpu-memory-utilization 0.92
      --host 0.0.0.0
      --port 8000
      --served-model-name large-model
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              device_ids: ['0', '1', '2', '3']
              capabilities: [gpu]
    profiles:
      - large          # only starts with: docker compose --profile large up

EOF
```

---

## Step 2 — Model Download: Ollama

```bash
# Start Ollama first
docker compose -f ~/ai-workstation/docker/compose.inference.yml up -d ollama

# Pull recommended models
docker exec ollama ollama pull qwen2.5-coder:32b    # code generation
docker exec ollama ollama pull llama3.3:70b         # general (will use 2-4 GPUs via vLLM instead)
docker exec ollama ollama pull mistral:7b           # fast chat, single GPU
docker exec ollama ollama pull nomic-embed-text     # embeddings for RAG

# List loaded models
docker exec ollama ollama list

# Test API
curl http://localhost:11434/v1/models
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"mistral:7b","messages":[{"role":"user","content":"Hello"}]}'
```

---

## Step 3 — Model Download: vLLM

```bash
# Install huggingface-cli
pip3 install huggingface_hub

# Download models to local storage
# Adjust model IDs to your preferences / licenses

mkdir -p /data/models/vllm

# Pair A model (34B-40B class)
huggingface-cli download Qwen/Qwen2.5-32B-Instruct \
  --local-dir /data/models/vllm/qwen2.5-32b \
  --exclude "*.gguf"

# Large model (70B class, 4-GPU)
huggingface-cli download meta-llama/Llama-3.3-70B-Instruct \
  --local-dir /data/models/vllm/llama3.3-70b \
  --exclude "*.gguf"

# Symlink active models
ln -sf /data/models/vllm/qwen2.5-32b /data/models/vllm/current
ln -sf /data/models/vllm/llama3.3-70b /data/models/vllm/large
```

---

## Step 4 — Start and Validate vLLM

```bash
# Start pair A
docker compose -f ~/ai-workstation/docker/compose.inference.yml up -d vllm-pair-a

# Monitor startup (model load takes 1-3 minutes for 32B)
docker logs -f vllm-pair-a

# Test
curl http://localhost:8000/v1/models
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "current-model",
    "messages": [{"role":"user","content":"What is 2+2?"}],
    "max_tokens": 50
  }'

# Check GPU utilization during inference
nvidia-smi dmon -s u -d 2
```

---

## Step 5 — vLLM Tuning for A5500

The A5500 has 24GB GDDR6 (not HBM) — memory bandwidth is lower than A100/H100 but VRAM capacity is reasonable. Key tuning parameters:

```bash
# For 32B models on 2x A5500 (48GB combined):
--gpu-memory-utilization 0.92   # leave 8% for activations/KV cache overhead
--max-model-len 32768           # conservative; can push to 65536 with quantization
--max-num-seqs 64               # concurrent sequences
--enable-chunked-prefill        # better latency for mixed short/long prompts

# For 70B on 4x A5500 (96GB combined):
--gpu-memory-utilization 0.90
--max-model-len 16384           # 70B fp16 is tight on 96GB; use fp8 for longer context
--quantization fp8              # enables longer context without sacrificing much quality

# For quantized models (AWQ/GPTQ) on pair A:
--quantization awq
--gpu-memory-utilization 0.95   # more headroom with quantization
```

---

## Step 6 — Model Recommendation Matrix

| Model | Size | GPUs | Engine | Use Case |
|-------|------|------|--------|----------|
| mistral:7b | 7B | 1 | Ollama | Fast chat, low latency |
| qwen2.5-coder:14b | 14B | 1 | Ollama | Code, single GPU |
| qwen2.5-coder:32b | 32B | [0,3] | vLLM | Primary code model |
| Llama-3.3-70B | 70B | [0,1,2,3] | vLLM | Best general reasoning |
| Llama-3.3-70B-AWQ | 70B | [0,3] | vLLM | 70B on 2 GPUs (quantized) |
| nomic-embed-text | — | 1 | Ollama | RAG embeddings |
| DeepSeek-R1:32b | 32B | [0,3] | vLLM | Reasoning / chain-of-thought |

---

## Validation Checklist

- [ ] Ollama running, `ollama list` shows downloaded models
- [ ] Ollama API responding at `:11434/v1/`
- [ ] vLLM pair A running on GPU0+GPU3, API at `:8000`
- [ ] `nvidia-smi` shows VRAM consumed correctly per service
- [ ] Inference latency acceptable (first token <2s for 32B on NVLink pair)
- [ ] `nvidia-smi dmon` shows GPU utilization >80% during inference
- [ ] No NCCL errors in vLLM logs

---

## Notes
- Ollama and vLLM both expose OpenAI-compatible APIs — Open WebUI uses the same endpoint format for both
- Never run Ollama and vLLM on the same GPUs simultaneously — the loadout manager handles this in Phase 06
- For `llama3.3-70b` you need a Hugging Face account with Meta license approval
- vLLM supports continuous batching by default — no config needed for multi-user throughput
