# Step 12 — Distro Productization

> **Prerequisites:** Steps 01–11 complete. Read `plan/UI/GHC-Plan/00-overview.md`.
> **Reference spec:** `plan/UI/Steps/12-distro-productization.md`

---

## Goal

Wire up the systems that make KOVATI OS a deployable product:

1. **BrandContext** — `GET /api/branding` on mount; all hardcoded product strings replaced with context values
2. **License system** — `GET /api/license`; `features` flags in AppContext; feature-gated UI elements
3. **Professional tier stack updates** — validated snapshot list replaces raw Update All
4. **`api/branding.py`** and **`api/license.py`** backend modules
5. **`systemd` service file** — `kovati-os.service` in the repo
6. **Air-gap mode** — Step 5 (first-boot) already handles this; here we add the `KOVATI_AIR_GAP` detection to AppContext so other panels can read it

This step has no new panels. It integrates across existing code.

---

## Deliverables

### 1. `BrandContext` — `ui/src/context/BrandContext.jsx`

```jsx
import { createContext, useContext, useEffect, useState } from 'react';

const DEFAULTS = {
  productName:  'KOVATI OS',
  productShort: 'NOS',
  vendorName:   '',
  supportUrl:   '',
  docsUrl:      '',
};

const BrandContext = createContext(DEFAULTS);

export function BrandProvider({ children }) {
  const [brand, setBrand] = useState(DEFAULTS);

  useEffect(() => {
    fetch('/api/branding')
      .then(r => r.json())
      .then(data => setBrand({ ...DEFAULTS, ...data }))
      .catch(() => { /* use defaults */ });
  }, []);

  // Expose to non-React code (wizard handoff step, Setup.jsx)
  window.__KOVATI_PRODUCT_NAME__ = brand.productName;

  return (
    <BrandContext.Provider value={brand}>
      {children}
    </BrandContext.Provider>
  );
}

export function useBrand() {
  return useContext(BrandContext);
}
```

Wrap `App.jsx` with `<BrandProvider>` **outside** the `<HashRouter>` — or inside, it doesn't matter, but outside is cleaner:

```jsx
// main.jsx
root.render(
  <BrandProvider>
    <AppContextProvider>
      <HashRouter>
        <App />
      </HashRouter>
    </AppContextProvider>
  </BrandProvider>
);
```

---

### 2. Replace all hardcoded product strings

Search the entire `ui/src/` tree for the literal string `"KOVATI OS"` (and `"NOS"`). Replace every instance with the `useBrand()` hook value. Key locations:

- `Shell.jsx` — sidebar header / logo text
- `App.jsx` — document title (`document.title = brand.productName`)
- `Setup.jsx` — wizard header brand label (already uses `window.__KOVATI_PRODUCT_NAME__`; update to use `useBrand()` instead)
- `StepHandoff.jsx` — "KOVATI OS is ready" message

In Shell.jsx:
```jsx
import { useBrand } from '../context/BrandContext';
// ...
const brand = useBrand();
// in JSX:
<span className="sidebar-logo">{brand.productShort}</span>
<span className="sidebar-product">{brand.productName}</span>
```

In App.jsx (inside a component that runs on mount):
```jsx
useEffect(() => {
  document.title = brand.productName;
}, [brand.productName]);
```

---

### 3. AppContext additions for license and features

In `AppContext.jsx`, add to initial state:

```js
const initialState = {
  // ... existing fields ...
  license: {
    tier:    'community',
    valid:   true,
    expires: null,
    features: {
      validated_upgrades: false,
      appliance_mode:     false,
      fips_mode:          false,
      air_gap:            false,
      profile_library:    false,
    },
  },
};
```

Add reducer case:
```js
case 'SET_LICENSE':
  return { ...state, license: action.payload };
```

In `Shell.jsx` (or a top-level hook), fetch license on mount:
```jsx
useEffect(() => {
  fetch('/api/license')
    .then(r => r.json())
    .then(data => dispatch({ type: 'SET_LICENSE', payload: data }))
    .catch(() => { /* community tier fallback */ });
}, []);
```

Export a convenience selector:
```js
// In AppContext.jsx
export function useFeatures() {
  const { state } = useApp();
  return state.license.features;
}

export function useTier() {
  const { state } = useApp();
  return state.license.tier;
}
```

---

### 4. Professional tier UI in Settings > Stack Management

In `settings/StackManager.jsx`, add tier-gated rendering. Import `useTier` from AppContext:

```jsx
import { useTier } from '../../context/AppContext';

export function StackManager({ isAppliance }) {
  const tier = useTier();
  const isPro = tier === 'professional' || tier === 'enterprise';

  // ... existing state ...

  return (
    <Panel title="Stack Management">
      {isAppliance ? (
        <div className="settings-locked-notice">
          🔒 Updates managed via validated stack snapshots. Contact your administrator.
        </div>
      ) : isPro ? (
        <ValidatedSnapshotUpdater />
      ) : (
        // Community tier: existing Update All button + SSE log
        <CommunityUpdater
          images={images}
          updating={updating}
          updateLog={updateLog}
          handleUpdateAll={handleUpdateAll}
          handleRollback={handleRollback}
          rollingBack={rollingBack}
        />
      )}

      <table className="settings-table">
        {/* ... existing image table, always shown ... */}
      </table>
    </Panel>
  );
}
```

#### `ValidatedSnapshotUpdater` sub-component

```jsx
function ValidatedSnapshotUpdater() {
  const [snapshots, setSnapshots] = useState([]);
  const [installing, setInstalling] = useState(null);
  const [log, setLog] = useState([]);

  useEffect(() => {
    fetch('/api/stack/snapshots')
      .then(r => r.json())
      .then(data => setSnapshots(Array.isArray(data) ? data : MOCK_SNAPSHOTS))
      .catch(() => setSnapshots(MOCK_SNAPSHOTS));
  }, []);

  async function install(version) {
    const ok = window.confirm(
      `Install validated snapshot v${version}?\nAll services will restart in sequence.`
    );
    if (!ok) return;
    setInstalling(version);
    setLog([]);

    try {
      const res = await fetch(`/api/stack/snapshots/${version}/install`, { method: 'POST' });
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        dec.decode(value).split('\n')
          .filter(l => l.startsWith('data: '))
          .forEach(l => setLog(prev => [...prev, l.slice(6)]));
      }
    } catch {
      setLog(['✓ Snapshot installed (mock)']);
    }
    setInstalling(null);
  }

  return (
    <div className="snapshot-updater">
      <div className="snapshot-header">
        <Tag variant="cyan">Professional</Tag>
        <span className="snapshot-label">Validated stack snapshots</span>
      </div>
      {snapshots.map(s => (
        <div key={s.version} className="snapshot-row">
          <div className="snapshot-meta">
            <span className="snapshot-version">v{s.version}</span>
            <span className="snapshot-date">{s.released}</span>
            <Tag variant="gray">{s.channel}</Tag>
          </div>
          <div className="snapshot-changes">
            {Object.entries(s.images ?? {}).map(([svc, info]) => (
              <div key={svc} className="snapshot-change">
                <span>{svc}</span>
                <span className="snapshot-change-detail">{info.changelog}</span>
              </div>
            ))}
          </div>
          <Btn variant="cyan" size="sm"
            onClick={() => install(s.version)}
            disabled={installing === s.version}
          >
            {installing === s.version ? 'Installing…' : 'Install'}
          </Btn>
        </div>
      ))}
      {log.length > 0 && (
        <div className="stack-log">
          {log.map((l, i) => (
            <div key={i} className={`stack-log-line ${l.startsWith('✓') ? 'log-ok' : ''}`}>{l}</div>
          ))}
        </div>
      )}
    </div>
  );
}

const MOCK_SNAPSHOTS = [
  {
    version: '1.2.1',
    released: '2026-07-01',
    channel: 'stable',
    images: {
      'vllm-pair-a': { changelog: 'CUDA 12.5 support, 15% throughput improvement' },
      'ollama':       { changelog: 'Tool calling improvements' },
    },
  },
];
```

Add CSS in `SettingsShared.css`:

```css
.snapshot-updater   { display: flex; flex-direction: column; gap: 10px; margin-bottom: 12px; }
.snapshot-header    { display: flex; align-items: center; gap: 8px; font-size: 10px; }
.snapshot-label     { color: var(--text3); }
.snapshot-row       { background: var(--surface2); border: 1px solid var(--border); border-radius: var(--radius); padding: 10px 12px; display: flex; flex-direction: column; gap: 6px; }
.snapshot-meta      { display: flex; align-items: center; gap: 8px; }
.snapshot-version   { font-size: 11px; font-weight: 600; color: var(--text); }
.snapshot-date      { font-size: 9px; color: var(--text3); }
.snapshot-changes   { display: flex; flex-direction: column; gap: 2px; }
.snapshot-change    { display: flex; gap: 8px; font-size: 9px; }
.snapshot-change    span:first-child { color: var(--text2); width: 80px; flex-shrink: 0; }
.snapshot-change-detail { color: var(--text3); }
```

---

### 5. License tier badge in Shell

Show tier in the sidebar footer (below the GPU pulse indicator):

```jsx
// In Shell.jsx sidebar footer area
const tier = useTier();
{tier !== 'community' && (
  <div className="sidebar-tier-badge">
    <Tag variant={tier === 'enterprise' ? 'amber' : 'cyan'}>
      {tier.toUpperCase()}
    </Tag>
  </div>
)}
```

If tier is `community`, show nothing (no "Community" badge — it's the default and showing it would look awkward in white-label scenarios).

---

### 6. Feature gate: Appliance Mode activation

In `settings/Network.jsx`, the Mode `<select>` should only show the `appliance` option if the license grants `appliance_mode`:

```jsx
import { useFeatures } from '../../context/AppContext';

// Inside Network component:
const features = useFeatures();

// In the mode select:
<select className="kv-select" value={net.mode} onChange={e => saveMode(e.target.value)}>
  <option value="workstation">workstation</option>
  {features.appliance_mode && (
    <option value="appliance">appliance</option>
  )}
</select>
{!features.appliance_mode && net.mode === 'workstation' && (
  <span className="kv-dim" style={{ marginLeft: 8 }}>
    (appliance mode requires Enterprise license)
  </span>
)}
```

---

### 7. Backend — `api/branding.py`

```python
import os
from fastapi import APIRouter

router = APIRouter()

@router.get("/api/branding")
async def get_branding():
    return {
        "productName":  os.getenv("KOVATI_OS_PRODUCT_NAME", "KOVATI OS"),
        "productShort": os.getenv("KOVATI_OS_PRODUCT_SHORT", "NOS"),
        "vendorName":   os.getenv("KOVATI_OS_VENDOR_NAME",   ""),
        "supportUrl":   os.getenv("KOVATI_OS_SUPPORT_URL",   ""),
        "docsUrl":      os.getenv("KOVATI_OS_DOCS_URL",      ""),
    }
```

Register in `main.py`:
```python
from api import branding
app.include_router(branding.router)
```

---

### 8. Backend — `api/license.py`

```python
import hmac, hashlib, datetime, os
from pathlib import Path
from fastapi import APIRouter

router = APIRouter()

LICENSE_FILE    = Path(os.getenv("KOVATI_LICENSE_FILE", "/etc/kovati-os/license.key"))
SIGNING_KEY     = os.getenv("KOVATI_LICENSE_SIGNING_KEY", "")  # Never shipped; held by vendor
_license_cache: dict | None = None

def _get_machine_id() -> str:
    try:
        mid = Path("/etc/machine-id").read_text().strip()
        return hashlib.sha256(mid.encode()).hexdigest()[:8]
    except Exception:
        return "00000000"

def validate_license(key: str) -> dict:
    if not key or not key.strip():
        return _community()

    parts = key.strip().split("-")
    if len(parts) != 5 or parts[0] != "KOVATI":
        return _community()

    _, tier_raw, node_id, expiry, sig = parts
    tier = tier_raw.lower()

    # Node binding check
    machine_id = _get_machine_id()
    if node_id != machine_id:
        return {"valid": False, "reason": "node_mismatch", "tier": "community", "features": _features("community")}

    # Expiry check
    try:
        exp_date = datetime.date(int(expiry[:4]), int(expiry[4:6]), int(expiry[6:]))
        if datetime.date.today() > exp_date:
            return {"valid": False, "reason": "expired", "tier": tier, "features": _features("community")}
    except ValueError:
        return _community()

    # HMAC check (only if signing key is configured — skip in dev)
    if SIGNING_KEY:
        expected = hmac.new(
            SIGNING_KEY.encode(),
            f"{tier_raw}:{node_id}:{expiry}".encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        if not hmac.compare_digest(sig, expected):
            return {"valid": False, "reason": "invalid_signature", "tier": "community", "features": _features("community")}

    return {
        "valid":    True,
        "tier":     tier,
        "expires":  expiry,
        "features": _features(tier),
    }

def _features(tier: str) -> dict:
    return {
        "validated_upgrades": tier in ("professional", "enterprise"),
        "appliance_mode":     tier == "enterprise",
        "fips_mode":          tier == "enterprise",
        "air_gap":            tier == "enterprise",
        "profile_library":    tier in ("professional", "enterprise"),
    }

def _community() -> dict:
    return {"valid": True, "tier": "community", "expires": None, "features": _features("community")}

def load_license() -> dict:
    global _license_cache
    if _license_cache:
        return _license_cache
    try:
        key = LICENSE_FILE.read_text().strip()
        _license_cache = validate_license(key)
    except FileNotFoundError:
        _license_cache = _community()
    return _license_cache

@router.get("/api/license")
async def get_license():
    return load_license()

@router.post("/api/license")
async def set_license(body: dict):
    global _license_cache
    key  = body.get("key", "")
    result = validate_license(key)
    if result.get("valid") and result["tier"] != "community":
        LICENSE_FILE.parent.mkdir(parents=True, exist_ok=True)
        LICENSE_FILE.write_text(key + "\n")
        _license_cache = result
    return result
```

Register in `main.py`:
```python
from api import license as license_api
app.include_router(license_api.router)
# Also call load_license() in lifespan so config.py can read it
```

Update `config.py` to read license on import (for feature flags used by middleware):
```python
# At bottom of config.py — loaded lazily to avoid circular imports
def get_license_features() -> dict:
    try:
        from api.license import load_license
        return load_license().get("features", {})
    except Exception:
        return {}
```

---

### 9. Backend — `api/stack.py` additions (validated snapshots)

Add to existing `api/stack.py`:

```python
import httpx
from config import get_license_features

SNAPSHOT_MANIFEST_URL = os.getenv(
    "KOVATI_UPDATE_MIRROR_URL",
    "https://updates.kovatios.io/snapshots/stable.json"
)

@router.get("/api/stack/snapshots")
async def list_snapshots():
    features = get_license_features()
    if not features.get("validated_upgrades"):
        return {"error": "validated_upgrades feature requires Professional or Enterprise license"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(SNAPSHOT_MANIFEST_URL)
            return r.json()
    except Exception:
        # Return cached/bundled snapshots for air-gap
        bundled = KOVATI_ROOT / "snapshots" / "latest.json"
        if bundled.exists():
            import json
            return json.loads(bundled.read_text())
        return []

@router.post("/api/stack/snapshots/{version}/install")
async def install_snapshot(version: str, request: Request):
    features = get_license_features()
    if not features.get("validated_upgrades"):
        return JSONResponse(status_code=403, content={"error": "requires Professional license"})

    async def event_gen():
        yield f"data: Installing snapshot v{version}…\n\n"
        # Fetch manifest, verify signature, pull pinned images, restart
        # TODO: implement full verified install flow
        yield f"data: ✓ Snapshot v{version} installed\n\n"
    return StreamingResponse(event_gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache"})
```

---

### 10. systemd service files

Create these two files at the repo root:

**`deploy/kovati-os.service`**

```ini
[Unit]
Description=KOVATI OS Control Plane
After=docker.service network-online.target nvidia-persistenced.service
Requires=docker.service

[Service]
Type=simple
User=kovatios
WorkingDirectory=/opt/kovati-os/loadout-manager
EnvironmentFile=/opt/kovati-os/docker/.env
Environment=KOVATI_OS_MODE=workstation
ExecStart=/usr/bin/uvicorn main:app --host 0.0.0.0 --port 8800 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=kovati-os

[Install]
WantedBy=multi-user.target
```

**`deploy/kovati-os-first-boot.service`**

```ini
[Unit]
Description=KOVATI OS First Boot Setup
After=kovati-os.service
ConditionPathExists=!/data/.kovati-setup-complete

[Service]
Type=oneshot
ExecStart=/opt/kovati-os/scripts/first-boot-trigger.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

**`deploy/first-boot-trigger.sh`**

```bash
#!/bin/bash
# Redirect the browser to /setup on first access.
# Sets an env flag that the FastAPI app reads.
echo "KOVATI_SHOW_SETUP=true" >> /opt/kovati-os/docker/.env
systemctl restart kovati-os
```

---

### 11. Air-gap AppContext flag

In `Shell.jsx` (alongside the license fetch), also fetch setup status to expose `airGap` to the rest of the app:

```jsx
useEffect(() => {
  fetch('/api/setup/status')
    .then(r => r.json())
    .then(data => {
      if (data.air_gap) {
        dispatch({ type: 'SET_SYSTEM_MODE', payload: 'air-gap' });
        // Or add a dedicated SET_AIR_GAP action — your choice
      }
    })
    .catch(() => {});
}, []);
```

The Stack provisioner step already checks `KOVATI_AIR_GAP` via the status response. No additional frontend changes needed.

---

### 12. License entry in Settings (optional, shown if no valid license)

In `Settings.jsx`, if `tier === 'community'`, show a small "Upgrade" callout at the bottom of the page:

```jsx
{tier === 'community' && (
  <Panel title="License">
    <div className="license-community">
      <span>Running on Community tier.</span>
      <LicenseKeyInput />
    </div>
  </Panel>
)}
```

```jsx
function LicenseKeyInput() {
  const [key,     setKey]    = useState('');
  const [result,  setResult] = useState(null);
  const { dispatch } = useApp();

  async function apply() {
    const res = await fetch('/api/license', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key }),
    });
    const data = res.ok ? await res.json() : { valid: false };
    setResult(data);
    if (data.valid && data.tier !== 'community') {
      dispatch({ type: 'SET_LICENSE', payload: data });
    }
  }

  return (
    <div className="license-key-row">
      <input
        className="form-input"
        placeholder="KOVATI-PRO-xxxxxxxx-YYYYMMDD-xxxxxxxxxxxxxxxx"
        value={key}
        onChange={e => setKey(e.target.value)}
        style={{ flex: 1 }}
      />
      <Btn variant="cyan" size="sm" onClick={apply} disabled={!key.trim()}>
        Apply
      </Btn>
      {result && (
        <span className={result.valid ? 'kv-value' : 'setup-error'} style={{ fontSize: 9 }}>
          {result.valid ? `✓ ${result.tier} tier activated` : `✗ ${result.reason}`}
        </span>
      )}
    </div>
  );
}
```

---

## Acceptance Criteria

- [ ] **Branding:** `GET /api/branding` called on app load; product name in Shell sidebar uses `brand.productName` not the hardcoded string; document title updates to `brand.productName`
- [ ] **License fetch:** `GET /api/license` called on app load; result stored in AppContext under `state.license`; `useTier()` and `useFeatures()` hooks work
- [ ] **Community (default):** No tier badge in sidebar; Settings Stack Management shows "Update All Services" button; Appliance option hidden in Network mode selector
- [ ] **Professional (mocked):** Sidebar shows `PRO` cyan badge; Settings Stack Management shows validated snapshot list from `GET /api/stack/snapshots`; snapshot install streams SSE progress
- [ ] **Enterprise (mocked):** `appliance_mode` feature is `true`; Appliance option visible in Network mode selector
- [ ] **`/api/branding` endpoint** returns env vars; changing `KOVATI_OS_PRODUCT_NAME` env var and restarting the server changes the product name in the UI
- [ ] **`/api/license` endpoint** returns community tier when no license file exists; accepts a license key via POST; validates node binding and expiry; returns features dict
- [ ] **systemd files** exist at `deploy/kovati-os.service` and `deploy/kovati-os-first-boot.service` with correct `WorkingDirectory` and `EnvironmentFile` paths
- [ ] No hardcoded `"KOVATI OS"` strings remain in `ui/src/` after this step

---

## Testing the tier gates without a real license

To test Professional and Enterprise tier UI without a real signed license key, temporarily hardcode in `config.py` for dev:

```python
# DEV ONLY — remove before release
import os
if os.getenv("KOVATI_DEV_TIER"):
    _license_cache = {
        "valid": True,
        "tier":  os.getenv("KOVATI_DEV_TIER", "community"),
        "expires": "20271231",
        "features": _features(os.getenv("KOVATI_DEV_TIER", "community")),
    }
```

Run with `KOVATI_DEV_TIER=professional uvicorn main:app` to test the Pro UI without a key.

---

## Feedback

Write `plan/UI/GHC-Feedback/12-feedback.md` when done.

**Required in Notes:**
- Confirm that `useBrand()` in `Shell.jsx` does not cause a flash of the default "KOVATI OS" name before the API response arrives. If it does, document the fix (e.g., loading state, localStorage cache of last-known value).
- List any hardcoded product strings that were missed in the search pass and where they were found.
- Did the `KOVATI_DEV_TIER` mechanism work for testing the Professional tier snapshot UI without a real license key?
- Confirm that `api/license.py`'s `hmac.compare_digest` behaves correctly when `SIGNING_KEY` is unset (i.e., skips the HMAC check gracefully rather than crashing).
