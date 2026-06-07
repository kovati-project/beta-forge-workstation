# Step 03 — Loadout Manager

> **Prerequisites:** Steps 01–02 complete. Read `plan/UI/GHC-Plan/00-overview.md`.
> **Reference spec:** `plan/UI/Steps/03-loadout-manager.md`

---

## Goal

Implement the Loadout panel (`/#/loadout`):

1. **NVLink topology diagram** — inline SVG with live GPU state (VRAM bars, color states)
2. **Profile cards grid** — 11 cards from `/loadouts`, active/available/incompatible states
3. **Switching banner** — full-width, shown when `state.switching === true`
4. **Activate flow** — confirmation dialog, `POST /activate/{name}`, 1s poll to completion

All required endpoints (`/loadouts`, `/status`, `/activate/{name}`, `/stop`) already exist.

---

## Spec Correction — Compatibility Matrix

The `incompatible_with` data below is the authoritative corrected version. It supersedes any
matrix in `ui-design-brief.md`. Use this mock to derive incompatibility client-side if the
live `/loadouts` response doesn't include the field.

---

## Deliverables

### 1. Mock Profile Data (canonical reference)

Use this if `/loadouts` returns profiles without `incompatible_with`. Also use it to verify
the live response structure and note any field-name differences in your feedback.

```js
// Keep in Loadout.jsx — replace with live API data once confirmed matching
export const PROFILES_MOCK = [
  {
    name: 'inference-pair-a',
    description: 'Tensor-parallel 32B–40B models (NVLink A)',
    gpus: [0, 3],
    nvlink_pairs: [[0, 3]],
    services: ['vllm-pair-a', 'ollama'],
    vram_required_gb: 48,
    use_case: '32B–40B fast inference',
    accent: 'cyan',
    exclusive: false,
    incompatible_with: ['inference-small', 'inference-4gpu', 'inference-4gpu-large',
                        'dual-stack', 'training-lora-text', 'training-lora-image', 'training-unsloth'],
  },
  {
    name: 'inference-pair-b',
    description: 'Tensor-parallel 30B–70B models (NVLink B)',
    gpus: [1, 2],
    nvlink_pairs: [[1, 2]],
    services: ['vllm-pair-b'],
    vram_required_gb: 48,
    use_case: '30B–70B fast inference',
    accent: 'cyan',
    exclusive: false,
    incompatible_with: ['inference-4gpu', 'inference-4gpu-large', 'dual-stack',
                        'training-lora-text', 'training-lora-image', 'image-studio'],
  },
  {
    name: 'inference-small',
    description: 'Light inference, 7B–13B models (GPU 0+3)',
    gpus: [0, 3],
    nvlink_pairs: [[0, 3]],
    services: ['ollama'],
    vram_required_gb: 16,
    use_case: '7B–13B via Ollama',
    accent: 'cyan',
    exclusive: false,
    incompatible_with: ['inference-pair-a', 'inference-4gpu', 'inference-4gpu-large',
                        'dual-stack', 'training-lora-text', 'training-unsloth'],
  },
  {
    name: 'inference-4gpu',
    description: 'Full tensor-parallel 70B+ models (all GPUs, TP=4)',
    gpus: [0, 1, 2, 3],
    nvlink_pairs: [[0, 3], [1, 2]],
    services: ['vllm-4gpu'],
    vram_required_gb: 88,
    use_case: '70B+ full precision (TP=4)',
    accent: 'cyan',
    exclusive: false,
    incompatible_with: ['inference-pair-a', 'inference-pair-b', 'inference-small',
                        'inference-4gpu-large', 'dual-stack',
                        'training-lora-text', 'training-lora-image', 'training-unsloth', 'image-studio'],
  },
  {
    name: 'inference-4gpu-large',
    description: 'Pipeline-parallel 130B+ models (all GPUs, TP=2 PP=2)',
    gpus: [0, 1, 2, 3],
    nvlink_pairs: [[0, 3], [1, 2]],
    services: ['vllm-4gpu'],
    vram_required_gb: 96,
    use_case: '130B+ pipeline-parallel — exclusive',
    accent: 'cyan',
    exclusive: true,
    incompatible_with: ['inference-pair-a', 'inference-pair-b', 'inference-small',
                        'inference-4gpu', 'dual-stack',
                        'training-lora-text', 'training-lora-image', 'training-unsloth', 'image-studio'],
  },
  {
    name: 'dual-stack',
    description: 'Two simultaneous 32B models (NVLink A + B)',
    gpus: [0, 1, 2, 3],
    nvlink_pairs: [[0, 3], [1, 2]],
    services: ['vllm-pair-a', 'vllm-pair-b'],
    vram_required_gb: 96,
    use_case: 'Two simultaneous 32B inference endpoints',
    accent: 'cyan',
    exclusive: true,
    incompatible_with: ['inference-pair-a', 'inference-pair-b', 'inference-small',
                        'inference-4gpu', 'inference-4gpu-large',
                        'training-lora-text', 'training-lora-image', 'training-unsloth', 'image-studio'],
  },
  {
    name: 'training-lora-text',
    description: 'Text fine-tuning via Axolotl FSDP (all GPUs)',
    gpus: [0, 1, 2, 3],
    nvlink_pairs: [[0, 3], [1, 2]],
    services: ['axolotl'],
    vram_required_gb: 90,
    use_case: 'Full text fine-tune FSDP — exclusive',
    accent: 'amber',
    exclusive: true,
    incompatible_with: ['inference-pair-a', 'inference-pair-b', 'inference-small',
                        'inference-4gpu', 'inference-4gpu-large', 'dual-stack',
                        'training-lora-image', 'training-unsloth', 'image-studio'],
  },
  {
    name: 'training-lora-image',
    description: 'Image LoRA fine-tuning via Kohya_ss (GPU 1+2)',
    gpus: [1, 2],
    nvlink_pairs: [[1, 2]],
    services: ['kohya', 'label-studio'],
    vram_required_gb: 48,
    use_case: 'Stable Diffusion LoRA / DreamBooth',
    accent: 'amber',
    exclusive: false,
    incompatible_with: ['inference-pair-b', 'inference-4gpu', 'inference-4gpu-large',
                        'dual-stack', 'training-lora-text', 'training-unsloth'],
  },
  {
    name: 'training-unsloth',
    description: 'Fast LoRA fine-tuning via Unsloth (GPU 0+3)',
    gpus: [0, 3],
    nvlink_pairs: [[0, 3]],
    services: ['unsloth'],
    vram_required_gb: 48,
    use_case: 'Fast LoRA fine-tuning (NVLink A)',
    accent: 'amber',
    exclusive: false,
    incompatible_with: ['inference-pair-a', 'inference-small', 'inference-4gpu',
                        'inference-4gpu-large', 'dual-stack',
                        'training-lora-text', 'training-lora-image'],
  },
  {
    name: 'image-studio',
    description: 'Image generation + text inference (GPU 0 + pair B)',
    gpus: [0, 1, 2],
    nvlink_pairs: [[1, 2]],
    services: ['comfyui', 'real-esrgan', 'rembg', 'vllm-pair-b'],
    vram_required_gb: 72,
    use_case: 'SDXL/FLUX image gen + 32B text inference',
    accent: 'purple',
    exclusive: false,
    incompatible_with: ['inference-pair-b', 'inference-4gpu', 'inference-4gpu-large',
                        'dual-stack', 'training-lora-text', 'training-lora-image'],
  },
  {
    name: 'idle',
    description: 'No GPU allocation — CPU-only services',
    gpus: [],
    nvlink_pairs: [],
    services: ['open-webui', 'n8n', 'prometheus'],
    vram_required_gb: 0,
    use_case: 'Maintenance, scheduling, browse chat history',
    accent: 'gray',
    exclusive: false,
    incompatible_with: [],
  },
];
```

---

### 2. `ui/src/components/NvlinkDiagram.jsx`

Inline SVG component. Reads live GPU state from AppContext.

**ViewBox:** `0 0 620 150`
**GPU boxes:** 100×60px
**Layout:**
- Row 1 (Bridge A): GPU 0 box at (10, 12), GPU 3 box at (510, 12), bridge line y=42
- Row 2 (Bridge B): GPU 1 box at (10, 82), GPU 2 box at (510, 82), bridge line y=112
- Bridge lines: x1=110, x2=510 (span between box edges)
- Bridge label: x=310 (centered), same y as line

```jsx
import { useApp } from '../context/AppContext';
import './NvlinkDiagram.css';

function gpuColorState(gpu) {
  if (!gpu) return 'idle';
  if (gpu.utilization_pct > 10) {
    // derive from context — passed as prop
    return 'active';
  }
  return 'idle';
}

const STATE_FILL = {
  idle:      'rgba(107,114,152,0.06)',
  cyan:      'rgba(0,217,255,0.12)',
  amber:     'rgba(255,179,71,0.12)',
  purple:    'rgba(192,132,252,0.12)',
};

const STATE_STROKE = {
  idle:   'var(--border)',
  cyan:   'var(--cyan)',
  amber:  'var(--amber)',
  purple: 'var(--purple)',
};

export function NvlinkDiagram({ activeProfile, profiles }) {
  const { state } = useApp();

  // Determine accent color for each GPU from the active profile
  function gpuAccent(gpuIndex) {
    if (!activeProfile || !profiles) return 'idle';
    const profile = profiles.find(p => p.name === activeProfile);
    if (!profile || !profile.gpus.includes(gpuIndex)) return 'idle';
    return profile.accent ?? 'cyan';
  }

  function renderGpuBox(gpuIndex, x, y) {
    const gpu = state.gpus.find(g => g.index === gpuIndex) ?? {
      index: gpuIndex, vram_used_gb: 0, vram_total_gb: 24, utilization_pct: 0, temp_c: 0
    };
    const accent = gpuAccent(gpuIndex);
    const fill   = STATE_FILL[accent]   ?? STATE_FILL.idle;
    const stroke = STATE_STROKE[accent] ?? STATE_STROKE.idle;

    const vramPct  = Math.min(gpu.vram_used_gb / gpu.vram_total_gb, 1);
    const barWidth = Math.round(vramPct * 96); // 100px wide box, 2px padding each side

    const isPulsing = state.switching && accent !== 'idle';

    return (
      <g key={gpuIndex}>
        <rect
          x={x} y={y} width={100} height={60}
          fill={fill} stroke={stroke} strokeWidth={isPulsing ? 2 : 1}
          rx={4}
          className={isPulsing ? 'nvlink-box-pulse' : ''}
        />
        {/* VRAM fill bar at bottom */}
        <rect
          x={x + 2} y={y + 52} width={barWidth} height={6}
          fill={stroke} opacity={0.6} rx={2}
        />
        {/* GPU label */}
        <text x={x + 10} y={y + 18}
          fill="var(--text)" fontSize={10} fontWeight={600} fontFamily="var(--mono)">
          GPU {gpuIndex}
        </text>
        {/* VRAM text */}
        <text x={x + 10} y={y + 32}
          fill="var(--text2)" fontSize={9} fontFamily="var(--mono)">
          {gpu.vram_used_gb.toFixed(1)}/{gpu.vram_total_gb} GB
        </text>
        {/* Util + Temp */}
        <text x={x + 10} y={y + 44}
          fill="var(--text3)" fontSize={8} fontFamily="var(--mono)">
          {gpu.utilization_pct}% · {gpu.temp_c}°C
        </text>
      </g>
    );
  }

  function renderBridge(bridgeName, y, accent) {
    const isActive = accent !== 'idle';
    const strokeColor = STATE_STROKE[accent] ?? STATE_STROKE.idle;
    const dashArray  = isActive ? '6,3' : '4,4';
    const opacity    = isActive ? 1 : 0.4;
    const labelColor = isActive ? strokeColor : 'var(--text3)';

    return (
      <g key={bridgeName}>
        <line
          x1={110} y1={y} x2={510} y2={y}
          stroke={strokeColor} strokeWidth={isActive ? 2 : 1}
          strokeDasharray={dashArray} opacity={opacity}
          className={isActive ? 'nvlink-bridge-animate' : ''}
        />
        <text x={310} y={y - 5}
          textAnchor="middle" fill={labelColor}
          fontSize={8} fontFamily="var(--mono)" letterSpacing={0.3}>
          {bridgeName} · 56.25 GB/s
        </text>
      </g>
    );
  }

  // Determine bridge accent: both GPUs in pair must match to show active color
  const bridgeAAccent = gpuAccent(0) !== 'idle' ? gpuAccent(0) : 'idle';
  const bridgeBAccent = gpuAccent(1) !== 'idle' ? gpuAccent(1) : 'idle';

  return (
    <div className="nvlink-diagram-wrap">
      <svg
        viewBox="0 0 620 150"
        className="nvlink-svg"
        aria-label="NVLink topology diagram"
      >
        {/* Row 1 — Bridge A */}
        {renderGpuBox(0, 10, 12)}
        {renderGpuBox(3, 510, 12)}
        {renderBridge('Bridge A', 42, bridgeAAccent)}

        {/* Row 2 — Bridge B */}
        {renderGpuBox(1, 10, 82)}
        {renderGpuBox(2, 510, 82)}
        {renderBridge('Bridge B', 112, bridgeBAccent)}
      </svg>
    </div>
  );
}
```

`NvlinkDiagram.css`:
```css
@import '../tokens.css';

.nvlink-diagram-wrap {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 12px;
}

.nvlink-svg {
  width: 100%;
  height: auto;
  display: block;
}

@keyframes nvlink-dash {
  to { stroke-dashoffset: -18; }
}

.nvlink-bridge-animate {
  animation: nvlink-dash 1s linear infinite;
}

@keyframes box-pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: .5; }
}

.nvlink-box-pulse {
  animation: box-pulse 1s ease-in-out infinite;
}
```

---

### 3. Profile Card Component — `ui/src/components/ProfileCard.jsx`

```jsx
import { Tag } from './Tag';
import { Btn } from './Btn';
import './ProfileCard.css';

function MiniGpuDiagram({ claimedGpus, accentColor }) {
  const all = [0, 1, 2, 3];
  // NVLink pairs: [0,3] and [1,2]
  const pairs = [[0, 3], [1, 2]];
  const claimed = new Set(claimedGpus);

  return (
    <div className="mini-gpu-diagram">
      <div className="mini-gpu-row">
        {all.map(i => (
          <div
            key={i}
            className={`mini-gpu-box ${claimed.has(i) ? `mini-gpu-active mini-gpu-${accentColor}` : ''}`}
          >
            {i}
          </div>
        ))}
      </div>
      {pairs.map(([a, b]) => {
        if (claimed.has(a) && claimed.has(b)) {
          return (
            <div key={`${a}-${b}`} className={`mini-bridge mini-bridge-${accentColor}`}>
              {a === 0 ? 'Bridge A' : 'Bridge B'}
            </div>
          );
        }
        return null;
      })}
    </div>
  );
}

export function ProfileCard({ profile, isActive, isSwitching, currentGpuState, onActivate }) {
  // VRAM pre-check: sum vram_free_gb for claimed GPUs
  const availableVram = (currentGpuState ?? [])
    .filter(g => profile.gpus.includes(g.index))
    .reduce((sum, g) => sum + g.vram_free_gb, 0);

  const vramOk = profile.vram_required_gb === 0 || availableVram >= profile.vram_required_gb;
  const accent = profile.accent ?? 'cyan';

  return (
    <div
      className={`profile-card ${isActive ? 'profile-card-active' : ''} profile-card-${accent}`}
      id={`profile-${profile.name}`}
    >
      {/* Top-right badge */}
      {isActive && (
        <span className="profile-badge profile-badge-active">ACTIVE</span>
      )}

      <div className="profile-name">{profile.name}</div>
      <div className="profile-desc">{profile.description}</div>

      <MiniGpuDiagram claimedGpus={profile.gpus} accentColor={accent} />

      <div className="profile-services">
        {profile.services.map(s => (
          <Tag key={s} variant={accent}>{s}</Tag>
        ))}
      </div>

      {/* VRAM pre-check */}
      {profile.vram_required_gb > 0 && (
        <div className={`profile-vram-check ${vramOk ? 'vram-ok' : 'vram-low'}`}>
          ~{profile.vram_required_gb} GB · {availableVram.toFixed(0)} GB avail{' '}
          {vramOk ? '✓' : '✗'}
        </div>
      )}

      <Btn
        variant={isActive ? 'gray' : accent === 'cyan' ? 'cyan' : accent === 'amber' ? 'amber' : 'gray'}
        size="md"
        disabled={isActive || isSwitching}
        onClick={() => onActivate(profile)}
      >
        {isActive ? 'Active' : isSwitching ? 'Switching…' : 'Activate'}
      </Btn>
    </div>
  );
}
```

`ProfileCard.css`:
```css
@import '../tokens.css';

.profile-card {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  transition: border-color .2s, background .2s;
}

.profile-card:hover:not(.profile-card-active) {
  border-color: var(--border2);
}

.profile-card-active {
  border: 2px solid var(--cyan);
  background: rgba(0,217,255,.04);
}

/* Inactive card badge positions */
.profile-badge {
  position: absolute;
  top: 10px;
  right: 10px;
  font-size: 9px;
  font-weight: 600;
  letter-spacing: .5px;
  padding: 1px 6px;
  border-radius: 3px;
}

.profile-badge-active {
  background: var(--cyan-dim);
  color: var(--cyan);
  border: 1px solid rgba(0,217,255,.35);
}

.profile-badge-locked {
  background: var(--surface3);
  color: var(--text3);
}

.profile-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text);
  padding-right: 50px; /* avoid badge overlap */
}

.profile-desc {
  font-size: 10px;
  color: var(--text3);
}

.profile-services {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.profile-vram-check {
  font-size: 9px;
}

.vram-ok  { color: var(--green); }
.vram-low { color: var(--red); }

/* Mini GPU diagram */
.mini-gpu-diagram {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.mini-gpu-row {
  display: flex;
  gap: 3px;
}

.mini-gpu-box {
  width: 22px;
  height: 16px;
  border: 1px solid var(--border);
  border-radius: 2px;
  background: transparent;
  font-size: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text3);
}

.mini-gpu-active {
  font-weight: 600;
}

.mini-gpu-cyan   { background: var(--cyan-dim);   border-color: var(--cyan);   color: var(--cyan); }
.mini-gpu-amber  { background: var(--amber-dim);  border-color: var(--amber);  color: var(--amber); }
.mini-gpu-purple { background: var(--purple-dim); border-color: var(--purple); color: var(--purple); }
.mini-gpu-gray   { background: var(--surface2);   border-color: var(--border2); color: var(--text3); }

.mini-bridge {
  font-size: 7px;
  letter-spacing: .3px;
  color: var(--text3);
  padding-left: 2px;
}

.mini-bridge-cyan   { color: var(--cyan); }
.mini-bridge-amber  { color: var(--amber); }
.mini-bridge-purple { color: var(--purple); }

/* Incompatible card */
.profile-card-incompatible {
  opacity: 0.45;
  cursor: default;
}

.profile-card-incompatible .profile-badge-locked {
  display: block;
}
```

---

### 4. Switching Banner

Extract as `ui/src/components/SwitchingBanner.jsx` — it is reused by both the Loadout page and
the Dashboard's loadout banner.

```jsx
export function SwitchingBanner({ targetProfile, phase }) {
  const phaseLabel = phase ?? 'stopping services…';

  return (
    <div className="switching-banner">
      <div className="switching-banner-header">
        <span className="switching-spin">⟳</span>
        <span>SWITCHING TO {targetProfile?.toUpperCase()}</span>
      </div>
      <div className="switching-banner-bar">
        <div className="switching-banner-fill" />
      </div>
      <div className="switching-banner-phase">{phaseLabel}</div>
      <div className="switching-banner-warn">GPU VRAM draining — do not power off · ~3–5 seconds</div>
    </div>
  );
}
```

```css
/* SwitchingBanner.css */
@import '../tokens.css';

.switching-banner {
  background: var(--surface);
  border: 1px solid var(--cyan);
  border-radius: var(--radius);
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  animation: banner-border-pulse 1s ease-in-out infinite;
}

@keyframes banner-border-pulse {
  0%, 100% { border-color: var(--cyan); }
  50%       { border-color: var(--border); }
}

.switching-banner-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--cyan);
  letter-spacing: .5px;
}

.switching-spin {
  display: inline-block;
  animation: spin 1s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.switching-banner-bar {
  height: 4px;
  background: var(--surface3);
  border-radius: 2px;
  overflow: hidden;
}

.switching-banner-fill {
  height: 100%;
  width: 35%;
  background: var(--cyan);
  animation: progress-slide 1.4s ease-in-out infinite;
}

@keyframes progress-slide {
  0%   { transform: translateX(-200%); }
  100% { transform: translateX(500%); }
}

.switching-banner-phase {
  font-size: 10px;
  color: var(--text2);
}

.switching-banner-warn {
  font-size: 9px;
  color: var(--text3);
}
```

---

### 5. `ui/src/pages/Loadout.jsx`

```jsx
import { useState, useEffect, useMemo } from 'react';
import { useApp } from '../context/AppContext';
import { NvlinkDiagram } from '../components/NvlinkDiagram';
import { ProfileCard }   from '../components/ProfileCard';
import { SwitchingBanner } from '../components/SwitchingBanner';
import { PROFILES_MOCK } from './Loadout.mock';
import './Loadout.css';

// Determine if confirmation is needed before activating a profile
function needsConfirmation(targetProfile, activeProfile, runningServices) {
  if (!activeProfile) return false;
  if (targetProfile.exclusive) return true;
  // Switching away from inference while services are running
  if (runningServices.length > 0) return true;
  return false;
}

export function Loadout() {
  const { state, dispatch } = useApp();
  const [profiles, setProfiles] = useState([]);
  const [switchError, setSwitchError] = useState(null);

  useEffect(() => {
    fetch('/loadouts')
      .then(r => r.json())
      .then(data => {
        // Handle both { profiles: [...] } and flat array response shapes
        const list = Array.isArray(data) ? data : (data.profiles ?? []);
        // Merge incompatible_with from mock if not in API response
        const merged = list.map(p => {
          const mock = PROFILES_MOCK.find(m => m.name === p.name);
          return mock
            ? { ...mock, ...p, incompatible_with: p.incompatible_with ?? mock.incompatible_with }
            : p;
        });
        setProfiles(merged.length > 0 ? merged : PROFILES_MOCK);
      })
      .catch(() => setProfiles(PROFILES_MOCK));
  }, []);

  function isIncompatible(profile) {
    if (!state.activeProfile) return false;
    const active = profiles.find(p => p.name === state.activeProfile);
    return active?.incompatible_with?.includes(profile.name) ?? false;
  }

  async function handleActivate(profile) {
    setSwitchError(null);
    if (isIncompatible(profile)) return; // button should be disabled anyway

    if (needsConfirmation(profile, state.activeProfile, state.runningServices)) {
      const ok = window.confirm(
        `Activate "${profile.name}"?\n\nThis will stop all currently running services.`
      );
      if (!ok) return;
    }

    try {
      const res = await fetch(`/activate/${profile.name}`, { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      // AppContext switching state is updated by useGpuStatus polling
    } catch (e) {
      setSwitchError(`Failed to activate "${profile.name}": ${e.message}`);
    }
  }

  const activeSwitchingTarget = state.switching ? state.activeProfile : null;

  if (profiles.length === 0) {
    return (
      <div className="loadout-empty-state">
        No profiles found — check <code>profiles.yaml</code>
      </div>
    );
  }

  return (
    <div className="loadout-page">
      <NvlinkDiagram activeProfile={state.activeProfile} profiles={profiles} />

      {state.switching && (
        <SwitchingBanner
          targetProfile={activeSwitchingTarget}
          phase={state.switchingPhase}
        />
      )}

      {switchError && (
        <div className="loadout-error">
          ⚠ {switchError}
          <button className="loadout-error-dismiss" onClick={() => setSwitchError(null)}>✕</button>
        </div>
      )}

      <div className="profile-grid">
        {profiles.map(profile => {
          const incompatible = isIncompatible(profile);
          return (
            <div
              key={profile.name}
              className={incompatible ? 'profile-card-incompatible' : ''}
              title={incompatible
                ? `Incompatible with ${state.activeProfile} — stop current profile first`
                : undefined}
            >
              <ProfileCard
                profile={profile}
                isActive={profile.name === state.activeProfile}
                isSwitching={state.switching}
                currentGpuState={state.gpus}
                onActivate={incompatible ? () => {} : handleActivate}
              />
              {incompatible && (
                <span className="profile-lock-overlay">🔒</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

Also create `ui/src/pages/Loadout.mock.js` exporting the `PROFILES_MOCK` array from Deliverable 1.

---

### 6. `ui/src/pages/Loadout.css`

```css
@import '../tokens.css';

.loadout-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.profile-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 10px;
}

.loadout-error {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--red-dim);
  border: 1px solid var(--red);
  border-radius: var(--radius);
  padding: 8px 12px;
  font-size: 10px;
  color: var(--red);
}

.loadout-error-dismiss {
  background: none;
  border: none;
  color: var(--red);
  cursor: pointer;
  font-size: 12px;
  padding: 0 4px;
}

.loadout-empty-state {
  padding: 32px;
  text-align: center;
  font-size: 11px;
  color: var(--text3);
}

/* Incompatible card wrapper */
.profile-card-incompatible {
  position: relative;
  opacity: 0.45;
  pointer-events: none;
}

.profile-lock-overlay {
  position: absolute;
  top: 10px;
  right: 10px;
  font-size: 12px;
  pointer-events: none;
}
```

---

### 7. AppContext update — add `switchingPhase`

Add `switchingPhase: null` to `initialState` and handle it in the reducer:

```js
case 'SET_GPU_STATUS':
  return {
    ...state,
    ...action.payload,
    switchingPhase: action.payload.switching_phase ?? null,
  };
```

This field comes from `/status` when available. If the endpoint doesn't return it, it stays null
and the SwitchingBanner uses its default phase text.

---

## Acceptance Criteria

- [ ] NVLink topology SVG renders all 4 GPU boxes with live data from AppContext (VRAM text, util%, temp)
- [ ] GPU boxes in active profile are cyan-tinted, idle boxes have subdued fill
- [ ] Bridge lines animate (dashed scrolling) when their pair is active, static dashed when idle
- [ ] GPU boxes pulse during `state.switching === true`
- [ ] Profile grid shows all 11 cards in auto-fill layout (`inference-small`, `inference-pair-a`, `inference-pair-b`, `inference-4gpu`, `inference-4gpu-large`, `dual-stack`, `image-studio`, `training-lora-image`, `training-lora-text`, `training-unsloth`, `idle`)
- [ ] Active profile card has cyan 2px border and "ACTIVE" badge
- [ ] Incompatible cards render at 50% opacity with 🔒 badge and `pointer-events: none`
- [ ] VRAM pre-check: green ✓ when avail > required, red ✗ when avail < required
- [ ] Mini GPU diagram: claimed squares have colored fill matching profile accent
- [ ] "Activate" shows `window.confirm` when switching away from a running profile
- [ ] `POST /activate/{name}` is called after confirmation; AppContext `switching` flips via next poll
- [ ] SwitchingBanner appears when `state.switching === true`; disappears when `false`
- [ ] No active profile renders "No profiles found" or profiles in available state

---

## Feedback

Write `plan/UI/GHC-Feedback/03-feedback.md` when done.

**Required in Notes:** Confirm the actual field name for the GPU list in the `/loadouts` response
(is it `gpus`, `gpu_ids`, `claimed_gpus`, or something else?). Also confirm whether `/loadouts`
returns `{ profiles: [...] }` or a flat array. These details are needed by future steps.
