import { useState, useEffect } from 'react';
import { getAPIKeys, createAPIKey, revokeAPIKey } from '../utils/exposeAPI';
import { Btn } from './Btn';
import './APIKeysSection.css';

const SCOPES = [
  { id: 'all-inference', label: 'All Inference' },
  { id: 'vllm-pair-a', label: 'vLLM Pair A' },
  { id: 'ollama', label: 'Ollama' },
  { id: 'vllm-4gpu', label: 'vLLM 4-GPU' },
];

export function APIKeysSection() {
  const [keys, setKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [newKeyScope, setNewKeyScope] = useState('all-inference');
  const [generatedToken, setGeneratedToken] = useState(null);
  const [copied, setCopied] = useState(false);
  const [creating, setCreating] = useState(false);
  const [revoking, setRevoking] = useState(null);

  useEffect(() => {
    loadKeys();
  }, []);

  const loadKeys = async () => {
    setLoading(true);
    const data = await getAPIKeys();
    setKeys(data.keys || []);
    setLoading(false);
  };

  const handleCreateKey = async () => {
    if (!newKeyName.trim()) return;

    setCreating(true);
    try {
      const result = await createAPIKey(newKeyName, newKeyScope);
      setGeneratedToken(result.token);
      setNewKeyName('');
      setNewKeyScope('all-inference');
      await loadKeys();
    } catch (error) {
      alert(`Failed to create key: ${error.message}`);
    } finally {
      setCreating(false);
    }
  };

  const handleCopyToken = async () => {
    try {
      await navigator.clipboard.writeText(generatedToken);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };

  const handleRevokeKey = async (name) => {
    if (!confirm(`Revoke API key "${name}"?`)) return;

    setRevoking(name);
    try {
      await revokeAPIKey(name);
      await loadKeys();
    } catch (error) {
      alert(`Failed to revoke key: ${error.message}`);
    } finally {
      setRevoking(null);
    }
  };

  return (
    <div className="api-keys-section">
      <div className="section-header">
        <h3>API Keys</h3>
        <Btn
          label="+ Create New Key"
          onClick={() => setShowModal(true)}
          size="sm"
          variant="amber"
        />
      </div>

      {loading ? (
        <div className="loading">Loading API keys...</div>
      ) : (
        <table className="keys-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Scope</th>
              <th>Created</th>
              <th>Last Used</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {keys.length === 0 ? (
              <tr>
                <td colSpan="5" className="empty">
                  No API keys created
                </td>
              </tr>
            ) : (
              keys.map((key) => (
                <tr key={key.name}>
                  <td className="key-name">{key.name}</td>
                  <td>{key.scope}</td>
                  <td>{key.created}</td>
                  <td>{key.last_used || '—'}</td>
                  <td>
                    <button
                      className="revoke-btn"
                      onClick={() => handleRevokeKey(key.name)}
                      disabled={revoking === key.name}
                      title="Revoke key"
                    >
                      Revoke
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      )}

      {showModal && (
        <div className="modal-overlay" onClick={() => setShowModal(false)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <h2>Create New API Key</h2>

            <div className="form-group">
              <label>Key Name</label>
              <input
                type="text"
                placeholder="e.g., laptop-kasemo"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                disabled={creating}
              />
            </div>

            <div className="form-group">
              <label>Scope</label>
              <select
                value={newKeyScope}
                onChange={(e) => setNewKeyScope(e.target.value)}
                disabled={creating}
              >
                {SCOPES.map((scope) => (
                  <option key={scope.id} value={scope.id}>
                    {scope.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="modal-buttons">
              <button
                className="btn-cancel"
                onClick={() => setShowModal(false)}
                disabled={creating}
              >
                Cancel
              </button>
              <Btn
                label="Generate Key"
                onClick={handleCreateKey}
                disabled={creating || !newKeyName.trim()}
              />
            </div>
          </div>
        </div>
      )}

      {generatedToken && (
        <div className="modal-overlay" onClick={() => setGeneratedToken(null)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <h2>⚠ Save Your Token</h2>
            <p className="warning-text">Copy this token now — it will not be shown again.</p>

            <div className="token-display">{generatedToken}</div>

            <div className="modal-buttons">
              <Btn
                label={copied ? '✓ Copied' : 'Copy Token'}
                onClick={handleCopyToken}
                variant="amber"
              />
              <button
                className="btn-close"
                onClick={() => setGeneratedToken(null)}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
