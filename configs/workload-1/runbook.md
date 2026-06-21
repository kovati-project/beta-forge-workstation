# Workload 1 — System Smoke Test

End-to-end validation of inference, image generation, and training on all 4 GPUs.
Expected duration: ~30 min. No permanent model changes.

---

## Prerequisites

- All base services running: `ollama`, `comfyui`, `postgres`, `minio`, `prometheus`, `grafana`
- `/data/models/vllm/qwen2.5-32b` present (or swap for any available model)
- `/data/datasets/text/formatted/train.jsonl` present (synthetic data OK — see Step 3)

---

## Step 1 — Inference: Ollama batch prompts (GPU 0, ~5 min)

```bash
# Pull a model if not already cached
docker exec ollama ollama pull qwen2.5:7b

# Batch 50 prompts and measure throughput
python3 - <<'EOF'
import requests, time, json

MODEL = "qwen2.5:7b"
PROMPTS = [f"Explain concept #{i} in one sentence." for i in range(50)]

start = time.time()
tokens = 0
for p in PROMPTS:
    r = requests.post("http://localhost:11434/api/generate",
                      json={"model": MODEL, "prompt": p, "stream": False})
    tokens += r.json().get("eval_count", 0)

elapsed = time.time() - start
print(f"50 prompts | {tokens} tokens | {tokens/elapsed:.1f} tok/s | {elapsed:.1f}s")
EOF
```

**Pass criteria:** ≥ 1000 tok/s, no OOM errors

---

## Step 2 — Image generation: ComfyUI API (GPU 0, ~5 min)

```bash
# Submit a simple txt2img job via ComfyUI API
python3 - <<'EOF'
import requests, json, time, uuid

WF = {
  "3": {"class_type": "KSampler",
        "inputs": {"seed": 42, "steps": 20, "cfg": 7.0,
                   "sampler_name": "euler", "scheduler": "normal",
                   "denoise": 1.0, "model": ["4", 0],
                   "positive": ["6", 0], "negative": ["7", 0],
                   "latent_image": ["5", 0]}},
  "4": {"class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "v1-5-pruned-emaonly.safetensors"}},
  "5": {"class_type": "EmptyLatentImage",
        "inputs": {"width": 512, "height": 512, "batch_size": 1}},
  "6": {"class_type": "CLIPTextEncode",
        "inputs": {"text": "a photo of an astronaut riding a horse on mars",
                   "clip": ["4", 1]}},
  "7": {"class_type": "CLIPTextEncode",
        "inputs": {"text": "ugly, blurry", "clip": ["4", 1]}},
  "8": {"class_type": "VAEDecode",
        "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
  "9": {"class_type": "SaveImage",
        "inputs": {"filename_prefix": "smoke-test", "images": ["8", 0]}}
}

cid = str(uuid.uuid4())
r = requests.post("http://localhost:8188/prompt",
                  json={"prompt": WF, "client_id": cid})
pid = r.json().get("prompt_id")
print(f"Queued prompt {pid}")

# Poll until done
while True:
    h = requests.get(f"http://localhost:8188/history/{pid}").json()
    if pid in h:
        outputs = h[pid]["outputs"]
        print(f"Done. Output: {json.dumps(outputs, indent=2)[:200]}")
        break
    time.sleep(2)
EOF
```

**Pass criteria:** Image saved to `/data/outputs/comfyui/`, no CUDA errors

---

## Step 3 — Generate synthetic fine-tune dataset (CPU, ~1 min)

```bash
mkdir -p /data/datasets/text/formatted

python3 - <<'EOF'
import json, random, pathlib

templates = [
    ("What is {topic}?", "A {topic} is a fundamental concept in AI."),
    ("Explain {topic} briefly.", "{topic} refers to the process of ..."),
    ("Define {topic}.", "{topic}: a key principle in machine learning."),
]
topics = ["attention", "backpropagation", "tokenization", "FSDP",
          "LoRA", "quantization", "gradient checkpointing", "KV cache",
          "speculative decoding", "RLHF", "DPO", "SFT", "RAG", "embeddings"]

out = pathlib.Path("/data/datasets/text/formatted/train.jsonl")
rows = []
for _ in range(200):
    t = random.choice(topics)
    instr, resp = random.choice(templates)
    rows.append({"instruction": instr.format(topic=t),
                 "input": "", "output": resp.format(topic=t)})

out.write_text("\n".join(json.dumps(r) for r in rows))
print(f"Wrote {len(rows)} examples to {out}")
EOF
```

---

## Step 4 — Training: Axolotl smoke test (all 4 GPUs, ~15 min)

```bash
# Run 20 training steps with a tiny LoRA on Qwen2.5-32B across all 4 GPUs
AXOLOTL_CONFIG=smoke_test.yml \
docker compose -f docker/compose.training.yml --profile training up axolotl

# Tail logs in another terminal
docker logs -f axolotl
```

**Pass criteria:**
- Steps 1–20 complete without OOM or NCCL errors
- Checkpoint saved to `/data/checkpoints/axolotl/smoke-test-001/`
- All 4 GPUs show >0% utilization during training (check Grafana or `nvidia-smi`)

---

## Step 5 — Monitoring validation (~2 min)

Open `http://<workstation>:8800` → Monitor panel.

Verify:
- GPU Telemetry: all 4 GPU cards show temp, VRAM used, utilization
- System Metrics: CPU heatmap active, RAM reading correct (~12 GB used)
- Grafana at `:3001` — GPU dashboard shows training spike in steps 1–20
- Prometheus at `:9091/targets` — all scrape targets healthy

---

## Pass/Fail Summary

| Check | Pass Criterion |
|-------|---------------|
| Ollama throughput | ≥ 1000 tok/s |
| ComfyUI image gen | Image saved, no CUDA error |
| Dataset gen | 200 examples in train.jsonl |
| Axolotl 20 steps | Completes without OOM/NCCL error |
| VRAM reporting | All 4 GPUs show correct values in UI |
| Grafana metrics | Training spike visible during Step 4 |
