# Step 13 — Integration QA

> **Prerequisites:** Steps 01–12 complete and all feedback filed.
> **Context:** This is the final integration pass before production build. It has no new panels.

---

## Goal

Verify the complete UI as a working system. This step requires GHC to:

1. **Fix all accumulated deviations** from the feedback files (list below)
2. **Run 10 end-to-end scenarios** that span multiple panels
3. **Audit security-sensitive code paths**
4. **Confirm API contract alignment** between frontend mock shapes and backend step 10 endpoints

No new files are introduced. All work is corrections and verifications on existing code.

---

## Part A — Deviations to Fix

These were noted as "deviations from spec" or "TODO" across feedback files 01–12. Fix each one.

### A1 — Loadout activation confirmation dialog (step 03)

**Location:** `ui/src/pages/Loadout.jsx` — the `handleActivate()` function.

**Fix:** Add `window.confirm` before calling `POST /activate/{name}`:

```js
async function handleActivate(name) {
  const profile = profiles.find(p => p.name === name);
  const svcList = profile?.services?.join(', ') ?? 'managed services';
  const ok = window.confirm(
    `Switch to "${name}"?\n\nThis will restart: ${svcList}.\nServices will be briefly unavailable (15–30 s).`
  );
  if (!ok) return;
  // ... existing POST /activate code
}
```

**Verify:** Clicking a profile card shows the confirm dialog; Cancel leaves the current profile active; OK triggers the switch.

---

### A2 — Model pull progress streaming (step 06, deviation 1)

**Location:** `ui/src/components/ModelsTab.jsx`

**Current state:** Pull starts and button becomes "Pulling…" but no progress is shown until it completes.

**Fix:** `POST /api/models/pull` returns an SSE stream with lines:
```
data: {"status": "pulling", "digest": "sha256:abc...", "completed": 1234, "total": 4321000000}
data: {"status": "success"}
```

Switch from a plain `fetch` to a `ReadableStream` reader:

```js
async function handlePull(name) {
  setPulling(name);
  setPullPct(0);
  try {
    const res = await fetch('/api/models/pull', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      dec.decode(value).split('\n')
        .filter(l => l.startsWith('data: '))
        .forEach(l => {
          try {
            const ev = JSON.parse(l.slice(6));
            if (ev.total > 0) setPullPct(Math.round((ev.completed / ev.total) * 100));
            if (ev.status === 'success') setPulling(null);
          } catch { /* incomplete chunk */ }
        });
    }
  } catch { /* API not ready — mock 3s delay */ }
  setPulling(null);
  // Refresh model list
}
```

Show a progress bar in the pulling row (same `provision-mini-bar` pattern from step 11).

---

### A3 — Checkpoint config view (step 06, deviation 2)

**Location:** `ui/src/components/CheckpointsTab.jsx` — the "View" button per checkpoint.

**Fix:** When "View" is clicked, fetch `GET /api/storage/preview?bucket=checkpoints&path={run}/{name}/config.yml&n=100` and display in a modal with monospace pre-formatted text:

```jsx
function ConfigModal({ path, onClose }) {
  const [lines, setLines] = useState([]);
  useEffect(() => {
    fetch(`/api/storage/preview?bucket=checkpoints&path=${encodeURIComponent(path)}&n=100`)
      .then(r => r.json())
      .then(data => setLines(data.lines ?? []));
  }, [path]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 600 }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          {path}
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          <pre style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text2)', margin: 0, whiteSpace: 'pre-wrap' }}>
            {lines.join('\n')}
          </pre>
        </div>
      </div>
    </div>
  );
}
```

---

### A4 — Backup schedule editing (step 06, deviation 3)

The storage tab shows the cron schedule as read-only. Step 09 (Settings > Backups) implements a proper inline cron editor. **Remove the read-only schedule display from StorageTab entirely** — the canonical editor lives in Settings. Replace with a link: `"Backup schedule managed in Settings →"` that calls `navigate('/settings')`.

---

### A5 — `/loadouts` field name documentation

From the step 03 feedback note (never resolved): GHC never reported the actual field names returned by `GET /loadouts`. 

**Action:** In `Loadout.jsx`, add a `console.log('loadouts response:', data)` on the raw API response (commented out but present for the step 10 wiring pass), and document the actual field names in a comment:

```js
// Expected shape from GET /loadouts (from profiles.yaml):
// { name, label, gpus: [0,3], services: [...], color: 'cyan', incompatible_with: [...] }
// TODO Step 10: verify these field names against the live API
```

---

### A6 — SSE proxy validation

**Location:** `ui/vite.config.js`

Verify `changeOrigin: true` was added in step 10 to all proxy entries. If not already done:

```js
server: {
  proxy: {
    '/api': { target: 'http://localhost:8800', changeOrigin: true },
    '/status': { target: 'http://localhost:8800', changeOrigin: true },
    '/loadouts': { target: 'http://localhost:8800', changeOrigin: true },
    '/activate': { target: 'http://localhost:8800', changeOrigin: true },
    '/stop': { target: 'http://localhost:8800', changeOrigin: true },
  },
},
```

Open the browser Network tab and verify `GET /api/services/vllm-pair-a/logs/stream` shows as a streaming response (not a pending XHR that never resolves).

---

### A7 — Window title after brand fetch

**Location:** `ui/src/App.jsx` or top-level brand consumer.

If there's a flash where the document title shows "KOVATI OS" for ~200ms before the brand API responds, add a localStorage cache:

```js
// On brand fetch success:
localStorage.setItem('kovati_product_name', data.productName);
document.title = data.productName;

// BrandContext initial state:
const DEFAULTS = {
  productName: localStorage.getItem('kovati_product_name') ?? 'KOVATI OS',
  // ...
};
```

This eliminates the flash on second and subsequent page loads.

---

## Part B — End-to-End Scenarios

Work through each scenario manually (with the dev server running and mock data). Confirm the full user journey succeeds without console errors.

---

### Scenario 1 — Loadout switch flow

1. Open `/#/loadouts`
2. Observe current profile (mock: `inference-pair-a`, active)
3. Click `inference-pair-b` card → confirm dialog appears
4. Click OK → `SwitchingBanner` appears with "Switching…" text
5. State transitions to `idle` after mock delay → banner disappears
6. Navigate to `/#/dashboard` → LoadoutBanner shows new active profile
7. GPU cards show updated VRAM allocation

**Pass criteria:** No console errors; profile card shows active state; Dashboard banner updates.

---

### Scenario 2 — Training launch sequence

1. Open `/#/training`
2. Select "Text LoRA" mode
3. Step 1: upload a mock `.jsonl` file (or select a pre-existing dataset)
4. Step 2: select `qwen2.5-7b-instruct` (VRAM: 8 GB — fits current pair)
5. Step 3: adjust rank to 16, alpha to 32
6. Step 4: confirm GPU assignment (GPU 0+3) and check acknowledgement checkbox
7. Step 5: click Launch — confirm dialog for profile switch appears
8. Mock training starts → navigate to `/#/training` — LiveTrainingView shows progress
9. Metrics show step counter incrementing, loss decreasing

**Pass criteria:** All 5 wizard steps navigate correctly; step gating enforced; live view appears after launch.

---

### Scenario 3 — API key lifecycle

1. Open `/#/expose`
2. Click "+ Create New Key" → modal opens
3. Enter name `test-key`, scope `ollama`
4. Click "Generate Key" → reveal view appears with token
5. Click "Copy Token" → button shows "✓ Copied"
6. Click "Close" → modal disappears; token is gone
7. Table shows `test-key` row with scope and "Never" last used
8. Click "Revoke" on `test-key` → confirm dialog appears
9. Confirm → row disappears

**Pass criteria:** Token shown exactly once; table updates; revoke works.

---

### Scenario 4 — Log viewer navigation from Tools

1. Open `/#/tools`
2. Find `vllm-pair-a` service card; expand it
3. Click "View full logs →" link (should navigate to `/#/monitor?service=vllm-pair-a`)
4. Monitor panel opens; Log Viewer has `vllm-pair-a` pre-selected
5. Logs appear; SSE stream shows new lines appearing
6. Scroll up → "↓ Jump to Bottom" button appears
7. Click "↓ Jump to Bottom" → auto-scroll resumes

**Pass criteria:** URL param pre-selects service; SSE streams; scroll lock works.

---

### Scenario 5 — GPU chart history on Monitor

1. Open `/#/monitor`
2. Verify 4 canvas charts render (no blank/black boxes)
3. Wait 3 seconds → observe a new data point appended and chart redraws
4. Verify active GPU pair (higher VRAM) appears first in the grid
5. Hover over GPU telemetry section — verify no console errors

**Pass criteria:** All 4 charts render with gradient; update on 3s poll; order is active-first.

---

### Scenario 6 — Secrets rotation (workstation mode)

1. Open `/#/settings` → Secrets section
2. Click "Rotate" on `POSTGRES_PASSWORD`
3. Confirm dialog shows: "langfuse, n8n, dify"
4. Click OK → spinning animation appears for each affected service
5. After mock 2s delay → "Last Rotated: just now" appears
6. Click "Rotate All 14 Secrets"
7. Step 1 modal → "Continue"
8. Step 2 modal → type "rotate all" → button enables
9. Confirm → all keys rotate in sequence

**Pass criteria:** Confirm dialog shows correct services; "just now" updates; two-step Rotate All gating enforced.

---

### Scenario 7 — First-boot wizard (re-run)

1. Open `/#/settings` → Platform section
2. Click "Re-run First-Boot Wizard" → admin confirm dialog
3. Confirm → navigate to `/#/setup`
4. Step 3 (Secrets) shows warning banner: "Secrets already exist"
5. Step 5 (Stack) shows "Start Provisioning" → click → mock SSE progress displays
6. Step 6 (Validate) → run → ≥ 22/25 checks pass → "Continue" enables
7. Step 7 → click "Go to Dashboard" → navigate to `/#/dashboard`
8. Return to `/#/setup` → redirects to `/#/dashboard` (setup_complete flag set)

**Pass criteria:** Warning shown on re-run; sessionStorage restore works on refresh; completion flag prevents re-entry.

---

### Scenario 8 — MCP server test + export

1. Open `/#/expose` → MCP Servers section
2. Toggle `mcp-fetch` ON → optimistic UI shows it running
3. Click "Test Connection" on `mcp-filesystem` → result shows "✓ connected — 4 tools available" for 10s
4. Click "Export claude_desktop_config.json" → download initiates
5. Open downloaded file → verify only running servers are listed
6. Toggle `mcp-filesystem` OFF → wait for result; export now excludes it

**Pass criteria:** Toggle updates card status; test result auto-clears after 10s; export reflects only running servers.

---

### Scenario 9 — Appliance mode restrictions

Set `systemMode = 'appliance'` in AppContext initial state temporarily.

1. Open `/#/settings`
   - Verify Secrets section shows locked notice (no Rotate buttons)
   - Verify Stack Management shows locked message (no Update All)
   - Verify Backups schedule is read-only
   - Verify Platform "Re-run Wizard" button absent
2. Open `/#/expose` → External Access
   - Verify all toggles are disabled with "Managed by administrator" tooltip
3. Revert AppContext change

**Pass criteria:** All appliance restrictions enforce correctly; no console errors in appliance mode.

---

### Scenario 10 — Resource management

1. Open `/#/resources?tab=vectors`
2. Click delete (✕) on a collection
3. Confirm modal appears — type the collection name
4. "Delete permanently" button enables only after correct name entered
5. Click → row disappears

2. Switch to `?tab=datasets`
3. Drag a file onto the upload zone → border turns cyan
4. Drop → upload progress bar appears (mock)
5. Click 👁 preview on a `.jsonl` file → modal shows table with instruction/input/output columns

**Pass criteria:** Name-match gating enforced on vector delete; drag-over state changes; preview modal renders JSONL as table.

---

## Part C — Security Audit

Walk through these points and confirm each:

| # | Check | Expected |
|---|-------|---------|
| C1 | `GET /api/secrets` response | Contains `key` and `affects` fields only — no `value`, no hash |
| C2 | `POST /api/keys` response | Contains `token` field exactly once; subsequent `GET /api/keys` shows name/scope/dates only |
| C3 | `POST /api/setup/generate-secrets` response | Contains `values` dict — only acceptable in this one endpoint during first-boot |
| C4 | Token reveal modal (Expose panel) | Closing by any method (✕ button, overlay click, Escape key) clears the token from React state |
| C5 | Step 3 wizard secrets | `values` object is NOT written to `sessionStorage` at any point |
| C6 | Training SSE log viewer | `/api/services/{name}/logs/stream` does not return any content from `.env` or credential files |
| C7 | No `console.log` of sensitive data | Search `ui/src/` for `console.log` calls — none should print token, password, or env var values |

For C4, add an `onKeyDown` handler to the modal overlay:
```jsx
// Modal overlay
useEffect(() => {
  function onEsc(e) { if (e.key === 'Escape') closeModal(); }
  document.addEventListener('keydown', onEsc);
  return () => document.removeEventListener('keydown', onEsc);
}, [modal]);
```

---

## Part D — API Shape Verification

For each endpoint the frontend calls, compare the mock data shape to what step 10's backend actually returns. Document any mismatches here as inline `// TODO: backend returns X, frontend expects Y` comments.

Priority endpoints to verify (these have the highest likelihood of shape mismatch):

| Endpoint | Frontend mock key | Check for |
|----------|-------------------|-----------|
| `GET /status` | `gpus[i].vram_used_gb` | Backend may return `vram_used` (bytes) not GB |
| `GET /loadouts` | `profile.services` | Field may be `managed_services` or `containers` |
| `GET /api/services` | `service.managed_by_loadout` | Field presence and null vs missing distinction |
| `GET /api/metrics/gpu` | `{ history: { "0": [...] } }` | Backend uses string keys "0"–"3" not integer keys |
| `GET /api/training/status` | `{ active, engine, model, step, loss, eta }` | Field names from actual axolotl log parsing |
| `GET /api/storage/buckets/{bucket}` | `[{ name, size, modified }]` | MinIO returns `object_name` not `name` |

---

## Acceptance Criteria

- [ ] All Part A deviations (A1–A7) fixed and verified
- [ ] All 10 scenarios run without console errors
- [ ] All 7 security checks pass
- [ ] No hardcoded `"KOVATI OS"` strings remain in `ui/src/` (grep confirms)
- [ ] No `console.log` statements expose token or password values
- [ ] Escape key closes all modals (add event listener where missing)
- [ ] `vite.config.js` has `changeOrigin: true` on all proxy entries

---

## Feedback

Write `plan/UI/GHC-Feedback/13-feedback.md` when done.

**Required in Notes:**
- List which Part A fixes introduced any regressions (e.g., loadout confirmation dialog broke the switching animation timing).
- Report the actual field name shape of `GET /loadouts` (list all top-level keys).
- Report the actual field name shape of `GET /status` GPU objects (list all keys and value types).
- Which of the 10 E2E scenarios had issues, and what was the root cause?
