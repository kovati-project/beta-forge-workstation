import { useState, useEffect, useRef } from 'react';
import {
  getModels, deleteModel, pullModel,
  getVllmLocalModels, activateVllmModel, downloadVllmModel, getVllmDownloadStatus,
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

function VllmModelsSection() {
  const [vllmData, setVllmData]       = useState({ models: [], slots: {} });
  const [loadTarget, setLoadTarget]   = useState({});     // { modelName: slotKey }
  const [activating, setActivating]   = useState(null);   // slotKey being set
  const [restarting, setRestarting]   = useState(null);   // slotKey being restarted
  const [dlRepo, setDlRepo]           = useState('');
  const [dlName, setDlName]           = useState('');
  const [dlStatus, setDlStatus]       = useState({});
  const [dlError, setDlError]         = useState(null);
  const pollRef = useRef(null);

  const loadVllm = async () => {
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
  };

  useEffect(() => {
    loadVllm();
  }, []);

  // Poll download status while running
  useEffect(() => {
    if (dlStatus?.status === 'running') {
      pollRef.current = setInterval(async () => {
        const s = await getVllmDownloadStatus();
        setDlStatus(s);
        if (s.status === 'done') {
          clearInterval(pollRef.current);
          loadVllm();
        } else if (s.status === 'error') {
          clearInterval(pollRef.current);
        }
      }, 3000);
    }
    return () => clearInterval(pollRef.current);
  }, [dlStatus?.status]);

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

  const handleDownload = async () => {
    setDlError(null);
    try {
      await downloadVllmModel(dlRepo.trim(), dlName.trim());
      setDlStatus({ status: 'running', repo_id: dlRepo.trim(), local_name: dlName.trim() });
    } catch (e) {
      setDlError(e.message);
    }
  };

  const handleRepoChange = (val) => {
    setDlRepo(val);
    if (!dlName || dlName === deriveLocalName(dlRepo)) {
      setDlName(deriveLocalName(val));
    }
  };

  const deriveLocalName = (repoId) => repoId.includes('/') ? repoId.split('/').pop() : repoId;

  const dlRunning = dlStatus?.status === 'running';

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

      {/* Available on Disk */}
      <div className="vllm-subsection-label">Available on Disk</div>
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
              <td colSpan="3" className="empty">No models downloaded yet</td>
            </tr>
          ) : (
            vllmData.models.map((m) => (
              <tr key={m.name}>
                <td className="model-name">{m.name}</td>
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
                    <Btn
                      label="Load"
                      size="sm"
                      disabled={activating !== null}
                      onClick={() => handleLoad(m.name)}
                    />
                  </div>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {/* Download from HuggingFace */}
      <div className="vllm-subsection-label">Download from HuggingFace</div>
      <div className="dl-form">
        <div className="dl-field">
          <label>Repo ID</label>
          <input
            type="text"
            placeholder="e.g. Qwen/Qwen2.5-32B-Instruct"
            value={dlRepo}
            onChange={e => handleRepoChange(e.target.value)}
            disabled={dlRunning}
          />
        </div>
        <div className="dl-field">
          <label>Save as</label>
          <input
            type="text"
            placeholder="e.g. qwen2.5-32b"
            value={dlName}
            onChange={e => setDlName(e.target.value)}
            disabled={dlRunning}
          />
        </div>
        <Btn
          label={dlRunning ? 'Downloading…' : 'Download'}
          size="sm"
          disabled={!dlRepo.trim() || !dlName.trim() || dlRunning}
          onClick={handleDownload}
        />
      </div>

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
    </div>
  );
}

export function ModelsTab() {
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [pullInput, setPullInput] = useState('');
  const [pulling, setPulling] = useState(false);
  const [pullError, setPullError] = useState(null);

  useEffect(() => {
    loadModels();
  }, []);

  const loadModels = async () => {
    setLoading(true);
    const data = await getModels();
    setModels(data.ollama || []);
    setLoading(false);
  };

  const handlePull = async () => {
    if (!pullInput.trim()) return;

    setPulling(true);
    setPullError(null);
    try {
      await pullModel(pullInput);
      setPullInput('');
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
    <div className="models-tab">
      <div className="pull-section">
        <div className="pull-input-group">
          <input
            type="text"
            placeholder="e.g., qwen2.5-32b"
            value={pullInput}
            onChange={(e) => setPullInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handlePull()}
            disabled={pulling}
          />
          <Btn
            label="Pull"
            onClick={handlePull}
            disabled={!pullInput.trim() || pulling}
            size="sm"
          />
        </div>
        {pullError && <div className="error-message">{pullError}</div>}
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
              <th>Last Used</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {models.length === 0 ? (
              <tr>
                <td colSpan="5" className="empty">
                  No models available
                </td>
              </tr>
            ) : (
              models.map((model) => (
                <tr key={model.name}>
                  <td className="model-name">{model.name}</td>
                  <td>{model.size}</td>
                  <td>{model.quantization || '—'}</td>
                  <td>{model.last_used || '—'}</td>
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

      <VllmModelsSection />
    </div>
  );
}
