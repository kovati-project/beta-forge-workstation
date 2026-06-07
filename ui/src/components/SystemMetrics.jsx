import { useSystemMetrics } from '../hooks/useSystemMetrics';
import './SystemMetrics.css';

function MetricCard({ value, label, color = '--text' }) {
  return (
    <div className="metric-card">
      <div className="metric-card-value" style={{ color: `var(${color})` }}>
        {value}
      </div>
      <div className="metric-card-label">{label}</div>
    </div>
  );
}

export function SystemMetrics() {
  const { metrics, error } = useSystemMetrics();

  if (error) {
    return (
      <div className="system-metrics">
        <div className="error-state">⚠ API unreachable — retrying…</div>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="system-metrics">
        <div className="skeleton-card"></div>
        <div className="skeleton-card"></div>
        <div className="skeleton-card"></div>
        <div className="skeleton-card"></div>
      </div>
    );
  }

  const cpu   = metrics.cpu_load_pct    ?? 0;
  const ram   = metrics.ram_used_gb     ?? 0;
  const ramTotal = metrics.ram_total_gb ?? 1;
  const vram  = metrics.vram_used_gb    ?? 0;
  const storageTb  = metrics.storage_used_tb  ?? 0;
  const storagePct = metrics.storage_used_pct ?? 0;

  let cpuColor = '--cyan';
  if (cpu > 90) cpuColor = '--red';
  else if (cpu > 70) cpuColor = '--amber';

  let ramColor = '--text';
  if ((ram / ramTotal) * 100 < 80) ramColor = '--green';

  let storageColor = '--text';
  if (storagePct > 80) storageColor = '--amber';

  return (
    <div className="system-metrics">
      <MetricCard
        value={`${Math.round(cpu)}%`}
        label="CPU Load"
        color={cpuColor}
      />
      <MetricCard
        value={`${Math.round(ram)} GB`}
        label="RAM"
        color={ramColor}
      />
      <MetricCard
        value={`${Math.round(vram)} GB`}
        label="VRAM Used"
        color="--cyan"
      />
      <MetricCard
        value={`${storageTb.toFixed(1)} TB`}
        label="Data Storage"
        color={storageColor}
      />
    </div>
  );
}
