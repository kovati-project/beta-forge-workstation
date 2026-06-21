import { useEffect, useRef, useState } from 'react';
import { getGPUMetrics } from '../utils/monitorAPI';
import { VBar } from './VBar';
import './GPUTelemetrySection.css';

function renderGPUChart(canvas, data, color) {
  if (!canvas || !data || data.length < 2) return;

  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const MAX_VRAM = 24;
  const points = data.map((v, i) => [
    (i / (data.length - 1)) * w,
    h - (Math.min(v, MAX_VRAM) / MAX_VRAM) * h,
  ]);

  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, color.replace(')', ', 0.2)').replace('rgb', 'rgba'));
  grad.addColorStop(1, 'transparent');

  ctx.beginPath();
  ctx.moveTo(points[0][0], h);
  points.forEach(([x, y]) => ctx.lineTo(x, y));
  ctx.lineTo(points[points.length - 1][0], h);
  ctx.fillStyle = grad;
  ctx.fill();

  ctx.beginPath();
  points.forEach(([x, y], i) => {
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.stroke();

  const lastValue = data[data.length - 1];
  ctx.fillStyle = color;
  ctx.font = '9px monospace';
  ctx.textAlign = 'right';
  ctx.fillText(`${lastValue.toFixed(1)} GB`, w - 4, 12);
}

export function GPUTelemetrySection() {
  const [gpuData, setGPUData] = useState({});
  const [loading, setLoading] = useState(true);
  const canvasRefs = useRef({});

  useEffect(() => {
    const load = async () => {
      const data = await getGPUMetrics();
      setGPUData(data);
      setLoading(false);
    };
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    Object.entries(gpuData).forEach(([gpuId, gpu]) => {
      if (gpu.vram_history && canvasRefs.current[gpuId]) {
        const color = gpu.active ? 'rgb(0,217,255)' : 'rgb(0,255,100)';
        renderGPUChart(canvasRefs.current[gpuId], gpu.vram_history, color);
      }
    });
  }, [gpuData]);

  if (loading) {
    return <div className="gpu-section loading">Loading GPU metrics...</div>;
  }

  // NVLink pair order: active pair (0,3) first, idle pair (1,2) second
  const orderedGPUs = ['GPU0', 'GPU3', 'GPU1', 'GPU2'];

  return (
    <div className="gpu-section">
      {/* VRAM sparkline charts */}
      <div className="charts-grid">
        {orderedGPUs.map((gpuId) => {
          const gpu = gpuData[gpuId];
          if (!gpu) return null;
          const status = gpu.active ? 'active' : 'idle';
          return (
            <div key={gpuId} className="gpu-chart">
              <div className="chart-header">
                <span className="chart-title">{gpuId} VRAM</span>
                <span className="chart-vram">
                  {gpu.vram_used_gb?.toFixed(1) ?? '—'} / {gpu.vram_total_gb ?? 24} GB
                </span>
                <span className={`status-badge ${status}`}>{status}</span>
              </div>
              <canvas
                ref={(el) => { canvasRefs.current[gpuId] = el; }}
                width={300}
                height={80}
                className="vram-canvas"
              />
              <div className="chart-footer">
                <span className="chart-stat">
                  {gpu.utilization ?? 0}% util
                </span>
                <span className="chart-stat">
                  {gpu.temp ?? 0}°C
                </span>
                <span className="chart-stat">
                  {gpu.power_w ?? 0} W
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Per-GPU gauges */}
      <div className="gauges-grid">
        {orderedGPUs.map((gpuId) => {
          const gpu = gpuData[gpuId];
          if (!gpu) return null;
          const vramPct = ((gpu.vram_used_gb ?? 0) / (gpu.vram_total_gb ?? 24)) * 100;
          const tempColor =
            gpu.temp > 75 ? 'red' : gpu.temp > 60 ? 'amber' : 'cyan';
          const vramVariant =
            vramPct > 80 ? 'red' : vramPct > 50 ? 'amber' : vramPct < 10 ? 'green' : 'cyan';
          return (
            <div key={`gauge-${gpuId}`} className="gauge-item">
              <span className="gauge-label">{gpuId}</span>
              <div className="gauge-row">
                <span className="gauge-sub">VRAM</span>
                <VBar
                  value={vramPct}
                  label={`${gpu.vram_used_gb?.toFixed(1)} GB`}
                  variant={vramVariant}
                />
              </div>
              <div className="gauge-row">
                <span className="gauge-sub">Temp</span>
                <VBar
                  value={(gpu.temp ?? 0)}
                  label={`${gpu.temp ?? 0}°C`}
                  variant={tempColor}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
