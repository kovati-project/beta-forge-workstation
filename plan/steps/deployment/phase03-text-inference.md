# Phase 03 — Text Inference Deployment

**Services:** Ollama (`:11434`), vLLM pair A (`:8000`)  
**Compose file:** `docker/compose.inference.yml`  
**Scripts:** `setup-storage.sh`, `deploy-phase03.sh`, `validate-phase03.sh`

---

## Prerequisites

- [ ] Phase 02 complete (driver, CUDA, Docker verified)
- [ ] Files copied to workstation: `scp -r docker scripts configs kasemo@10.10.10.2:~/ai-workstation/`

---

## Step 1 — Create Storage Layout

```bash
ssh kasemo@10.10.10.2 "bash ~/ai-workstation/scripts/setup-storage.sh"
```

Creates and sets ownership on:
- `/data/models/ollama`
- `/data/models/vllm`
- `/data/models/hf-cache`
- `/data/checkpoints`, `/data/datasets`, `/data/docker`

---

## Step 2 — Start Ollama

The deploy script starts Ollama immediately. vLLM only starts if the model symlink is already in place — safe to run before downloading models.

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/deploy-phase03.sh"
```

Expected output: Ollama starts, vLLM skipped with symlink warning.

---

## Step 3 — Pull Ollama Models

```bash
ssh kasemo@10.10.10.2 "docker exec ollama ollama pull mistral:7b"
ssh kasemo@10.10.10.2 "docker exec ollama ollama pull qwen2.5-coder:14b"
ssh kasemo@10.10.10.2 "docker exec ollama ollama pull nomic-embed-text"
```

`nomic-embed-text` is required before Phase 05 (RAG embedding). Pull it now.

---

## Step 4 — Download vLLM Model (Qwen2.5-32B)

This is the primary pair A model. Download time depends on bandwidth (~65GB).

```bash
ssh kasemo@10.10.10.2 "pip3 install -q huggingface_hub"

ssh kasemo@10.10.10.2 "huggingface-cli download Qwen/Qwen2.5-32B-Instruct \
  --local-dir /data/models/vllm/qwen2.5-32b \
  --exclude '*.gguf'"

ssh kasemo@10.10.10.2 "ln -sf /data/models/vllm/qwen2.5-32b /data/models/vllm/current"
```

---

## Step 5 — Start vLLM Pair A

Re-run the deploy script after the symlink is set — it will pick up the model and start vLLM.

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/deploy-phase03.sh"
```

Model load takes 1–3 minutes. Monitor with:

```bash
ssh kasemo@10.10.10.2 "docker logs -f vllm-pair-a"
```

---

## Step 6 — Download 70B Model (Optional, Requires Llama License)

Requires Meta license approval on Hugging Face. Skip if not needed yet.

```bash
ssh kasemo@10.10.10.2 "huggingface-cli login"   # enter HF token with Llama access

ssh kasemo@10.10.10.2 "huggingface-cli download meta-llama/Llama-3.3-70B-Instruct \
  --local-dir /data/models/vllm/llama3.3-70b \
  --exclude '*.gguf'"

ssh kasemo@10.10.10.2 "ln -sf /data/models/vllm/llama3.3-70b /data/models/vllm/large"
```

Start the 4-GPU profile:

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && docker compose -f docker/compose.inference.yml --profile large up -d vllm-4gpu"
```

**Note:** vLLM 4-GPU uses all GPUs. Stop pair A and ComfyUI first.

---

## Step 7 — Validate

```bash
ssh kasemo@10.10.10.2 "cd ~/ai-workstation && bash scripts/validate-phase03.sh"
```

All automated checks must pass before proceeding to Phase 05.

---

## Quick Reference — Manage Services

```bash
# Status
ssh kasemo@10.10.10.2 "docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'"

# GPU usage
ssh kasemo@10.10.10.2 "nvidia-smi"

# Stop a service
ssh kasemo@10.10.10.2 "docker stop vllm-pair-a"

# Restart Ollama
ssh kasemo@10.10.10.2 "docker restart ollama"

# Swap vLLM model (update symlink, restart container)
ssh kasemo@10.10.10.2 "ln -sf /data/models/vllm/new-model /data/models/vllm/current && docker restart vllm-pair-a"
```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| vLLM OOM on startup | Reduce `--gpu-memory-utilization` in `docker/compose.inference.yml` |
| NCCL errors in vLLM logs | Verify `configs/nccl/nccl.conf` is mounted: `docker inspect vllm-pair-a \| grep nccl` |
| Ollama not showing models | `docker exec ollama ollama list` — confirm pull completed |
| vLLM slow first token | Normal for cold start; subsequent requests will be faster |
