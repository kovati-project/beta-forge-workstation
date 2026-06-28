import { useState, useEffect } from 'react';
import { getStorageDetail } from '../utils/resourcesAPI';
import { VBar } from './VBar';
import './StorageDetail.css';

const TYPE_LABELS = {
  minio: 'MinIO',
  qdrant: 'Qdrant',
  postgres: 'PostgreSQL',
  filesystem: 'Filesystem',
};

function HardwareCard({ hardware }) {
  if (!hardware) return null;
  const color = hardware.percent > 90 ? 'red' : hardware.percent > 70 ? 'amber' : 'cyan';
  const device = hardware.device?.replace('/dev/', '') || '—';
  return (
    <div className="detail-hardware-card">
      <div className="detail-hardware-card__header">Hardware</div>
      <div className="detail-hardware-card__grid">
        <div className="hw-field">
          <span className="hw-label">Device</span>
          <span className="hw-value hw-value--mono">{device}</span>
        </div>
        <div className="hw-field">
          <span className="hw-label">Mount</span>
          <span className="hw-value hw-value--mono hw-value--cyan">{hardware.mountpoint}</span>
        </div>
        <div className="hw-field">
          <span className="hw-label">Filesystem</span>
          <span className="hw-value">{hardware.fstype}</span>
        </div>
        <div className="hw-field">
          <span className="hw-label">Total</span>
          <span className="hw-value">{hardware.total_human}</span>
        </div>
        <div className="hw-field">
          <span className="hw-label">Used</span>
          <span className="hw-value">{hardware.used_human}</span>
        </div>
        <div className="hw-field">
          <span className="hw-label">Free</span>
          <span className="hw-value hw-value--free">{hardware.free_human}</span>
        </div>
      </div>
      {hardware.percent > 0 && (
        <div className="detail-hardware-card__bar">
          <VBar value={hardware.percent} label={`${hardware.percent}% used`} variant={color} />
        </div>
      )}
    </div>
  );
}

function MetaCard({ type, name, meta }) {
  if (!meta) return null;

  const rows = [];

  if (type === 'minio') {
    rows.push(['Objects', meta.object_count ?? '—']);
  }

  if (type === 'qdrant') {
    rows.push(['Status', meta.status ?? '—']);
    rows.push(['Points', (meta.points_count ?? 0).toLocaleString()]);
    rows.push(['Segments', meta.segments_count ?? '—']);
    if (meta.vectors_config) {
      const cfg = meta.vectors_config;
      const size = typeof cfg === 'object' && cfg.size ? cfg.size : '—';
      const dist = typeof cfg === 'object' && cfg.distance ? cfg.distance : (meta.distance ?? '—');
      rows.push(['Vector size', size]);
      rows.push(['Distance', dist]);
    }
    if (meta.on_disk_payload !== null && meta.on_disk_payload !== undefined) {
      rows.push(['On-disk payload', meta.on_disk_payload ? 'Yes' : 'No']);
    }
  }

  if (type === 'postgres') {
    rows.push(['Tables', meta.table_count ?? '—']);
  }

  if (type === 'filesystem') {
    rows.push(['Path', meta.path ?? '—']);
    rows.push(['Items', meta.item_count ?? '—']);
  }

  if (rows.length === 0) return null;

  return (
    <div className="detail-meta-card">
      <div className="detail-meta-card__header">Collection Info</div>
      <table className="detail-meta-table">
        <tbody>
          {rows.map(([label, value]) => (
            <tr key={label}>
              <td className="meta-label">{label}</td>
              <td className="meta-value">{value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ItemsTable({ type, items }) {
  if (!items || items.length === 0) {
    return (
      <div className="detail-empty">
        {type === 'qdrant' ? 'No item listing available for vector collections.' : 'No items found.'}
      </div>
    );
  }

  const columns = {
    minio: [
      { key: 'name', label: 'Object' },
      { key: 'size_human', label: 'Size' },
      { key: 'last_modified', label: 'Modified', render: (r) => r.last_modified ? new Date(r.last_modified).toLocaleDateString() : '—' },
    ],
    postgres: [
      { key: 'name', label: 'Table' },
      { key: 'size_human', label: 'Size' },
    ],
    filesystem: [
      { key: 'name', label: 'Name', render: (r) => <span className={r.is_dir ? 'item-dir' : ''}>{r.is_dir ? '📁 ' : ''}{r.name}</span> },
      { key: 'size_human', label: 'Size' },
      { key: 'modified', label: 'Modified', render: (r) => r.modified ? new Date(r.modified).toLocaleDateString() : '—' },
    ],
  }[type] ?? [{ key: 'name', label: 'Name' }];

  return (
    <table className="detail-items-table">
      <thead>
        <tr>
          {columns.map((c) => <th key={c.key}>{c.label}</th>)}
        </tr>
      </thead>
      <tbody>
        {items.map((item, idx) => (
          <tr key={idx}>
            {columns.map((c) => (
              <td key={c.key}>{c.render ? c.render(item) : (item[c.key] ?? '—')}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function StorageDetail({ type, name, onBack }) {
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getStorageDetail(type, name)
      .then((d) => {
        if (d) setDetail(d);
        else setError('No data returned from server.');
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [type, name]);

  return (
    <div className="storage-detail">
      <div className="detail-nav">
        <button className="detail-back" onClick={onBack}>
          ← Storage
        </button>
        <div className="detail-title">
          <span className={`type-badge type-badge--${type}`}>{TYPE_LABELS[type] ?? type}</span>
          <span className="detail-name">{name}</span>
        </div>
      </div>

      {loading && <div className="detail-loading">Loading…</div>}

      {error && <div className="detail-error">{error}</div>}

      {!loading && detail && (
        <div className="detail-body">
          <div className="detail-cards-row">
            <HardwareCard hardware={detail.hardware} />
            <MetaCard type={type} name={name} meta={detail.meta} />
          </div>

          <div className="detail-section">
            <div className="detail-section__header">
              {type === 'qdrant' ? 'Vector Collection Details' : 'Contents'}
            </div>
            <ItemsTable type={type} items={detail.items} />
          </div>
        </div>
      )}
    </div>
  );
}
