/**
 * Step 1: Hardware Probe
 */

import { useState, useEffect } from 'react';
import { setupAPI } from '../../utils/setupAPI';
import './Step1Hardware.css';

export default function Step1Hardware({ onComplete, onData }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [hardware, setHardware] = useState(null);

  useEffect(() => {
    const probe = async () => {
      try {
        const data = await setupAPI.probeHardware();
        setHardware(data);
        onData(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    probe();
  }, [onData]);

  if (loading) {
    return (
      <div className="setup-step">
        <h2>Step 1: Hardware Detection</h2>
        <div className="loading-indicator">
          <div className="spinner"></div>
          <p>Detecting GPU configuration...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="setup-step">
        <h2>Step 1: Hardware Detection</h2>
        <div className="error-box">
          <p>⚠ GPU detection failed: {error}</p>
          <button onClick={() => window.location.reload()}>Retry</button>
        </div>
      </div>
    );
  }

  return (
    <div className="setup-step">
      <h2>Step 1: Hardware Detection</h2>
      <div className="hardware-summary">
        <div className="hw-section">
          <h3>CPU</h3>
          <p>{hardware.cpu.model}</p>
          <p className="detail">{hardware.cpu.cores} cores / {hardware.cpu.threads} threads · {hardware.cpu.ram_gb} GB RAM</p>
        </div>

        <div className="hw-section">
          <h3>GPUs ({hardware.gpus.length})</h3>
          {hardware.gpus.map((gpu, i) => (
            <div key={i} className="gpu-item">
              <span className="gpu-name">GPU {gpu.index}: {gpu.name}</span>
              <span className="gpu-vram">{gpu.vram_gb} GB</span>
            </div>
          ))}
        </div>

        {hardware.nvlink_pairs.length > 0 && (
          <div className="hw-section">
            <h3>NVLink Topology</h3>
            {hardware.nvlink_pairs.map((pair, i) => (
              <p key={i} className="nvlink-item">
                GPU {pair[0]} ↔ GPU {pair[1]} (56.25 GB/s)
              </p>
            ))}
          </div>
        )}

        <div className="hw-section">
          <h3>Storage</h3>
          <p>{hardware.storage.total_gb} GB total · {hardware.storage.free_gb} GB free</p>
        </div>
      </div>

      <div className="step-actions">
        <button className="btn-primary" onClick={() => onComplete()}>
          Next: Profile →
        </button>
      </div>
    </div>
  );
}
