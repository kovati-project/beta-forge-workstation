# GHC Task: Phase 03 — Text Inference Stack
**Brief ID:** P03-001  
**Source doc:** `/plan/steps/03-inference-text.md`  
**Write feedback to:** `/plan/ghc-feedback/phase03-inference-text.md`

---

## Context

Phase 02 is complete. The workstation (`adapress`, 10.10.10.2) is running:
- Ubuntu 26.04 LTS
- NVIDIA driver 595.71.05
- CUDA 13.3
- Docker with NVIDIA Container Runtime (default runtime = nvidia)
- All 4x RTX A5500 (96GB VRAM total) with NVLink active

**Confirmed NVLink topology:**
```
Pair A: GPU0 (bus 0x21) ←—NV4—→ GPU3 (bus 0x43)   CUDA_VISIBLE_DEVICES=0,3
Pair B: GPU1 (bus 0x22) ←—NV4—→ GPU2 (bus 0x41)   CUDA_VISIBLE_DEVICES=1,2
```

**Current access:** direct SSH as `kasemo@10.10.10.2`. No reverse proxy in place (Phase 01 tabled).

This phase deploys Ollama and vLLM. These are the OpenAI-compatible API endpoints that Open WebUI (Phase 05), the loadout manager (Phase 06), and all agentic services consume. Get these right and the rest of the stack plugs in cleanly.

---

## Scope

Deploy three things:

1. **Docker Compose file** — defines Ollama + vLLM services with correct GPU assignments
2. **NCCL config** — GPU-to-GPU communication tuning for NVLink
3. **Storage layout** — `/data/models/` directory structure

**What is NOT in scope for this brief:**
- Starting vLLM pair B or the 4-GPU profile (those are loadout-manager territory, Phase 06)
- Downloading models (bandwidth-dependent, user does this manually using the instructions you provide)
- Open WebUI integration (Phase 05)

---

## Step 1 — Storage Layout

Create a setup script that the user runs on the workstation to establish the `/data/` structure.

Create `scripts/setup-storage.sh`:

```bash
#!/usr/bin/env bash
# Creates /data/ directory structure for AI workstation.
# Run once on the workstation as a user with sudo.
# Safe to re-run — uses mkdir -p throughout.
set -euo pipefail

sudo mkdir -p /data/models/ollama
sudo mkdir -p /data/models/vllm
sudo mkdir -p /data/models/hf-cache
sudo mkdir -p /data/docker
sudo mkdir -p /data/checkpoints
sudo mkdir -p /data/datasets

# Set ownership so kasemo can write without sudo
sudo chown -R kasemo:kasemo /data/models
sudo chown -R kasemo:kasemo /data/checkpoints
sudo chown -R kasemo:kasemo /data/datasets

echo "Storage layout created:"
df -h /data 2>/dev/null || df -h /
echo ""
echo "Directories:"
ls -la /data/
```

---

## Step 2 — NCCL Config

NCCL governs GPU-to-GPU communication in vLLM's tensor parallel operations. Without this, vLLM falls back to PCIe transfers between NVLink-paired GPUs.

Create `configs/nccl/nccl.conf`:

```bash
# Prefer NVLink for P2P transfers
NCCL_P2P_LEVEL=NVL
# Enable shared memory for same-node transfers
NCCL_SHM_DISABLE=0
# Use all available NVLink channels
NCCL_MIN_NCHANNELS=4
```

---

## Step 3 — Docker Compose: Text Inference

Create `docker/compose.inference.yml`:

```yaml
services:

  # ── Ollama ────────────────────────────────────────────────────────────────────
  # Lightweight model management. Hot-swap capable. Good for 7B–14B chat models.
  # Uses GPU0 by default; loadout manager overrides CUDA_VISIBLE_DEVICES at runtime.
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
              device_ids: ['0']
              capabilities: [gpu]

  # ── vLLM: NVLink Pair A [GPU0, GPU3] ─────────────────────────────────────────
  # High-throughput serving for 32B–40B models.
  # CUDA_VISIBLE_DEVICES=0,3 maps to the confirmed NVLink bridge.
  # --model path is a symlink — update /data/models/vllm/current before starting.
  vllm-pair-a:
    image: vllm/vllm-openai:latest
    container_name: vllm-pair-a
    restart: unless-stopped
    ipc: host
    ports:
      - "8000:8000"
    volumes:
      - /data/models/vllm:/models
      - /data/models/hf-cache:/root/.cache/huggingface
      - ./configs/nccl/nccl.conf:/etc/nccl.conf:ro
    environment:
      - CUDA_VISIBLE_DEVICES=0,3
      - NCCL_P2P_LEVEL=NVL
      - NCCL_SHM_DISABLE=0
      - HF_HOME=/root/.cache/huggingface
    command: >
      --model /models/current
      --tensor-parallel-size 2
      --max-model-len 32768
      --gpu-memory-utilization 0.92
      --max-num-seqs 64
      --enable-chunked-prefill
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

  # ── vLLM: NVLink Pair B [GPU1, GPU2] ─────────────────────────────────────────
  # Second independent inference slot. Same config as pair A, different GPUs/port.
  # Not started by default — use profile "pair-b" or the loadout manager.
  vllm-pair-b:
    image: vllm/vllm-openai:latest
    container_name: vllm-pair-b
    restart: unless-stopped
    ipc: host
    ports:
      - "8001:8000"
    volumes:
      - /data/models/vllm:/models
      - /data/models/hf-cache:/root/.cache/huggingface
      - ./configs/nccl/nccl.conf:/etc/nccl.conf:ro
    environment:
      - CUDA_VISIBLE_DEVICES=1,2
      - NCCL_P2P_LEVEL=NVL
      - NCCL_SHM_DISABLE=0
      - HF_HOME=/root/.cache/huggingface
    command: >
      --model /models/current-b
      --tensor-parallel-size 2
      --max-model-len 32768
      --gpu-memory-utilization 0.92
      --max-num-seqs 64
      --enable-chunked-prefill
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
    profiles:
      - pair-b

  # ── vLLM: Full 4-GPU [GPU0, GPU1, GPU2, GPU3] ────────────────────────────────
  # For 70B+ models. Requires all GPUs free — mutually exclusive with pair A/B.
  # fp8 quantization allows longer context on 96GB total VRAM.
  vllm-4gpu:
    image: vllm/vllm-openai:latest
    container_name: vllm-4gpu
    restart: unless-stopped
    ipc: host
    ports:
      - "8002:8000"
    volumes:
      - /data/models/vllm:/models
      - /data/models/hf-cache:/root/.cache/huggingface
      - ./configs/nccl/nccl.conf:/etc/nccl.conf:ro
    environment:
      - CUDA_VISIBLE_DEVICES=0,1,2,3
      - NCCL_P2P_LEVEL=NVL
      - NCCL_SHM_DISABLE=0
      - HF_HOME=/root/.cache/huggingface
    command: >
      --model /models/large
      --tensor-parallel-size 4
      --max-model-len 32768
      --gpu-memory-utilization 0.90
      --quantization fp8
      --max-num-seqs 32
      --enable-chunked-prefill
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
      - large
```

---

## Step 4 — Deploy & Validate Instructions

Create `scripts/deploy-phase03.sh`:

```bash
#!/usr/bin/env bash
# Deploy Phase 03: Text Inference Stack
# Run on the workstation as kasemo.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== Phase 03: Text Inference Deploy ==="
echo ""

# ── 1. Storage ────────────────────────────────────────────────────────────────
echo "[1/4] Verifying storage layout..."
for dir in /data/models/ollama /data/models/vllm /data/models/hf-cache; do
    if [[ ! -d "$dir" ]]; then
        echo "  Missing: $dir — run scripts/setup-storage.sh first"
        exit 1
    fi
done
echo "  ✓ Storage directories present"

# ── 2. Ollama ─────────────────────────────────────────────────────────────────
echo "[2/4] Starting Ollama..."
docker compose -f "$REPO_ROOT/docker/compose.inference.yml" up -d ollama
sleep 5
if docker exec ollama ollama list &>/dev/null; then
    echo "  ✓ Ollama running"
else
    echo "  ✗ Ollama not responding — check: docker logs ollama"
    exit 1
fi

# ── 3. Model symlink check ────────────────────────────────────────────────────
echo "[3/4] Checking vLLM model symlink..."
if [[ ! -e /data/models/vllm/current ]]; then
    echo "  ⚠  /data/models/vllm/current symlink not set."
    echo "     Download a model first, then:"
    echo "     ln -sf /data/models/vllm/<model-dir> /data/models/vllm/current"
    echo "  Skipping vLLM start."
else
    echo "  ✓ Symlink: $(readlink /data/models/vllm/current)"
    echo "[4/4] Starting vLLM pair A..."
    docker compose -f "$REPO_ROOT/docker/compose.inference.yml" up -d vllm-pair-a
    echo "  Waiting for model load (this takes 1–3 min for 32B)..."
    timeout 300 bash -c 'until curl -sf http://localhost:8000/v1/models &>/dev/null; do sleep 5; done' \
        && echo "  ✓ vLLM pair A ready" \
        || echo "  ✗ vLLM pair A did not come up in 5 min — check: docker logs vllm-pair-a"
fi

echo ""
echo "=== Deploy complete ==="
echo ""
echo "Manual model downloads (run after this script):"
echo ""
echo "  Ollama models:"
echo "    docker exec ollama ollama pull mistral:7b"
echo "    docker exec ollama ollama pull qwen2.5-coder:14b"
echo "    docker exec ollama ollama pull nomic-embed-text"
echo ""
echo "  vLLM 32B model (pair A):"
echo "    pip3 install -q huggingface_hub"
echo "    huggingface-cli download Qwen/Qwen2.5-32B-Instruct \\"
echo "      --local-dir /data/models/vllm/qwen2.5-32b --exclude '*.gguf'"
echo "    ln -sf /data/models/vllm/qwen2.5-32b /data/models/vllm/current"
echo "    docker compose -f docker/compose.inference.yml up -d vllm-pair-a"
echo ""
echo "  vLLM 70B model (4-GPU, requires Meta HF license):"
echo "    huggingface-cli download meta-llama/Llama-3.3-70B-Instruct \\"
echo "      --local-dir /data/models/vllm/llama3.3-70b --exclude '*.gguf'"
echo "    ln -sf /data/models/vllm/llama3.3-70b /data/models/vllm/large"
```

---

## Step 5 — Validate Script

Create `scripts/validate-phase03.sh`:

```bash
#!/usr/bin/env bash
# Run on the workstation after deploy-phase03.sh and model downloads complete.
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
PASS=0; FAIL=0; WARN=0

check() {
    local desc="$1"; shift
    if eval "$@" &>/dev/null; then
        echo -e "${GREEN}✓${NC} $desc"
        ((PASS++))
    else
        echo -e "${RED}✗${NC} $desc"
        ((FAIL++))
    fi
}

warn() {
    echo -e "${YELLOW}?${NC} $1 — check manually"
    ((WARN++))
}

echo "=== Phase 03 Validation ==="
echo ""

# Ollama
check "Ollama container running"         "docker ps --filter name=ollama --filter status=running | grep -q ollama"
check "Ollama API responding"            "curl -sf http://localhost:11434/v1/models"
check "Ollama has at least one model"    "docker exec ollama ollama list 2>/dev/null | grep -qv '^NAME'"
check "nomic-embed-text present"         "docker exec ollama ollama list 2>/dev/null | grep -q nomic-embed-text"

# vLLM pair A
echo ""
if docker ps --filter name=vllm-pair-a --filter status=running | grep -q vllm-pair-a; then
    check "vLLM pair A container running"  "true"
    check "vLLM pair A API responding"     "curl -sf http://localhost:8000/v1/models"
    check "vLLM pair A using GPU 0+3"      "docker exec vllm-pair-a env | grep -q 'CUDA_VISIBLE_DEVICES=0,3'"
    warn "First-token latency <2s for 32B — test: curl -s http://localhost:8000/v1/chat/completions -H 'Content-Type: application/json' -d '{\"model\":\"current-model\",\"messages\":[{\"role\":\"user\",\"content\":\"hi\"}],\"max_tokens\":5}'"
    warn "GPU0+GPU3 VRAM consumed — check: nvidia-smi"
    warn "No NCCL errors — check: docker logs vllm-pair-a 2>&1 | grep -i nccl"
    warn "GPU utilization >80% during inference — check: nvidia-smi dmon -s u -d 2"
else
    echo -e "${YELLOW}—${NC} vLLM pair A not running (model not downloaded yet — skip until symlink is set)"
fi

# Storage
echo ""
check "/data/models/ollama exists"       "test -d /data/models/ollama"
check "/data/models/vllm exists"         "test -d /data/models/vllm"
check "/data/models/hf-cache exists"     "test -d /data/models/hf-cache"

echo ""
echo "Result: ${PASS} passed, ${FAIL} failed, ${WARN} manual checks"
[[ $FAIL -eq 0 ]] && echo -e "${GREEN}Phase 03 READY${NC}" || echo -e "${RED}Phase 03 NOT READY — fix failures above${NC}"
exit $FAIL
```

---

## Constraints

- **Do not start vLLM pair B or vLLM 4-GPU by default.** They are behind Docker Compose profiles (`pair-b`, `large`). The loadout manager (Phase 06) manages which profile runs.
- **Do not run Ollama and vLLM on the same GPU simultaneously.** The compose file assigns them to separate GPUs. Flag this clearly in feedback.
- **`ipc: host` is required on vLLM containers** — vLLM uses shared memory for tensor parallel communication. Without it, NCCL falls back to slower paths.
- **The Llama-3.3-70B download requires a Meta license** accepted on Hugging Face. The deploy script must print a clear note about this rather than attempting the download unconditionally.
- **Do not pin vLLM or Ollama image versions** to a specific tag other than `latest` — the user will manage version pinning in Phase 14 (Operations Runbook).
- **nccl.conf is mounted read-only** into vLLM containers. Do not bake NCCL settings only into environment variables — the file mount is the canonical path.

---

## Done When

- [ ] `scripts/setup-storage.sh` created
- [ ] `configs/nccl/nccl.conf` created
- [ ] `docker/compose.inference.yml` created with all four services (ollama, vllm-pair-a, vllm-pair-b, vllm-4gpu)
- [ ] `vllm-pair-b` and `vllm-4gpu` gated behind Docker Compose profiles
- [ ] `scripts/deploy-phase03.sh` created — includes model download instructions in output
- [ ] `scripts/validate-phase03.sh` created — exits non-zero on any hard failure
- [ ] All files use Unix line endings (LF)
- [ ] No model weights or HF tokens in any file

---

## Return to Claude

In your feedback file, include:
1. List of all files created with their paths
2. Any deviations from the compose spec and why
3. Flag: is `ipc: host` present on all vLLM services?
4. Flag: are pair-b and 4gpu behind profiles?
5. Flag: does the deploy script print Llama license instructions rather than downloading unconditionally?
6. Any blockers or questions before Phase 04 can start
