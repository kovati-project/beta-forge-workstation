# Step 05 — Training Workflows

> **Prerequisites:** Steps 01–04 complete. Read `plan/UI/GHC-Plan/00-overview.md`.
> **Reference spec:** `plan/UI/Steps/05-training-workflows.md`

---

## Goal

Implement the Training panel (`/#/training`):

1. **Mode selector** — Text LoRA (Axolotl) vs Image LoRA (Kohya_ss) cards
2. **Step wizard** — 5-step guided flow for each mode
3. **Live training view** — SSE log stream, live metrics, GPU VRAM bars
4. **Training state persistence** — AppContext so navigating away and returning restores live view

**Spec note:** Kohya_ss must open in a **new tab** (`window.open`). No iframe embeds. This is the canonical decision per `00-overview.md §Standing Rules`.

All training API endpoints (`/api/training/*`) do not exist yet — stubbed with mock data until Step 10.

---

## Deliverables

### 1. AppContext update

Add training state to `initialState` and the reducer.

```js
// In initialState:
training: {
  active: false,
  engine: null,         // 'axolotl' | 'kohya' | null
  model: null,
  dataset: null,
  step: 0,
  totalSteps: 0,
  epoch: 0,
  totalEpochs: 0,
  loss: null,
  gradNorm: null,
  eta: null,
},
```

```js
// In reducer:
case 'SET_TRAINING_STATUS':
  return { ...state, training: { ...state.training, ...action.payload } };
```

---

### 2. Mock data constants

Create `ui/src/data/trainingMock.js`:

```js
// TODO Step 10: replace with live API responses

export const MOCK_TEXT_DATASETS = [
  { name: 'alpaca-52k.jsonl',         size: '84 MB',  modified: '2d ago',  records: 52002 },
  { name: 'custom-instruct-3k.jsonl', size: '12 MB',  modified: '12d ago', records: 3108 },
  { name: 'openhermes-2.5-subset.jsonl', size: '41 MB', modified: '8d ago', records: 24110 },
];

export const MOCK_IMAGE_DATASETS = [
  { name: 'char-concept-v2.zip', size: '1.2 GB', modified: '5d ago',  imageCount: 144 },
  { name: 'style-dataset-v1.zip', size: '890 MB', modified: '18d ago', imageCount: 96 },
];

export const MOCK_TEXT_MODELS = [
  { id: 'qwen2.5-32b-instruct', label: 'Qwen2.5-32B (recommended)' },
  { id: 'qwen2.5-7b-instruct',  label: 'Qwen2.5-7B' },
  { id: 'qwen3-30b-a3b',        label: 'Qwen3-30B-A3B' },
  { id: 'llama-3.1-8b',         label: 'Llama 3.1 8B' },
];

export const MOCK_IMAGE_BASE_MODELS = [
  { id: 'sdxl-1.0',  label: 'SDXL 1.0 (recommended)' },
  { id: 'sd-1.5',    label: 'Stable Diffusion 1.5' },
  { id: 'flux-dev',  label: 'FLUX.1-dev' },
];

export const VRAM_ESTIMATES = {
  'qwen2.5-32b-instruct': 65,
  'qwen2.5-7b-instruct':   8,
  'qwen3-30b-a3b':         20,
  'llama-3.1-8b':          10,
};

export const MOCK_TRAINING_LOG = [
  '14:28:33 [INFO]  step 842 · loss: 1.5211 · ETA 2h14m',
  '14:26:52 [WARN]  GPU0 temp 81°C · threshold 85°C',
  '14:24:11 [INFO]  step 500 · loss: 1.7043',
  '14:21:30 [INFO]  step 400 · loss: 1.8812',
  '14:18:44 [INFO]  step 300 · loss: 2.1037',
];

export const MOCK_TRAINING_STATUS = {
  active: false,
  engine: null,
  step: 0,
  totalSteps: 3200,
  epoch: 0,
  totalEpochs: 3,
  loss: null,
  gradNorm: null,
  eta: null,
};
```

---

### 3. `ui/src/components/StepIndicator.jsx`

Reusable step progress bar. Used by both Text and Image wizards.

```jsx
import './StepIndicator.css';

export function StepIndicator({ steps, currentStep }) {
  return (
    <div className="step-indicator">
      {steps.map((label, i) => {
        const state = i < currentStep ? 'done' : i === currentStep ? 'current' : 'future';
        return (
          <div key={i} className={`step-item step-${state}`}>
            <div className="step-label">{i + 1} {label}</div>
            {i < steps.length - 1 && <div className="step-connector" />}
          </div>
        );
      })}
    </div>
  );
}
```

```css
/* StepIndicator.css */
@import '../tokens.css';

.step-indicator {
  display: flex;
  align-items: center;
  gap: 0;
  font-size: 10px;
  letter-spacing: .3px;
  margin-bottom: 16px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 0;
}

.step-label {
  padding: 4px 8px;
  border-bottom: 2px solid transparent;
  white-space: nowrap;
}

.step-done    .step-label { color: var(--green); border-color: var(--green); }
.step-current .step-label { color: var(--cyan);  border-color: var(--cyan); font-weight: 600; }
.step-future  .step-label { color: var(--text3); border-color: var(--border); }

.step-connector {
  width: 24px;
  height: 1px;
  background: var(--border);
  flex-shrink: 0;
}
```

---

### 4. `ui/src/pages/Training.jsx`

Main page component. Handles mode selection and delegates to sub-wizards.

```jsx
import { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { TextLoraWizard }  from './training/TextLoraWizard';
import { ImageLoraWizard } from './training/ImageLoraWizard';
import { LiveTrainingView } from './training/LiveTrainingView';
import { MOCK_TRAINING_STATUS } from '../data/trainingMock';
import './Training.css';

export function Training() {
  const { state, dispatch } = useApp();
  const [mode, setMode] = useState(null); // 'text' | 'image' | null

  // On mount, check if training is already active
  useEffect(() => {
    fetch('/api/training/status')
      .then(r => r.json())
      .then(data => {
        if (data.active) {
          dispatch({ type: 'SET_TRAINING_STATUS', payload: data });
          setMode(data.engine === 'kohya' ? 'image' : 'text');
        }
      })
      .catch(() => {
        // API not ready yet — use mock (not running)
        dispatch({ type: 'SET_TRAINING_STATUS', payload: MOCK_TRAINING_STATUS });
      });
  }, []);

  // If training is active, show live view regardless of mode
  if (state.training.active) {
    return <LiveTrainingView />;
  }

  if (mode === 'text')  return <TextLoraWizard  onBack={() => setMode(null)} />;
  if (mode === 'image') return <ImageLoraWizard onBack={() => setMode(null)} />;

  // Mode selector
  return (
    <div className="training-mode-selector">
      <ModeCard
        icon="◉"
        title="Text Model"
        subtitle="LLM LoRA via Axolotl / Unsloth"
        gpuLabel="GPU 0+3 · amber"
        accent="amber"
        onClick={() => setMode('text')}
      />
      <ModeCard
        icon="◈"
        title="Image Model"
        subtitle="Diffusion LoRA via Kohya_ss"
        gpuLabel="GPU 1+2 · purple"
        accent="purple"
        onClick={() => setMode('image')}
      />
    </div>
  );
}

function ModeCard({ icon, title, subtitle, gpuLabel, accent, onClick }) {
  return (
    <button className={`mode-card mode-card-${accent}`} onClick={onClick}>
      <span className={`mode-card-icon mode-icon-${accent}`}>{icon}</span>
      <span className="mode-card-title">{title}</span>
      <span className="mode-card-subtitle">{subtitle}</span>
      <span className={`mode-card-gpu tag tag-${accent}`}>{gpuLabel}</span>
    </button>
  );
}
```

```css
/* Training.css */
@import '../tokens.css';

.training-mode-selector {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.mode-card {
  flex: 1;
  min-width: 220px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  font-family: var(--mono);
  text-align: left;
  transition: border-color .2s, background .2s;
}

.mode-card:hover {
  background: var(--surface2);
}

.mode-card-amber:hover { border-color: var(--amber); }
.mode-card-purple:hover { border-color: var(--purple); }

.mode-card-icon {
  font-size: 22px;
}

.mode-icon-amber  { color: var(--amber); }
.mode-icon-purple { color: var(--purple); }

.mode-card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}

.mode-card-subtitle {
  font-size: 10px;
  color: var(--text3);
}

.mode-card-gpu {
  margin-top: 4px;
}
```

---

### 5. `ui/src/pages/training/TextLoraWizard.jsx`

5-step wizard. State is entirely local (`useState`). Validated before advancing.

```jsx
import { useState } from 'react';
import { useApp } from '../../context/AppContext';
import { StepIndicator } from '../../components/StepIndicator';
import { Panel } from '../../components/Panel';
import { Btn } from '../../components/Btn';
import { VBar } from '../../components/VBar';
import {
  MOCK_TEXT_DATASETS, MOCK_TEXT_MODELS,
  VRAM_ESTIMATES,
} from '../../data/trainingMock';
import './TextLoraWizard.css';

const STEPS = ['Dataset', 'Base Model', 'LoRA Config', 'GPU Assign', 'Launch'];

// Static estimate: rough formula, not guaranteed
function estimateDuration(modelId, records, epochs) {
  const gpuHoursPerEpoch = (VRAM_ESTIMATES[modelId] ?? 20) / 10;
  const epochHours = (records / 10000) * gpuHoursPerEpoch;
  const total = epochHours * epochs;
  if (total < 1) return `~${Math.round(total * 60)}m`;
  return `~${total.toFixed(1)}h`;
}

export function TextLoraWizard({ onBack }) {
  const { state, dispatch } = useApp();
  const [step, setStep] = useState(0);
  const [error, setError] = useState(null);

  // Wizard form state
  const [datasetSource, setDatasetSource] = useState('browse'); // 'browse' | 'upload'
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [uploadPreview, setUploadPreview] = useState(null);
  const [selectedModel, setSelectedModel] = useState(MOCK_TEXT_MODELS[0].id);
  const [loraConfig, setLoraConfig] = useState({
    rank: 64, alpha: 128, lr: '2e-5', epochs: 3, microBatch: 2, gradAccum: 4,
  });
  const [profileAcknowledged, setProfileAcknowledged] = useState(false);
  const [launching, setLaunching] = useState(false);
  const [waitingForSwitch, setWaitingForSwitch] = useState(false);

  function handleNext() {
    setError(null);
    if (step === 0 && !selectedDataset) { setError('Select or upload a dataset.'); return; }
    if (step === 3 && !profileAcknowledged && state.runningServices.length > 0) {
      setError('Acknowledge the service interruption to continue.');
      return;
    }
    setStep(s => s + 1);
  }

  function handleFileUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const lines = ev.target.result.split('\n').filter(Boolean);
      try {
        const preview = lines.slice(0, 3).map(l => JSON.parse(l));
        if (!preview[0].instruction) throw new Error('Missing "instruction" key');
        setUploadPreview({ name: file.name, records: lines.length, rows: preview });
        setSelectedDataset({ name: file.name, records: lines.length, source: 'upload' });
      } catch {
        setError('Invalid JSONL: must have "instruction", "input", "output" keys.');
      }
    };
    reader.readAsText(file.slice(0, 50000)); // read first 50KB for preview
  }

  async function handleLaunch() {
    setError(null);
    setLaunching(true);

    // Step 1: activate profile
    try {
      const res = await fetch('/activate/training-lora-text', { method: 'POST' });
      if (!res.ok) throw new Error(`Activate failed: HTTP ${res.status}`);
    } catch (e) {
      setError(e.message);
      setLaunching(false);
      return;
    }

    // Step 2: wait for switching: false (poll state.switching via useEffect below)
    setWaitingForSwitch(true);
    // The useEffect below watches state.switching and fires startTraining when ready
  }

  // Watch for profile switch completion, then POST /api/training/start
  // This useEffect fires whenever state.switching changes
  React.useEffect(() => {
    if (!waitingForSwitch || state.switching) return;
    setWaitingForSwitch(false);
    startTraining();
  }, [state.switching, waitingForSwitch]);

  async function startTraining() {
    const payload = {
      engine: 'axolotl',
      model: selectedModel,
      dataset_path: selectedDataset?.name ?? '',
      lora_config: {
        rank: loraConfig.rank,
        alpha: loraConfig.alpha,
        lr: loraConfig.lr,
        epochs: loraConfig.epochs,
        micro_batch: loraConfig.microBatch,
        grad_accum: loraConfig.gradAccum,
      },
    };

    try {
      const res = await fetch('/api/training/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`Start failed: HTTP ${res.status}`);
      dispatch({
        type: 'SET_TRAINING_STATUS',
        payload: {
          active: true, engine: 'axolotl',
          model: selectedModel,
          dataset: selectedDataset?.name,
          totalEpochs: loraConfig.epochs,
        },
      });
    } catch (e) {
      // TODO Step 10: real API not available yet — simulate launch for UI testing
      dispatch({
        type: 'SET_TRAINING_STATUS',
        payload: {
          active: true, engine: 'axolotl',
          model: selectedModel,
          dataset: selectedDataset?.name ?? 'mock-dataset.jsonl',
          totalEpochs: loraConfig.epochs, totalSteps: 3200,
        },
      });
    } finally {
      setLaunching(false);
    }
  }

  const vramEst  = VRAM_ESTIMATES[selectedModel] ?? '—';
  const effectiveBatch = loraConfig.microBatch * loraConfig.gradAccum * 4; // 4 GPUs

  return (
    <div className="text-lora-wizard">
      <div className="wizard-header">
        <button className="wizard-back" onClick={onBack}>← Back</button>
        <span className="wizard-title">Text Model LoRA · Axolotl</span>
      </div>

      <StepIndicator steps={STEPS} currentStep={step} />

      {error && <div className="wizard-error">⚠ {error}</div>}

      <Panel>
        {/* ── Step 0: Dataset ─────────────────────────────── */}
        {step === 0 && (
          <div className="wizard-step">
            <div className="step-source-toggle">
              <button
                className={`source-btn ${datasetSource === 'browse' ? 'source-btn-active' : ''}`}
                onClick={() => setDatasetSource('browse')}
              >Browse MinIO</button>
              <button
                className={`source-btn ${datasetSource === 'upload' ? 'source-btn-active' : ''}`}
                onClick={() => setDatasetSource('upload')}
              >Upload .jsonl</button>
            </div>

            {datasetSource === 'browse' ? (
              <table className="dataset-table">
                <thead>
                  <tr><th>Name</th><th>Records</th><th>Modified</th><th></th></tr>
                </thead>
                <tbody>
                  {MOCK_TEXT_DATASETS.map(d => (
                    <tr
                      key={d.name}
                      className={selectedDataset?.name === d.name ? 'row-selected' : ''}
                      onClick={() => setSelectedDataset(d)}
                    >
                      <td>{d.name}</td>
                      <td>{d.records.toLocaleString()}</td>
                      <td>{d.modified}</td>
                      <td>{selectedDataset?.name === d.name && '✓'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="upload-zone" onDragOver={e => e.preventDefault()}
                onDrop={e => { e.preventDefault(); handleFileUpload({ target: { files: e.dataTransfer.files } }); }}>
                <span>Drop .jsonl here or</span>
                <label className="upload-label">
                  Browse
                  <input type="file" accept=".jsonl" onChange={handleFileUpload} hidden />
                </label>
              </div>
            )}

            {(uploadPreview ?? selectedDataset) && (
              <div className="dataset-preview">
                <div className="preview-header">FORMAT PREVIEW (first 3 rows)</div>
                <div className="preview-cols">instruction · input · output</div>
              </div>
            )}
          </div>
        )}

        {/* ── Step 1: Base Model ──────────────────────────── */}
        {step === 1 && (
          <div className="wizard-step">
            <div className="step-label-heading">BASE MODEL</div>
            <select
              className="model-select"
              value={selectedModel}
              onChange={e => setSelectedModel(e.target.value)}
            >
              {MOCK_TEXT_MODELS.map(m => (
                <option key={m.id} value={m.id}>{m.label}</option>
              ))}
            </select>
            <div className="model-vram-info">
              VRAM estimate: ~{vramEst} GB for QLoRA (4-bit base)
              <span className="vram-avail"> · 96 GB via training-lora-text ✓</span>
            </div>
          </div>
        )}

        {/* ── Step 2: LoRA Config ─────────────────────────── */}
        {step === 2 && (
          <div className="wizard-step lora-config-grid">
            <SliderField label="LoRA Rank" value={loraConfig.rank} min={8} max={128}
              onChange={v => setLoraConfig(c => ({ ...c, rank: v }))} />
            <SliderField label="LoRA Alpha" value={loraConfig.alpha} min={16} max={256}
              onChange={v => setLoraConfig(c => ({ ...c, alpha: v }))} />
            <NumberField label="Learning Rate" value={loraConfig.lr} type="text"
              onChange={v => setLoraConfig(c => ({ ...c, lr: v }))} />
            <NumberField label="Epochs" value={loraConfig.epochs} min={1} max={20}
              onChange={v => setLoraConfig(c => ({ ...c, epochs: +v }))} />
            <NumberField label="Micro Batch" value={loraConfig.microBatch} min={1} max={8}
              onChange={v => setLoraConfig(c => ({ ...c, microBatch: +v }))} />
            <NumberField label="Grad Accum" value={loraConfig.gradAccum} min={1} max={16}
              onChange={v => setLoraConfig(c => ({ ...c, gradAccum: +v }))} />
            <div className="effective-batch">
              Effective batch size: {loraConfig.microBatch} × {loraConfig.gradAccum} × 4 GPUs = <strong>{effectiveBatch}</strong>
            </div>
          </div>
        )}

        {/* ── Step 3: GPU Assignment ──────────────────────── */}
        {step === 3 && (
          <div className="wizard-step">
            <div className="step-label-heading">GPU ASSIGNMENT</div>
            <div className="gpu-assign-profile">
              <span className="assign-profile-name">training-lora-text</span>
              <span className="assign-profile-desc">All 4 GPUs · FSDP · 96 GB VRAM</span>
            </div>
            {/* Mini GPU diagram: reuse the box style from ProfileCard */}
            <div className="assign-mini-gpus">
              {[0,1,2,3].map(i => (
                <div key={i} className="mini-gpu-box mini-gpu-amber">{i}</div>
              ))}
            </div>
            {state.runningServices.length > 0 && (
              <div className="assign-warning">
                <div className="assign-warning-msg">
                  ⚠ This will stop all inference services:
                  <span className="assign-service-list"> {state.runningServices.join(', ')}</span>
                </div>
                <label className="assign-checkbox">
                  <input
                    type="checkbox"
                    checked={profileAcknowledged}
                    onChange={e => setProfileAcknowledged(e.target.checked)}
                  />
                  I understand active inference will be interrupted
                </label>
              </div>
            )}
          </div>
        )}

        {/* ── Step 4: Launch ──────────────────────────────── */}
        {step === 4 && (
          <div className="wizard-step">
            <div className="step-label-heading">SUMMARY</div>
            <div className="launch-summary">
              <div><span>Model</span><span>{MOCK_TEXT_MODELS.find(m => m.id === selectedModel)?.label}</span></div>
              <div><span>Dataset</span><span>{selectedDataset?.name ?? '—'} ({selectedDataset?.records?.toLocaleString()} records)</span></div>
              <div><span>LoRA</span><span>r={loraConfig.rank} α={loraConfig.alpha} · LR={loraConfig.lr} · {loraConfig.epochs} epochs</span></div>
              <div><span>GPU</span><span>training-lora-text (all 4, FSDP)</span></div>
              <div><span>Est. duration</span><span>{estimateDuration(selectedModel, selectedDataset?.records ?? 10000, loraConfig.epochs)}</span></div>
            </div>
          </div>
        )}
      </Panel>

      {/* Nav buttons */}
      <div className="wizard-nav">
        {step > 0 && (
          <Btn variant="gray" size="sm" onClick={() => setStep(s => s - 1)} disabled={launching}>
            ← Back
          </Btn>
        )}
        {step < STEPS.length - 1 ? (
          <Btn variant="cyan" size="sm" onClick={handleNext}>
            Next →
          </Btn>
        ) : (
          <Btn
            variant="amber"
            size="md"
            onClick={handleLaunch}
            disabled={launching || waitingForSwitch}
          >
            {waitingForSwitch ? 'Switching profile…' : launching ? 'Starting…' : 'Start Training'}
          </Btn>
        )}
      </div>
    </div>
  );
}

// Small helper form controls
function SliderField({ label, value, min, max, onChange }) {
  return (
    <div className="form-field">
      <label className="form-label">{label}</label>
      <div className="slider-row">
        <span className="slider-min">{min}</span>
        <input type="range" min={min} max={max} value={value}
          onChange={e => onChange(+e.target.value)} />
        <span className="slider-max">{max}</span>
        <span className="slider-val">{value}</span>
      </div>
    </div>
  );
}

function NumberField({ label, value, min, max, type = 'number', onChange }) {
  return (
    <div className="form-field">
      <label className="form-label">{label}</label>
      <input
        className="form-input"
        type={type}
        value={value}
        min={min}
        max={max}
        onChange={e => onChange(e.target.value)}
      />
    </div>
  );
}
```

Also add `import React from 'react'` at the top (for `React.useEffect` in the component).
Or import `useEffect` explicitly — whichever pattern is consistent with the rest of the codebase.

---

### 6. `ui/src/pages/training/ImageLoraWizard.jsx`

Follows the same structural pattern as TextLoraWizard. 5 steps: Dataset, Annotation, Config, GPU Assignment, Launch.

**Key differences from TextLoraWizard:**

**Step 0 — Dataset:** Thumbnail grid for image folders (use `<img>` tags). Warn if `.txt` captions are missing. "Open Label Studio →" button starts the container then opens `http://{host}:8081` in a new tab.

**Step 1 — Annotation (Optional):** Shows Label Studio service status. If stopped, `POST /api/services/label-studio/start` then open in new tab. Mark step as completable even if Label Studio is stopped (annotation is optional).

**Step 2 — Config:**
```js
const [config, setConfig] = useState({
  baseModel: 'sdxl-1.0',
  rank: 32,
  steps: 1000,
  lr: '1e-4',
  resolution: '1024',
  clipSkip: 2,
});
```

**Step 3 — GPU Assignment:** Auto-selects `training-lora-image` (GPU 1+2). Show benefit note: "GPU 0+3 remain available for inference-pair-a". No acknowledgment checkbox needed (inference can continue on GPU 0+3).

**Step 4 — Launch:** Two buttons:
- `[Launch Guided]` — `POST /activate/training-lora-image` (if needed) → `POST /api/training/start` with `engine: 'kohya'`
- `[Open Kohya_ss UI ↗]` — activate profile then `window.open('http://{host}:7862', '_blank')`

"Open Kohya_ss UI ↗" is the **secondary** action (`Btn variant="gray"`). "Launch Guided" is primary (`Btn variant="purple"`).

Use MOCK_IMAGE_DATASETS and MOCK_IMAGE_BASE_MODELS from `trainingMock.js`.

For the thumbnail grid: mock with placeholder `<div>` boxes (80×80px, `--surface3` background, image filename below) since real MinIO URLs require the backend.

---

### 7. `ui/src/pages/training/LiveTrainingView.jsx`

Shown when `state.training.active === true`.

```jsx
import { useState, useEffect, useRef } from 'react';
import { useApp } from '../../context/AppContext';
import { Panel } from '../../components/Panel';
import { Btn } from '../../components/Btn';
import { VBar } from '../../components/VBar';
import { MOCK_TRAINING_LOG } from '../../data/trainingMock';
import './LiveTrainingView.css';

export function LiveTrainingView() {
  const { state, dispatch } = useApp();
  const training = state.training;

  const [lines, setLines]     = useState(MOCK_TRAINING_LOG);
  const [metrics, setMetrics] = useState({
    step: training.step ?? 842,
    loss: training.loss ?? 1.5211,
    gradNorm: training.gradNorm ?? 0.578,
    eta: training.eta ?? '2h 14m',
  });
  const [autoScroll, setAutoScroll] = useState(true);
  const logRef = useRef(null);

  const engine   = training.engine ?? 'axolotl';
  const service  = engine === 'kohya' ? 'kohya' : 'axolotl';

  // SSE log stream
  useEffect(() => {
    let es;
    try {
      es = new EventSource(`/api/services/${service}/logs/stream`);
      es.onmessage = (e) => {
        setLines(prev => [...prev.slice(-199), e.data]);
        // Parse metrics from log line
        const stepMatch = e.data.match(/step (\d+)(?:\/(\d+))?.*?loss[: ]+([\d.]+)/i);
        const etaMatch  = e.data.match(/ETA\s+([\dh m]+)/i);
        const gnMatch   = e.data.match(/grad[_\s]norm[: ]+([\d.]+)/i);
        if (stepMatch) {
          setMetrics(m => ({
            ...m,
            step: +stepMatch[1],
            loss: +stepMatch[3],
            ...(etaMatch  ? { eta: etaMatch[1] }  : {}),
            ...(gnMatch   ? { gradNorm: +gnMatch[1] } : {}),
          }));
        }
      };
      es.onerror = () => es.close(); // silently close — mock data remains
    } catch {
      // SSE not available; mock data persists
    }
    return () => es?.close();
  }, [service]);

  // Auto-scroll log to bottom
  useEffect(() => {
    if (autoScroll && logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [lines, autoScroll]);

  function handleLogScroll() {
    const el = logRef.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
    setAutoScroll(atBottom);
  }

  async function handleStop() {
    if (!window.confirm('Stop training? The current checkpoint will be preserved.')) return;
    try {
      await fetch('/api/training/stop', { method: 'POST' });
    } catch { /* API not ready */ }
    dispatch({ type: 'SET_TRAINING_STATUS', payload: { active: false, engine: null } });
  }

  async function handleExport() {
    try {
      const res = await fetch('/api/training/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ run_name: training.model ?? 'run' }),
      });
      if (res.ok) {
        const d = await res.json();
        alert(`Checkpoint exported to: ${d.path ?? '/data/checkpoints/text/'}`);
      }
    } catch {
      alert('Export API not available yet (Step 10).');
    }
  }

  const stepPct  = training.totalSteps > 0
    ? (metrics.step / training.totalSteps) * 100 : 0;
  const epochPct = training.totalEpochs > 0
    ? ((training.epoch ?? 1) / training.totalEpochs) * 100 : 0;

  return (
    <div className="live-training">
      <Panel title={`Training: ${training.model ?? '—'} · ${engine}`}
             subtitle={`epoch ${training.epoch ?? 1}/${training.totalEpochs ?? 3}`}>
        <div className="live-progress">
          <div className="progress-row">
            <span className="progress-label">EPOCH</span>
            <VBar pct={epochPct} variant="amber" />
            <span className="progress-val">{training.epoch ?? 1}/{training.totalEpochs ?? 3}</span>
          </div>
          <div className="progress-row">
            <span className="progress-label">STEP</span>
            <VBar pct={stepPct} variant="amber" />
            <span className="progress-val">{metrics.step}/{training.totalSteps ?? 3200}</span>
          </div>
        </div>

        <div className="live-gpus">
          {state.gpus.map(gpu => (
            <div key={gpu.index} className="live-gpu-row">
              <span className="live-gpu-label">GPU{gpu.index}</span>
              <VBar
                pct={(gpu.vram_used_gb / gpu.vram_total_gb) * 100}
                variant="amber"
              />
              <span className="live-gpu-val">{gpu.vram_used_gb.toFixed(1)}/{gpu.vram_total_gb} GB</span>
            </div>
          ))}
        </div>

        <div className="live-metrics">
          <span>LOSS: <strong>{metrics.loss?.toFixed(4) ?? '—'}</strong></span>
          <span>GRAD NORM: <strong>{metrics.gradNorm?.toFixed(3) ?? '—'}</strong></span>
          <span>LR: <strong>{training.lr ?? '2e-5'}</strong></span>
          <span>ETA: <strong>{metrics.eta ?? '—'}</strong></span>
        </div>

        <div className="live-log-wrap">
          <div className="live-log-header">LOG OUTPUT</div>
          <div
            className="live-log"
            ref={logRef}
            onScroll={handleLogScroll}
          >
            {lines.map((line, i) => {
              const color = line.includes('[WARN]') ? 'var(--amber)'
                : line.includes('[ERROR]') ? 'var(--red)'
                : 'var(--text2)';
              return (
                <div key={i} className="live-log-line" style={{ color }}>{line}</div>
              );
            })}
          </div>
          {!autoScroll && (
            <button className="log-scroll-btn" onClick={() => setAutoScroll(true)}>
              ↓ scroll to live
            </button>
          )}
        </div>

        <div className="live-actions">
          <Btn variant="gray" size="sm" onClick={handleExport}>Export Checkpoint</Btn>
          <Btn variant="red"  size="sm" onClick={handleStop}>Stop Training</Btn>
        </div>
      </Panel>
    </div>
  );
}
```

```css
/* LiveTrainingView.css */
@import '../../tokens.css';

.live-training { display: flex; flex-direction: column; gap: 0; }

.live-progress { display: flex; flex-direction: column; gap: 6px; margin-bottom: 14px; }

.progress-row, .live-gpu-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.progress-label, .live-gpu-label {
  font-size: 9px;
  color: var(--text3);
  width: 40px;
  flex-shrink: 0;
  letter-spacing: .4px;
}

.progress-val, .live-gpu-val {
  font-size: 9px;
  color: var(--text2);
  width: 72px;
  text-align: right;
  flex-shrink: 0;
}

.progress-row .vbar-track,
.live-gpu-row .vbar-track { flex: 1; }

.live-gpus { display: flex; flex-direction: column; gap: 5px; margin-bottom: 14px; }

.live-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  font-size: 10px;
  color: var(--text3);
  margin-bottom: 14px;
}

.live-metrics strong { color: var(--amber); }

.live-log-wrap {
  position: relative;
  background: #070b1c;
  border-radius: 3px;
  padding: 8px;
  margin-bottom: 12px;
}

.live-log-header {
  font-size: 9px;
  color: var(--text3);
  margin-bottom: 6px;
  letter-spacing: .4px;
}

.live-log {
  height: 160px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.live-log-line {
  font-size: 10px;
  font-family: var(--mono);
  line-height: 1.5;
  white-space: pre;
  overflow: hidden;
  text-overflow: ellipsis;
}

.log-scroll-btn {
  position: absolute;
  bottom: 12px;
  right: 12px;
  background: var(--surface3);
  border: 1px solid var(--border2);
  color: var(--cyan);
  font-family: var(--mono);
  font-size: 9px;
  border-radius: 3px;
  padding: 2px 8px;
  cursor: pointer;
}

.live-actions { display: flex; gap: 8px; }

/* Wizard shared styles */
.wizard-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.wizard-back {
  background: none;
  border: none;
  color: var(--text3);
  font-family: var(--mono);
  font-size: 10px;
  cursor: pointer;
  padding: 0;
}

.wizard-back:hover { color: var(--text); }

.wizard-title { font-size: 13px; font-weight: 600; color: var(--text); }

.wizard-error {
  background: var(--red-dim);
  border: 1px solid var(--red);
  border-radius: var(--radius);
  padding: 6px 10px;
  font-size: 10px;
  color: var(--red);
  margin-bottom: 10px;
}

.wizard-nav {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 12px;
}

.wizard-step { display: flex; flex-direction: column; gap: 12px; }

.step-label-heading {
  font-size: 9px;
  color: var(--text3);
  letter-spacing: .5px;
  font-weight: 600;
}

/* Slider */
.lora-config-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

.form-field { display: flex; flex-direction: column; gap: 4px; }

.form-label { font-size: 9px; color: var(--text3); }

.form-input {
  background: var(--surface3);
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--text);
  font-family: var(--mono);
  font-size: 10px;
  padding: 4px 6px;
}

.slider-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 9px;
  color: var(--text3);
}

.slider-row input[type=range] { flex: 1; accent-color: var(--cyan); }
.slider-val { color: var(--cyan); font-weight: 600; min-width: 24px; }

.effective-batch {
  grid-column: span 2;
  font-size: 10px;
  color: var(--text3);
}

.effective-batch strong { color: var(--text); }

/* Dataset table */
.dataset-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 10px;
}

.dataset-table th {
  text-align: left;
  color: var(--text3);
  font-size: 9px;
  border-bottom: 1px solid var(--border);
  padding: 4px 6px;
}

.dataset-table td {
  padding: 6px 6px;
  color: var(--text2);
  border-bottom: 1px solid var(--border);
  cursor: pointer;
}

.dataset-table tr.row-selected td {
  color: var(--cyan);
  background: var(--cyan-dim);
}

.dataset-table tr:hover:not(.row-selected) td { background: var(--surface2); }

/* Upload zone */
.upload-zone {
  border: 2px dashed var(--border2);
  border-radius: var(--radius);
  padding: 24px;
  text-align: center;
  font-size: 11px;
  color: var(--text3);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  cursor: pointer;
}

.upload-zone:hover { border-color: var(--cyan); background: var(--cyan-dim); }

.upload-label {
  color: var(--cyan);
  cursor: pointer;
  text-decoration: underline;
}

/* Step source toggle */
.step-source-toggle {
  display: flex;
  gap: 4px;
}

.source-btn {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--text3);
  font-family: var(--mono);
  font-size: 9px;
  padding: 4px 10px;
  cursor: pointer;
}

.source-btn-active {
  background: var(--cyan-dim);
  border-color: var(--cyan);
  color: var(--cyan);
}

/* GPU Assignment step */
.assign-mini-gpus {
  display: flex;
  gap: 4px;
}

.assign-warning {
  background: var(--amber-dim);
  border: 1px solid var(--amber);
  border-radius: var(--radius);
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 10px;
}

.assign-warning-msg { color: var(--amber); }
.assign-service-list { color: var(--text2); }

.assign-checkbox {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text2);
  cursor: pointer;
}

/* Launch summary */
.launch-summary {
  display: grid;
  grid-template-columns: 100px 1fr;
  gap: 6px 10px;
  font-size: 10px;
}

.launch-summary > div { display: contents; }
.launch-summary span:first-child { color: var(--text3); }
.launch-summary span:last-child  { color: var(--text2); }

/* Model select */
.model-select {
  background: var(--surface3);
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--text);
  font-family: var(--mono);
  font-size: 10px;
  padding: 6px 8px;
  width: 100%;
}

.model-vram-info {
  font-size: 10px;
  color: var(--text3);
}

.vram-avail { color: var(--green); }

/* GPU assign profile */
.gpu-assign-profile {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.assign-profile-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--amber);
}

.assign-profile-desc {
  font-size: 10px;
  color: var(--text3);
}
```

---

## Acceptance Criteria

- [ ] Mode selector shows two cards (Text/Image); clicking either enters the wizard; Back button returns to selector
- [ ] Step indicator shows correct state (done/current/future) and advances on Next
- [ ] Text LoRA Step 0: browse mode shows mock dataset table; selecting a row highlights it; upload mode parses JSONL and shows record count
- [ ] Text LoRA Step 0: invalid JSONL (missing keys) shows inline error
- [ ] Text LoRA Step 2: sliders update live readout; effective batch size updates dynamically
- [ ] Text LoRA Step 3: if runningServices is non-empty, acknowledgment checkbox is required before Next
- [ ] Text LoRA Step 4: "Start Training" calls POST /activate then waits for state.switching === false before POST /api/training/start
- [ ] On successful (or mock) launch, LiveTrainingView renders and replaces the wizard
- [ ] LiveTrainingView: SSE connects to `/api/services/axolotl/logs/stream`; falls back to mock log lines on error
- [ ] Log auto-scrolls to bottom as new lines arrive; stops auto-scroll when user scrolls up; "↓ scroll to live" button re-engages it
- [ ] "Stop Training" shows confirm dialog → dispatches `active: false` → returns to mode selector
- [ ] Navigating away from `/training` and back restores live view if `state.training.active === true`
- [ ] Image LoRA Step 4: "Open Kohya_ss UI ↗" opens `:7862` in a new tab (no iframe)

---

## Feedback

Write `plan/UI/GHC-Feedback/05-feedback.md` when done.

**Required in Notes:**
- Does `new EventSource(...)` work in the Vite dev environment with the proxy config? If not, describe the workaround applied.
- Confirm the `React.useEffect` watching `state.switching` fires correctly on the first poll after POST /activate (i.e., the profile switch completes before training start is triggered).
