import { useEffect, useRef, useState } from 'react';
import { getGPUMetrics } from '../utils/monitorAPI';
import { VBar } from './VBar';
import './GPUTelemetrySection.css';

const GPU_MAX_VRAM = 24; // GB

function renderGPUChart(canvas, data, color) {
  if (!canvas || !data || data.length < 2) return;

  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  const w = canvas.width;
  const h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  const points = data.map((v, i) => [
    (i / (data.length - 1)) * w,
    h - (Math.min(v, GPU_MAX_VRAM) / GPU_MAX_VRAM) * h,
  ]);

  // Fill area under line
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  const rgbColor = color; // Assume color is already in rgb format
  grad.addColorStop(0, rgbColor.replace(')', ', 0.2)').replace('rgb', 'rgba'));
  grad.addColorStop(1, 'transparent');

  ctx.beginPath();
  ctx.moveTo(points[0][0], h);
  points.forEach(([x, y]) => ctx.lineTo(x, y));
  ctx.lineTo(points[points.length - 1][0], h);
  ctx.fillStyle = grad;
  ctx.fill();

  // Draw line
  ctx.beginPath();
  points.forEach(([x, y], i) => {
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = rgbColor;
  ctx.lineWidth = 1.5;
  ctx.stroke();

  // Last value label
  const lastValue = data[data.length - 1];
  const labelText = `${lastValue.toFixed(1)} GB`;
  ctx.fillStyle = rgbColor;
  ctx.font = '9px --mono';
  ctx.textAlign = 'right';
  ctx.fillText(labelText, w - 4, 12);
}

export function GPUTelemetrySection() {
  const [gpuData, setGPUData] = useState({});
  const [loading, setLoading] = useState(true);
  const canvasRefs = useRef({});

  useEffect(() => {
    const loadMetrics = async () => {
      const data = await getGPUMetrics();
      setGPUData(data);
      setLoading(false);
    };
    loadMetrics();
  }, []);

  useEffect(() => {
    // Render charts when data updates
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

  const orderedGPUs = ['GPU0', 'GPU3', 'GPU1', 'GPU2']; // Active pair first

  return (
    <div className="gpu-section">
      <div className="charts-grid">
        {orderedGPUs.map((gpuId) => {
          const gpu = gpuData[gpuId];
          if (!gpu) return null;

          const status = gpu.active ? 'active' : 'idle';
          const chartColor = gpu.active ? '#00d9ff' : '#00ff64';

          return (
            <div key={gpuId} className="gpu-chart">
              <div className="chart-header">
                <span className="chart-title">{gpuId} VRAM</span>
                <span className={`status-badge ${status}`}>{status}</span>
              </div>
              <canvas
                ref={(el) => {
                  canvasRefs.current[gpuId] = el;
                }}
                width={300}
                height={80}
                className="vram-canvas"
              />
            </div>
          );
        })}
      </div>

      <div className="gauges-grid">
        {Object.entries(gpuData).map(([gpuId, gpu]) => {
          const tempColor =
            gpu.temp > 75 ? 'red' : gpu.temp > 60 ? 'amber' : 'cyan';
          return (
            <div key={`temp-${gpuId}`} className="gauge-item">
              <span className="gauge-label">
                {gpuId} Temp
              </span>
              <VBar
                value={(gpu.temp / 100) * 100}
                label={`${gpu.temp}°C`}
                variant={tempColor}
              />
            </div>
          );
        })}

        {gpuData.CPU && (
          <div className="gauge-item">
            <span className="gauge-label">CPU Load</span>
            <VBar
              value={gpuData.CPU.utilization}
              label={`${gpuData.CPU.utilization.toFixed(0)}%`}
              variant={
                gpuData.CPU.utilization > 90
                  ? 'red'
                  : gpuData.CPU.utilization > 70
                    ? 'amber'
                    : 'cyan'
              }
            />
          </div>
        )}

        {gpuData.RAM && (
          <div className="gauge-item">
            <span className="gauge-label">RAM Used</span>
            <VBar
              value={(gpuData.RAM.used / gpuData.RAM.total) * 100}
              label={`${(gpuData.RAM.used / 1024).toFixed(0)} GB`}
              variant="green"
            />
          </div>
        )}
      </div>
    </div>
  );
}
