import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getStorageSummary, getBackupHistory, runBackupNow } from '../utils/resourcesAPI';
import { VBar } from './VBar';
import { Btn } from './Btn';
import { StorageDetail } from './StorageDetail';
import './StorageTab.css';

const TYPE_LABELS = {
  minio: 'MinIO',
  qdrant: 'Qdrant',
  postgres: 'PostgreSQL',
  filesystem: 'Filesystem',
};

function TypeBadge({ type }) {
  return <span className={`type-badge type-badge--${type}`}>{TYPE_LABELS[type] ?? type}</span>;
}

function PartitionCard({ partition }) {
  const color = partition.percent > 90 ? 'red' : partition.percent > 70 ? 'amber' : 'cyan';
  const device = partition.device.replace('/dev/', '');
  return (
    <div className="partition-card">
      <div className="partition-card__meta">
        <span className="partition-card__device">{device}</span>
        <span className="partition-card__mount">{partition.mountpoint}</span>
        <span className="partition-card__fs">{partition.fstype}</span>
      </div>
      <div className="partition-card__bar">
        <VBar value={partition.percent} label={`${partition.percent}%`} variant={color} />
      </div>
      <div className="partition-card__stats">
        <span><span className="stat-label">Total</span> {partition.total_human}</span>
        <span><span className="stat-label">Used</span> {partition.used_human}</span>
        <span><span className="stat-label">Free</span> {partition.free_human}</span>
      </div>
    </div>
  );
}

function CollectionTable({ type, columns, rows, onSelect }) {
  if (!rows || rows.length === 0) {
    return (
      <div className="collection-empty">No {TYPE_LABELS[type]} collections found</div>
    );
  }
  return (
    <table className="collection-table">
      <thead>
        <tr>
          {columns.map((c) => (
            <th key={c.key}>{c.label}</th>
          ))}
          <th className="col-arrow" />
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr
            key={row.name}
            className="collection-row"
            onClick={() => onSelect(type, row.name)}
          >
            {columns.map((c) => (
              <td key={c.key}>{c.render ? c.render(row) : (row[c.key] ?? '—')}</td>
            ))}
            <td className="col-arrow">›</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function BackupSection({ storage, backups, backingUp, onRunBackup }) {
  return (
    <>
      <section className="storage-section">
        <h3>Backup Management</h3>
        <div className="backup-info">
          <div className="backup-row">
            <div className="label">Schedule:</div>
            <div className="value">
              <input
                type="text"
                defaultValue={storage?.backup_schedule ?? '0 6 * * *'}
                className="schedule-input"
              />
            </div>
          </div>
        </div>
        <Btn
          label={backingUp ? 'Running…' : 'Run Backup Now'}
          onClick={onRunBackup}
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
            </tr>
          </thead>
          <tbody>
            {backups.length === 0 ? (
              <tr>
                <td colSpan="3" className="empty">No backups</td>
              </tr>
            ) : (
              backups.map((backup, idx) => (
                <tr key={idx}>
                  <td>{backup.date}</td>
                  <td>{backup.size || backup.size_human || '—'}</td>
                  <td className={backup.status === 'success' || backup.success ? 'success' : 'failed'}>
                    {backup.status === 'success' || backup.success ? '✓ success' : '✗ failed'}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </section>
    </>
  );
}

export function StorageTab() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(true);
  const [backingUp, setBackingUp] = useState(false);

  const detailParam = searchParams.get('detail');
  let detailType = null;
  let detailName = null;
  if (detailParam) {
    const sep = detailParam.indexOf(':');
    detailType = detailParam.slice(0, sep);
    detailName = detailParam.slice(sep + 1);
  }

  useEffect(() => {
    loadAll();
  }, []);

  const loadAll = async () => {
    setLoading(true);
    const [summary, history] = await Promise.all([getStorageSummary(), getBackupHistory()]);
    setData(summary);
    setBackups(history?.backups ?? []);
    setLoading(false);
  };

  const handleSelect = (type, name) => {
    setSearchParams({ tab: 'storage', detail: `${type}:${name}` });
  };

  const handleBack = () => {
    setSearchParams({ tab: 'storage' });
  };

  const handleRunBackup = async () => {
    setBackingUp(true);
    try {
      await runBackupNow();
      await loadAll();
    } catch (error) {
      alert(`Backup failed: ${error.message}`);
    } finally {
      setBackingUp(false);
    }
  };

  if (detailType && detailName) {
    return (
      <StorageDetail
        type={detailType}
        name={detailName}
        onBack={handleBack}
      />
    );
  }

  if (loading) {
    return <div className="storage-tab"><div className="loading">Loading storage data…</div></div>;
  }

  const collections = data?.collections ?? {};
  const partitions = data?.partitions ?? [];

  const minioColumns = [
    { key: 'name', label: 'Bucket' },
    { key: 'object_count', label: 'Objects' },
    { key: 'size_human', label: 'Size' },
    { key: 'mountpoint', label: 'Mount' },
  ];

  const qdrantColumns = [
    { key: 'name', label: 'Collection' },
    { key: 'points_count', label: 'Points' },
    { key: 'size_human', label: 'Size' },
    { key: 'mountpoint', label: 'Mount' },
  ];

  const postgresColumns = [
    { key: 'name', label: 'Database' },
    { key: 'size_human', label: 'Size' },
    { key: 'mountpoint', label: 'Mount' },
  ];

  const filesystemColumns = [
    { key: 'name', label: 'Directory' },
    { key: 'path', label: 'Path' },
    { key: 'size_human', label: 'Size' },
    { key: 'mountpoint', label: 'Mount' },
  ];

  return (
    <div className="storage-tab">
      <section className="storage-section">
        <h3>Hardware / Partitions</h3>
        {partitions.length === 0 ? (
          <div className="collection-empty">No partition data available</div>
        ) : (
          <div className="partitions-list">
            {partitions.map((p) => (
              <PartitionCard key={p.mountpoint} partition={p} />
            ))}
          </div>
        )}
      </section>

      <section className="storage-section">
        <h3>
          <TypeBadge type="minio" /> Buckets
        </h3>
        <CollectionTable
          type="minio"
          columns={minioColumns}
          rows={collections.minio}
          onSelect={handleSelect}
        />
      </section>

      <section className="storage-section">
        <h3>
          <TypeBadge type="qdrant" /> Collections
        </h3>
        <CollectionTable
          type="qdrant"
          columns={qdrantColumns}
          rows={collections.qdrant}
          onSelect={handleSelect}
        />
      </section>

      <section className="storage-section">
        <h3>
          <TypeBadge type="postgres" /> Databases
        </h3>
        <CollectionTable
          type="postgres"
          columns={postgresColumns}
          rows={collections.postgres}
          onSelect={handleSelect}
        />
      </section>

      <section className="storage-section">
        <h3>
          <TypeBadge type="filesystem" /> Directories
        </h3>
        <CollectionTable
          type="filesystem"
          columns={filesystemColumns}
          rows={collections.filesystem}
          onSelect={handleSelect}
        />
      </section>

      <BackupSection
        storage={data}
        backups={backups}
        backingUp={backingUp}
        onRunBackup={handleRunBackup}
      />
    </div>
  );
}
