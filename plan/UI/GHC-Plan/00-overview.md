# KOVATI OS — GHC Working Instructions

> Read this file once before starting any step. It establishes project context, standing rules,
> repo layout, and how to write feedback. These instructions apply to every step unless a step
> file explicitly overrides them.

---

## What You Are Building

A single browser-based UI — **KOVATI OS** — that acts as the control plane for a bare-metal
multi-GPU AI workstation. It replaces 20+ individual service UIs. The operator opens one URL
(`:8800`) and from there can:

- Monitor all 4 GPUs in real time
- Switch between GPU allocation profiles (loadouts) with one click
- Enable/disable individual Docker services
- Launch LoRA fine-tuning jobs (text and image)
- Browse models, datasets, checkpoints, and vector collections
- Expose MCP servers and OpenAI-compatible endpoints
- View metrics, logs, and LLM traces

**Audience:** ML engineers and power users. Not a consumer product.

---

## Hardware (Fixed — Do Not Abstract Away)

| Component | Spec |
|-----------|------|
| CPU | AMD Threadripper Pro 5955WX — 32 cores |
| RAM | 512 GB DDR4 ECC |
| GPU 0 | NVIDIA RTX A5500 — 24 GB VRAM — NVLink Bridge A |
| GPU 1 | NVIDIA RTX A5500 — 24 GB VRAM — NVLink Bridge B |
| GPU 2 | NVIDIA RTX A5500 — 24 GB VRAM — NVLink Bridge B |
| GPU 3 | NVIDIA RTX A5500 — 24 GB VRAM — NVLink Bridge A |
| Total VRAM | 96 GB |

NVLink pairs: GPU 0 ↔ GPU 3 (Bridge A), GPU 1 ↔ GPU 2 (Bridge B). These pairs must never be
split across active profiles.

---

## Tech Stack

| Concern | Choice |
|---------|--------|
| Frontend | React 18, Vite 5 |
| Routing | React Router v6, **hash mode** (`/#/dashboard`) |
| Styling | Plain CSS custom properties — **no Tailwind, no CSS-in-JS** |
| Font | JetBrains Mono loaded via `<link>` in `index.html` (IBM Plex Mono as fallback) |
| Icons | Unicode glyphs or inline SVG — no icon library |
| State | React Context + `useReducer` (`AppContext`) |
| Charts | Vanilla `<canvas>` for MVP — no chart library |
| Backend | Extend existing FastAPI (`loadout-manager/main.py`) at `:8800` |
| Real-time | Polling (3s GPU, 10s services) for most data; SSE for training log streams |
| Build output | `ui/dist/` → copied to `loadout-manager/static/` → served by FastAPI |

---

## Repository Layout

```
ai-workstation-project/
├── loadout-manager/
│   ├── main.py              ← Existing FastAPI — extend, do not rewrite from scratch
│   ├── profiles.yaml        ← GPU profiles — source of truth, do not modify
│   ├── api/                 ← NEW: split routers added here
│   │   ├── services.py
│   │   ├── metrics.py
│   │   └── ...
│   └── static/              ← Built React app (gitignored, produced by npm run build)
├── ui/                      ← NEW: React frontend
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── tokens.css
│   │   ├── shell.css
│   │   ├── context/AppContext.jsx
│   │   ├── hooks/
│   │   ├── components/
│   │   └── pages/
│   ├── public/
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── docker/
│   ├── compose.inference.yml
│   ├── compose.studio.yml
│   ├── compose.training.yml
│   ├── compose.agentic.yml
│   ├── compose.storage.yml
│   ├── compose.webui.yml
│   ├── compose.voice.yml
│   ├── compose.monitoring.yml
│   └── compose.auth.yml
└── scripts/
    ├── healthcheck.sh
    ├── start-all.sh
    └── update-system.sh
```

---

## Design Tokens (Canonical — Use Everywhere)

All colors are CSS custom properties defined in `ui/src/tokens.css`. No hardcoded hex values
in any component file.

```css
:root {
  --bg:         #0a0e27;   /* page background */
  --surface:    #1a1f3a;   /* primary card */
  --surface2:   #232844;   /* nested card */
  --surface3:   #2a3050;   /* input background */
  --border:     #2e3560;
  --border2:    #3d4580;

  --cyan:       #00d9ff;   /* inference / active / primary accent */
  --cyan-dim:   rgba(0,217,255,0.12);
  --amber:      #ffb347;   /* training / warning */
  --amber-dim:  rgba(255,179,71,0.12);
  --purple:     #c084fc;   /* image generation */
  --purple-dim: rgba(192,132,252,0.12);
  --green:      #4ade80;   /* healthy / ready */
  --green-dim:  rgba(74,222,128,0.12);
  --red:        #f87171;   /* error / stopped */
  --red-dim:    rgba(248,113,113,0.12);

  --text:       #e0e0e0;
  --text2:      #9aa0c0;
  --text3:      #6b7298;

  --radius:     6px;
  --mono:       'JetBrains Mono', 'IBM Plex Mono', monospace;
}
```

---

## Standing Rules

1. **No Tailwind.** All styles use CSS custom properties. Component-specific styles go in
   co-located `.css` files or in `shell.css` for layout.

2. **No iframes.** For services with their own UIs (Grafana, ComfyUI, Kohya), open them in
   a new tab. Iframe embeds are deferred to v2.

3. **Hash routing only.** All routes are `/#/pagename`. React Router v6 `<HashRouter>`.
   This avoids server-side route configuration.

4. **Font first.** `font-family: var(--mono)` on `body`. This is an operator tool — monospace
   is a hard requirement, not a style preference.

5. **Polling, not WebSocket.** GPU stats poll every 3s (1s during profile switch). Service
   health polls every 10s. Only training logs use SSE streaming.

6. **Frontend never calls third-party services directly.** All data (Docker, Prometheus,
   Langfuse, MinIO, Qdrant, Ollama) flows through the FastAPI backend at `:8800`.

7. **Preserve existing backend endpoints.** `GET /status`, `GET /loadouts`,
   `POST /activate/{name}`, `POST /stop`, `GET /health` — do not modify these.

8. **Secrets never returned in responses.** `/api/secrets` returns key names only.
   Values are never exposed through the API under any circumstances.

9. **`KOVATI_OS_PRODUCT_NAME` env var** controls the product name in all UI copy. Default
   value: `"KOVATI OS"`. Never hardcode the string.

---

## Loadout Color Scheme

| Profile type | Accent color | CSS var |
|-------------|-------------|---------|
| Inference (any) | Cyan | `--cyan` |
| Training | Amber | `--amber` |
| Image generation | Purple | `--purple` |
| Idle / stopped | Gray | `--text3` |

---

## Backend API Overview

The frontend consumes these endpoints (all at `:8800`):

**Existing (do not modify):**
- `GET /status` — GPU stats, active profile, switching state
- `GET /loadouts` — all profiles from `profiles.yaml`
- `POST /activate/{name}` — switch profile (async)
- `POST /stop` — stop all services
- `GET /health`

**New (added progressively in later steps):**
- `GET /api/services` — all Docker container statuses
- `GET /api/services/{name}/logs` — last N log lines
- `GET /api/services/{name}/logs/stream` — SSE log tail
- `POST /api/services/{name}/start` / `stop`
- `GET /api/metrics/gpu` — 30-min VRAM history
- `GET /api/metrics/system` — CPU/RAM/disk/network from Prometheus
- `GET /api/alerts` — active Prometheus alerts
- `GET /api/traces` — LLM traces from Langfuse
- `GET /api/models` — merged model list from Ollama + vLLM
- `GET /api/storage/buckets/{bucket}` — MinIO file listing
- `GET /api/vectors/collections` — Qdrant collections
- `POST /api/training/start` / `stop` / `export`
- `GET /api/secrets` — key names only
- `POST /api/secrets/{key}/rotate`
- `GET /api/network` — WireGuard, Caddy, jumpbox IP
- `GET /api/activity` — last N events

---

## How to Write Feedback

After completing each step, write a feedback file to:

```
plan/UI/GHC-Feedback/NN-feedback.md
```

Where `NN` matches the step number (e.g., `01-feedback.md` for step 01).

**Required sections:**

```markdown
# Step NN — Feedback

## Status
COMPLETE | PARTIAL | BLOCKED

## Files Created / Modified
- path/to/file.jsx — brief description
- ...

## Acceptance Criteria
- [x] Criterion 1 — passed
- [ ] Criterion 2 — did not pass, reason

## Deviations from Spec
List anything you implemented differently from the step file, and why.

## Blockers
Any unresolved issues, missing context, or decisions needed before the next step.

## Notes
Anything the orchestrator should know before writing the next step.
```

---

## Component Spec Documents

Each component has a detailed spec in `plan/UI/Steps/`. When a step file references one of
these, read the full spec before implementing. The step file summarizes requirements; the
spec document has layout diagrams, exact CSS, and component API details.

| Step | Spec File |
|------|-----------|
| 01 | `Steps/01-frontend-shell.md` |
| 02 | `Steps/02-dashboard.md` |
| 03 | `Steps/03-loadout-manager.md` |
| 04 | `Steps/04-tools-panel.md` |
| 05 | `Steps/05-training-workflows.md` |
| 06 | `Steps/06-resources-panel.md` |
| 07 | `Steps/07-expose-panel.md` |
| 08 | `Steps/08-monitor-panel.md` |
| 09 | `Steps/09-settings-panel.md` |
| 10 | `Steps/10-backend-api.md` |
| 11 | `Steps/11-firstboot-wizard.md` |
