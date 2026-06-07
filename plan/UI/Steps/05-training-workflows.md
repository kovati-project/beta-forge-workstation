# KOVATI OS — Component Spec 05
## Training Workflows
*Text LoRA wizard · Image LoRA wizard · Live training view*

---

## 1. Purpose

The Training panel guides operators through launching fine-tuning jobs without requiring direct access to Axolotl configs or Kohya_ss UI. It presents a structured wizard that captures the most common configuration parameters, validates GPU availability, enforces the correct profile switch, and streams live training output.

Two distinct workflows exist: **Text LoRA** (Axolotl or Unsloth, targeting LLMs) and **Image LoRA** (Kohya_ss, targeting diffusion models). They share the step-flow UI structure but differ in all parameter specifics.

---

## 2. Layout

### Mode Selector (initial state)

```
┌──────────────────────────┐  ┌──────────────────────────┐
│          ◉               │  │          ◈               │
│                          │  │                          │
│      Text Model          │  │      Image Model         │
│   LLM LoRA via           │  │   Diffusion LoRA via     │
│   Axolotl / Unsloth      │  │   Kohya_ss               │
│                          │  │                          │
│  [GPU 0+1+2+3 amber]     │  │  [GPU 1+2 purple]        │
│                          │  │                          │
└──────────────────────────┘  └──────────────────────────┘
```

Two equal-width cards. Clicking one selects it (border highlights with the appropriate accent color) and reveals the wizard below.

---

## 3. Step Progress Indicator

```
[1 Dataset]━━[2 Base Model]━━[3 LoRA Config]━━[4 GPU Assign]━━[5 Launch]
```

- Completed steps: `--green` border-bottom, green text
- Current step: `--cyan` border-bottom, cyan text
- Future steps: `--border` border-bottom, `--text3` text
- 10px, letter-spacing .3px

Step state is local to the component (`useState`). Validation must pass before advancing to the next step.

---

## 4. Text LoRA Workflow (Axolotl / Unsloth)

### Step 1 — Dataset

```
┌──────────────────────────────────────────────────────────┐
│ DATASET SOURCE                                           │
│                                                          │
│  ○ Upload .jsonl file                                   │
│  ● Browse MinIO /data/training/text/formatted/          │
│                                                          │
│ ┌──────────────────────────────────────────────────┐   │
│ │  Name                  │  Records  │  Modified    │   │
│ │  alpaca-52k.jsonl       │  52,002   │  2d ago      │   │
│ │  custom-instruct-3k.jsonl│ 3,108    │  12d ago     │   │
│ └──────────────────────────────────────────────────┘   │
│                                                          │
│ FORMAT PREVIEW (first 3 rows):                           │
│  instruction | input | output                            │
│  "Explain..." | ""   | "Sure..."                        │
│  "Write..."   | "..." | "Here..."                       │
└──────────────────────────────────────────────────────────┘
```

**Upload mode:** `<input type="file" accept=".jsonl">` + drag-drop zone. On file select, parse first 3 rows client-side for preview (JSONL → JSON.parse per line). Show record count.

**Browse mode:** `GET /api/storage/buckets/training/text/formatted` → file list table. Click to select. Preview fetched from `GET /api/storage/preview?path={path}&n=3`.

**Validation:** File must be valid JSONL with `instruction`, `input`, `output` keys. Show inline error if malformed.

---

### Step 2 — Base Model

```
┌──────────────────────────────────────────────────────────┐
│ BASE MODEL                                               │
│                                                          │
│  [Qwen2.5-32B (recommended)               ▾]            │
│  [Qwen2.5-7B                                ]            │
│  [Qwen3-30B-A3B                             ]            │
│                                                          │
│  VRAM estimate: ~65 GB for QLoRA (4-bit base)            │
│  Available: 96 GB via training-lora-text profile ✓       │
│                                                          │
│  ⓘ Default: Qwen2.5-32B — pre-configured in             │
│     axolotl/config.yml                                  │
└──────────────────────────────────────────────────────────┘
```

Model list populated from `GET /api/models` (merged Ollama + vLLM + MinIO checkpoints).

VRAM estimate is static per model (from a hardcoded map — not computed dynamically):
```js
const VRAM_ESTIMATES = {
  'qwen2.5-32b': 65,
  'qwen2.5-7b':  8,
  'qwen3-30b-a3b': 20,
};
```

---

### Step 3 — LoRA Config

Two-column form layout.

| Parameter | Control | Default | Range |
|-----------|---------|---------|-------|
| LoRA Rank | Range slider | 64 | 8–128 |
| LoRA Alpha | Range slider | 128 | 16–256 |
| Learning Rate | Text input | `2e-5` | — |
| Epochs | Number input | 3 | 1–20 |
| Micro Batch Size | Number input | 2 | 1–8 |
| Gradient Accumulation | Number input | 4 | 1–16 |

Range sliders show current value as a numeric readout between the min and max labels (updates live on `oninput`).

**Effective batch size** computed and displayed: `micro_batch × grad_accum × num_gpus` = `2 × 4 × 4 = 32`

---

### Step 4 — GPU Assignment

```
┌──────────────────────────────────────────────────────────┐
│ GPU ASSIGNMENT                                           │
│                                                          │
│  Recommended: training-lora-text                         │
│  All 4 GPUs · FSDP · 90 GB VRAM                         │
│                                                          │
│  [0■] [1■] [2■] [3■]  ← mini GPU diagram, amber         │
│  Bridge A ━━━━━ Bridge B ━━━━━                           │
│                                                          │
│  ⚠ This will stop all inference services:                │
│    vllm-pair-a, ollama                                   │
│                                                          │
│  □ I understand active inference will be interrupted     │
│                                                          │
│  Alternative: training-lora-image is not available       │
│  (requires text model, not image LoRA path)             │
└──────────────────────────────────────────────────────────┘
```

Profile switch warning: list all currently-running services that will be stopped. Checkbox must be checked to enable "Next".

---

### Step 5 — Launch

**Pre-launch state:**
```
[Start Training] button

Summary:
  Model: Qwen2.5-32B-Instruct
  Dataset: alpaca-52k.jsonl (52,002 records)
  LoRA r=64 α=128 · LR=2e-5 · 3 epochs
  GPU: training-lora-text (all 4, FSDP)
  Est. duration: ~2h 30m
```

Est. duration is static estimate based on model size × dataset size × epochs (rough formula, not guaranteed).

**"Start Training" action:**
1. `POST /activate/training-lora-text` → wait for `switching: false`
2. `POST /api/training/start` with config payload
3. Transition to Live Training View

---

## 5. Image LoRA Workflow (Kohya_ss)

### Step 1 — Dataset

Upload zip of images or browse MinIO `/data/training/images/`.

Thumbnail grid preview (4-per-row, 80px thumbnails) for the selected folder.

**Caption file check:** Warn if `.txt` caption files are missing alongside images. "Open Label Studio →" button (starts Label Studio container if stopped, opens `:8081` in new tab).

### Step 2 — Annotation (Optional)

```
Label Studio integration for image captioning/tagging.
[Open Label Studio ↗]  ← starts container, opens new tab
Service status: [● running :8081]
```

If Label Studio is stopped, clicking the button calls `POST /api/services/label-studio/start` first, waits for running status, then opens the URL.

### Step 3 — Training Config

| Parameter | Control | Default |
|-----------|---------|---------|
| Base model | Select | SDXL 1.0 |
| LoRA network rank | Number | 32 |
| Training steps | Number | 1000 |
| Learning rate | Text | `1e-4` |
| Resolution | Select | 1024 / 768 / 512 |
| Clip skip | Number | 2 |

### Step 4 — GPU Assignment

Auto-selects `training-lora-image` (GPU 1+2, NVLink B). Note that GPU 0+3 remain free for inference — show this as a benefit: "GPU 0+3 remain available for inference-pair-a".

### Step 5 — Launch

Two options:

**Option A — Guided:** Submit config to Kohya API and stream logs inline (same Live Training View as text LoRA).

**Option B — Native UI:** `POST /activate/training-lora-image` (if needed) then open Kohya_ss at `:7860` in new tab. No log streaming in the UI.

Button layout:
```
[Launch Guided] [Open Kohya_ss UI ↗]
```

---

## 6. Live Training View

Replaces the wizard after training starts. Persists until the operator navigates away (training continues in background).

```
┌──────────────────────────────────────────────────────────┐
│ Training: Qwen2.5-32B · LoRA rank 64         epoch 1/3  │
├──────────────────────────────────────────────────────────┤
│ EPOCH PROGRESS  [████░░░░░░░░░░░░░░░░░░] 1/3            │
│ STEP           [████████░░░░░░░░░░░░░] 842/3200         │
│                                                          │
│ GPU VRAM (all 4):                                        │
│ GPU0 [███████████████████░] 23.1/24 GB                  │
│ GPU1 [██████████████████░░] 22.5/24 GB                  │
│ GPU2 [██████████████████░░] 22.8/24 GB                  │
│ GPU3 [█████████████████░░░] 22.3/24 GB                  │
│                                                          │
│ LOSS: 1.5211  GRAD NORM: 0.578  LR: 2e-5  ETA: 2h 14m  │
│                                                          │
│ ┌ LOG OUTPUT ─────────────────────────────────────────┐ │
│ │ 14:28:33 [INFO]  step 842 · loss: 1.5211 · ETA 2h14m│ │
│ │ 14:26:52 [WARN]  GPU0 temp 81°C · threshold 85°C     │ │
│ │ 14:24:11 [INFO]  step 500 · loss: 1.7043             │ │
│ └──────────────────────────────────────────────────────┘ │
│                                                          │
│ [Export Checkpoint]  [Stop Training]                     │
└──────────────────────────────────────────────────────────┘
```

### Log Streaming

```js
// SSE connection
const es = new EventSource('/api/services/axolotl/logs/stream');
es.onmessage = (e) => {
  setLines(prev => [...prev.slice(-199), e.data]);
  // Auto-parse loss/step from line
  const match = e.data.match(/step (\d+).*loss: ([\d.]+)/);
  if (match) setMetrics({ step: +match[1], loss: +match[2] });
};
```

Log area: `height: 160px`, `overflow-y: auto`, auto-scroll to bottom unless user has manually scrolled up (detect with scroll event).

### Live Metrics

Parsed from log lines (regex):
- `step N/Y` → step progress
- `loss: X.XXXX` → current loss
- `grad_norm: X.XXX` → gradient norm
- `ETA Xh Xm` → estimated time remaining

GPU VRAM bars: from `GET /status` 3s poll (same data as Dashboard).

### Stop Training

`Btn variant="red"` → confirmation dialog → `POST /api/training/stop` → wait for container to reach stopped state → navigate back to mode selector.

### Export Checkpoint

`Btn variant="gray"` → `POST /api/training/export` → MinIO path `/data/checkpoints/text/{run-name}/`. Shows export progress and final path.

---

## 7. Training API Endpoints

| Action | Endpoint | Method | Payload |
|--------|----------|--------|---------|
| Start text training | `/api/training/start` | POST | `{engine, model, dataset_path, lora_config}` |
| Stop training | `/api/training/stop` | POST | — |
| Training status | `/api/training/status` | GET | — |
| Export checkpoint | `/api/training/export` | POST | `{run_name}` |
| Log stream | `/api/services/{name}/logs/stream` | GET (SSE) | — |

### Training Start Payload

```json
{
  "engine": "axolotl",
  "model": "qwen2.5-32b-instruct",
  "dataset_path": "/data/training/text/formatted/alpaca-52k.jsonl",
  "lora_config": {
    "rank": 64,
    "alpha": 128,
    "lr": "2e-5",
    "epochs": 3,
    "micro_batch": 2,
    "grad_accum": 4
  }
}
```

---

## 8. State Persistence

Training state (running/not running, current metrics) is stored in AppContext so navigating away and returning shows the live view if training is still active. On mount, `GET /api/training/status` determines whether to show the wizard or the live view.
