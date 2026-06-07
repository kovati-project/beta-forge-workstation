import { useState, useEffect } from 'react';
import {
  getBackupConfig,
  getBackupHistory,
  updateBackupSchedule,
  runBackupNow,
  deleteBackup,
} from '../utils/settingsAPI';
import './BackupsSection.css';

export function BackupsSection({ isAppliance }) {
  const [config, setConfig] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editingSchedule, setEditingSchedule] = useState(false);
  const [tempSchedule, setTempSchedule] = useState('');
  const [backingUp, setBackingUp] = useState(false);
  const [backupProgress, setBackupProgress] = useState('');
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadData = async () => {
      const cfg = await getBackupConfig();
      const hist = await getBackupHistory();
      setConfig(cfg);
      setHistory(hist.backups || []);
      setTempSchedule(cfg.schedule || '0 6 * * *');
      setLoading(false);
    };
    loadData();
  }, []);

  const handleEditSchedule = () => {
    setEditingSchedule(true);
  };

  const handleSaveSchedule = async () => {
    try {
      await updateBackupSchedule(tempSchedule);
      setConfig((prev) => ({ ...prev, schedule: tempSchedule }));
      setEditingSchedule(false);
      setError(null);
    } catch (err) {
      setError(`Failed to update schedule: ${err.message}`);
    }
  };

  const handleCancelSchedule = () => {
    setEditingSchedule(false);
  };

  const handleRunBackup = async () => {
    if (!window.confirm('Run backup now?')) return;

    setBackingUp(true);
    setBackupProgress('Starting backup...');
    setError(null);

    try {
      const response = await runBackupNow();
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        setBackupProgress((prev) => prev + '\n' + chunk);
      }

      // Reload history
      const hist = await getBackupHistory();
      setHistory(hist.backups || []);
    } catch (err) {
      setError(`Backup failed: ${err.message}`);
    } finally {
      setBackingUp(false);
    }
  };

  const handleDeleteBackup = async (backupId) => {
    if (!window.confirm('Delete this backup?')) return;

    try {
      await deleteBackup(backupId);
      const hist = await getBackupHistory();
      setHistory(hist.backups || []);
    } catch (err) {
      setError(`Failed to delete backup: ${err.message}`);
    }
  };

  if (loading) {
    return <div className="backups-section loading">Loading backup config...</div>;
  }

  if (!config) {
    return <div className="backups-section empty">No backup config</div>;
  }

  return (
    <div className="backups-section">
      {error && <div className="error-banner">{error}</div>}

      <div className="config-display">
        <div className="config-row">
          <span className="label">Last backup:</span>
          <span className="value">
            {config.last_backup ? (
              <>
                {config.last_backup.date} · {config.last_backup.size} ·{' '}
                {config.last_backup.status === 'success' ? (
                  <span className="status-ok">✓ success</span>
                ) : (
                  <span className="status-fail">✗ {config.last_backup.status}</span>
                )}
              </>
            ) : (
              'Never'
            )}
          </span>
        </div>

        <div className="config-row">
          <span className="label">Schedule:</span>
          {editingSchedule ? (
            <div className="schedule-edit">
              <input
                type="text"
                value={tempSchedule}
                onChange={(e) => setTempSchedule(e.target.value)}
                className="schedule-input"
                placeholder="0 6 * * *"
              />
              <button className="save-btn" onClick={handleSaveSchedule}>
                Save
              </button>
              <button className="cancel-btn" onClick={handleCancelSchedule}>
                Cancel
              </button>
            </div>
          ) : (
            <div className="schedule-view">
              <code>{config.schedule}</code>
              {!isAppliance && (
                <button className="edit-btn" onClick={handleEditSchedule}>
                  Edit Schedule
                </button>
              )}
            </div>
          )}
        </div>

        <div className="config-row">
          <span className="label">Destination:</span>
          <span className="value">
            {config.destination}{' '}
            <a href="#" className="browse-link">
              [Browse ↗]
            </a>
          </span>
        </div>
      </div>

      {!isAppliance && (
        <button
          className="run-backup-btn"
          onClick={handleRunBackup}
          disabled={backingUp}
        >
          {backingUp ? '⟳ Backup running...' : 'Run Backup Now'}
        </button>
      )}

      {backingUp && (
        <div className="backup-progress">
          <pre>{backupProgress}</pre>
        </div>
      )}

      <div className="history-section">
        <h3>History (Last 10)</h3>
        <table className="history-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Size</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {history.length === 0 ? (
              <tr>
                <td colSpan="4" className="empty">
                  No backups yet
                </td>
              </tr>
            ) : (
              history.map((backup) => (
                <tr key={backup.id} className={backup.status === 'fail' ? 'fail' : ''}>
                  <td className="date">{backup.date}</td>
                  <td className="size">{backup.size}</td>
                  <td className={`status status-${backup.status}`}>
                    {backup.status === 'success' ? '✓ ok' : `✗ ${backup.status}`}
                  </td>
                  <td className="actions">
                    <button
                      className="delete-btn"
                      onClick={() => handleDeleteBackup(backup.id)}
                    >
                      Delete
                    </button>
                    {backup.status === 'fail' && (
                      <button className="retry-btn">Retry</button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
