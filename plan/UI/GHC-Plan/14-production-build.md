# Step 14 — Production Build & Deployment

> **Prerequisites:** Step 13 (Integration QA) complete and accepted.
> **Context:** The UI is feature-complete. This step converts the dev-mode project into a shippable artifact: optimized Vite bundle served by FastAPI, Docker multi-stage build, and a CI pipeline script.

No new UI features are introduced. All work is build tooling, configuration, and deployment infrastructure.

---

## Part 1 — Vite Production Configuration

### 1.1 — Code splitting by route

Update `ui/vite.config.js` to enable route-level lazy loading and improve chunk splitting.

**Before (implicit single bundle):** All pages in one chunk.

**After:** Each page component is a dynamic import. Update `ui/src/App.jsx`:

```jsx
import { lazy, Suspense } from 'react';

const Dashboard  = lazy(() => import('./pages/Dashboard'));
const Loadout    = lazy(() => import('./pages/Loadout'));
const Tools      = lazy(() => import('./pages/Tools'));
const Training   = lazy(() => import('./pages/Training'));
const Resources  = lazy(() => import('./pages/Resources'));
const Expose     = lazy(() => import('./pages/Expose'));
const Monitor    = lazy(() => import('./pages/Monitor'));
const Settings   = lazy(() => import('./pages/Settings'));
const Setup      = lazy(() => import('./pages/Setup'));

// Wrap Routes in Suspense
<Suspense fallback={<div className="page-loading">Loading…</div>}>
  <Routes>
    {/* ... */}
  </Routes>
</Suspense>
```

Add the `.page-loading` class to `ui/src/tokens.css`:
```css
.page-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  color: var(--text2);
  font-family: var(--mono);
  font-size: 13px;
}
```

### 1.2 — vite.config.js production settings

Replace the current `vite.config.js` with:

```js
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig(({ command }) => ({
  plugins: [react()],

  build: {
    outDir: '../loadout-manager/static',
    emptyOutDir: true,
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom', 'react-router-dom'],
        },
      },
    },
  },

  server: command === 'serve' ? {
    port: 5173,
    proxy: {
      '/api':      { target: 'http://localhost:8800', changeOrigin: true },
      '/status':   { target: 'http://localhost:8800', changeOrigin: true },
      '/loadouts': { target: 'http://localhost:8800', changeOrigin: true },
      '/activate': { target: 'http://localhost:8800', changeOrigin: true },
      '/stop':     { target: 'http://localhost:8800', changeOrigin: true },
      '/health':   { target: 'http://localhost:8800', changeOrigin: true },
    },
  } : {},
}));
```

**Critical note:** `outDir: '../loadout-manager/static'` outputs directly into the FastAPI static serving directory. This eliminates a copy step.

### 1.3 — Build output targets

After `npm run build` in `ui/`:
- `loadout-manager/static/index.html`
- `loadout-manager/static/assets/vendor-[hash].js` (~140 KB gzip)
- `loadout-manager/static/assets/index-[hash].js` (~60 KB gzip)
- `loadout-manager/static/assets/Dashboard-[hash].js`, etc. (one per page)

Verify these targets exist after build. If the vendor chunk exceeds 300 KB gzip, investigate — React + React Router should not be that large.

---

## Part 2 — FastAPI Static Serving

### 2.1 — Static mount configuration

`loadout-manager/main.py` must mount the static directory with a catch-all for hash routing.

Add after all API routers are registered:

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

STATIC_DIR = Path(__file__).parent / "static"

@app.get("/")
async def serve_root():
    return FileResponse(STATIC_DIR / "index.html")

# Hash routing: /dashboard, /loadouts, etc. all serve index.html
# The browser's hash router handles the rest
@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # First try to serve the file directly (JS/CSS assets)
    target = STATIC_DIR / full_path
    if target.exists() and target.is_file():
        return FileResponse(target)
    # Fallback: serve index.html for all non-file routes
    return FileResponse(STATIC_DIR / "index.html")

# Mount static assets LAST (catch-all path handler above takes precedence for SPA routes)
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")
```

**Important:** The `/{full_path:path}` catch-all route must be registered AFTER all API routes. The `app.mount("/assets", ...)` is a named mount for the hashed asset files. The dynamic route handles `/dashboard`, `/loadouts`, etc., all of which must return `index.html`.

### 2.2 — Verify static serving works

Run `npm run build` from `ui/`, then:

```bash
cd loadout-manager
uvicorn main:app --host 0.0.0.0 --port 8800
```

Open `http://localhost:8800/` — the dashboard should load.
Open `http://localhost:8800/monitor` — should also load (hash routing falls back to index.html).
Open `http://localhost:8800/assets/vendor-[hash].js` — should return JS directly, not index.html.

---

## Part 3 — Environment Variable Injection

The UI must never have hardcoded environment-specific values. Implement runtime injection via a `/env.js` script served by FastAPI.

### 3.1 — Backend: `/env.js` endpoint

Add to `loadout-manager/main.py` (before the catch-all route):

```python
@app.get("/env.js", response_class=PlainTextResponse)
async def env_js():
    product_name = os.getenv("KOVATI_OS_PRODUCT_NAME", "KOVATI OS")
    product_short = os.getenv("KOVATI_OS_PRODUCT_SHORT", "NOS")
    vendor_name = os.getenv("KOVATI_OS_VENDOR_NAME", "")
    support_url = os.getenv("KOVATI_OS_SUPPORT_URL", "")
    docs_url = os.getenv("KOVATI_OS_DOCS_URL", "")
    return f"""window.__KOVATI_ENV__ = {{
  productName: {json.dumps(product_name)},
  productShort: {json.dumps(product_short)},
  vendorName: {json.dumps(vendor_name)},
  supportUrl: {json.dumps(support_url)},
  docsUrl: {json.dumps(docs_url)},
}};"""
```

Import `PlainTextResponse` from `fastapi.responses` and `json` at the top of `main.py`.

### 3.2 — Frontend: load env.js before React mounts

Edit `ui/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>KOVATI OS</title>
    <link rel="preconnect" href="/" />
    <script src="/env.js"></script>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

### 3.3 — BrandContext reads from window.__KOVATI_ENV__

Update `ui/src/context/BrandContext.jsx` initial state:

```jsx
const env = window.__KOVATI_ENV__ ?? {};
const DEFAULTS = {
  productName: env.productName ?? localStorage.getItem('kovati_product_name') ?? 'KOVATI OS',
  productShort: env.productShort ?? 'NOS',
  vendorName: env.vendorName ?? '',
  supportUrl: env.supportUrl ?? '',
  docsUrl: env.docsUrl ?? '',
};
```

The `GET /api/branding` fetch still runs on mount and wins over `window.__KOVATI_ENV__` (for dynamic updates without reload). `window.__KOVATI_ENV__` serves as a synchronous bootstrap value that eliminates the flash before the async fetch resolves.

### 3.4 — document.title initialization

In `ui/src/main.jsx`, before mounting React:

```js
const env = window.__KOVATI_ENV__ ?? {};
document.title = env.productName ?? localStorage.getItem('kovati_product_name') ?? 'KOVATI OS';
```

---

## Part 4 — Docker Multi-Stage Build

Create `Dockerfile` at the repo root (next to `loadout-manager/` and `ui/`):

```dockerfile
# Stage 1: Build React UI
FROM node:22-alpine AS ui-builder
WORKDIR /build/ui
COPY ui/package*.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

# Stage 2: Python backend with built UI
FROM python:3.12-slim
WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY loadout-manager/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend source
COPY loadout-manager/ ./

# Copy built UI from stage 1 (vite outputs to loadout-manager/static)
COPY --from=ui-builder /build/loadout-manager/static ./static

# Non-root user
RUN adduser --disabled-password --gecos '' kovati
RUN chown -R kovati:kovati /app
USER kovati

EXPOSE 8800
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8800", "--workers", "2"]
```

Create `.dockerignore` at the repo root:

```
ui/node_modules
ui/dist
loadout-manager/__pycache__
loadout-manager/.venv
loadout-manager/*.db
loadout-manager/static
**/.env
**/*.pyc
.git
```

### Build and test locally

```bash
docker build -t kovati-os:dev .
docker run -it --rm \
  -p 8800:8800 \
  -e KOVATI_OS_PRODUCT_NAME="My AI Station" \
  -e KOVATI_ENV_FILE=/data/.env \
  -v /opt/kovati:/data \
  kovati-os:dev
```

Visit `http://localhost:8800/` — should show the full UI with product name "My AI Station".

---

## Part 5 — Makefile

Create `Makefile` at the repo root:

```makefile
.PHONY: dev build docker lint test clean

# Run frontend and backend in parallel during development
dev:
	@echo "Starting dev servers..."
	@(cd ui && npm run dev) & \
	 (cd loadout-manager && uvicorn main:app --reload --port 8800) & \
	 wait

# Build React UI (outputs to loadout-manager/static)
build:
	cd ui && npm run build

# Build Docker image
docker:
	docker build -t kovati-os:$(shell git rev-parse --short HEAD 2>/dev/null || echo dev) .

# Run Python linter
lint:
	cd loadout-manager && python -m ruff check . && python -m ruff format --check .

# Run Python tests
test:
	cd loadout-manager && python -m pytest tests/ -v

# Remove build artifacts
clean:
	rm -rf ui/node_modules ui/dist loadout-manager/static loadout-manager/__pycache__
```

---

## Part 6 — CI Pipeline Script

Create `.github/workflows/build.yml` (or `ci/build.sh` if the project doesn't use GitHub Actions):

```yaml
name: Build

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'npm'
          cache-dependency-path: ui/package-lock.json

      - name: Install frontend deps
        run: npm ci
        working-directory: ui

      - name: Build frontend
        run: npm run build
        working-directory: ui

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install backend deps
        run: pip install -r requirements.txt ruff pytest
        working-directory: loadout-manager

      - name: Lint backend
        run: ruff check .
        working-directory: loadout-manager

      - name: Run backend tests
        run: pytest tests/ -v --tb=short
        working-directory: loadout-manager

      - name: Build Docker image
        run: docker build -t kovati-os:ci .
```

If the project uses a local Gitea instance instead of GitHub, adapt to `.gitea/workflows/build.yml` — the syntax is identical (Gitea Actions is compatible with GitHub Actions).

---

## Part 7 — Bundle Size Audit

After `npm run build`, run the following and report sizes in the feedback file:

```bash
du -sh loadout-manager/static/assets/*.js | sort -h
```

Expected maximums (gzip):
| Chunk | Max size |
|-------|----------|
| `vendor-*.js` | 150 KB gzip |
| `index-*.js` | 80 KB gzip |
| Any single page chunk | 40 KB gzip |

If any chunk exceeds its limit, investigate:

1. **Vendor chunk > 150 KB:** Check if `react-router-dom` is pulling in unexpected deps. Run `npm ls react-router-dom` to inspect.

2. **index.js > 80 KB:** Something is being imported into `App.jsx` that should be lazy-loaded. Check imports.

3. **Page chunk > 40 KB:** That page imports a large dependency. Common culprit: the canvas chart helper or a large mock data file. Move mock data behind a dynamic import:

```js
// In dev only — strip from production bundle
if (import.meta.env.DEV) {
  const { MOCK_GPU_HISTORY } = await import('../data/monitorMock.js');
  // use mock data
}
```

---

## Acceptance Criteria

- [ ] `npm run build` completes without warnings in `ui/`
- [ ] `loadout-manager/static/` contains `index.html` and `assets/` after build
- [ ] `uvicorn main:app` at `:8800` serves the UI; hash routes (`/monitor`, `/settings`) all load index.html
- [ ] `window.__KOVATI_ENV__` is populated before React mounts; no flash of wrong product name
- [ ] `docker build -t kovati-os:dev .` completes in under 3 minutes on first build
- [ ] `docker run` container serves the UI correctly at `:8800`
- [ ] `make dev` starts both frontend and backend
- [ ] Vendor chunk ≤ 150 KB gzip; no page chunk > 40 KB gzip
- [ ] No `KOVATI OS` string hardcoded in `ui/index.html` title (uses `window.__KOVATI_ENV__` initialization)
- [ ] CI pipeline file exists and runs clean on a fresh clone

---

## Feedback

Write `plan/UI/GHC-Feedback/14-feedback.md` when done.

**Required in Notes:**
- Paste the actual output of `du -sh loadout-manager/static/assets/*.js | sort -h` (pre-gzip is fine if gzip isn't available)
- Note any Vite build warnings (unused exports, missing deps, etc.)
- Confirm the Docker build completes and the container serves the UI
- Report any issues with the `/env.js` endpoint (e.g., CORS on the script tag, caching headers)
- If GitHub Actions / Gitea was configured, link to the first CI run result
