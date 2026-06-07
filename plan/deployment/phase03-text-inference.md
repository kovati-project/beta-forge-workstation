# Phase 03 — Text Inference

**Services:** Ollama (`:11434`), vLLM pair A (`:8000`)  
**Compose file:** `docker/compose.inference.yml`  
**Scripts:** `setup-storage.sh`, `deploy-phase03.sh`, `validate-phase03.sh`

---

## Prerequisites

- [ ] Phase 02 complete (driver 595.71.05, CUDA 13.3, Docker with nvidia runtime)
- [ ] Files on workstation: `scp -r docker scripts configs kasemo@10.10.10.2:~/ai-workstation/`

---

## Step 1 — Create Storage Layout

```bash
ssh kasemo@10.10.10.2 "bash ~/ai-workstation/scripts/setup-storage.sh"
```

Creates:
- `/data/models/ollama`
- `/data/models/vllm`
- `/data/models/hf-cache`
- `/data/checkpoints`, `/data/datasets`, `/data/docker`

---

## Step 2 — Start Ollama

The deploy script starts Ollama immediately. vLLM only starts once the model symlink is set — safe to run before downloading models.

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/deploy-phase03.sh"
```

Expected: Ollama starts, vLLM skipped with a symlink warning.

---

## Step 3 — Pull Ollama Models

```bash
ssh kasemo@10.10.10.2 "docker exec ollama ollama pull mistral:7b"
ssh kasemo@10.10.10.2 "docker exec ollama ollama pull qwen2.5-coder:14b"
ssh kasemo@10.10.10.2 "docker exec ollama ollama pull nomic-embed-text"
```

`nomic-embed-text` is required by Phase 05 (RAG). Pull it now.

---

## Step 4 — Download vLLM Model (Qwen2.5-32B, ~65GB)

```bash
ssh kasemo@10.10.10.2 "pip3 install -q huggingface_hub"

ssh kasemo@10.10.10.2 "huggingface-cli download Qwen/Qwen2.5-32B-Instruct \
  --local-dir /data/models/vllm/qwen2.5-32b \
  --exclude '*.gguf'"

ssh kasemo@10.10.10.2 "ln -sf /data/models/vllm/qwen2.5-32b /data/models/vllm/current"
```

---

## Step 5 — Start vLLM Pair A

Re-run deploy after the symlink is set:

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/deploy-phase03.sh"
```

Model load takes 1–3 minutes. Monitor:

```bash
ssh kasemo@10.10.10.2 "docker logs -f vllm-pair-a"
```

---

## Step 6 — Download 70B Model (Optional — Requires Llama License)

Requires Meta HF license approval. Skip if not needed yet.

```bash
ssh kasemo@10.10.10.2 "huggingface-cli login"

ssh kasemo@10.10.10.2 "huggingface-cli download meta-llama/Llama-3.3-70B-Instruct \
  --local-dir /data/models/vllm/llama3.3-70b \
  --exclude '*.gguf'"

ssh kasemo@10.10.10.2 "ln -sf /data/models/vllm/llama3.3-70b /data/models/vllm/large"

ssh kasemo@10.10.10.2 "cd ~/ai-workstation && \
  docker compose -f docker/compose.inference.yml --profile large up -d vllm-4gpu"
```

**Note:** vLLM 4-GPU uses all GPUs. Stop pair A and ComfyUI first.

---

## Step 7 — Validate

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase03.sh"
```

All automated checks must pass before proceeding to Phase 05.

---

## Quick Reference

```bash
# Container status
ssh kasemo@10.10.10.2 "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"

# GPU usage
ssh kasemo@10.10.10.2 "nvidia-smi"

# Stop vLLM pair A
ssh kasemo@10.10.10.2 "docker stop vllm-pair-a"

# Restart Ollama
ssh kasemo@10.10.10.2 "docker restart ollama"

# Swap vLLM model
ssh kasemo@10.10.10.2 "ln -sf /data/models/vllm/new-model /data/models/vllm/current \
  && docker restart vllm-pair-a"

# List Ollama models
ssh kasemo@10.10.10.2 "docker exec ollama ollama list"
```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| vLLM OOM on startup | Reduce `--gpu-memory-utilization` in `docker/compose.inference.yml` |
| NCCL errors in vLLM logs | Verify `configs/nccl/nccl.conf` is mounted: `docker inspect vllm-pair-a \| grep nccl` |
| Ollama not showing models | `docker exec ollama ollama list` — confirm pull completed |
| vLLM slow first token | Normal for cold start; subsequent requests will be faster |
| vLLM not starting (symlink missing) | Confirm `/data/models/vllm/current` symlink exists and points to a valid directory |
