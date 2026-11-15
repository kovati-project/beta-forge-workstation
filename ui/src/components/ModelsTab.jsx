import { useState, useEffect, useRef, useCallback } from 'react';
import {
  getModels, deleteModel, pullModel,
  getVllmLocalModels, activateVllmModel, downloadVllmModel, getVllmDownloadStatus,
  searchHuggingFace, getLocalModels, registerLocalModel,
} from '../utils/resourcesAPI';
import { Btn } from './Btn';
import './ModelsTab.css';

const SLOT_LABELS = {
  'pair-a': 'Pair A',
  'pair-b': 'Pair B',
  '4gpu':   '4-GPU',
};

const SLOT_TO_SERVICE = {
  'pair-a': 'vllm-pair-a',
  'pair-b': 'vllm-pair-b',
  '4gpu':   'vllm-4gpu',
};

// Hugging Face pipeline tags offered as a task filter ('' = any task).
const HF_TASKS = [
  ['', 'Any task'],
  ['text-generation', 'Text generation'],
  ['image-text-to-text', 'Vision-language'],
  ['feature-extraction', 'Embeddings'],
  ['sentence-similarity', 'Sentence similarity'],
  ['text-classification', 'Text classification'],
  ['automatic-speech-recognition', 'Speech to text'],
  ['text-to-speech', 'Text to speech'],
  ['text-to-image', 'Text to image'],
  ['image-to-image', 'Image to image'],
];

const FORMAT_LABELS = {
  hf: 'HF',
  adapter: 'LoRA adapter',
  gguf: 'GGUF',
  safetensors: 'safetensors',
};

const deriveLocalName = (repoId) => (repoId.includes('/') ? repoId.split('/').pop() : repoId);

function formatBytes(bytes) {
  if (typeof bytes !== 'number' || !bytes) return '—';
  const gb = bytes / 1e9;
  return gb >= 1 ? `${gb.toFixed(1)} GB` : `${Math.round(bytes / 1e6)} MB`;
}

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : d.toISOString().slice(0, 10);
}

// One vLLM download at a time (the backend enforces it); shared by the
// by-repo form and the Hugging Face browser so both show the same progress.
function useVllmDownload(onDone) {
  const [dlStatus, setDlStatus] = useState({});
  const [dlError, setDlError]   = useState(null);
  const pollRef = useRef(null);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    // Pick up a download started before this page was opened.
    getVllmDownloadStatus().then(s => s && setDlStatus(s));
  }, []);

  useEffect(() => {
    if (dlStatus?.status === 'running') {
      pollRef.current = setInterval(async () => {
        const s = await getVllmDownloadStatus();
        setDlStatus(s);
        if (s.status === 'done') {
          clearInterval(pollRef.current);
          onDoneRef.current?.();
        } else if (s.status === 'error') {
          clearInterval(pollRef.current);
        }
      }, 3000);
    }
    return () => clearInterval(pollRef.current);
  }, [dlStatus?.status]);

  const start = async (repoId, localName) => {
    setDlError(null);
    try {
      await downloadVllmModel(repoId, localName);
      setDlStatus({ status: 'running', repo_id: repoId, local_name: localName });
      return true;
    } catch (e) {
      setDlError(e.message);
      return false;
    }
  };

  return { dlStatus, dlError, start, running: dlStatus?.status === 'running' };
}

function DownloadStatus({ dl }) {
  const { dlStatus, dlError } = dl;
  return (
    <>
      {dlError && <div className="error-message">{dlError}</div>}
      {dlStatus?.status === 'running' && (
        <div className="dl-status">
          Downloading <strong>{dlStatus.repo_id}</strong> → {dlStatus.local_name}…
        </div>
      )}
      {dlStatus?.status === 'done' && (
        <div className="dl-status dl-done">
          Download complete: {dlStatus.local_name}
        </div>
      )}
      {dlStatus?.status === 'error' && (
        <div className="error-message">Download failed: {dlStatus.error}</div>
      )}
    </>
  );
}

function OllamaSection({ refreshKey }) {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pullInput, setPullInput] = useState('');
  const [pulling, setPulling] = useState(false);
  const [pullError, setPullError] = useState(null);
  const [pullNote, setPullNote] = useState(null);

  const loadModels = useCallback(async () => {
    setLoading(true);
    const data = await getModels();
    // GET /api/models returns { models: [...] }.
    setModels(data?.models || []);
    setLoading(false);
  }, []);

  useEffect(() => { loadModels(); }, [loadModels, refreshKey]);

  const handlePull = async () => {
    const name = pullInput.trim();
    if (!name) return;

    setPulling(true);
    setPullError(null);
    setPullNote(null);
    try {
      await pullModel(name);
      setPullInput('');
      // The pull runs in the background on the host; it appears once Ollama finishes.
      setPullNote(`Pulling ${name} in the background. Refresh to see it once Ollama finishes.`);
      await loadModels();
    } catch (error) {
      setPullError(error.message);
    } finally {
      setPulling(false);
    }
  };

  const handleDelete = async (name) => {
    if (!confirm(`Delete model "${name}"?`)) return;

    try {
      await deleteModel(name);
      await loadModels();
    } catch (error) {
      console.error('Delete failed:', error);
    }
  };

  return (
    <div className="models-section">
      <div className="vllm-section-header">Ollama Models</div>
      <div className="pull-section">
        <div className="pull-input-group">
          <input
            type="text"
            placeholder="e.g. qwen2.5:32b or hf.co/bartowski/Qwen2.5-7B-Instruct-GGUF"
            value={pullInput}
            onChange={(e) => setPullInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handlePull()}
            disabled={pulling}
          />
          <Btn onClick={handlePull} disabled={!pullInput.trim() || pulling} size="sm">
            Pull
          </Btn>
          <Btn onClick={loadModels} disabled={loading} size="sm">Refresh</Btn>
        </div>
        {pullError && <div className="error-message">{pullError}</div>}
        {pullNote && <div className="dl-status">{pullNote}</div>}
      </div>

      {loading ? (
        <div className="loading">Loading models...</div>
      ) : (
        <table className="models-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Size</th>
              <th>Quantization</th>
              <th>Modified</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {models.length === 0 ? (
              <tr>
                <td colSpan="5" className="empty">
                  No Ollama models (or Ollama is not running)
                </td>
              </tr>
            ) : (
              models.map((model) => (
                <tr key={model.name}>
                  <td className="model-name">{model.name}</td>
                  <td>{formatBytes(model.size)}</td>
                  <td>{model.quantization || '—'}</td>
                  <td>{formatDate(model.modified) || '—'}</td>
                  <td>
                    <button
                      className="action-btn"
                      onClick={() => handleDelete(model.name)}
                      title="Delete model"
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}

function VllmModelsSection({ refreshKey, dl }) {
  const [vllmData, setVllmData]       = useState({ models: [], slots: {} });
  const [loadTarget, setLoadTarget]   = useState({});     // { modelName: slotKey }
  const [activating, setActivating]   = useState(null);   // slotKey being set
  const [restarting, setRestarting]   = useState(null);   // slotKey being restarted
  const [dlRepo, setDlRepo]           = useState('');
  const [dlName, setDlName]           = useState('');

  const loadVllm = useCallback(async () => {
    const data = await getVllmLocalModels();
    setVllmData(data);
    // initialise load-target dropdowns to first slot
    setLoadTarget(prev => {
      const next = { ...prev };
      for (const m of data.models) {
        if (!next[m.name]) next[m.name] = 'pair-a';
      }
      return next;
    });
  }, []);

  useEffect(() => { loadVllm(); }, [loadVllm, refreshKey]);

  const handleLoad = async (modelName) => {
    const slot = loadTarget[modelName] || 'pair-a';
    setActivating(slot);
    try {
      await activateVllmModel(slot, modelName);
      await loadVllm();
    } catch (e) {
      console.error('Activate failed:', e);
    } finally {
      setActivating(null);
    }
  };

  const handleRestart = async (slot) => {
    const svc = SLOT_TO_SERVICE[slot];
    setRestarting(slot);
    try {
      await fetch(`/api/services/${svc}/stop`, { method: 'POST' });
      await new Promise(r => setTimeout(r, 1000));
      await fetch(`/api/services/${svc}/start`, { method: 'POST' });
    } catch (e) {
      console.error('Restart failed:', e);
    } finally {
      setRestarting(null);
    }
  };

  const handleRepoChange = (val) => {
    setDlRepo(val);
    if (!dlName || dlName === deriveLocalName(dlRepo)) {
      setDlName(deriveLocalName(val));
    }
  };

  return (
    <div className="vllm-section">
      <div className="vllm-section-header">vLLM Models</div>

      {/* Active Slots */}
      <div className="vllm-subsection-label">Active Slots</div>
      <table className="models-table">
        <thead>
          <tr>
            <th>Slot</th>
            <th>Active Model</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(SLOT_LABELS).map(([slot, label]) => {
            const active = vllmData.slots[slot];
            return (
              <tr key={slot}>
                <td className="model-name">{label}</td>
                <td>{active || <span className="empty-slot">—</span>}</td>
                <td>
                  {active && (
                    <button
                      className="action-btn restart-btn"
                      onClick={() => handleRestart(slot)}
                      disabled={restarting === slot}
                      title={`Restart ${SLOT_TO_SERVICE[slot]}`}
                    >
                      {restarting === slot ? 'Restarting…' : 'Restart Service'}
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* In /data/models/vllm: downloaded or registered */}
      <div className="vllm-subsection-label">Ready for vLLM</div>
      <table className="models-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Size</th>
            <th>Load to Slot</th>
          </tr>
        </thead>
        <tbody>
          {vllmData.models.length === 0 ? (
            <tr>
              <td colSpan="3" className="empty">
                No models yet. Download one, or register one from Local Models below.
              </td>
            </tr>
          ) : (
            vllmData.models.map((m) => (
              <tr key={m.name}>
                <td className="model-name">
                  {m.name}
                  {m.registered_from && (
                    <div className="model-path" title="Registered from disk, not copied">
                      → {m.registered_from}
                    </div>
                  )}
                </td>
                <td>{m.size_gb} GB</td>
                <td>
                  <div className="load-row">
                    <select
                      className="slot-select"
                      value={loadTarget[m.name] || 'pair-a'}
                      onChange={e => setLoadTarget(prev => ({ ...prev, [m.name]: e.target.value }))}
                    >
                      {Object.entries(SLOT_LABELS).map(([k, v]) => (
                        <option key={k} value={k}>{v}</option>
                      ))}
                    </select>
                    <Btn size="sm" disabled={activating !== null} onClick={() => handleLoad(m.name)}>
                      Load
                    </Btn>
                  </div>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* Download by exact repo id */}
      <div className="vllm-subsection-label">Download by repo id</div>
      <div className="dl-form">
        <div className="dl-field">
          <label>Repo ID</label>
          <input
            type="text"
            placeholder="e.g. Qwen/Qwen2.5-32B-Instruct"
            value={dlRepo}
            onChange={e => handleRepoChange(e.target.value)}
            disabled={dl.running}
          />
        </div>
        <div className="dl-field">
          <label>Save as</label>
          <input
            type="text"
            placeholder="e.g. qwen2.5-32b"
            value={dlName}
            onChange={e => setDlName(e.target.value)}
            disabled={dl.running}
          />
        </div>
        <Btn
          size="sm"
          disabled={!dlRepo.trim() || !dlName.trim() || dl.running}
          onClick={() => dl.start(dlRepo.trim(), dlName.trim())}
        >
          {dl.running ? 'Downloading…' : 'Download'}
        </Btn>
      </div>

      <DownloadStatus dl={dl} />
    </div>
  );
}

function LocalModelsSection({ refreshKey, onRegistered }) {
  const [data, setData]         = useState({ roots: [], models: [] });
  const [scanning, setScanning] = useState(false);
  const [error, setError]       = useState(null);
  const [names, setNames]       = useState({});      // { path: name to register as }
  const [busy, setBusy]         = useState(null);    // path being registered

  const scan = useCallback(async () => {
    setScanning(true);
    setError(null);
    try {
      setData(await getLocalModels());
    } catch (e) {
      setError(e.message);
    } finally {
      setScanning(false);
    }
  }, []);

  useEffect(() => { scan(); }, [scan, refreshKey]);

  const handleRegister = async (m) => {
    const name = (names[m.path] ?? m.name).trim();
    setBusy(m.path);
    setError(null);
    try {
      await registerLocalModel(m.path, name);
      await scan();
      onRegistered?.();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(null);
    }
  };

  const roots = data.roots?.length ? data.roots : ['/data/models', '/data/checkpoints'];

  return (
    <div className="vllm-section">
      <div className="local-header">
        <div className="vllm-section-header">Local Models</div>
        <Btn size="sm" onClick={scan} disabled={scanning}>
          {scanning ? 'Scanning…' : 'Rescan'}
        </Btn>
      </div>

      <div className="local-note">
        Models already on the workstation, including fine-tuned checkpoints. To add your
        own, copy the model folder onto the host (scp, rsync or a USB drive) under{' '}
        <code>{roots[0]}/&lt;name&gt;/</code> or <code>{roots[1]}/&lt;run&gt;/</code>,
        then press Rescan. A folder counts as a model when it holds{' '}
        <code>config.json</code> (Hugging Face format), <code>*.safetensors</code> or{' '}
        <code>*.gguf</code> files. Hugging Face format models can be registered for
        vLLM: the entry links to the folder, so nothing is copied or downloaded.
      </div>

      {error && <div className="error-message">{error}</div>}

      <table className="models-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Format</th>
            <th>Size</th>
            <th>Use with vLLM</th>
          </tr>
        </thead>
        <tbody>
          {data.models.length === 0 ? (
            <tr>
              <td colSpan="4" className="empty">
                {scanning ? 'Scanning…' : `No models found under ${roots.join(' or ')}`}
              </td>
            </tr>
          ) : (
            data.models.map((m) => (
              <tr key={m.path}>
                <td className="model-name">
                  {m.name}
                  <div className="model-path">{m.path}</div>
                </td>
                <td>{FORMAT_LABELS[m.format] || m.format}</td>
                <td>{m.size_gb} GB</td>
                <td>
                  {m.registered_as ? (
                    <span className="registered">Registered as {m.registered_as}</span>
                  ) : m.registerable ? (
                    <div className="load-row">
                      <input
                        className="register-name"
                        type="text"
                        value={names[m.path] ?? m.name}
                        onChange={e => setNames(prev => ({ ...prev, [m.path]: e.target.value }))}
                        disabled={busy !== null}
                        aria-label={`Name to register ${m.name} as`}
                      />
                      <Btn
                        size="sm"
                        disabled={busy !== null || !(names[m.path] ?? m.name).trim()}
                        onClick={() => handleRegister(m)}
                      >
                        {busy === m.path ? 'Registering…' : 'Register'}
                      </Btn>
                    </div>
                  ) : (
                    <span
                      className="empty-slot"
                      title="vLLM loads Hugging Face format (config.json) directories"
                    >
                      —
                    </span>
                  )}
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function HfBrowseSection({ dl, onOllamaPulled }) {
  const [query, setQuery]         = useState('');
  const [task, setTask]           = useState('text-generation');
  const [results, setResults]     = useState(null);
  const [searching, setSearching] = useState(false);
  const [error, setError]         = useState(null);
  const [note, setNote]           = useState(null);

  const canSearch = Boolean(query.trim() || task) && !searching;

  const handleSearch = async () => {
    if (!canSearch) return;
    setSearching(true);
    setError(null);
    setNote(null);
    try {
      const data = await searchHuggingFace(query.trim(), task);
      setResults(data.results || []);
    } catch (err) {
      setError(err.message);
      setResults(null);
    } finally {
      setSearching(false);
    }
  };

  const handleDownload = async (r) => {
    setNote(null);
    if (await dl.start(r.id, r.suggested_name || deriveLocalName(r.id).toLowerCase())) {
      setNote(`Downloading ${r.id} for vLLM. It appears under Installed → Ready for vLLM when done.`);
    }
  };

  const handleOllamaPull = async (r) => {
    setError(null);
    setNote(null);
    try {
      await pullModel(`hf.co/${r.id}`);
      setNote(`Ollama is pulling hf.co/${r.id} in the background.`);
      onOllamaPulled?.();
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <div className="models-section">
      <div className="vllm-section-header">Browse Hugging Face</div>
      <div className="hf-search">
        <input
          type="text"
          placeholder="Search by name, e.g. qwen coder, llama 70b, whisper"
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleSearch(); }}
          disabled={searching}
        />
        <select
          className="slot-select"
          value={task}
          onChange={e => setTask(e.target.value)}
          aria-label="Task"
        >
          {HF_TASKS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
        <Btn size="sm" disabled={!canSearch} onClick={handleSearch}>
          {searching ? 'Searching…' : 'Search'}
        </Btn>
      </div>

      {error && <div className="error-message">{error}</div>}
      {note && <div className="dl-status">{note}</div>}
      <DownloadStatus dl={dl} />

      {results && results.length === 0 && (
        <div className="hf-empty">No models matched that search.</div>
      )}

      {results && results.length > 0 && (
        <div className="hf-results">
          {results.map(r => (
            <div key={r.id} className="hf-result">
              <div className="hf-result-main">
                <a
                  className="hf-result-id"
                  href={`https://huggingface.co/${r.id}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {r.id}
                </a>
                <span className="hf-result-meta">
                  {r.pipeline_tag && <span className="hf-tag">{r.pipeline_tag}</span>}
                  {r.gguf && <span className="hf-tag">gguf</span>}
                  {r.gated && (
                    <span
                      className="hf-gated"
                      title="Accept the licence on huggingface.co and set HUGGINGFACE_TOKEN in Settings"
                    >
                      gated
                    </span>
                  )}
                  <span>{(r.downloads || 0).toLocaleString()} downloads</span>
                  <span>{(r.likes || 0).toLocaleString()} likes</span>
                  {formatDate(r.lastModified) && <span>updated {formatDate(r.lastModified)}</span>}
                </span>
              </div>
              <div className="hf-result-actions">
                {r.gguf ? (
                  <Btn size="sm" onClick={() => handleOllamaPull(r)} title={`ollama pull hf.co/${r.id}`}>
                    Pull to Ollama
                  </Btn>
                ) : (
                  <Btn
                    size="sm"
                    disabled={dl.running}
                    onClick={() => handleDownload(r)}
                    title={`Download into /data/models/vllm/${r.suggested_name}`}
                  >
                    Download for vLLM
                  </Btn>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function ModelsTab() {
  const [mode, setMode] = useState('installed');   // 'installed' | 'hf'
  const [refreshKey, setRefreshKey] = useState(0);
  const refresh = useCallback(() => setRefreshKey(k => k + 1), []);
  const dl = useVllmDownload(refresh);

  return (
    <div className="models-tab">
      <div className="models-mode" role="tablist">
        <button
          role="tab"
          aria-selected={mode === 'installed'}
          className={`models-mode-btn ${mode === 'installed' ? 'active' : ''}`}
          onClick={() => setMode('installed')}
        >
          Installed
        </button>
        <button
          role="tab"
          aria-selected={mode === 'hf'}
          className={`models-mode-btn ${mode === 'hf' ? 'active' : ''}`}
          onClick={() => setMode('hf')}
        >
          Browse Hugging Face
        </button>
      </div>

      {mode === 'installed' ? (
        <>
          <OllamaSection refreshKey={refreshKey} />
          <VllmModelsSection refreshKey={refreshKey} dl={dl} />
          <LocalModelsSection refreshKey={refreshKey} onRegistered={refresh} />
        </>
      ) : (
        <HfBrowseSection dl={dl} onOllamaPulled={refresh} />
      )}
    </div>
  );
}
