# Step 06 — Resources Panel

> **Prerequisites:** Steps 01–05 complete. Read `plan/UI/GHC-Plan/00-overview.md`.
> **Reference spec:** `plan/UI/Steps/06-resources-panel.md`

---

## Goal

Implement the Resources panel (`/#/resources`) with 5 URL-addressable tabs:

1. **Models** — Ollama model table, vLLM endpoint table, LoRA adapters, pull new model
2. **Datasets** — drag-drop upload zone, MinIO file browser (3 sections)
3. **Checkpoints** — grouped by run name, load/merge actions
4. **Vectors** — Qdrant collections table, re-embed, two-step delete
5. **Storage** — disk usage, MinIO bucket breakdown, PostgreSQL sizes, backup controls

All data endpoints are from Step 10. Provide mock data for every tab.

---

## Deliverables

### 1. Mock data — `ui/src/data/resourcesMock.js`

```js
// TODO Step 10: replace with live API responses

export const MOCK_OLLAMA_MODELS = [
  { name: 'qwen2.5-32b-instruct', size: '65 GB', quant: 'Q4_K_M', lastUsed: '2h ago',  loaded: true  },
  { name: 'qwen2.5-7b-instruct',  size: '4.1 GB', quant: 'Q4_K_M', lastUsed: '1d ago',  loaded: false },
  { name: 'nomic-embed-text-v1.5',size: '274 MB', quant: 'F32',    lastUsed: '3d ago',  loaded: false },
  { name: 'llama-3.1-8b-instruct',size: '4.7 GB', quant: 'Q4_K_M', lastUsed: '5d ago',  loaded: false },
];

export const MOCK_VLLM_ENDPOINTS = [
  { endpoint: ':8000/v1', model: 'qwen2.5-32b-instruct', gpus: 'GPU 0+3', vram: '42.1 GB', status: 'running' },
  { endpoint: ':8001/v1', model: '(stopped)',             gpus: 'GPU 1+2', vram: '—',       status: 'stopped' },
];

export const MOCK_LORA_ADAPTERS = [
  { name: 'qwen25-32b-20250115.bin',   baseModel: 'qwen2.5-32b', date: 'Jan 15', size: '1.8 GB', type: 'text' },
  { name: 'char-lora-v3.safetensors', baseModel: 'sdxl-1.0',    date: 'Jan 10', size: '380 MB', type: 'image' },
];

export const MOCK_TEXT_FILES = {
  'text/raw': [
    { name: 'raw-scraped-web-v2.jsonl',     size: '240 MB', modified: '15d ago' },
    { name: 'reddit-askscience-2024.jsonl', size: '88 MB',  modified: '22d ago' },
  ],
  'text/formatted': [
    { name: 'alpaca-52k.jsonl',             size: '84 MB',  modified: '2d ago'  },
    { name: 'custom-instruct-3k.jsonl',     size: '12 MB',  modified: '12d ago' },
    { name: 'openhermes-2.5-subset.jsonl',  size: '41 MB',  modified: '8d ago'  },
  ],
  'images': [
    { name: 'char-concept-v2.zip',  size: '1.2 GB', modified: '5d ago'  },
    { name: 'style-dataset-v1.zip', size: '890 MB', modified: '18d ago' },
  ],
};

export const MOCK_CHECKPOINTS = [
  {
    runName: 'qwen25-32b-20250115',
    type: 'text LoRA',
    date: 'Jan 15',
    files: [
      { name: 'checkpoint-step-800.bin', size: '1.2 GB' },
      { name: 'checkpoint-final.bin',    size: '1.8 GB' },
      { name: 'adapter_config.json',     size: '2 KB'   },
    ],
  },
  {
    runName: 'char-lora-v3',
    type: 'image LoRA',
    date: 'Jan 10',
    files: [
      { name: 'char-lora-v3.safetensors', size: '380 MB' },
      { name: 'training_params.json',     size: '1 KB'   },
    ],
  },
];

export const MOCK_VECTOR_COLLECTIONS = [
  { name: 'codebase-embeddings', vectors: 142880, dim: 768, diskGb: 1.1 },
  { name: 'docs-nomic',          vectors: 28441,  dim: 768, diskGb: 0.21 },
  { name: 'chat-history-embeds', vectors: 4102,   dim: 768, diskGb: 0.03 },
];

export const MOCK_STORAGE_SUMMARY = {
  disk: { usedTb: 14.8, totalTb: 20 },
  buckets: [
    { name: 'models/',      usedTb: 10.1, color: 'var(--cyan)'   },
    { name: 'training/',    usedTb: 2.7,  color: 'var(--amber)'  },
    { name: 'checkpoints/', usedTb: 1.2,  color: 'var(--purple)' },
    { name: 'backups/',     usedTb: 0.8,  color: 'var(--green)'  },
  ],
  postgres: [
    { db: 'langfuse', sizeGb: 2.4 },
    { db: 'n8n',      sizeGb: 0.89 },
    { db: 'dify',     sizeGb: 1.1  },
  ],
};

export const MOCK_BACKUP_HISTORY = [
  { date: '2026-06-05 06:00', sizeGb: 42, status: 'success' },
  { date: '2026-06-04 06:00', sizeGb: 41, status: 'success' },
  { date: '2026-06-03 06:00', sizeGb: 41, status: 'success' },
  { date: '2026-06-02 06:00', sizeGb: 40, status: 'failed'  },
];
```

---

### 2. `ui/src/pages/Resources.jsx`

Tab routing via `?tab=` URL parameter.

```jsx
import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ModelsTab }      from './resources/ModelsTab';
import { DatasetsTab }    from './resources/DatasetsTab';
import { CheckpointsTab } from './resources/CheckpointsTab';
import { VectorsTab }     from './resources/VectorsTab';
import { StorageTab }     from './resources/StorageTab';
import './Resources.css';

const TABS = [
  { id: 'models',      label: 'Models'      },
  { id: 'datasets',    label: 'Datasets'    },
  { id: 'checkpoints', label: 'Checkpoints' },
  { id: 'vectors',     label: 'Vectors'     },
  { id: 'storage',     label: 'Storage'     },
];

export function Resources() {
  const location = useLocation();
  const navigate = useNavigate();
  const params   = new URLSearchParams(location.search);
  const activeTab = params.get('tab') ?? 'models';

  function setTab(id) {
    navigate(`/resources?tab=${id}`, { replace: true });
  }

  return (
    <div className="resources-page">
      <div className="resources-header">
        <span className="resources-title">Resources</span>
      </div>

      <div className="tab-bar">
        {TABS.map(t => (
          <button
            key={t.id}
            className={`tab-btn ${activeTab === t.id ? 'tab-btn-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="tab-content">
        {activeTab === 'models'      && <ModelsTab />}
        {activeTab === 'datasets'    && <DatasetsTab />}
        {activeTab === 'checkpoints' && <CheckpointsTab />}
        {activeTab === 'vectors'     && <VectorsTab />}
        {activeTab === 'storage'     && <StorageTab />}
      </div>
    </div>
  );
}
```

```css
/* Resources.css */
@import '../tokens.css';

.resources-page { display: flex; flex-direction: column; gap: 14px; }

.resources-header { display: flex; align-items: center; gap: 12px; }

.resources-title { font-size: 13px; font-weight: 600; color: var(--text); }

.tab-bar {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--border);
}

.tab-btn {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  padding: 6px 14px;
  font-family: var(--mono);
  font-size: 10px;
  color: var(--text3);
  cursor: pointer;
  white-space: nowrap;
  transition: color .15s, border-color .15s;
}

.tab-btn:hover { color: var(--text2); }

.tab-btn-active {
  color: var(--cyan);
  border-bottom-color: var(--cyan);
}

.tab-content { min-height: 0; }
```

---

### 3. `ui/src/pages/resources/ModelsTab.jsx`

```jsx
import { useState } from 'react';
import { Panel } from '../../components/Panel';
import { Btn }   from '../../components/Btn';
import { MOCK_OLLAMA_MODELS, MOCK_VLLM_ENDPOINTS, MOCK_LORA_ADAPTERS } from '../../data/resourcesMock';
import './ModelsTab.css';

export function ModelsTab() {
  const [models, setModels] = useState(MOCK_OLLAMA_MODELS);
  const [pullName, setPullName] = useState('');
  const [pullProgress, setPullProgress] = useState(null); // null | 'pulling' | 'done' | 'error'
  const [openMenuFor, setOpenMenuFor] = useState(null); // model name

  async function handlePull() {
    if (!pullName.trim()) return;
    setPullProgress('pulling');
    try {
      const res = await fetch('/api/models/pull', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: pullName.trim() }),
      });
      if (!res.ok) throw new Error();
      setPullProgress('done');
      setPullName('');
      setTimeout(() => setPullProgress(null), 3000);
    } catch {
      // API not ready — simulate pull for UI testing
      setTimeout(() => {
        setModels(prev => [...prev, {
          name: pullName.trim(), size: '—', quant: '—', lastUsed: 'just now', loaded: false,
        }]);
        setPullProgress('done');
        setPullName('');
        setTimeout(() => setPullProgress(null), 2000);
      }, 1500);
    }
  }

  async function handleDelete(name) {
    if (!window.confirm(`Delete model "${name}"? This cannot be undone.`)) return;
    try {
      await fetch(`/api/models/${encodeURIComponent(name)}`, { method: 'DELETE' });
    } catch { /* API not ready */ }
    setModels(prev => prev.filter(m => m.name !== name));
  }

  function copyToClipboard(text) {
    navigator.clipboard.writeText(text).catch(() => {});
  }

  return (
    <div className="models-tab">
      {/* Pull new model */}
      <Panel title="OLLAMA MODELS">
        <div className="pull-row">
          <input
            className="pull-input"
            placeholder="Model name (e.g. qwen2.5:7b)"
            value={pullName}
            onChange={e => setPullName(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handlePull()}
          />
          <Btn variant="cyan" size="sm" onClick={handlePull}
            disabled={!pullName.trim() || pullProgress === 'pulling'}>
            {pullProgress === 'pulling' ? 'Pulling…' : 'Pull'}
          </Btn>
        </div>
        {pullProgress === 'done'  && <div className="pull-status pull-ok">Model pulled successfully.</div>}
        {pullProgress === 'error' && <div className="pull-status pull-err">Pull failed — check model name.</div>}

        <table className="models-table">
          <thead>
            <tr>
              <th>Name</th><th>Size</th><th>Quant</th><th>Last Used</th><th></th>
            </tr>
          </thead>
          <tbody>
            {models.map(m => (
              <tr key={m.name}>
                <td style={{ color: m.loaded ? 'var(--cyan)' : 'var(--text)' }}>{m.name}</td>
                <td>{m.size}</td>
                <td>{m.quant}</td>
                <td>{m.lastUsed}</td>
                <td className="model-actions-cell">
                  <div className="model-menu-wrap">
                    <button
                      className="model-menu-btn"
                      onClick={() => setOpenMenuFor(openMenuFor === m.name ? null : m.name)}
                    >▼</button>
                    {openMenuFor === m.name && (
                      <div className="model-menu">
                        <button onClick={() => { copyToClipboard(m.name); setOpenMenuFor(null); }}>Copy model ID</button>
                        <button onClick={() => { handleDelete(m.name); setOpenMenuFor(null); }} className="menu-item-danger">Delete</button>
                      </div>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      {/* vLLM endpoints */}
      <Panel title="VLLM ENDPOINTS">
        <table className="models-table">
          <thead>
            <tr><th>Endpoint</th><th>Model ID</th><th>TP Config</th><th>VRAM</th></tr>
          </thead>
          <tbody>
            {MOCK_VLLM_ENDPOINTS.map(e => (
              <tr key={e.endpoint}>
                <td style={{ color: 'var(--cyan)' }}>{e.endpoint}</td>
                <td style={{ color: e.status === 'running' ? 'var(--text)' : 'var(--text3)' }}>{e.model}</td>
                <td>{e.gpus}</td>
                <td>{e.vram}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      {/* LoRA adapters */}
      <Panel title="CUSTOM LORA ADAPTERS">
        <table className="models-table">
          <thead>
            <tr><th>Name</th><th>Base Model</th><th>Date</th><th>Size</th><th></th></tr>
          </thead>
          <tbody>
            {MOCK_LORA_ADAPTERS.map(a => (
              <tr key={a.name}>
                <td>{a.name}</td>
                <td>{a.baseModel}</td>
                <td>{a.date}</td>
                <td>{a.size}</td>
                <td>
                  <Btn variant="cyan" size="sm" onClick={async () => {
                    try {
                      await fetch('/api/models/load-lora', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name: a.name, base_model: a.baseModel }),
                      });
                    } catch { /* API not ready */ }
                    alert(`Load LoRA: ${a.name}\n(API available in Step 10)`);
                  }}>
                    Load
                  </Btn>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}
```

```css
/* ModelsTab.css */
@import '../../tokens.css';

.models-tab { display: flex; flex-direction: column; gap: 12px; }

.pull-row {
  display: flex;
  gap: 8px;
  margin-bottom: 8px;
}

.pull-input {
  flex: 1;
  background: var(--surface3);
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--text);
  font-family: var(--mono);
  font-size: 10px;
  padding: 5px 8px;
}

.pull-status { font-size: 9px; margin-bottom: 8px; }
.pull-ok  { color: var(--green); }
.pull-err { color: var(--red); }

.models-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 10px;
}

.models-table th {
  text-align: left;
  color: var(--text3);
  font-size: 9px;
  border-bottom: 1px solid var(--border);
  padding: 4px 6px;
}

.models-table td {
  padding: 6px 6px;
  color: var(--text2);
  border-bottom: 1px solid var(--border);
}

.models-table tr:last-child td { border-bottom: none; }

.model-actions-cell { position: relative; width: 32px; }

.model-menu-wrap { position: relative; }

.model-menu-btn {
  background: none;
  border: none;
  color: var(--text3);
  cursor: pointer;
  font-family: var(--mono);
  font-size: 9px;
  padding: 2px 4px;
}

.model-menu-btn:hover { color: var(--text); }

.model-menu {
  position: absolute;
  right: 0;
  top: 100%;
  background: var(--surface2);
  border: 1px solid var(--border2);
  border-radius: var(--radius);
  min-width: 140px;
  z-index: 10;
  overflow: hidden;
}

.model-menu button {
  display: block;
  width: 100%;
  background: none;
  border: none;
  text-align: left;
  padding: 7px 12px;
  font-family: var(--mono);
  font-size: 10px;
  color: var(--text2);
  cursor: pointer;
}

.model-menu button:hover { background: var(--surface3); color: var(--text); }
.menu-item-danger { color: var(--red) !important; }
```

---

### 4. `ui/src/pages/resources/DatasetsTab.jsx`

Drag-and-drop upload zone + collapsible file browser sections.

```jsx
import { useState, useRef } from 'react';
import { VBar } from '../../components/VBar';
import { Btn }  from '../../components/Btn';
import { MOCK_TEXT_FILES } from '../../data/resourcesMock';
import './DatasetsTab.css';

const DESTINATIONS = ['text/formatted', 'text/raw', 'images'];

export function DatasetsTab() {
  const [dragOver, setDragOver]       = useState(false);
  const [destPath, setDestPath]       = useState('text/formatted');
  const [uploads, setUploads]         = useState([]);   // { name, progress, done }
  const [expandedSections, setExpand] = useState(new Set(['text/formatted']));
  const [previewData, setPreviewData] = useState(null); // { name, rows } | null
  const inputRef = useRef(null);

  function toggleSection(key) {
    setExpand(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  function startUpload(file) {
    const id = file.name;
    setUploads(prev => [...prev, { name: id, progress: 0, done: false }]);

    const form = new FormData();
    form.append('file', file);
    form.append('path', `/data/training/${destPath}/${file.name}`);

    const xhr = new XMLHttpRequest();
    xhr.upload.onprogress = (e) => {
      if (!e.lengthComputable) return;
      const pct = Math.round((e.loaded / e.total) * 100);
      setUploads(prev => prev.map(u => u.name === id ? { ...u, progress: pct } : u));
    };
    xhr.onload = () => {
      setUploads(prev => prev.map(u => u.name === id ? { ...u, done: true, progress: 100 } : u));
    };
    xhr.onerror = () => {
      // API not ready — simulate completion
      let prog = 0;
      const iv = setInterval(() => {
        prog = Math.min(prog + 20, 100);
        setUploads(prev => prev.map(u => u.name === id ? { ...u, progress: prog } : u));
        if (prog >= 100) {
          clearInterval(iv);
          setUploads(prev => prev.map(u => u.name === id ? { ...u, done: true } : u));
        }
      }, 200);
    };
    xhr.open('POST', '/api/storage/upload');
    xhr.send(form);
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    Array.from(e.dataTransfer.files).forEach(startUpload);
  }

  async function handlePreview(path, name) {
    try {
      const res = await fetch(`/api/storage/preview?path=${encodeURIComponent(path)}&n=5`);
      if (!res.ok) throw new Error();
      const data = await res.json();
      setPreviewData({ name, rows: data.rows ?? [] });
    } catch {
      // Mock preview
      setPreviewData({
        name,
        rows: [
          { instruction: 'Explain quantum entanglement', input: '', output: 'Sure, quantum...' },
          { instruction: 'Write a haiku about rain', input: '', output: 'Drops on the glass...' },
          { instruction: 'Summarize this article', input: 'The paper...', output: 'The study found...' },
        ],
      });
    }
  }

  async function handleDelete(path, name) {
    if (!window.confirm(`Delete "${name}"? This cannot be undone.`)) return;
    try {
      await fetch(`/api/storage/file?path=${encodeURIComponent(path)}`, { method: 'DELETE' });
    } catch { /* API not ready */ }
  }

  const SECTION_LABELS = {
    'text/raw': 'text/raw/',
    'text/formatted': 'text/formatted/',
    'images': 'images/',
  };

  return (
    <div className="datasets-tab">
      {/* Upload zone */}
      <div
        className={`upload-zone ${dragOver ? 'upload-zone-active' : ''}`}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <span>Drop .jsonl or .zip here to upload</span>
        <span className="upload-dest">→ /data/training/{destPath}/</span>
        <input ref={inputRef} type="file" accept=".jsonl,.zip" multiple hidden
          onChange={e => Array.from(e.target.files).forEach(startUpload)} />
      </div>

      {/* Destination selector */}
      <div className="dest-selector">
        <span className="dest-label">Destination:</span>
        {DESTINATIONS.map(d => (
          <button
            key={d}
            className={`dest-btn ${destPath === d ? 'dest-btn-active' : ''}`}
            onClick={() => setDestPath(d)}
          >
            {d}
          </button>
        ))}
      </div>

      {/* Active uploads */}
      {uploads.map(u => (
        <div key={u.name} className={`upload-progress ${u.done ? 'upload-done' : ''}`}>
          <span className="upload-name">{u.name}</span>
          <VBar pct={u.progress} variant={u.done ? 'green' : 'cyan'} />
          <span className="upload-pct">{u.progress}%</span>
        </div>
      ))}

      {/* File browser */}
      {Object.entries(SECTION_LABELS).map(([key, label]) => (
        <div key={key} className="file-section">
          <button
            className="file-section-header"
            onClick={() => toggleSection(key)}
          >
            <span>{expandedSections.has(key) ? '▾' : '▸'}</span>
            <span>{label}</span>
            <span className="file-section-count">{MOCK_TEXT_FILES[key]?.length ?? 0} files</span>
          </button>

          {expandedSections.has(key) && (
            <table className="files-table">
              <thead>
                <tr><th>Name</th><th>Size</th><th>Modified</th><th></th></tr>
              </thead>
              <tbody>
                {(MOCK_TEXT_FILES[key] ?? []).map(f => (
                  <tr key={f.name}>
                    <td>{f.name}</td>
                    <td>{f.size}</td>
                    <td>{f.modified}</td>
                    <td className="file-actions">
                      <Btn variant="gray" size="sm"
                        onClick={() => handlePreview(`/data/training/${key}/${f.name}`, f.name)}>
                        Preview
                      </Btn>
                      <Btn variant="gray" size="sm"
                        onClick={() => window.open(`/api/storage/download?path=${encodeURIComponent(`/data/training/${key}/${f.name}`)}`, '_blank')}>
                        Download
                      </Btn>
                      <Btn variant="red" size="sm"
                        onClick={() => handleDelete(`/data/training/${key}/${f.name}`, f.name)}>
                        Delete
                      </Btn>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ))}

      {/* Preview modal */}
      {previewData && (
        <div className="modal-overlay" onClick={() => setPreviewData(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <span>{previewData.name} — preview</span>
              <button className="modal-close" onClick={() => setPreviewData(null)}>✕</button>
            </div>
            <table className="preview-table">
              <thead>
                <tr><th>instruction</th><th>input</th><th>output</th></tr>
              </thead>
              <tbody>
                {previewData.rows.map((row, i) => (
                  <tr key={i}>
                    <td>{row.instruction}</td>
                    <td>{row.input}</td>
                    <td>{row.output}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
```

```css
/* DatasetsTab.css */
@import '../../tokens.css';

.datasets-tab { display: flex; flex-direction: column; gap: 12px; }

.upload-zone {
  border: 2px dashed var(--border2);
  border-radius: var(--radius);
  padding: 20px;
  text-align: center;
  font-size: 11px;
  color: var(--text3);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
  transition: border-color .15s, background .15s;
}

.upload-zone:hover,
.upload-zone-active {
  border-color: var(--cyan);
  background: var(--cyan-dim);
  color: var(--text2);
}

.upload-dest { font-size: 9px; }

.dest-selector {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 9px;
  color: var(--text3);
}

.dest-btn {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--text3);
  font-family: var(--mono);
  font-size: 9px;
  padding: 3px 8px;
  cursor: pointer;
}

.dest-btn-active {
  background: var(--cyan-dim);
  border-color: var(--cyan);
  color: var(--cyan);
}

.upload-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 9px;
}

.upload-name { flex: 1; color: var(--text2); min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.upload-pct  { width: 32px; text-align: right; color: var(--text3); }
.upload-progress .vbar-track { width: 100px; flex-shrink: 0; }
.upload-done .upload-name { color: var(--green); }

.file-section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.file-section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  background: none;
  border: none;
  padding: 8px 12px;
  font-family: var(--mono);
  font-size: 10px;
  color: var(--text2);
  cursor: pointer;
  text-align: left;
}

.file-section-header:hover { background: var(--surface2); }

.file-section-count { margin-left: auto; font-size: 9px; color: var(--text3); }

.files-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 10px;
}

.files-table th {
  color: var(--text3);
  font-size: 9px;
  text-align: left;
  padding: 4px 10px;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}

.files-table td {
  padding: 6px 10px;
  color: var(--text2);
  border-bottom: 1px solid var(--border);
}

.files-table tr:last-child td { border-bottom: none; }

.file-actions { display: flex; gap: 4px; justify-content: flex-end; }

/* Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,.6);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.modal {
  background: var(--surface);
  border: 1px solid var(--border2);
  border-radius: var(--radius);
  min-width: 480px;
  max-width: 720px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text);
  border-bottom: 1px solid var(--border);
}

.modal-close {
  background: none;
  border: none;
  color: var(--text3);
  cursor: pointer;
  font-size: 12px;
  padding: 2px 4px;
}

.preview-table {
  font-size: 10px;
  border-collapse: collapse;
  width: 100%;
  overflow-y: auto;
  display: block;
  max-height: calc(80vh - 60px);
}

.preview-table th {
  background: var(--surface2);
  border-bottom: 1px solid var(--border);
  padding: 6px 10px;
  color: var(--text3);
  font-size: 9px;
  text-align: left;
  position: sticky;
  top: 0;
}

.preview-table td {
  padding: 6px 10px;
  color: var(--text2);
  border-bottom: 1px solid var(--border);
  vertical-align: top;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
```

---

### 5. `ui/src/pages/resources/CheckpointsTab.jsx`

Collapsible run groups. "Merge & Pull" text LoRA action; clipboard copy path for image LoRA.

```jsx
import { useState } from 'react';
import { Btn } from '../../components/Btn';
import { MOCK_CHECKPOINTS } from '../../data/resourcesMock';
import './CheckpointsTab.css';

export function CheckpointsTab() {
  const [expanded, setExpanded] = useState(new Set([MOCK_CHECKPOINTS[0].runName]));

  function toggle(name) {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  }

  async function handleLoad(run, file) {
    if (run.type === 'text LoRA') {
      if (!window.confirm(`Load "${file.name}" into Ollama?\nThis will create a new modelfile.`)) return;
      try {
        await fetch('/api/models/load-lora', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: `/data/checkpoints/${run.runName}/${file.name}`, base_model: run.runName }),
        });
      } catch { /* API not ready */ }
      alert(`Load LoRA: (API available in Step 10)\n/data/checkpoints/${run.runName}/${file.name}`);
    } else {
      // Image LoRA: copy path
      navigator.clipboard.writeText(`/data/checkpoints/${run.runName}/${file.name}`).catch(() => {});
      alert(`Path copied: /data/checkpoints/${run.runName}/${file.name}`);
    }
  }

  return (
    <div className="checkpoints-tab">
      {MOCK_CHECKPOINTS.map(run => (
        <div key={run.runName} className="checkpoint-run">
          <button className="checkpoint-run-header" onClick={() => toggle(run.runName)}>
            <span>{expanded.has(run.runName) ? '▾' : '▸'}</span>
            <span className="run-name">{run.runName}</span>
            <span className="run-type tag tag-{run.type === 'text LoRA' ? 'amber' : 'purple'}">
              {run.type}
            </span>
            <span className="run-date">{run.date}</span>
          </button>
          {expanded.has(run.runName) && (
            <table className="checkpoint-files-table">
              <tbody>
                {run.files.map(f => (
                  <tr key={f.name}>
                    <td className="ckpt-name">{f.name}</td>
                    <td className="ckpt-size">{f.size}</td>
                    <td className="ckpt-actions">
                      {f.name.endsWith('.bin') || f.name.endsWith('.safetensors') ? (
                        <Btn variant="cyan" size="sm" onClick={() => handleLoad(run, f)}>
                          {run.type === 'text LoRA' ? 'Load into Ollama' : 'Copy Path'}
                        </Btn>
                      ) : (
                        <Btn variant="gray" size="sm"
                          onClick={() => alert(`View: /data/checkpoints/${run.runName}/${f.name}\n(Step 10)`)}>
                          View
                        </Btn>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ))}
    </div>
  );
}
```

```css
/* CheckpointsTab.css */
@import '../../tokens.css';

.checkpoints-tab { display: flex; flex-direction: column; gap: 6px; }

.checkpoint-run {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}

.checkpoint-run-header {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  background: none;
  border: none;
  padding: 8px 12px;
  font-family: var(--mono);
  font-size: 10px;
  color: var(--text2);
  cursor: pointer;
  text-align: left;
}

.checkpoint-run-header:hover { background: var(--surface2); }

.run-name { flex: 1; font-weight: 600; color: var(--text); }
.run-date { font-size: 9px; color: var(--text3); }

.checkpoint-files-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 10px;
}

.checkpoint-files-table td {
  padding: 6px 12px;
  border-top: 1px solid var(--border);
  color: var(--text2);
}

.ckpt-name { flex: 1; }
.ckpt-size { color: var(--text3); width: 72px; }
.ckpt-actions { text-align: right; }
```

---

### 6. `ui/src/pages/resources/VectorsTab.jsx`

Two-step delete confirmation (type collection name). Re-embed action. Create new collection.

```jsx
import { useState } from 'react';
import { Btn } from '../../components/Btn';
import { MOCK_VECTOR_COLLECTIONS } from '../../data/resourcesMock';
import './VectorsTab.css';

export function VectorsTab() {
  const [collections, setCollections] = useState(MOCK_VECTOR_COLLECTIONS);
  const [deletingName, setDeletingName] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState('');
  const [creating, setCreating] = useState(false);
  const [newCol, setNewCol] = useState({ name: '', dim: 768, distance: 'cosine' });

  async function handleReEmbed(name) {
    try {
      await fetch('/api/vectors/re-embed', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ collection: name }),
      });
    } catch { /* API not ready */ }
    alert(`Re-embed triggered for "${name}"\n(API available in Step 10)`);
  }

  async function handleDeleteConfirm() {
    if (deleteConfirm !== deletingName) return;
    try {
      await fetch(`/api/vectors/collections/${encodeURIComponent(deletingName)}`, { method: 'DELETE' });
    } catch { /* API not ready */ }
    setCollections(prev => prev.filter(c => c.name !== deletingName));
    setDeletingName(null);
    setDeleteConfirm('');
  }

  async function handleCreate() {
    if (!newCol.name.trim()) return;
    try {
      await fetch('/api/vectors/collections', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newCol),
      });
    } catch { /* API not ready */ }
    setCollections(prev => [...prev, { name: newCol.name, vectors: 0, dim: newCol.dim, diskGb: 0 }]);
    setCreating(false);
    setNewCol({ name: '', dim: 768, distance: 'cosine' });
  }

  return (
    <div className="vectors-tab">
      <table className="vectors-table">
        <thead>
          <tr><th>Collection</th><th>Vectors</th><th>Dim</th><th>Disk</th><th></th></tr>
        </thead>
        <tbody>
          {collections.map(c => (
            <tr key={c.name}>
              <td>{c.name}</td>
              <td>{c.vectors.toLocaleString()}</td>
              <td>{c.dim}</td>
              <td>{c.diskGb >= 1 ? `${c.diskGb.toFixed(1)} GB` : `${Math.round(c.diskGb * 1000)} MB`}</td>
              <td className="vec-actions">
                <Btn variant="gray" size="sm" onClick={() => handleReEmbed(c.name)}>Re-embed</Btn>
                <Btn variant="red"  size="sm" onClick={() => setDeletingName(c.name)}>Delete</Btn>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <Btn variant="cyan" size="sm" onClick={() => setCreating(true)}>+ New Collection</Btn>

      {/* Two-step delete confirmation */}
      {deletingName && (
        <div className="modal-overlay" onClick={() => { setDeletingName(null); setDeleteConfirm(''); }}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <span>Delete collection "{deletingName}"?</span>
              <button className="modal-close" onClick={() => { setDeletingName(null); setDeleteConfirm(''); }}>✕</button>
            </div>
            <div className="delete-confirm-body">
              <p>This will permanently delete all {collections.find(c => c.name === deletingName)?.vectors.toLocaleString()} vectors.</p>
              <p>Type the collection name to confirm:</p>
              <input
                className="confirm-input"
                placeholder={deletingName}
                value={deleteConfirm}
                onChange={e => setDeleteConfirm(e.target.value)}
              />
              <Btn
                variant="red"
                size="md"
                disabled={deleteConfirm !== deletingName}
                onClick={handleDeleteConfirm}
              >
                Delete permanently
              </Btn>
            </div>
          </div>
        </div>
      )}

      {/* Create collection form */}
      {creating && (
        <div className="create-collection-form">
          <div className="create-row">
            <input className="form-input" placeholder="Collection name"
              value={newCol.name} onChange={e => setNewCol(c => ({ ...c, name: e.target.value }))} />
            <input className="form-input form-input-short" type="number" placeholder="Dim" min={1}
              value={newCol.dim} onChange={e => setNewCol(c => ({ ...c, dim: +e.target.value }))} />
            <select className="form-select" value={newCol.distance}
              onChange={e => setNewCol(c => ({ ...c, distance: e.target.value }))}>
              <option value="cosine">cosine</option>
              <option value="dot">dot</option>
              <option value="euclidean">euclidean</option>
            </select>
            <Btn variant="cyan" size="sm" onClick={handleCreate}>Create</Btn>
            <Btn variant="gray" size="sm" onClick={() => setCreating(false)}>Cancel</Btn>
          </div>
        </div>
      )}
    </div>
  );
}
```

```css
/* VectorsTab.css */
@import '../../tokens.css';

.vectors-tab { display: flex; flex-direction: column; gap: 12px; }

.vectors-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 10px;
}

.vectors-table th {
  text-align: left;
  color: var(--text3);
  font-size: 9px;
  border-bottom: 1px solid var(--border);
  padding: 4px 8px;
}

.vectors-table td {
  padding: 7px 8px;
  color: var(--text2);
  border-bottom: 1px solid var(--border);
}

.vectors-table tr:last-child td { border-bottom: none; }

.vec-actions { display: flex; gap: 4px; }

.delete-confirm-body {
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 10px;
  color: var(--text2);
}

.confirm-input {
  background: var(--surface3);
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--text);
  font-family: var(--mono);
  font-size: 10px;
  padding: 5px 8px;
}

.create-collection-form {
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 10px 12px;
}

.create-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

.form-input {
  background: var(--surface3);
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--text);
  font-family: var(--mono);
  font-size: 10px;
  padding: 5px 8px;
  flex: 1;
  min-width: 120px;
}

.form-input-short { flex: 0 0 64px; min-width: 64px; }

.form-select {
  background: var(--surface3);
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--text);
  font-family: var(--mono);
  font-size: 10px;
  padding: 5px 8px;
}
```

---

### 7. `ui/src/pages/resources/StorageTab.jsx`

Disk usage bar, stacked MinIO bar, PostgreSQL table, backup controls.

```jsx
import { useState } from 'react';
import { VBar } from '../../components/VBar';
import { Btn }  from '../../components/Btn';
import { MOCK_STORAGE_SUMMARY, MOCK_BACKUP_HISTORY } from '../../data/resourcesMock';
import './StorageTab.css';

export function StorageTab() {
  const [summary]   = useState(MOCK_STORAGE_SUMMARY);
  const [backups, setBackups] = useState(MOCK_BACKUP_HISTORY);
  const [cron, setCron]       = useState('0 6 * * *');
  const [editingCron, setEditingCron] = useState(false);
  const [backupRunning, setBackupRunning] = useState(false);

  const diskPct   = (summary.disk.usedTb / summary.disk.totalTb) * 100;
  const diskVar   = diskPct > 90 ? 'red' : diskPct > 70 ? 'amber' : 'green';
  const totalBucketTb = summary.buckets.reduce((s, b) => s + b.usedTb, 0);

  async function runBackup() {
    setBackupRunning(true);
    try {
      await fetch('/api/backup/run', { method: 'POST' });
    } catch { /* API not ready */ }
    setTimeout(() => {
      const now = new Date().toISOString().replace('T', ' ').slice(0, 16);
      setBackups(prev => [{ date: now, sizeGb: Math.round(summary.disk.usedTb * 100), status: 'success' }, ...prev.slice(0, 9)]);
      setBackupRunning(false);
    }, 2000);
  }

  return (
    <div className="storage-tab">
      {/* Disk usage */}
      <div className="storage-section">
        <div className="storage-section-title">/DATA PARTITION</div>
        <div className="disk-summary">
          {summary.disk.usedTb.toFixed(1)} TB / {summary.disk.totalTb} TB
          <span className="disk-pct"> · {Math.round(diskPct)}%</span>
        </div>
        <VBar pct={diskPct} variant={diskVar} />
      </div>

      {/* MinIO stacked bar */}
      <div className="storage-section">
        <div className="storage-section-title">MINIO BUCKETS</div>
        <div className="stacked-bar">
          {summary.buckets.map(b => (
            <div
              key={b.name}
              className="stacked-segment"
              style={{
                width: `${(b.usedTb / totalBucketTb) * 100}%`,
                background: b.color,
              }}
              title={`${b.name} · ${b.usedTb.toFixed(1)} TB`}
            />
          ))}
        </div>
        <div className="bucket-legend">
          {summary.buckets.map(b => (
            <div key={b.name} className="bucket-legend-row">
              <span className="bucket-dot" style={{ background: b.color }} />
              <span className="bucket-name">{b.name}</span>
              <span className="bucket-used">{b.usedTb.toFixed(1)} TB</span>
            </div>
          ))}
        </div>
      </div>

      {/* PostgreSQL sizes */}
      <div className="storage-section">
        <div className="storage-section-title">POSTGRESQL DATABASES</div>
        <table className="pg-table">
          <thead><tr><th>Database</th><th>Size</th></tr></thead>
          <tbody>
            {summary.postgres.map(p => (
              <tr key={p.db}>
                <td>{p.db}</td>
                <td>{p.sizeGb >= 1 ? `${p.sizeGb.toFixed(1)} GB` : `${Math.round(p.sizeGb * 1000)} MB`}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Backup controls */}
      <div className="storage-section">
        <div className="storage-section-title">BACKUP</div>
        <div className="backup-meta">
          <div>
            <span className="meta-label">Last backup</span>
            <span>{backups[0]?.date} · {backups[0]?.sizeGb} GB ·
              <span style={{ color: backups[0]?.status === 'success' ? 'var(--green)' : 'var(--red)' }}>
                {' '}{backups[0]?.status === 'success' ? '✓ success' : '✗ failed'}
              </span>
            </span>
          </div>
          <div className="backup-schedule-row">
            <span className="meta-label">Schedule</span>
            {editingCron ? (
              <>
                <input className="cron-input" value={cron} onChange={e => setCron(e.target.value)} />
                <Btn variant="cyan" size="sm" onClick={() => setEditingCron(false)}>Save</Btn>
              </>
            ) : (
              <>
                <code className="cron-val">{cron}</code>
                <button className="cron-edit-btn" onClick={() => setEditingCron(true)}>edit</button>
              </>
            )}
          </div>
        </div>
        <Btn variant="gray" size="sm" onClick={runBackup} disabled={backupRunning}>
          {backupRunning ? 'Running…' : 'Run Backup Now'}
        </Btn>

        <table className="backup-history-table">
          <thead><tr><th>Date</th><th>Size</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {backups.map((b, i) => (
              <tr key={i}>
                <td>{b.date}</td>
                <td>{b.sizeGb} GB</td>
                <td style={{ color: b.status === 'success' ? 'var(--green)' : 'var(--red)' }}>
                  {b.status === 'success' ? '✓ success' : '✗ failed'}
                </td>
                <td>
                  <Btn variant="red" size="sm"
                    onClick={() => window.confirm(`Delete backup from ${b.date}?`) && setBackups(prev => prev.filter((_, j) => j !== i))}>
                    Delete
                  </Btn>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

```css
/* StorageTab.css */
@import '../../tokens.css';

.storage-tab { display: flex; flex-direction: column; gap: 16px; }

.storage-section { display: flex; flex-direction: column; gap: 8px; }

.storage-section-title {
  font-size: 9px;
  color: var(--text3);
  letter-spacing: .5px;
  font-weight: 600;
}

.disk-summary { font-size: 12px; color: var(--text); }
.disk-pct     { font-size: 10px; color: var(--text3); }

/* Stacked bar */
.stacked-bar {
  display: flex;
  height: 10px;
  border-radius: 5px;
  overflow: hidden;
  background: var(--surface3);
}

.stacked-segment { height: 100%; transition: width .3s; cursor: default; }

.bucket-legend { display: flex; flex-direction: column; gap: 4px; margin-top: 4px; }

.bucket-legend-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
}

.bucket-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  flex-shrink: 0;
}

.bucket-name { flex: 1; color: var(--text2); }
.bucket-used { color: var(--text3); }

/* PG table */
.pg-table {
  font-size: 10px;
  border-collapse: collapse;
  width: 100%;
  max-width: 320px;
}

.pg-table th {
  color: var(--text3);
  font-size: 9px;
  text-align: left;
  padding: 3px 8px;
  border-bottom: 1px solid var(--border);
}

.pg-table td { padding: 5px 8px; color: var(--text2); }

/* Backup */
.backup-meta { display: flex; flex-direction: column; gap: 6px; font-size: 10px; color: var(--text2); }

.meta-label {
  display: inline-block;
  width: 88px;
  font-size: 9px;
  color: var(--text3);
}

.backup-schedule-row { display: flex; align-items: center; gap: 8px; }

.cron-val {
  font-family: var(--mono);
  font-size: 10px;
  color: var(--cyan);
  background: var(--cyan-dim);
  border-radius: 3px;
  padding: 1px 6px;
}

.cron-edit-btn {
  background: none;
  border: none;
  font-family: var(--mono);
  font-size: 9px;
  color: var(--text3);
  cursor: pointer;
  text-decoration: underline;
}

.cron-input {
  background: var(--surface3);
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--text);
  font-family: var(--mono);
  font-size: 10px;
  padding: 3px 8px;
  width: 120px;
}

.backup-history-table {
  font-size: 10px;
  border-collapse: collapse;
  width: 100%;
}

.backup-history-table th {
  color: var(--text3);
  font-size: 9px;
  text-align: left;
  padding: 4px 6px;
  border-bottom: 1px solid var(--border);
}

.backup-history-table td {
  padding: 6px 6px;
  color: var(--text2);
  border-bottom: 1px solid var(--border);
}

.backup-history-table tr:last-child td { border-bottom: none; }
```

---

## Acceptance Criteria

- [ ] Tab bar renders all 5 tabs; active tab has cyan underline; URL updates to `?tab=X` on click
- [ ] Browser back/forward navigates between tabs
- [ ] **Models:** Ollama table renders with cyan name for loaded models; pull form adds new entry after 1.5s mock delay; dropdown menu shows copy/delete options; delete confirms and removes row
- [ ] **Datasets:** Drag-over state turns upload zone cyan; file input works; upload progress bar animates 0→100% (mock); file browser accordion collapses/expands; Preview opens modal with 3-row table; modal closes on overlay click
- [ ] **Checkpoints:** Run groups expand/collapse; "Load into Ollama" confirms; image LoRA "Copy Path" writes to clipboard
- [ ] **Vectors:** Table shows all collections with `.toLocaleString()` formatted counts; Re-embed shows alert; Delete opens modal requiring exact name match before enabling "Delete permanently"
- [ ] **Storage:** Disk VBar colored correctly (amber at 74%); stacked MinIO bar segments proportional; "Run Backup Now" shows "Running…" state then appends to history; cron edit saves on click
- [ ] `npm run dev` shows no console errors navigating across all 5 tabs

---

## Feedback

Write `plan/UI/GHC-Feedback/06-feedback.md` when done.

**Required in Notes:**
- Does the XHR upload (not fetch) work correctly through the Vite dev server proxy? Note any CORS or proxy config changes needed.
- Confirm `navigator.clipboard.writeText` works in the dev environment (requires HTTPS or localhost).
