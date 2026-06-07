import { useState, useEffect } from 'react';
import { getStorageSummary, getBackupHistory, runBackupNow } from '../utils/resourcesAPI';
import { VBar } from './VBar';
import { Btn } from './Btn';
import './StorageTab.css';

export function StorageTab() {
  const [storage, setStorage] = useState(null);
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [backingUp, setBackingUp] = useState(false);

  useEffect(() => {
    loadStorageData();
  }, []);

  const loadStorageData = async () => {
    setLoading(true);
    const [summary, history] = await Promise.all([
      getStorageSummary(),
      getBackupHistory(),
    ]);
    setStorage(summary);
    setBackups(history.backups || []);
    setLoading(false);
  };

  const handleRunBackup = async () => {
    setBackingUp(true);
    try {
      await runBackupNow();
      await loadStorageData();
    } catch (error) {
      alert(`Backup failed: ${error.message}`);
    } finally {
      setBackingUp(false);
    }
  };

  if (loading) {
    return <div className="storage-tab"><div className="loading">Loading storage data...</div></div>;
  }

  if (!storage) {
    return <div className="storage-tab"><div className="loading">No storage data available</div></div>;
  }

  const diskPercent = (storage.disk_used / storage.disk_total) * 100;
  const diskColor = diskPercent > 90 ? 'red' : diskPercent > 70 ? 'amber' : 'cyan';

  return (
    <div className="storage-tab">
      <section className="storage-section">
        <h3>Disk Usage</h3>
        <div className="disk-info">
          <div className="disk-label">
            /data/ partition — {storage.disk_used_human} / {storage.disk_total_human}
          </div>
          <VBar
            value={diskPercent}
            label={`${diskPercent.toFixed(0)}%`}
            variant={diskColor}
          />
        </div>
      </section>

      <section className="storage-section">
        <h3>MinIO Buckets</h3>
        <div className="buckets-chart">
          <div className="stacked-bar">
            {storage.buckets?.map((bucket) => {
              const width = (bucket.size_bytes / storage.total_minio_bytes) * 100;
              return (
                <div
                  key={bucket.name}
                  className="bucket-bar"
                  style={{
                    width: `${width}%`,
                    backgroundColor: `var(--${bucket.color})`,
                  }}
                  title={`${bucket.name}: ${bucket.size_human}`}
                />
              );
            })}
          </div>
        </div>
        <div className="buckets-table">
          <div className="table-header">
            <div>Bucket</div>
            <div>Used</div>
            <div>Percent</div>
          </div>
          {storage.buckets?.map((bucket) => {
            const percent = (bucket.size_bytes / storage.total_minio_bytes) * 100;
            return (
              <div key={bucket.name} className="table-row">
                <div className="bucket-name">
                  <span
                    className="bucket-indicator"
                    style={{ backgroundColor: `var(--${bucket.color})` }}
                  />
                  {bucket.name}
                </div>
                <div>{bucket.size_human}</div>
                <div>{percent.toFixed(1)}%</div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="storage-section">
        <h3>PostgreSQL Databases</h3>
        <table className="pg-table">
          <thead>
            <tr>
              <th>Database</th>
              <th>Size</th>
            </tr>
          </thead>
          <tbody>
            {storage.databases?.map((db) => (
              <tr key={db.name}>
                <td>{db.name}</td>
                <td>{db.size_human}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="storage-section">
        <h3>Backup Management</h3>
        <div className="backup-info">
          <div className="backup-row">
            <div className="label">Last backup:</div>
            <div className="value">
              {storage.last_backup ? (
                <>
                  <span>{storage.last_backup.time}</span>
                  <span>{storage.last_backup.size_human}</span>
                  <span className={storage.last_backup.success ? 'success' : 'failed'}>
                    {storage.last_backup.success ? '✓ success' : '✗ failed'}
                  </span>
                </>
              ) : (
                'Never'
              )}
            </div>
          </div>
          <div className="backup-row">
            <div className="label">Schedule:</div>
            <div className="value">
              <input type="text" defaultValue={storage.backup_schedule} className="schedule-input" />
            </div>
          </div>
        </div>
        <Btn
          label="Run Backup Now"
          onClick={handleRunBackup}
          disabled={backingUp}
          variant="amber"
        />
      </section>

      <section className="storage-section">
        <h3>Backup History</h3>
        <table className="backups-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Size</th>
              <th>Status</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {backups.length === 0 ? (
              <tr>
                <td colSpan="4" className="empty">
                  No backups
                </td>
              </tr>
            ) : (
              backups.map((backup, idx) => (
                <tr key={idx}>
                  <td>{backup.date}</td>
                  <td>{backup.size_human}</td>
                  <td className={backup.success ? 'success' : 'failed'}>
                    {backup.success ? '✓ success' : '✗ failed'}
                  </td>
                  <td>
                    <button className="delete-btn" title="Delete backup">
                      ✕
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </div>
  );
}
