import { useState, useEffect } from 'react';
import { getModels, deleteModel, pullModel } from '../utils/resourcesAPI';
import { Btn } from './Btn';
import './ModelsTab.css';

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
    </div>
  );
}
