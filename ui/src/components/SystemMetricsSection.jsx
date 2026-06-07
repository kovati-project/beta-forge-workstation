import { useEffect, useState } from 'react';
import { getSystemMetrics } from '../utils/monitorAPI';
import { VBar } from './VBar';
import './SystemMetricsSection.css';

export function SystemMetricsSection() {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadMetrics = async () => {
      const data = await getSystemMetrics();
      setMetrics(data);
      setLoading(false);
    };
    loadMetrics();
  }, []);

  if (loading) {
    return <div className="system-section loading">Loading system metrics...</div>;
  }

  if (!metrics) {
    return <div className="system-section empty">No system metrics available</div>;
  }

  // Generate CPU heatmap (64 cells for Threadripper)
  const cpuCores = metrics.cpu_cores || Array(64).fill(0);
  const getCPUColor = (utilization) => {
    if (utilization < 20) return 'var(--surface3)';
    if (utilization < 50) return 'rgba(0, 217, 255, 0.2)';
    if (utilization < 80) return 'rgba(255, 179, 71, 0.6)';
    return 'var(--red)';
  };

  return (
    <div className="system-section">
      <div className="metric-group">
        <h3>CPU Heatmap (64 cores)</h3>
        <div className="cpu-heatmap">
          {cpuCores.map((util, idx) => (
            <div
              key={idx}
              className="cpu-cell"
              style={{ backgroundColor: getCPUColor(util) }}
              title={`CPU ${idx}: ${util.toFixed(0)}%`}
            />
          ))}
        </div>
      </div>

      <div className="metric-group">
        <h3>System Resources</h3>
        <div className="metrics-bars">
          {metrics.ram && (
            <div className="bar-item">
              <span className="bar-label">RAM</span>
              <VBar
                value={(metrics.ram.used / metrics.ram.total) * 100}
                label={`${(metrics.ram.used / 1024).toFixed(0)} / ${(metrics.ram.total / 1024).toFixed(0)} GB`}
                variant="green"
              />
            </div>
          )}

          {metrics.disk_io && (
            <div className="bar-item">
              <span className="bar-label">Disk I/O</span>
              <div className="dual-bar">
                <VBar
                  value={Math.min(100, (metrics.disk_io.read / 1000) * 100)}
                  label={`${(metrics.disk_io.read / 1024).toFixed(0)} MB/s read`}
                  variant="cyan"
                />
                <VBar
                  value={Math.min(100, (metrics.disk_io.write / 1000) * 100)}
                  label={`${(metrics.disk_io.write / 1024).toFixed(0)} MB/s write`}
                  variant="amber"
                />
              </div>
            </div>
          )}

          {metrics.network && (
            <div className="bar-item">
              <span className="bar-label">Network</span>
              <div className="dual-bar">
                <VBar
                  value={Math.min(100, (metrics.network.rx / 10000000) * 100)}
                  label={`${(metrics.network.rx / 1000000000).toFixed(2)} Gbps rx`}
                  variant="cyan"
                />
                <VBar
                  value={Math.min(100, (metrics.network.tx / 10000000) * 100)}
                  label={`${(metrics.network.tx / 1000000000).toFixed(2)} Gbps tx`}
                  variant="amber"
                />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
