import { useState, useEffect } from 'react';
import { Btn } from './Btn';
import { VBar } from './VBar';
import { useApp } from '../context/AppContext';
import { useLogStream } from '../hooks/useTraining';
import { stopTraining, exportCheckpoint } from '../utils/trainingAPI';
import './LiveTrainingView.css';

export function LiveTrainingView({ mode, config, onStop }) {
  const { state } = useApp();
  const { lines } = useLogStream(mode === 'text' ? 'axolotl' : 'kohya');
  const [metrics, setMetrics] = useState({
    step: 0,
    totalSteps: config?.lora_config?.epochs || 1,
    loss: 0,
    gradNorm: 0,
    eta: '—',
  });
  const [stopping, setStopping] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState(null);

  // Parse metrics from log lines
  useEffect(() => {
    if (lines.length === 0) return;

    const lastLine = lines[lines.length - 1] || '';
    
    // Parse step: "step 842/3200"
    const stepMatch = lastLine.match(/step\s+(\d+)\/(\d+)/);
    if (stepMatch) {
      setMetrics((prev) => ({
        ...prev,
        step: parseInt(stepMatch[1]),
        totalSteps: parseInt(stepMatch[2]),
      }));
    }

    // Parse loss: "loss: 1.5211"
    const lossMatch = lastLine.match(/loss:\s+([\d.]+)/);
    if (lossMatch) {
      setMetrics((prev) => ({
        ...prev,
        loss: parseFloat(lossMatch[1]),
      }));
    }

    // Parse grad norm: "grad_norm: 0.578"
    const gradMatch = lastLine.match(/grad_norm:\s+([\d.]+)/);
    if (gradMatch) {
      setMetrics((prev) => ({
        ...prev,
        gradNorm: parseFloat(gradMatch[1]),
      }));
    }

    // Parse ETA: "ETA 2h 14m"
    const etaMatch = lastLine.match(/ETA\s+(\d+h\s+\d+m)/i);
    if (etaMatch) {
      setMetrics((prev) => ({
        ...prev,
        eta: etaMatch[1],
      }));
    }
  }, [lines]);

  const handleStop = async () => {
    if (!window.confirm('Stop training? This will halt the current job.')) return;

    setStopping(true);
    try {
      await stopTraining();
      onStop?.();
    } catch (error) {
      console.error('Failed to stop training:', error);
    } finally {
      setStopping(false);
    }
  };

  const handleExport = async () => {
    setExporting(true);
    setExportError(null);
    try {
      const result = await exportCheckpoint(config?.run_name || 'training-export');
      alert(`Checkpoint exported to: ${result.path || '/data/checkpoints/'}`);
    } catch (error) {
      setExportError(error.message);
    } finally {
      setExporting(false);
    }
  };

  const modelLabel = mode === 'text' ? config?.model || 'Model' : 'Image Model';
  const epochProgress = Math.min(
    100,
    Math.round((metrics.step / metrics.totalSteps) * 100)
  );

  return (
    <div className="live-training-view">
      <div className="training-header">
        <span className="training-title">
          Training: {modelLabel} · LoRA rank {config?.lora_config?.rank || '—'}
        </span>
        <span className="training-epoch">
          epoch {Math.ceil(metrics.step / (metrics.totalSteps / (config?.lora_config?.epochs || 1)))} / {config?.lora_config?.epochs || 1}
        </span>
      </div>

      <div className="training-progress">
        <div className="progress-section">
          <span className="progress-label">EPOCH PROGRESS</span>
          <div className="progress-bar-wrapper">
            <VBar pct={epochProgress} variant="cyan" />
          </div>
          <span className="progress-text">
            {metrics.step} / {metrics.totalSteps}
          </span>
        </div>
      </div>

      {/* GPU VRAM */}
      <div className="gpu-section">
        <div className="section-title">GPU VRAM (all 4):</div>
        <div className="gpu-bars">
          {state.gpus?.map((gpu) => (
            <div key={gpu.index} className="gpu-bar-item">
              <span className="gpu-label">GPU{gpu.index}</span>
              <div className="gpu-bar-wrapper">
                <VBar
                  pct={Math.round((gpu.vram_used_gb / 24) * 100)}
                  variant="cyan"
                />
              </div>
              <span className="gpu-value">
                {gpu.vram_used_gb.toFixed(1)}/24 GB
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Metrics */}
      <div className="metrics-section">
        <div className="metrics-row">
          <span className="metric-label">LOSS:</span>
          <span className="metric-value">{metrics.loss.toFixed(4)}</span>
          <span className="metric-label">GRAD NORM:</span>
          <span className="metric-value">{metrics.gradNorm.toFixed(3)}</span>
          <span className="metric-label">LR:</span>
          <span className="metric-value">{config?.lora_config?.lr || '—'}</span>
          <span className="metric-label">ETA:</span>
          <span className="metric-value">{metrics.eta}</span>
        </div>
      </div>

      {/* Log Output */}
      <div className="logs-section">
        <div className="logs-header">LOG OUTPUT</div>
        <div className="live-training-logs">
          {lines.map((line, idx) => (
            <div key={idx} className="log-line">
              {line}
            </div>
          ))}
        </div>
      </div>

      {/* Actions */}
      <div className="training-actions">
        <Btn
          variant="gray"
          size="sm"
          onClick={handleExport}
          disabled={exporting}
        >
          {exporting ? 'Exporting...' : 'Export Checkpoint'}
        </Btn>
        <Btn
          variant="red"
          size="sm"
          onClick={handleStop}
          disabled={stopping}
        >
          {stopping ? 'Stopping...' : 'Stop Training'}
        </Btn>
      </div>

      {exportError && (
        <div className="export-error">
          ⚠ Export failed: {exportError}
        </div>
      )}
    </div>
  );
}
