# Step 11 — First-Boot Wizard

> **Prerequisites:** Steps 01–10 complete. Read `plan/UI/GHC-Plan/00-overview.md`.
> **Reference spec:** `plan/UI/Steps/11-firstboot-wizard.md`

---

## Goal

Implement the First-Boot Wizard at `/#/setup` — a 7-step guided flow that runs **outside** the main Shell (no sidebar, no topbar). After completion it redirects to `/#/dashboard` and writes a completion flag so the wizard never auto-launches again.

Steps:

| # | Step | Key action |
|---|------|-----------|
| 1 | Hardware Probe | `POST /api/setup/probe` → display CPU/GPU/NVLink/storage |
| 2 | Profile Recommendation | `POST /api/setup/recommend` → show recommended profile, allow change |
| 3 | Secret Generation | `POST /api/setup/generate-secrets` → show redacted values once, download, checkbox |
| 4 | Network Setup | jumpbox IP, WireGuard keygen, Caddy toggle |
| 5 | Stack Provisioner | `POST /api/setup/provision` (SSE) → pull container images with progress |
| 6 | Validation Suite | `POST /api/setup/validate` (SSE) → health checks, ≥22/25 to continue |
| 7 | Handoff | Service links, MCP config download, "Go to Dashboard" |

**State persistence:** `sessionStorage` (survives browser refresh, not tab close). Secret values are **never** written to sessionStorage.

---

## Deliverables

### 1. App.jsx route update

The `/setup` route renders `<Setup />` **without** the Shell wrapper. Update App.jsx:

```jsx
// Inside HashRouter
<Routes>
  <Route path="/setup" element={<Setup />} />
  <Route path="*" element={
    <Shell>
      <Routes>
        <Route path="/"           element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard"  element={<Dashboard />} />
        <Route path="/loadouts"   element={<Loadout />} />
        <Route path="/tools"      element={<Tools />} />
        <Route path="/training"   element={<Training />} />
        <Route path="/resources"  element={<Resources />} />
        <Route path="/expose"     element={<Expose />} />
        <Route path="/monitor"    element={<Monitor />} />
        <Route path="/settings"   element={<Settings />} />
      </Routes>
    </Shell>
  } />
</Routes>
```

On first load: check `GET /api/setup/status`. If `{ complete: false }`, navigate to `/#/setup`. If complete, stay on dashboard.

---

### 2. Mock data — `ui/src/data/setupMock.js`

```js
// TODO Step 10: replace with live API responses

export const MOCK_HARDWARE = {
  cpu:  { model: 'AMD Threadripper Pro 5955WX', cores: 64, ram_gb: 512 },
  gpus: [
    { index: 0, name: 'NVIDIA RTX A5500', vram_gb: 24, bus_id: '0x21' },
    { index: 1, name: 'NVIDIA RTX A5500', vram_gb: 24, bus_id: '0x22' },
    { index: 2, name: 'NVIDIA RTX A5500', vram_gb: 24, bus_id: '0x41' },
    { index: 3, name: 'NVIDIA RTX A5500', vram_gb: 24, bus_id: '0x43' },
  ],
  nvlink_pairs: [[0, 3], [1, 2]],
  total_vram_gb: 96,
  storage: { data_path: '/data', total_gb: 20480, free_gb: 18636 },
};

export const MOCK_RECOMMENDED_PROFILE = {
  name:        'dual-stack',
  description: 'Two simultaneous 32B models · all GPUs',
  gpu_pairs:   ['GPU 0+3 (Bridge A)', 'GPU 1+2 (Bridge B)'],
  services:    ['vllm-pair-a', 'vllm-pair-b'],
  total_vram:  96,
};

// Fake values for UI testing only — never committed to backend
export const MOCK_GENERATED_SECRETS = {
  POSTGRES_PASSWORD:            'Y3nK9qR2mXpL8vF5sJ1dZ6wA4tH0uN7',
  LANGFUSE_SECRET_KEY:          'K5bM2xQ8nP1jR4vW7tA9cE6yZ0sD3fH',
  LANGFUSE_SALT:                'N8pQ1wE4rY7uI2oP5aTb6cXd9fGhJkLm',
  MINIO_ROOT_PASSWORD:          'R6sT3vU9xW2zB5nM8pQ1eY4iO7uA0cD',
  MINIO_SECRET_KEY:             'V2xZ8bN5mK3jH6gF9dA1cE4wQ7rT0yP',
  AUTHENTIK_SECRET_KEY:         'P7qS4vU1xY8nM5jK2hG0fD9cB6wA3eR',
  AUTHENTIK_BOOTSTRAP_PASSWORD: 'SecurePass-2026-Init-XkZ9',
  N8N_ENCRYPTION_KEY:           'L4tR8wP2xN6bM1jK5hG9fD3cA7eQ0vU',
  DIFY_SECRET_KEY:              'H6gF3dA9cE2wQ5rT8vU1xZ7bN4mK0jP',
  GRAFANA_ADMIN_PASSWORD:       'GrafanaAdmin-Xk9mP3nQ7',
  OPEN_WEBUI_SECRET_KEY:        'B5nM2xQ8wE4rY7uI1oP6aTbcXd0fGhJ',
  SEARXNG_SECRET_KEY:           'J9kL6mN3pQ0rS7tU4vW1xY8zA5bC2dE',
  CADDY_API_KEY:                'F1gH4iJ7kL0mN3oP6qR9sT2uV5wX8yZ',
  KOVATI_INTERNAL_TOKEN:        'D8eA1bC4fG7hI0jK3lM6nO9pQ2rS5tU',
};

export const MOCK_PROVISION_GROUPS = [
  {
    group: 'Infrastructure',
    images: [
      { name: 'postgres:16',          size_gb: 1.2, status: 'done' },
      { name: 'redis:7-alpine',       size_gb: 0.04, status: 'done' },
    ],
  },
  {
    group: 'Storage',
    images: [
      { name: 'minio/minio:latest',   size_gb: 0.18, status: 'pulling', pct: 72 },
      { name: 'qdrant/qdrant:latest', size_gb: 0.32, status: 'pending' },
    ],
  },
  {
    group: 'Inference',
    images: [
      { name: 'vllm/vllm-openai:v0.9.1', size_gb: 4.3, status: 'pending' },
      { name: 'ollama/ollama:latest',     size_gb: 1.6, status: 'pending' },
    ],
  },
];

export const MOCK_HEALTH_CHECKS = [
  { name: 'PostgreSQL',  port: 5432,  status: 'pass',    detail: 'CREATE DATABASE ok' },
  { name: 'Redis',       port: 6379,  status: 'pass',    detail: 'PING ok' },
  { name: 'MinIO',       url: ':9000', status: 'pass',   detail: 'Bucket listing ok' },
  { name: 'Qdrant',      url: ':6333', status: 'pass',   detail: '/healthz → 200' },
  { name: 'Authentik',   url: ':9080', status: 'pass',   detail: '/api/v3/root/config/ → 200' },
  { name: 'n8n',         url: ':5678', status: 'pass',   detail: '/healthz → 200' },
  { name: 'Prometheus',  url: ':9091', status: 'pass',   detail: '/-/healthy → 200' },
  { name: 'Grafana',     url: ':3001', status: 'pass',   detail: '/api/health → 200' },
  { name: 'Ollama',      url: ':11434',status: 'pending',detail: 'Loading model…' },
  { name: 'Open WebUI',  url: ':3000', status: 'pass',   detail: '/health → 200' },
  { name: 'vLLM Pair A', url: ':8000', status: 'pass',   detail: '/v1/models → [{qwen2.5-32b}]' },
  { name: 'GPU VRAM',    url: null,    status: 'pass',   detail: 'GPU 0: 21.4/24 GB · GPU 3: 19.8/24 GB' },
];
```

---

### 3. `ui/src/pages/Setup.jsx` (wizard shell)

```jsx
import { useState, useEffect, useCallback } from 'react';
import { useNavigate }  from 'react-router-dom';
import { WizardProgress } from './setup/WizardProgress';
import { StepHardware }   from './setup/StepHardware';
import { StepProfile }    from './setup/StepProfile';
import { StepSecrets }    from './setup/StepSecrets';
import { StepNetwork }    from './setup/StepNetwork';
import { StepStack }      from './setup/StepStack';
import { StepValidate }   from './setup/StepValidate';
import { StepHandoff }    from './setup/StepHandoff';
import './Setup.css';

const STEP_NAMES = ['Hardware', 'Profile', 'Secrets', 'Network', 'Stack', 'Validate', 'Handoff'];
const TOTAL = 7;

const STEP_COMPONENTS = [
  StepHardware, StepProfile, StepSecrets, StepNetwork,
  StepStack, StepValidate, StepHandoff,
];

function loadSession() {
  try {
    return {
      step:     parseInt(sessionStorage.getItem('setup_step') ?? '1', 10),
      hardware: JSON.parse(sessionStorage.getItem('setup_hardware') ?? 'null'),
      profile:  sessionStorage.getItem('setup_profile'),
      network:  JSON.parse(sessionStorage.getItem('setup_network') ?? 'null'),
      completed:JSON.parse(sessionStorage.getItem('setup_completed') ?? '[]'),
    };
  } catch {
    return { step: 1, hardware: null, profile: null, network: null, completed: [] };
  }
}

export function Setup() {
  const navigate = useNavigate();
  const session  = loadSession();

  const [currentStep, setStep]      = useState(session.step);
  const [stepData,    setStepData]  = useState({
    hardware: session.hardware,
    profile:  session.profile,
    network:  session.network,
  });
  const [completed, setCompleted]   = useState(new Set(session.completed));
  const [failed,    setFailed]      = useState(new Set());

  function advance(stepResult = {}) {
    const key = stepKeyForIndex(currentStep - 1);
    const newData = { ...stepData, ...(key ? { [key]: stepResult } : {}) };
    setStepData(newData);
    setCompleted(c => new Set([...c, currentStep]));

    // Persist to sessionStorage (never persist secret values)
    if (key && key !== 'secrets') {
      sessionStorage.setItem(`setup_${key}`, JSON.stringify(stepResult));
    }
    sessionStorage.setItem('setup_step', String(currentStep + 1));
    sessionStorage.setItem('setup_completed', JSON.stringify([...completed, currentStep]));

    if (currentStep < TOTAL) {
      setStep(s => s + 1);
    }
  }

  function goBack() {
    if (currentStep > 1) {
      setStep(s => s - 1);
      sessionStorage.setItem('setup_step', String(currentStep - 1));
    }
  }

  function markFailed(step) {
    setFailed(f => new Set([...f, step]));
  }

  const StepComponent = STEP_COMPONENTS[currentStep - 1];

  return (
    <div className="wizard-page">
      <div className="wizard-header">
        <div className="wizard-brand">
          {window.__KOVATI_PRODUCT_NAME__ ?? 'KOVATI OS'} — Setup
        </div>
        <WizardProgress
          steps={STEP_NAMES}
          current={currentStep}
          completed={completed}
          failed={failed}
        />
      </div>

      <div className="wizard-body">
        <StepComponent
          data={stepData}
          onNext={advance}
          onBack={goBack}
          onFail={() => markFailed(currentStep)}
          isFirst={currentStep === 1}
          isLast={currentStep === TOTAL}
        />
      </div>
    </div>
  );
}

function stepKeyForIndex(idx) {
  return ['hardware', 'profile', null, 'network', null, null, null][idx];
}
```

---

### 4. `ui/src/pages/setup/WizardProgress.jsx`

```jsx
import './WizardProgress.css';

export function WizardProgress({ steps, current, completed, failed }) {
  return (
    <div className="wizard-progress">
      {steps.map((label, i) => {
        const n = i + 1;
        const isDone  = completed.has(n);
        const isErr   = failed.has(n);
        const isActive= n === current;
        let cls = 'wp-step';
        if (isDone)   cls += ' wp-done';
        if (isErr)    cls += ' wp-error';
        if (isActive) cls += ' wp-active';

        return (
          <div key={n} className={cls}>
            {i > 0 && <div className="wp-connector" />}
            <div className="wp-dot">
              {isDone  ? '✓' : isErr ? '✗' : n}
            </div>
            <div className="wp-label">{label}</div>
          </div>
        );
      })}
    </div>
  );
}
```

```css
/* WizardProgress.css */
@import '../../tokens.css';

.wizard-progress {
  display: flex;
  align-items: flex-start;
  gap: 0;
}

.wp-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  position: relative;
  flex: 1;
}

.wp-connector {
  position: absolute;
  left: -50%;
  top: 11px;
  width: 100%;
  height: 1px;
  background: var(--border);
}

.wp-done  .wp-connector,
.wp-active .wp-connector { background: var(--cyan); }

.wp-dot {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: var(--surface3);
  border: 1.5px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  color: var(--text3);
  position: relative;
  z-index: 1;
  font-weight: 600;
}

.wp-done  .wp-dot  { background: var(--cyan-dim); border-color: var(--cyan);  color: var(--cyan);  }
.wp-active .wp-dot { background: var(--surface2); border-color: var(--cyan);  color: var(--cyan);  }
.wp-error  .wp-dot { background: rgba(239,68,68,.2); border-color: var(--red); color: var(--red); }

.wp-label { font-size: 8px; color: var(--text3); white-space: nowrap; }
.wp-active .wp-label { color: var(--cyan); }
.wp-done   .wp-label { color: var(--text2); }
```

---

### 5. `ui/src/pages/setup/StepHardware.jsx`

Calls `POST /api/setup/probe` on mount. Shows spinner while probing. On error shows retry/skip.

```jsx
import { useState, useEffect } from 'react';
import { WizardCard } from './WizardCard';
import { Btn }        from '../../components/Btn';
import { MOCK_HARDWARE } from '../../data/setupMock';
import './SetupShared.css';

export function StepHardware({ onNext, onFail }) {
  const [status,   setStatus]  = useState('probing'); // probing | done | error
  const [hardware, setHardware]= useState(null);
  const [error,    setError]   = useState('');

  async function probe() {
    setStatus('probing');
    setError('');
    try {
      const res = await fetch('/api/setup/probe', { method: 'POST' });
      const data = res.ok ? await res.json() : null;
      if (data) {
        setHardware(data);
        setStatus('done');
      } else {
        throw new Error(`HTTP ${res.status}`);
      }
    } catch (e) {
      // Fallback to mock for UI development
      setHardware(MOCK_HARDWARE);
      setStatus('done');
      // For a real error: setError(e.message); setStatus('error'); onFail();
    }
  }

  useEffect(() => { probe(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <WizardCard title="Step 1: Hardware Detection" onNext={() => onNext(hardware)} nextDisabled={status !== 'done'}>
      {status === 'probing' && (
        <div className="setup-probing">
          <span className="probe-spinner">↻</span> Detecting GPU configuration…
        </div>
      )}

      {status === 'error' && (
        <div className="setup-error">
          <div>⚠ GPU detection failed: {error}</div>
          <div className="setup-error-hint">Ensure NVIDIA drivers ≥ 525 are installed.</div>
          <div className="setup-error-actions">
            <Btn variant="cyan"  size="sm" onClick={probe}>Retry</Btn>
            <Btn variant="gray"  size="sm" onClick={() => onNext(null)}>Skip (CPU-only mode)</Btn>
          </div>
        </div>
      )}

      {status === 'done' && hardware && (
        <div className="hw-result">
          <div className="hw-card">
            <HwRow label="CPU" value={`${hardware.cpu.model} · ${hardware.cpu.cores}c · ${hardware.cpu.ram_gb} GB`} />
            {hardware.gpus.map(g => (
              <HwRow key={g.index}
                label={`GPU ${g.index}`}
                value={`${g.name} · ${g.vram_gb} GB · bus ${g.bus_id}`}
              />
            ))}

            {hardware.nvlink_pairs.length > 0 && (
              <div className="hw-section-label">NVLink</div>
            )}
            {hardware.nvlink_pairs.map(([a, b], i) => (
              <HwRow key={i}
                label={`Bridge ${String.fromCharCode(65 + i)}`}
                value={`GPU ${a} ↔ GPU ${b} · 56.25 GB/s`}
                highlight
              />
            ))}

            <div className="hw-section-label">Storage</div>
            <HwRow
              label={hardware.storage.data_path}
              value={`${(hardware.storage.total_gb / 1024).toFixed(0)} TB total · ${(hardware.storage.free_gb / 1024).toFixed(1)} TB free`}
            />
          </div>
          <div className="setup-ok">✓ Hardware detected successfully</div>
        </div>
      )}
    </WizardCard>
  );
}

function HwRow({ label, value, highlight }) {
  return (
    <div className={`hw-row ${highlight ? 'hw-row-highlight' : ''}`}>
      <span className="hw-row-label">{label}</span>
      <span className="hw-row-value">{value}</span>
    </div>
  );
}
```

---

### 6. `ui/src/pages/setup/StepProfile.jsx`

Shows the recommended profile card. "Change Profile" expands a list of all 8 profiles.

```jsx
import { useState } from 'react';
import { WizardCard }  from './WizardCard';
import { Tag }         from '../../components/Tag';
import { Btn }         from '../../components/Btn';
import { MOCK_RECOMMENDED_PROFILE } from '../../data/setupMock';
import './SetupShared.css';

// All profiles for the picker — same data as step 03 profiles
const ALL_PROFILES = [
  { name: 'dual-stack',      label: 'Dual Stack',         gpu_pairs: ['GPU 0+3', 'GPU 1+2'], description: 'Two 32B models · 96 GB total' },
  { name: 'inference-pair-a',label: 'Inference Pair A',   gpu_pairs: ['GPU 0+3'],            description: 'Single 32B model · 48 GB' },
  { name: 'inference-pair-b',label: 'Inference Pair B',   gpu_pairs: ['GPU 1+2'],            description: 'Single 32B model · 48 GB' },
  { name: 'inference-4gpu',  label: 'Inference 4-GPU',    gpu_pairs: ['All 4'],              description: '70B+ model · tensor parallel' },
  { name: 'inference-small', label: 'Inference Small',    gpu_pairs: ['GPU 0+3'],            description: '7B model · single pair' },
  { name: 'training-lora-text', label: 'LoRA Text',       gpu_pairs: ['GPU 0+3'],            description: 'Axolotl · exclusive' },
  { name: 'training-lora-image', label: 'LoRA Image',     gpu_pairs: ['GPU 1+2'],            description: 'Kohya · exclusive' },
  { name: 'idle',            label: 'Idle',               gpu_pairs: [],                     description: 'No GPUs active' },
];

export function StepProfile({ data, onNext, onBack }) {
  const [selected,  setSelected]  = useState(
    data.profile ?? MOCK_RECOMMENDED_PROFILE.name
  );
  const [showAll,   setShowAll]   = useState(false);
  const [recommended] = useState(MOCK_RECOMMENDED_PROFILE); // TODO Step 10: from API

  const selectedProfile = ALL_PROFILES.find(p => p.name === selected) ?? ALL_PROFILES[0];

  return (
    <WizardCard
      title="Step 2: Recommended Profile"
      onNext={() => onNext(selected)}
      onBack={onBack}
    >
      <div className="profile-summary">
        Based on your hardware ({data.hardware?.gpus?.length ?? 4}× RTX A5500 · {data.hardware?.total_vram_gb ?? 96} GB NVLink mesh), we recommend:
      </div>

      <div className="profile-rec-card">
        <div className="profile-rec-star">★</div>
        <div className="profile-rec-body">
          <div className="profile-rec-name">{selectedProfile.label}</div>
          <div className="profile-rec-desc">{selectedProfile.description}</div>
          <div className="profile-rec-gpus">
            {selectedProfile.gpu_pairs.map(g => (
              <Tag key={g} variant="cyan">{g}</Tag>
            ))}
          </div>
        </div>
      </div>

      {!showAll ? (
        <Btn variant="gray" size="sm" onClick={() => setShowAll(true)}>Change Profile</Btn>
      ) : (
        <div className="profile-picker">
          {ALL_PROFILES.map(p => (
            <div
              key={p.name}
              className={`profile-picker-row ${selected === p.name ? 'picker-selected' : ''}`}
              onClick={() => setSelected(p.name)}
            >
              <div className="picker-radio">{selected === p.name ? '●' : '○'}</div>
              <div className="picker-info">
                <span className="picker-name">{p.label}</span>
                <span className="picker-desc">{p.description}</span>
              </div>
              <div className="picker-gpus">
                {p.gpu_pairs.map(g => <Tag key={g} variant="gray">{g}</Tag>)}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="setup-note">
        This profile will be activated after stack provisioning.
      </div>
    </WizardCard>
  );
}
```

---

### 7. `ui/src/pages/setup/StepSecrets.jsx`

**Critical security step.** Secret values are returned by the API and shown exactly once. They are never stored in sessionStorage. Checkbox required to advance.

```jsx
import { useState, useEffect, useRef } from 'react';
import { WizardCard } from './WizardCard';
import { Btn }        from '../../components/Btn';
import { MOCK_GENERATED_SECRETS } from '../../data/setupMock';
import './SetupShared.css';

export function StepSecrets({ onNext, onBack }) {
  const [status,   setStatus]   = useState('idle');  // idle | generating | done | error
  const [keys,     setKeys]     = useState([]);      // key names only — always shown
  const [values,   setValues]   = useState(null);    // key→value map — shown once, then null
  const [revealed, setRevealed] = useState(false);
  const [checked,  setChecked]  = useState(false);
  const [rerun,    setRerun]    = useState(false);   // set if .env already exists

  useEffect(() => {
    // Check if secrets already exist
    fetch('/api/secrets')
      .then(r => r.json())
      .then(data => {
        if (data.keys?.length > 0) setRerun(true);
      })
      .catch(() => {});
  }, []);

  async function generate() {
    setStatus('generating');
    try {
      const res = await fetch('/api/setup/generate-secrets', { method: 'POST' });
      const data = res.ok ? await res.json() : null;
      if (data) {
        setKeys(data.keys ?? Object.keys(MOCK_GENERATED_SECRETS));
        setValues(data.values ?? MOCK_GENERATED_SECRETS); // API returns values THIS ONCE ONLY
        setStatus('done');
      } else {
        throw new Error(`HTTP ${res.status}`);
      }
    } catch {
      // Fall back to mock for UI testing
      setKeys(Object.keys(MOCK_GENERATED_SECRETS));
      setValues(MOCK_GENERATED_SECRETS);
      setStatus('done');
    }
  }

  function downloadEnv() {
    if (!values) return;
    const lines = Object.entries(values).map(([k, v]) => `${k}=${v}`).join('\n');
    const blob = new Blob([lines + '\n'], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `kovati-os-secrets-${new Date().toISOString().slice(0, 10)}.env`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  // Advance: clear values from memory — they cannot be recovered
  function handleNext() {
    setValues(null);
    onNext({});
  }

  return (
    <WizardCard
      title="Step 3: Secret Generation"
      onNext={handleNext}
      onBack={onBack}
      nextDisabled={status !== 'done' || !checked}
      nextLabel="Next: Network →"
    >
      {rerun && (
        <div className="setup-warn-banner">
          ⚠ Secrets already exist. Re-generating will invalidate existing service data.
          Consider keeping existing secrets unless you are re-initialising from scratch.
        </div>
      )}

      <div className="secrets-intro">
        {keys.length > 0 ? keys.length : 14} cryptographic secrets will be generated and written to{' '}
        <code>docker/.env</code>. This file is gitignored and stays on this machine.
      </div>

      {status === 'idle' && (
        <div className="setup-actions">
          <Btn variant="cyan" size="md" onClick={generate}>Generate Secrets</Btn>
          {rerun && (
            <Btn variant="gray" size="sm" onClick={() => { setKeys(Object.keys(MOCK_GENERATED_SECRETS)); setStatus('done'); setValues(null); }}>
              Keep Existing Secrets
            </Btn>
          )}
        </div>
      )}

      {status === 'generating' && (
        <div className="setup-probing">
          <span className="probe-spinner">↻</span> Generating {keys.length || 14} secrets…
        </div>
      )}

      {status === 'done' && (
        <>
          <div className="secrets-grid">
            {keys.map(k => (
              <div key={k} className="secret-row">
                <span className="secret-row-key">{k}</span>
                <span className="secret-row-val">
                  {revealed && values
                    ? <code className="secret-value-text">{values[k]}</code>
                    : <span className="secret-redacted">██████████████████████████████</span>
                  }
                </span>
              </div>
            ))}
          </div>

          <div className="secrets-warn">
            ⚠ Secret values are shown only here and never again.<br />
            Download a backup copy before continuing.
          </div>

          <div className="secrets-actions">
            <Btn variant="gray" size="sm" onClick={() => setRevealed(r => !r)}>
              {revealed ? 'Hide Values' : 'Reveal All'}
            </Btn>
            {values && (
              <Btn variant="cyan" size="sm" onClick={downloadEnv}>
                ⬇ Download .env Backup
              </Btn>
            )}
          </div>

          <label className="setup-checkbox">
            <input
              type="checkbox"
              checked={checked}
              onChange={e => setChecked(e.target.checked)}
            />
            <span>I have saved a secure backup of my secrets</span>
          </label>
        </>
      )}
    </WizardCard>
  );
}
```

---

### 8. `ui/src/pages/setup/StepNetwork.jsx`

```jsx
import { useState } from 'react';
import { WizardCard } from './WizardCard';
import { Btn }        from '../../components/Btn';
import './SetupShared.css';

export function StepNetwork({ onNext, onBack }) {
  const [jumpboxIp,   setJumpboxIp]  = useState('10.0.0.1');
  const [wgMode,      setWgMode]     = useState('generate'); // skip | generate
  const [wgPubKey,    setWgPubKey]   = useState('');
  const [wgGenerated, setWgGenerated]= useState(false);
  const [caddyEnabled,setCaddy]      = useState(true);
  const [copying,     setCopying]    = useState(false);

  async function generateKeypair() {
    try {
      const res = await fetch('/api/setup/network/wg-keygen', { method: 'POST' });
      const data = res.ok ? await res.json() : null;
      if (data?.public_key) {
        setWgPubKey(data.public_key);
        setWgGenerated(true);
        return;
      }
    } catch { /* fall through to mock */ }
    // Mock keypair for UI development
    setWgPubKey('3X4Y5Z6A7B8C9D0E1F2G3H4I5J6K7L8M9N0O1P2Q3R4S5T6U=');
    setWgGenerated(true);
  }

  function copyKey() {
    navigator.clipboard.writeText(wgPubKey).catch(() => {});
    setCopying(true);
    setTimeout(() => setCopying(false), 2000);
  }

  function handleNext() {
    onNext({
      jumpbox_ip:    jumpboxIp,
      wg_enabled:    wgMode === 'generate',
      caddy_enabled: caddyEnabled,
    });
  }

  return (
    <WizardCard title="Step 4: Network Configuration" onNext={handleNext} onBack={onBack}>
      <div className="setup-field">
        <label className="setup-field-label">Jumpbox / reverse proxy IP</label>
        <input
          className="setup-input"
          value={jumpboxIp}
          onChange={e => setJumpboxIp(e.target.value)}
        />
      </div>

      <div className="setup-field">
        <label className="setup-field-label">This machine's LAN IP (detected)</label>
        <div className="setup-detected">
          eth0 · 10.0.0.5 (10GbE) — primary<br />
          eth1 · 192.168.1.100 (1GbE) — management
          {/* TODO Step 10: from /api/network interfaces */}
        </div>
      </div>

      <div className="setup-field">
        <label className="setup-field-label">WireGuard VPN</label>
        <div className="setup-radio-group">
          <label className="setup-radio">
            <input type="radio" value="skip" checked={wgMode === 'skip'} onChange={() => setWgMode('skip')} />
            <span>Skip (LAN-only access)</span>
          </label>
          <label className="setup-radio">
            <input type="radio" value="generate" checked={wgMode === 'generate'} onChange={() => setWgMode('generate')} />
            <span>Generate WireGuard keypair</span>
          </label>
        </div>

        {wgMode === 'generate' && (
          <div className="wg-section">
            {!wgGenerated ? (
              <Btn variant="cyan" size="sm" onClick={generateKeypair}>Generate Keypair</Btn>
            ) : (
              <div className="wg-pubkey-row">
                <span className="wg-pubkey-label">Public key:</span>
                <code className="wg-pubkey">{wgPubKey.slice(0, 24)}…</code>
                <button className={`copy-btn ${copying ? 'copy-btn-done' : ''}`} onClick={copyKey}>
                  {copying ? '✓ copied' : 'Copy'}
                </button>
              </div>
            )}
            {wgGenerated && (
              <div className="setup-note">
                Add this to your WireGuard server's [Peer] config.
              </div>
            )}
          </div>
        )}
      </div>

      <div className="setup-field">
        <label className="setup-field-label">Caddy reverse proxy</label>
        <div className="setup-radio-group">
          <label className="setup-radio">
            <input type="radio" value="1" checked={caddyEnabled} onChange={() => setCaddy(true)} />
            <span>Enable (recommended for external access)</span>
          </label>
          <label className="setup-radio">
            <input type="radio" value="0" checked={!caddyEnabled} onChange={() => setCaddy(false)} />
            <span>Skip (direct port access only)</span>
          </label>
        </div>
      </div>
    </WizardCard>
  );
}
```

---

### 9. `ui/src/pages/setup/StepStack.jsx`

SSE via fetch+ReadableStream (POST-initiated). Shows per-image progress with group headers.

Air-gap mode: if `KOVATI_AIR_GAP=true` env is returned from `/api/setup/status`, show "loading from local cache" instead of pull progress.

```jsx
import { useState, useRef } from 'react';
import { WizardCard } from './WizardCard';
import { Btn }        from '../../components/Btn';
import { MOCK_PROVISION_GROUPS } from '../../data/setupMock';
import './SetupShared.css';

export function StepStack({ onNext, onBack, onFail }) {
  const [status,    setStatus]   = useState('idle');   // idle | pulling | done | error
  const [imageRows, setImageRows]= useState([]);
  const [elapsed,   setElapsed]  = useState(0);
  const [total,     setTotal]    = useState(0);
  const [done,      setDoneCount]= useState(0);
  const timerRef = useRef(null);

  async function startProvision() {
    setStatus('pulling');
    setElapsed(0);
    timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000);

    // Count total images from mock for progress display
    const allImages = MOCK_PROVISION_GROUPS.flatMap(g => g.images);
    setTotal(allImages.length);
    setImageRows(allImages.map(img => ({ ...img, status: 'pending', pct: 0 })));

    try {
      const res = await fetch('/api/setup/provision', { method: 'POST' });
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let doneCount = 0;

      while (true) {
        const { done: streamDone, value } = await reader.read();
        if (streamDone) break;

        dec.decode(value).split('\n')
          .filter(l => l.startsWith('data: '))
          .forEach(l => {
            const line = l.slice(6);
            // Parse SSE events: "PULL:image:pct" or "DONE:image:size" or "ERROR:image:msg"
            if (line.startsWith('PULL:')) {
              const [, name, pct] = line.split(':');
              setImageRows(rows => rows.map(r =>
                r.name === name ? { ...r, status: 'pulling', pct: parseInt(pct) } : r
              ));
            } else if (line.startsWith('DONE:')) {
              const [, name, size] = line.split(':');
              doneCount++;
              setDoneCount(doneCount);
              setImageRows(rows => rows.map(r =>
                r.name === name ? { ...r, status: 'done', size_gb: parseFloat(size) } : r
              ));
            } else if (line.startsWith('ERROR:')) {
              const [, name, msg] = line.split(':');
              setImageRows(rows => rows.map(r =>
                r.name === name ? { ...r, status: 'error', error: msg } : r
              ));
            }
          });
      }
      clearInterval(timerRef.current);
      setStatus('done');
    } catch {
      // Mock provisioning for UI development
      await mockProvision();
    }
  }

  async function mockProvision() {
    const allImages = MOCK_PROVISION_GROUPS.flatMap(g => g.images);
    setTotal(allImages.length);
    let d = 0;
    for (const img of allImages) {
      setImageRows(rows => rows.map(r =>
        r.name === img.name ? { ...r, status: 'pulling', pct: 0 } : r
      ));
      for (let pct = 0; pct <= 100; pct += 25) {
        await new Promise(r => setTimeout(r, 150));
        setImageRows(rows => rows.map(r =>
          r.name === img.name ? { ...r, pct } : r
        ));
      }
      d++;
      setDoneCount(d);
      setImageRows(rows => rows.map(r =>
        r.name === img.name ? { ...r, status: 'done' } : r
      ));
    }
    clearInterval(timerRef.current);
    setStatus('done');
  }

  const fmtTime = s => `${Math.floor(s / 60)}m ${s % 60}s`;

  return (
    <WizardCard
      title="Step 5: Stack Provisioning"
      onNext={() => onNext({})}
      onBack={onBack}
      nextDisabled={status !== 'done'}
      showNext={status === 'done'}
    >
      {status === 'idle' && (
        <div className="setup-actions">
          <Btn variant="cyan" size="md" onClick={startProvision}>
            Start Provisioning
          </Btn>
          <div className="setup-note">
            Pulling container images (~15–40 GB). This may take 15–40 minutes.
          </div>
        </div>
      )}

      {(status === 'pulling' || status === 'done') && (
        <>
          <div className="provision-progress-row">
            <div className="provision-bar-track">
              <div className="provision-bar-fill" style={{ width: `${total ? (done / total) * 100 : 0}%` }} />
            </div>
            <span className="provision-count">{done} / {total} images</span>
          </div>

          <div className="provision-image-list">
            {imageRows.map(img => (
              <div key={img.name} className={`provision-row provision-row-${img.status}`}>
                <span className="provision-icon">
                  {img.status === 'done'    ? '✓' :
                   img.status === 'pulling' ? '↓' :
                   img.status === 'error'   ? '✗' : '○'}
                </span>
                <span className="provision-name">{img.name}</span>
                {img.status === 'pulling' && (
                  <div className="provision-mini-bar-track">
                    <div className="provision-mini-bar-fill" style={{ width: `${img.pct}%` }} />
                  </div>
                )}
                {img.status === 'done' && img.size_gb > 0 && (
                  <span className="provision-size">{img.size_gb} GB</span>
                )}
                {img.status === 'error' && (
                  <span className="provision-error">{img.error}</span>
                )}
              </div>
            ))}
          </div>

          {status === 'pulling' && (
            <div className="provision-elapsed">Elapsed: {fmtTime(elapsed)}</div>
          )}

          {status === 'done' && (
            <div className="setup-ok">✓ All images provisioned</div>
          )}
        </>
      )}
    </WizardCard>
  );
}
```

---

### 10. `ui/src/pages/setup/StepValidate.jsx`

SSE delivers JSON check events. Continue enabled at ≥ 22/25 passes.

```jsx
import { useState } from 'react';
import { WizardCard } from './WizardCard';
import { Btn }        from '../../components/Btn';
import { MOCK_HEALTH_CHECKS } from '../../data/setupMock';
import './SetupShared.css';

export function StepValidate({ onNext, onBack }) {
  const [status,  setStatus]  = useState('idle');
  const [checks,  setChecks]  = useState([]);
  const [passing, setPassing] = useState(0);
  const TOTAL_CHECKS = 25;
  const PASS_THRESHOLD = 22;

  async function runValidation() {
    setStatus('running');
    setChecks([]);
    setPassing(0);

    try {
      const res = await fetch('/api/setup/validate', { method: 'POST' });
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let p = 0;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        dec.decode(value).split('\n')
          .filter(l => l.startsWith('data: '))
          .forEach(l => {
            try {
              const check = JSON.parse(l.slice(6));
              setChecks(prev => {
                const next = prev.filter(c => c.name !== check.name);
                return [...next, check];
              });
              if (check.status === 'pass') { p++; setPassing(p); }
            } catch { /* non-JSON line — ignore */ }
          });
      }
      setStatus('done');
    } catch {
      // Mock validation for UI development
      await mockValidate();
    }
  }

  async function mockValidate() {
    let p = 0;
    for (const chk of MOCK_HEALTH_CHECKS) {
      await new Promise(r => setTimeout(r, 300));
      setChecks(prev => {
        const next = prev.filter(c => c.name !== chk.name);
        return [...next, chk];
      });
      if (chk.status === 'pass') { p++; setPassing(p); }
    }
    setStatus('done');
  }

  const canContinue = status === 'done' && passing >= PASS_THRESHOLD;
  const pending  = checks.filter(c => c.status === 'pending').length;

  return (
    <WizardCard
      title="Step 6: Stack Validation"
      onNext={() => onNext({})}
      onBack={onBack}
      nextDisabled={!canContinue}
      showNext={status === 'done'}
    >
      {status === 'idle' && (
        <Btn variant="cyan" size="md" onClick={runValidation}>
          Start Health Checks
        </Btn>
      )}

      {(status === 'running' || status === 'done') && (
        <>
          <div className="validate-check-list">
            {checks.map(c => (
              <div key={c.name} className={`validate-row validate-${c.status}`}>
                <span className="validate-icon">
                  {c.status === 'pass' ? '✓' : c.status === 'fail' ? '✗' : '⟳'}
                </span>
                <span className="validate-name">{c.name}</span>
                <span className="validate-port">{c.url ?? ''}</span>
                <span className="validate-detail">{c.detail}</span>
              </div>
            ))}
          </div>

          <div className="validate-summary">
            <div className="validate-progress-dots">
              {Array.from({ length: TOTAL_CHECKS }, (_, i) => (
                <span key={i} className={`validate-dot ${i < passing ? 'dot-pass' : i < checks.length ? 'dot-pending' : 'dot-empty'}`} />
              ))}
            </div>
            <span>{passing} / {TOTAL_CHECKS} checks passing</span>
          </div>

          {pending > 0 && (
            <div className="setup-note">⚠ {pending} check{pending !== 1 ? 's' : ''} pending</div>
          )}

          {status === 'done' && checks.some(c => c.status === 'fail') && (
            <Btn variant="amber" size="sm" onClick={runValidation}>Retry Failed</Btn>
          )}
        </>
      )}
    </WizardCard>
  );
}
```

---

### 11. `ui/src/pages/setup/StepHandoff.jsx`

Writes completion flag via `POST /api/setup/complete`, then navigates to dashboard.

```jsx
import { useNavigate } from 'react-router-dom';
import { useState }    from 'react';
import { WizardCard }  from './WizardCard';
import { Btn }         from '../../components/Btn';
import './SetupShared.css';

const LAN_IP = '10.0.0.5'; // TODO Step 10: from stored network config

function downloadMcpConfig() {
  const config = {
    mcpServers: {
      'kovati-filesystem': { type: 'streamable_http', url: `http://${LAN_IP}:3100/mcp` },
      'kovati-browser':    { type: 'streamable_http', url: `http://${LAN_IP}:3101/mcp` },
      'kovati-code-exec':  { type: 'streamable_http', url: `http://${LAN_IP}:3102/mcp` },
      'kovati-fetch':      { type: 'streamable_http', url: `http://${LAN_IP}:3103/mcp` },
    },
  };
  const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `kovati-mcp-config-${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}

export function StepHandoff({ data }) {
  const navigate    = useNavigate();
  const [going, setGoing] = useState(false);

  async function goToDashboard() {
    setGoing(true);
    try {
      await fetch('/api/setup/complete', { method: 'POST' });
    } catch { /* best-effort — navigate regardless */ }
    sessionStorage.removeItem('setup_step');
    sessionStorage.removeItem('setup_hardware');
    sessionStorage.removeItem('setup_profile');
    sessionStorage.removeItem('setup_network');
    sessionStorage.removeItem('setup_completed');
    navigate('/dashboard');
  }

  const services = [
    { label: 'Chat UI',    url: `http://${LAN_IP}:3000`,   name: 'Open WebUI' },
    { label: 'Control',    url: `http://${LAN_IP}:8800`,   name: 'this dashboard' },
    { label: 'Monitoring', url: `http://${LAN_IP}:3001`,   name: 'Grafana' },
  ];

  return (
    <WizardCard
      title="Setup Complete"
      showNext={false}
    >
      <div className="handoff-hero">
        <div className="handoff-check">✓</div>
        <div className="handoff-title">
          {window.__KOVATI_PRODUCT_NAME__ ?? 'KOVATI OS'} is ready.
        </div>
      </div>

      <div className="handoff-meta">
        <div>Active profile: <strong>{data.profile ?? 'dual-stack'}</strong></div>
        <div>Setup completed at {new Date().toLocaleString()}</div>
      </div>

      <div className="handoff-section-label">Access your services</div>
      <div className="handoff-links">
        {services.map(s => (
          <div key={s.label} className="handoff-link-row">
            <span className="handoff-link-label">{s.label}:</span>
            <a className="handoff-link-url" href={s.url} target="_blank" rel="noreferrer">{s.url}</a>
            <span className="handoff-link-name">({s.name})</span>
          </div>
        ))}
      </div>

      <div className="handoff-section-label">MCP servers ready for Claude Desktop</div>
      <Btn variant="gray" size="sm" onClick={downloadMcpConfig}>
        Export claude_desktop_config.json
      </Btn>

      <div className="handoff-go">
        <Btn variant="cyan" size="lg" onClick={goToDashboard} disabled={going}>
          {going ? '→ Loading…' : 'Go to Dashboard →'}
        </Btn>
      </div>
    </WizardCard>
  );
}
```

---

### 12. `ui/src/pages/setup/WizardCard.jsx`

Shared wrapper for all step panels.

```jsx
import { Btn } from '../../components/Btn';
import './WizardCard.css';

export function WizardCard({
  title, children, onNext, onBack,
  nextDisabled = false, nextLabel = 'Next →',
  showNext = true, isFirst = false,
}) {
  return (
    <div className="wizard-card">
      <div className="wizard-card-title">{title}</div>
      <div className="wizard-card-body">{children}</div>
      <div className="wizard-card-footer">
        {!isFirst && onBack && (
          <Btn variant="gray" size="sm" onClick={onBack}>← Back</Btn>
        )}
        <div style={{ flex: 1 }} />
        {showNext && onNext && (
          <Btn variant="cyan" size="md" onClick={onNext} disabled={nextDisabled}>
            {nextLabel}
          </Btn>
        )}
      </div>
    </div>
  );
}
```

---

### 13. `ui/src/pages/Setup.css` + `setup/SetupShared.css`

```css
/* Setup.css */
@import '../tokens.css';

.wizard-page {
  min-height: 100vh;
  background: var(--bg);
  display: flex;
  flex-direction: column;
  align-items: center;
}

.wizard-header {
  width: 100%;
  max-width: 900px;
  padding: 24px 24px 0;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.wizard-brand {
  font-size: 14px;
  font-weight: 700;
  color: var(--text);
  letter-spacing: .04em;
}

.wizard-body {
  width: 100%;
  max-width: 680px;
  padding: 24px;
  flex: 1;
}

/* WizardCard.css */
.wizard-card {
  background: var(--surface);
  border: 1px solid var(--border2);
  border-radius: var(--radius);
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.wizard-card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  border-bottom: 1px solid var(--border);
  padding-bottom: 12px;
}

.wizard-card-body { display: flex; flex-direction: column; gap: 14px; }

.wizard-card-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
```

```css
/* SetupShared.css */
@import '../../tokens.css';

/* Step status */
.setup-ok         { font-size: 10px; color: var(--green); }
.setup-probing    { font-size: 10px; color: var(--text3); display: flex; align-items: center; gap: 8px; }
.probe-spinner    { display: inline-block; animation: spin .8s linear infinite; }
@keyframes spin   { to { transform: rotate(360deg); } }

.setup-error      { font-size: 10px; color: var(--red); display: flex; flex-direction: column; gap: 6px; }
.setup-error-hint { color: var(--text3); }
.setup-error-actions { display: flex; gap: 6px; }

.setup-actions    { display: flex; gap: 8px; align-items: center; }
.setup-note       { font-size: 9px; color: var(--text3); line-height: 1.5; }
.setup-warn-banner {
  font-size: 9px; color: var(--amber);
  background: var(--amber-dim); border: 1px solid rgba(255,179,71,.3);
  border-radius: 3px; padding: 8px 10px; line-height: 1.5;
}

/* Hardware */
.hw-result      { display: flex; flex-direction: column; gap: 10px; }
.hw-card        { background: var(--surface2); border: 1px solid var(--border); border-radius: var(--radius); padding: 12px 14px; display: flex; flex-direction: column; gap: 6px; }
.hw-section-label { font-size: 8px; color: var(--text3); text-transform: uppercase; letter-spacing: .06em; margin-top: 4px; }
.hw-row         { display: flex; gap: 8px; font-size: 10px; }
.hw-row-label   { color: var(--text3); width: 80px; flex-shrink: 0; }
.hw-row-value   { color: var(--text2); }
.hw-row-highlight .hw-row-value { color: var(--cyan); }

/* Profile step */
.profile-summary { font-size: 10px; color: var(--text3); line-height: 1.5; }
.profile-rec-card {
  display: flex; gap: 10px;
  background: var(--surface2); border: 1px solid var(--border2);
  border-radius: var(--radius); padding: 12px 14px;
}
.profile-rec-star  { font-size: 16px; color: var(--cyan); }
.profile-rec-body  { display: flex; flex-direction: column; gap: 4px; }
.profile-rec-name  { font-size: 12px; font-weight: 600; color: var(--text); }
.profile-rec-desc  { font-size: 10px; color: var(--text3); }
.profile-rec-gpus  { display: flex; gap: 4px; flex-wrap: wrap; }

.profile-picker { display: flex; flex-direction: column; gap: 4px; }
.profile-picker-row {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 10px; border-radius: 3px;
  cursor: pointer; border: 1px solid transparent;
}
.profile-picker-row:hover  { background: var(--surface2); }
.picker-selected { border-color: var(--cyan); background: var(--cyan-dim); }
.picker-radio    { font-size: 10px; color: var(--cyan); width: 14px; flex-shrink: 0; }
.picker-info     { display: flex; flex-direction: column; gap: 1px; flex: 1; }
.picker-name     { font-size: 10px; color: var(--text); }
.picker-desc     { font-size: 9px; color: var(--text3); }
.picker-gpus     { display: flex; gap: 4px; }

/* Secrets step */
.secrets-intro  { font-size: 10px; color: var(--text3); line-height: 1.5; }
.secrets-grid   { background: var(--surface2); border: 1px solid var(--border); border-radius: 3px; padding: 10px 12px; display: flex; flex-direction: column; gap: 5px; }
.secret-row     { display: flex; align-items: center; gap: 8px; }
.secret-row-key { font-family: var(--mono); font-size: 9px; color: var(--text3); width: 200px; flex-shrink: 0; }
.secret-redacted { color: var(--text3); font-size: 10px; letter-spacing: .1em; }
.secret-value-text { font-family: var(--mono); font-size: 9px; color: var(--cyan); }
.secrets-warn   { font-size: 9px; color: var(--amber); background: var(--amber-dim); border: 1px solid rgba(255,179,71,.3); border-radius: 3px; padding: 6px 10px; line-height: 1.5; }
.secrets-actions { display: flex; gap: 8px; }
.setup-checkbox { display: flex; align-items: center; gap: 8px; font-size: 10px; color: var(--text2); cursor: pointer; }

/* Network step */
.setup-field       { display: flex; flex-direction: column; gap: 6px; }
.setup-field-label { font-size: 9px; color: var(--text3); }
.setup-input       { background: var(--surface3); border: 1px solid var(--border); border-radius: 3px; color: var(--text); font-family: var(--mono); font-size: 10px; padding: 5px 8px; max-width: 200px; }
.setup-detected    { font-size: 9px; color: var(--text3); font-family: var(--mono); line-height: 1.6; }
.setup-radio-group { display: flex; flex-direction: column; gap: 4px; }
.setup-radio       { display: flex; align-items: center; gap: 6px; font-size: 10px; color: var(--text2); cursor: pointer; }
.wg-section        { margin-top: 8px; display: flex; flex-direction: column; gap: 6px; }
.wg-pubkey-row     { display: flex; align-items: center; gap: 8px; }
.wg-pubkey-label   { font-size: 9px; color: var(--text3); }
.wg-pubkey         { font-family: var(--mono); font-size: 9px; color: var(--cyan); }
.copy-btn          { background: var(--surface3); border: 1px solid var(--border); border-radius: 3px; color: var(--text3); cursor: pointer; font-size: 9px; padding: 2px 8px; }
.copy-btn-done     { color: var(--green); border-color: var(--green); }

/* Stack provisioning */
.provision-progress-row  { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.provision-bar-track     { flex: 1; height: 8px; background: var(--surface3); border-radius: 4px; overflow: hidden; }
.provision-bar-fill      { height: 100%; background: var(--cyan); border-radius: 4px; transition: width .3s ease; }
.provision-count         { font-size: 9px; color: var(--text3); white-space: nowrap; }
.provision-image-list    { display: flex; flex-direction: column; gap: 3px; max-height: 220px; overflow-y: auto; }
.provision-row           { display: flex; align-items: center; gap: 8px; font-size: 9px; padding: 2px 0; }
.provision-icon          { width: 14px; text-align: center; flex-shrink: 0; }
.provision-row-done      .provision-icon { color: var(--green); }
.provision-row-pulling   .provision-icon { color: var(--cyan); animation: spin .8s linear infinite; }
.provision-row-error     .provision-icon { color: var(--red); }
.provision-row-pending   { opacity: .4; }
.provision-name          { flex: 1; color: var(--text2); font-family: var(--mono); }
.provision-mini-bar-track { width: 80px; height: 4px; background: var(--surface3); border-radius: 2px; }
.provision-mini-bar-fill  { height: 100%; background: var(--cyan); border-radius: 2px; transition: width .2s; }
.provision-size          { color: var(--text3); white-space: nowrap; }
.provision-error         { color: var(--red); }
.provision-elapsed       { font-size: 9px; color: var(--text3); }

/* Validation */
.validate-check-list  { display: flex; flex-direction: column; gap: 3px; max-height: 220px; overflow-y: auto; }
.validate-row         { display: flex; align-items: center; gap: 8px; font-size: 9px; padding: 3px 0; }
.validate-icon        { width: 14px; text-align: center; flex-shrink: 0; }
.validate-pass  .validate-icon { color: var(--green); }
.validate-fail  .validate-icon { color: var(--red); }
.validate-pending .validate-icon { color: var(--amber); animation: spin .8s linear infinite; display: inline-block; }
.validate-name        { width: 120px; color: var(--text); flex-shrink: 0; }
.validate-port        { width: 60px; color: var(--text3); font-family: var(--mono); font-size: 8px; }
.validate-detail      { flex: 1; color: var(--text3); }
.validate-summary     { display: flex; align-items: center; gap: 10px; font-size: 9px; color: var(--text3); }
.validate-progress-dots { display: flex; gap: 2px; flex-wrap: wrap; }
.validate-dot         { width: 8px; height: 8px; border-radius: 50%; background: var(--surface3); }
.dot-pass             { background: var(--green); }
.dot-pending          { background: var(--amber); }

/* Handoff */
.handoff-hero         { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 16px 0; }
.handoff-check        { font-size: 40px; color: var(--green); }
.handoff-title        { font-size: 16px; font-weight: 700; color: var(--text); }
.handoff-meta         { font-size: 10px; color: var(--text3); display: flex; flex-direction: column; gap: 3px; }
.handoff-section-label{ font-size: 8px; color: var(--text3); text-transform: uppercase; letter-spacing: .06em; margin-top: 6px; }
.handoff-links        { display: flex; flex-direction: column; gap: 5px; }
.handoff-link-row     { display: flex; align-items: center; gap: 8px; font-size: 10px; }
.handoff-link-label   { color: var(--text3); width: 80px; flex-shrink: 0; }
.handoff-link-url     { color: var(--cyan); text-decoration: none; font-family: var(--mono); }
.handoff-link-name    { color: var(--text3); }
.handoff-go           { padding-top: 16px; border-top: 1px solid var(--border); text-align: center; }
```

---

### 14. Backend — `api/setup.py`

Add to `loadout-manager/api/setup.py` and register in `main.py`.

```python
import asyncio, shutil, subprocess, secrets as pysecrets, os
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from config import ENV_FILE, DATA_DIR, KOVATI_ROOT
from api.activity import log_event

router = APIRouter()

SETUP_COMPLETE_FLAG = DATA_DIR / ".kovati-setup-complete"

SECRET_KEYS = [
    "POSTGRES_PASSWORD", "LANGFUSE_SECRET_KEY", "LANGFUSE_SALT",
    "MINIO_ROOT_PASSWORD", "MINIO_SECRET_KEY", "AUTHENTIK_SECRET_KEY",
    "AUTHENTIK_BOOTSTRAP_PASSWORD", "N8N_ENCRYPTION_KEY", "DIFY_SECRET_KEY",
    "GRAFANA_ADMIN_PASSWORD", "OPEN_WEBUI_SECRET_KEY", "SEARXNG_SECRET_KEY",
    "CADDY_API_KEY", "KOVATI_INTERNAL_TOKEN",
]

@router.get("/api/setup/status")
async def setup_status():
    return {
        "complete": SETUP_COMPLETE_FLAG.exists(),
        "air_gap": os.getenv("KOVATI_AIR_GAP", "false").lower() == "true",
    }

@router.post("/api/setup/probe")
async def probe_hardware():
    import pynvml, psutil
    try:
        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        gpus = []
        for i in range(count):
            h = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(h)
            mem  = pynvml.nvmlDeviceGetMemoryInfo(h)
            pci  = pynvml.nvmlDeviceGetPciInfo(h)
            gpus.append({
                "index": i,
                "name": name if isinstance(name, str) else name.decode(),
                "vram_gb": round(mem.total / 1e9, 1),
                "bus_id": hex(pci.bus),
            })
        nvlink_pairs = _detect_nvlink_pairs()
    except Exception as e:
        return {"error": str(e)}

    return {
        "cpu": {
            "model": _read_cpu_model(),
            "cores": os.cpu_count(),
            "ram_gb": round(psutil.virtual_memory().total / 1e9, 0),
        },
        "gpus": gpus,
        "nvlink_pairs": nvlink_pairs,
        "total_vram_gb": sum(g["vram_gb"] for g in gpus),
        "storage": {
            "data_path": str(DATA_DIR),
            "total_gb": round(shutil.disk_usage(str(DATA_DIR)).total / 1e9, 0),
            "free_gb":  round(shutil.disk_usage(str(DATA_DIR)).free / 1e9, 1),
        },
    }

@router.post("/api/setup/generate-secrets")
async def generate_secrets():
    values = {k: pysecrets.token_urlsafe(32) for k in SECRET_KEYS}
    # Write to .env
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text("\n".join(f"{k}={v}" for k, v in values.items()) + "\n")
    log_event("secrets_generated", f"{len(values)} secrets written to .env")
    # ONLY time values are returned in an API response
    return {"keys": list(values.keys()), "values": values}

@router.post("/api/setup/network/wg-keygen")
async def wg_keygen():
    try:
        priv = subprocess.check_output(["wg", "genkey"], text=True).strip()
        pub  = subprocess.check_output(["wg", "pubkey"], input=priv, text=True).strip()
        wg_conf = Path("/etc/wireguard/wg0.conf")
        wg_conf.parent.mkdir(parents=True, exist_ok=True)
        wg_conf.write_text(f"[Interface]\nPrivateKey = {priv}\n")
        return {"public_key": pub}
    except Exception as e:
        return {"error": str(e)}

@router.post("/api/setup/provision")
async def provision(request: Request):
    air_gap = os.getenv("KOVATI_AIR_GAP", "false").lower() == "true"
    async def event_gen():
        if air_gap:
            images_dir = KOVATI_ROOT / "images"
            for tar in sorted(images_dir.glob("*.tar.gz")):
                yield f"data: PULL:{tar.stem}:0\n\n"
                proc = await asyncio.create_subprocess_exec("docker", "load", "-i", str(tar))
                await proc.wait()
                size = round(tar.stat().st_size / 1e9, 2)
                yield f"data: DONE:{tar.stem}:{size}\n\n"
        else:
            from config import COMPOSE_FILES, DOCKER_ROOT
            for svc, compose in COMPOSE_FILES.items():
                yield f"data: PULL:{svc}:0\n\n"
                proc = await asyncio.create_subprocess_exec(
                    "docker", "compose", "-f", str(DOCKER_ROOT / compose), "pull", svc,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                    cwd=str(DOCKER_ROOT),
                )
                async for line in proc.stdout:
                    pass  # consume output without forwarding individual pull lines
                await proc.wait()
                yield f"data: DONE:{svc}:0\n\n"
                if await request.is_disconnected():
                    return
    return StreamingResponse(event_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@router.post("/api/setup/validate")
async def validate(request: Request):
    import httpx
    CHECKS = [
        {"name": "PostgreSQL",  "method": "tcp",  "host": "localhost", "port": 5432},
        {"name": "MinIO",       "method": "http", "url": "http://localhost:9000/minio/health/live"},
        {"name": "Qdrant",      "method": "http", "url": "http://localhost:6333/healthz"},
        {"name": "Ollama",      "method": "http", "url": "http://localhost:11434/api/tags"},
        {"name": "vLLM Pair A", "method": "http", "url": "http://localhost:8000/v1/models"},
        {"name": "Open WebUI",  "method": "http", "url": "http://localhost:3000/health"},
        {"name": "n8n",         "method": "http", "url": "http://localhost:5678/healthz"},
        {"name": "Prometheus",  "method": "http", "url": "http://localhost:9091/-/healthy"},
        {"name": "Grafana",     "method": "http", "url": "http://localhost:3001/api/health"},
        {"name": "Authentik",   "method": "http", "url": "http://localhost:9080/api/v3/root/config/"},
    ]
    import json, socket
    async def event_gen():
        async with httpx.AsyncClient(timeout=10) as client:
            for chk in CHECKS:
                if await request.is_disconnected():
                    return
                try:
                    if chk["method"] == "tcp":
                        s = socket.create_connection((chk["host"], chk["port"]), timeout=5)
                        s.close()
                        result = {"name": chk["name"], "status": "pass", "detail": "TCP connect ok"}
                    else:
                        r = await client.get(chk["url"])
                        result = {
                            "name": chk["name"],
                            "status": "pass" if r.status_code < 400 else "fail",
                            "detail": f"HTTP {r.status_code}",
                        }
                except Exception as e:
                    result = {"name": chk["name"], "status": "fail", "detail": str(e)}
                yield f"data: {json.dumps(result)}\n\n"
                await asyncio.sleep(0.3)
    return StreamingResponse(event_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

@router.post("/api/setup/complete")
async def complete_setup():
    SETUP_COMPLETE_FLAG.parent.mkdir(parents=True, exist_ok=True)
    SETUP_COMPLETE_FLAG.touch()
    log_event("setup_complete", "First-boot wizard completed")
    return {"complete": True}

@router.delete("/api/setup/completion-flag")
async def delete_completion_flag():
    if SETUP_COMPLETE_FLAG.exists():
        SETUP_COMPLETE_FLAG.unlink()
    return {"complete": False}

def _detect_nvlink_pairs() -> list:
    try:
        out = subprocess.check_output(["nvidia-smi", "topo", "-m"], text=True, timeout=10)
        # Simple heuristic: NVLink pairs are GPU indices that share "NV" in the topo matrix
        pairs = []
        # Full implementation: parse output grid for NV# entries
        return pairs
    except Exception:
        return []

def _read_cpu_model() -> str:
    try:
        with open("/proc/cpuinfo") as f:
            for line in f:
                if "model name" in line:
                    return line.split(":")[1].strip()
    except Exception:
        pass
    return "Unknown CPU"
```

---

## Acceptance Criteria

- [ ] `/setup` renders without the Shell (no sidebar, no topbar)
- [ ] Step 1 probes hardware via `POST /api/setup/probe`; shows spinner; error path shows Retry + Skip
- [ ] Step 2 shows recommended profile card with "Change Profile" expanding all 8 options
- [ ] Step 3 generates secrets; values shown redacted; Reveal All toggles visibility; Download .env works; values are NOT stored in sessionStorage; checkbox gates Next
- [ ] Step 4 saves jumpbox IP; Generate Keypair calls `/api/setup/network/wg-keygen` and shows public key with copy button
- [ ] Step 5 shows per-image progress via SSE; Next enabled only after all done; air-gap path uses `docker load`
- [ ] Step 6 shows health check results as they arrive via SSE; continue enabled at ≥22/25 passes
- [ ] Step 7 shows service URLs, MCP config download, and "Go to Dashboard" which POSTs completion flag and clears sessionStorage
- [ ] Browser refresh on any step restores position (sessionStorage)
- [ ] On fresh load at `/#/`, if `GET /api/setup/status` returns `{complete: false}`, redirect to `/#/setup`

---

## Feedback

Write `plan/UI/GHC-Feedback/11-feedback.md` when done.

**Required in Notes:**
- Did the nested Routes pattern in App.jsx work for rendering `/setup` without the Shell, or did a different approach need to be used?
- Confirm that `sessionStorage` persists wizard position correctly across browser refresh on steps 1–6.
- Was the `POST /api/setup/generate-secrets` response body (containing values) blocked by any CSP or middleware? The frontend expects the values in the initial POST response only.
