# Step 15 — Profile & Service Corrections

> **Prerequisites:** Steps 01–07 already complete (feedback filed). Steps 08–14 may or may not be complete.
> **Context:** A gap analysis against `plan/PROJECT_PLAN.md` found that the executed step 03 (Loadout Manager) was built against an incomplete profile list, and the Tools panel (step 04) has no concept of always-on services. This step corrects both without touching any other panel.

No new pages. Changes are isolated to:
- `ui/src/pages/Loadout.mock.js`
- `ui/src/pages/Loadout.jsx` (minor, one condition)
- `ui/src/data/servicesMock.js` (or wherever the Tools mock lives — check step 04 output)
- `ui/src/components/tools/ServiceCard.jsx` (or equivalent)

---

## Part A — Profile Mock Corrections

### A1 — Missing and incorrect profiles

Open `ui/src/pages/Loadout.mock.js`. The current mock has **8 entries**. Replace the entire `PROFILES_MOCK` array with the following **11-entry corrected version**:

```js
// ui/src/pages/Loadout.mock.js
export const PROFILES_MOCK = [
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
    incompatible_with: [
      'inference-pair-a', 'inference-4gpu', 'inference-4gpu-large',
      'dual-stack', 'training-lora-text', 'training-unsloth',
    ],
  },
  {
    name: 'inference-pair-a',
    description: 'Tensor-parallel 32B–40B models (NVLink A)',
    gpus: [0, 3],
    nvlink_pairs: [[0, 3]],
    services: ['vllm-pair-a', 'ollama'],
    vram_required_gb: 48,
    use_case: '32B–40B fast inference (NVLink A)',
    accent: 'cyan',
    exclusive: false,
    incompatible_with: [
      'inference-small', 'inference-4gpu', 'inference-4gpu-large',
      'dual-stack', 'training-lora-text', 'training-lora-image', 'training-unsloth',
    ],
  },
  {
    name: 'inference-pair-b',
    description: 'Tensor-parallel 32B–40B models (NVLink B)',
    gpus: [1, 2],
    nvlink_pairs: [[1, 2]],
    services: ['vllm-pair-b'],
    vram_required_gb: 48,
    use_case: '32B–40B fast inference (NVLink B)',
    accent: 'cyan',
    exclusive: false,
    incompatible_with: [
      'inference-4gpu', 'inference-4gpu-large', 'dual-stack',
      'training-lora-text', 'training-lora-image', 'image-studio',
    ],
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
    incompatible_with: [
      'inference-pair-a', 'inference-pair-b', 'inference-small', 'inference-4gpu-large',
      'dual-stack', 'training-lora-text', 'training-lora-image', 'training-unsloth', 'image-studio',
    ],
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
    incompatible_with: [
      'inference-pair-a', 'inference-pair-b', 'inference-small', 'inference-4gpu',
      'dual-stack', 'training-lora-text', 'training-lora-image', 'training-unsloth', 'image-studio',
    ],
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
    incompatible_with: [
      'inference-pair-a', 'inference-pair-b', 'inference-small',
      'inference-4gpu', 'inference-4gpu-large',
      'training-lora-text', 'training-lora-image', 'training-unsloth', 'image-studio',
    ],
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
    incompatible_with: [
      'inference-pair-b', 'inference-4gpu', 'inference-4gpu-large',
      'dual-stack', 'training-lora-text', 'training-lora-image',
    ],
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
    incompatible_with: [
      'inference-pair-b', 'inference-4gpu', 'inference-4gpu-large',
      'dual-stack', 'training-lora-text', 'training-unsloth',
    ],
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
    incompatible_with: [
      'inference-pair-a', 'inference-pair-b', 'inference-small',
      'inference-4gpu', 'inference-4gpu-large', 'dual-stack',
      'training-lora-image', 'training-unsloth', 'image-studio',
    ],
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
    incompatible_with: [
      'inference-pair-a', 'inference-small', 'inference-4gpu',
      'inference-4gpu-large', 'dual-stack',
      'training-lora-text', 'training-lora-image',
    ],
  },
  {
    name: 'idle',
    description: 'No GPU allocation — CPU-only services',
    gpus: [],
    nvlink_pairs: [],
    services: [],
    vram_required_gb: 0,
    use_case: 'Maintenance, scheduling, browse chat history',
    accent: 'gray',
    exclusive: false,
    incompatible_with: [],
  },
];
```

### A2 — Changes summary vs old mock

| Profile | Change |
|---------|--------|
| `inference-small` | Removed `llama-cpp`, `tabby` from services (not in catalog); GPUs corrected to `[0, 3]` |
| `inference-pair-a` | `incompatible_with` expanded to include `inference-4gpu-large`, `dual-stack`, `training-unsloth` |
| `inference-pair-b` | `incompatible_with` expanded; added `image-studio` |
| `inference-4gpu` | `vram_required_gb` corrected to 88 (not 96); description clarified TP=4; `incompatible_with` expanded |
| `inference-4gpu-large` | **NEW** — all 4 GPUs, TP=2 PP=2, 96 GB, exclusive |
| `dual-stack` | **NEW** — was missing entirely from the old mock |
| `image-studio` | GPUs corrected to `[0, 1, 2]` (GPU 3 not used); services expanded to include `real-esrgan`, `rembg`; VRAM corrected to 72 GB |
| `training-lora-image` | Added `label-studio` to services; `incompatible_with` expanded |
| `training-lora-text` | **GPUs corrected to `[0,1,2,3]`** (Axolotl FSDP uses all 4 GPUs, not just [0,3]); VRAM corrected to 90 GB |
| `training-unsloth` | **NEW** — GPU 0+3, NVLink A, 48 GB |
| `idle` | `services` corrected to `[]` (was listing `open-webui`, `n8n`, `prometheus` which are always-on, not profile-managed) |

### A3 — Loadout.jsx change: dynamic card label

In `Loadout.jsx`, anywhere that hardcodes the string "8 profiles" or a literal count of profiles, replace with a dynamic count:

```jsx
// Before
<p className="loadout-subtitle">8 GPU allocation profiles</p>

// After
<p className="loadout-subtitle">{profiles.length} GPU allocation profiles</p>
```

If no such label exists, skip this change.

---

## Part B — Always-On Services in Tools Panel

### B1 — What "always-on" means

The Tools panel currently shows all services with enable/disable toggles. Some services **must never be stopped by the operator** — they are infrastructure that other services depend on (auth, DB, monitoring). These are displayed differently:

- **No enable/disable toggle** — replaced with a `SYSTEM` badge
- **Cannot be stopped from the UI** — the stop button is hidden
- **Always show as running** (or show an error state if they're somehow down, without offering a stop action)

### B2 — Always-on service list

Add this constant to the services mock file (wherever step 04 placed the services mock data — likely `ui/src/data/servicesMock.js` or `ui/src/data/toolsMock.js`):

```js
// Services that run independent of loadout profiles.
// The UI must not offer enable/disable toggles for these.
export const ALWAYS_ON_SERVICES = new Set([
  'postgres',
  'postgresql',
  'open-webui',
  'searxng',
  'prometheus',
  'grafana',
  'node-exporter',
  'cadvisor',
  'authentik-server',
  'authentik-worker',
  'n8n',
  'langfuse',
  'langfuse-worker',
]);
```

The set uses the Docker service names as they appear in the compose files. If GHC's step 04 used different names in the mock, match them exactly — the important thing is that the set is checked, not the specific names.

### B3 — ServiceCard update

In the ServiceCard component (check the file GHC created in step 04 — likely `ui/src/components/tools/ServiceCard.jsx` or `ui/src/pages/tools/ServiceCard.jsx`), make the following change:

**Before** (schematic — match the actual code):
```jsx
<div className="service-card-actions">
  <Toggle checked={service.enabled} onChange={() => onToggle(service.name)} />
  <Btn size="sm" onClick={() => onViewLogs(service.name)}>Logs</Btn>
</div>
```

**After**:
```jsx
import { ALWAYS_ON_SERVICES } from '../../data/servicesMock';

// Inside the component:
const isAlwaysOn = ALWAYS_ON_SERVICES.has(service.name);

<div className="service-card-actions">
  {isAlwaysOn ? (
    <span className="service-badge-system" title="System service — managed independently of loadout profiles">
      SYSTEM
    </span>
  ) : (
    <Toggle checked={service.enabled} onChange={() => onToggle(service.name)} />
  )}
  <Btn size="sm" onClick={() => onViewLogs(service.name)}>Logs</Btn>
</div>
```

Add to the service card CSS (same file as the existing `.service-badge-*` classes):
```css
.service-badge-system {
  font-size: 9px;
  font-weight: 600;
  letter-spacing: .5px;
  padding: 2px 7px;
  border-radius: 3px;
  background: var(--surface3);
  color: var(--text3);
  border: 1px solid var(--border2);
  white-space: nowrap;
}
```

### B4 — Stop All button guard

In the Tools panel's "Stop All" action (if one exists), add a guard so always-on services are excluded:

```js
async function handleStopAll() {
  const stoppable = services.filter(s => !ALWAYS_ON_SERVICES.has(s.name) && s.enabled);
  if (stoppable.length === 0) return;
  const ok = window.confirm(`Stop ${stoppable.length} services? System services will keep running.`);
  if (!ok) return;
  // ... existing stop logic using stoppable list
}
```

---

## Part C — Verify Backend Profile Config

### C1 — Check profiles.yaml

Open `loadout-manager/profiles.yaml` (or wherever the backend profile definitions live). Verify that:

1. `inference-4gpu-large` exists as a profile with `pipeline_parallel: 2`, `tensor_parallel: 2`
2. `dual-stack` exists as a profile starting both `vllm-pair-a` and `vllm-pair-b`
3. `training-unsloth` exists as a profile starting the `unsloth` service
4. `training-lora-text` claims GPUs `[0, 1, 2, 3]` (all four, not just [0, 3])
5. `image-studio` claims GPUs `[0, 1, 2]` and starts `comfyui`, `real-esrgan`, `rembg`, `vllm-pair-b`

If `profiles.yaml` is missing any of these entries, **add them**. Each profile should follow the existing file's schema exactly. Do not change any existing profile entry unless fixing an error found by checking against this list.

If the backend profile format does not have a `pipeline_parallel` field and the `vllm-4gpu` service is launched with command-line flags instead, make sure the `inference-4gpu-large` profile launches `vllm-4gpu` with `--tensor-parallel-size 2 --pipeline-parallel-size 2` instead of the `--tensor-parallel-size 4` used by `inference-4gpu`.

This may require a separate service entry in the compose file: `vllm-4gpu-large` (or a runtime flag override). Document the approach chosen in the feedback file.

### C2 — Check compose files for missing services

Verify `docker/compose.training.yml` has a service entry for `unsloth`. If it is missing, add:

```yaml
  unsloth:
    image: unsloth/unsloth:latest
    runtime: nvidia
    environment:
      - NVIDIA_VISIBLE_DEVICES=${UNSLOTH_GPU_IDS:-0,3}
    volumes:
      - /data/models:/models
      - /data/training:/workspace
    ports:
      - "8501:8501"
    profiles:
      - training-unsloth
    restart: unless-stopped
```

---

## Acceptance Criteria

- [ ] `PROFILES_MOCK` has exactly 11 entries matching the list in §A1
- [ ] `inference-4gpu-large` profile card renders correctly in the grid — all 4 GPU squares lit cyan, `exclusive: true` label visible, VRAM shows 96 GB required
- [ ] `dual-stack` card renders correctly — all 4 GPU squares lit cyan, Bridge A and Bridge B labels shown, `exclusive: true`
- [ ] `training-unsloth` card renders correctly — GPU squares 0 and 3 lit amber, Bridge A label shown
- [ ] `training-lora-text` card shows 4 GPU squares lit (not 2) and VRAM requirement 90 GB
- [ ] `image-studio` card shows 3 GPU squares lit (0, 1, 2), services include `real-esrgan` and `rembg`
- [ ] `idle` card shows no GPU squares lit and no service tags
- [ ] All 11 cards render without console errors
- [ ] Incompatibility locks correctly: activating `inference-pair-a` dims `inference-4gpu-large`, `dual-stack`, `training-unsloth` (in addition to existing incompatibles)
- [ ] Always-on services in the Tools panel show `SYSTEM` badge instead of enable/disable toggle
- [ ] Always-on services are excluded from any "Stop All" operation
- [ ] `profiles.yaml` backend file has all 11 profiles (or documents why some are missing)

---

## Feedback

Write `plan/UI/GHC-Feedback/15-feedback.md` when done.

**Required in Notes:**
- Confirm whether `inference-4gpu-large` requires a separate compose service entry (`vllm-4gpu-large`) or can reuse `vllm-4gpu` with different flags passed at activation time. Document the approach.
- List which always-on services already had `SYSTEM` treatment (none expected) vs which required the badge to be added.
- Confirm the exact Docker service names used for `unsloth` and `real-esrgan` in the compose files — these must match `ALWAYS_ON_SERVICES` set entries.
- Were any profiles already present in `profiles.yaml` that needed correction (e.g., wrong GPU list for `training-lora-text`)? List them.
