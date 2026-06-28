import { useState, useEffect } from 'react';
import { getConfig, updateConfig } from '../utils/settingsAPI';
import './ConfigSection.css';

export function ConfigSection({ isAppliance }) {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState('');
  const [showValue, setShowValue] = useState(false);
  const [saving, setSaving] = useState(null);
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(null);

  useEffect(() => {
    loadConfig();
  }, []);

  async function loadConfig() {
    setLoading(true);
    const data = await getConfig();
    setEntries(data.config || []);
    setLoading(false);
  }

  function startEdit(entry) {
    setEditing(entry.key);
    setDraft(entry.sensitive ? '' : entry.current_value);
    setShowValue(false);
    setError(null);
  }

  function cancelEdit() {
    setEditing(null);
    setDraft('');
    setShowValue(false);
  }

  async function handleSave(key) {
    setSaving(key);
    setError(null);
    try {
      await updateConfig(key, draft);
      setSaved(key);
      setTimeout(() => setSaved(null), 2000);
      setEditing(null);
      setDraft('');
      // Refresh to update value_set indicator
      const data = await getConfig();
      setEntries(data.config || []);
    } catch (err) {
      setError(`Failed to save ${key}: ${err.message}`);
    } finally {
      setSaving(null);
    }
  }

  if (isAppliance) {
    return (
      <div className="config-section appliance">
        <p>Configuration managed by administrator. Contact your administrator to update settings.</p>
      </div>
    );
  }

  if (loading) {
    return <div className="config-section loading">Loading configuration...</div>;
  }

  // Group entries by category
  const grouped = entries.reduce((acc, entry) => {
    if (!acc[entry.category]) acc[entry.category] = [];
    acc[entry.category].push(entry);
    return acc;
  }, {});

  return (
    <div className="config-section">
      {error && <div className="error-banner">{error}</div>}

      {Object.entries(grouped).map(([category, items]) => (
        <div key={category} className="config-category">
          <h4 className="config-category-title">{category}</h4>
          <table className="config-table">
            <thead>
              <tr>
                <th>Key</th>
                <th>Description</th>
                <th>Value</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {items.map((entry) => {
                const isEditing = editing === entry.key;
                const isSaving = saving === entry.key;
                const wasSaved = saved === entry.key;

                return (
                  <tr key={entry.key} className={isEditing ? 'config-row editing' : 'config-row'}>
                    <td className="config-key">{entry.key}</td>
                    <td className="config-desc">{entry.description}</td>
                    <td className="config-value">
                      {isEditing ? (
                        <div className="config-edit-row">
                          {entry.affects?.length > 0 && (
                            <div className="restart-notice">
                              Saving will restart: {entry.affects.join(', ')}
                            </div>
                          )}
                          <div className="config-input-row">
                            <input
                              className="config-input"
                              type={entry.sensitive && !showValue ? 'password' : 'text'}
                              value={draft}
                              onChange={(e) => setDraft(e.target.value)}
                              placeholder={entry.sensitive ? 'Enter new value...' : 'Enter value...'}
                              autoFocus
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') handleSave(entry.key);
                                if (e.key === 'Escape') cancelEdit();
                              }}
                            />
                            {entry.sensitive && (
                              <button
                                className="toggle-vis-btn"
                                type="button"
                                onClick={() => setShowValue((v) => !v)}
                                title={showValue ? 'Hide' : 'Show'}
                              >
                                {showValue ? '🙈' : '👁'}
                              </button>
                            )}
                          </div>
                        </div>
                      ) : (
                        <span className={entry.value_set ? 'value-set' : 'value-unset'}>
                          {entry.sensitive
                            ? (entry.value_set ? '••••••' : 'not set')
                            : (entry.current_value || 'not set')}
                        </span>
                      )}
                    </td>
                    <td className="config-actions">
                      {isEditing ? (
                        <>
                          <button
                            className="save-btn"
                            onClick={() => handleSave(entry.key)}
                            disabled={isSaving}
                          >
                            {isSaving ? 'Saving...' : 'Save'}
                          </button>
                          <button
                            className="cancel-btn"
                            onClick={cancelEdit}
                            disabled={isSaving}
                          >
                            Cancel
                          </button>
                        </>
                      ) : (
                        <button
                          className="edit-btn"
                          onClick={() => startEdit(entry)}
                          disabled={editing !== null}
                          title="Edit value"
                        >
                          {wasSaved ? 'Saved' : 'Edit'}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ))}
    </div>
  );
}
