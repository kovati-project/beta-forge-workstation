import React from 'react';
import { DotStatus } from './DotStatus';
import { Tag } from './Tag';
import { VBar } from './VBar';
import './GpuCard.css';

function GpuCardContent({ gpu, activeProfile }) {
  if (!gpu) {
    return (
      <div className="gpu-card skeleton">
        <div className="skeleton-bar"></div>
        <div className="skeleton-bar"></div>
        <div className="skeleton-bar"></div>
      </div>
    );
  }

  // Determine border color based on temp
  let borderClass = 'gpu-card-default';
  if (gpu.temp_c > 85) {
    borderClass = 'gpu-card-critical';
  } else if (gpu.temp_c > 75) {
    borderClass = 'gpu-card-warning';
  } else if (gpu.claimed_by_profile) {
    borderClass = 'gpu-card-claimed';
  }

  // Determine temp color
  let tempColor = '--text';
  if (gpu.temp_c > 75) tempColor = '--amber';
  if (gpu.temp_c > 85) tempColor = '--red';
  if (gpu.temp_c < 60) tempColor = '--green';

  // Determine service tag
  let serviceTag = null;
  let serviceVariant = 'gray';
  if (gpu.active_service) {
    serviceTag = gpu.active_service;
    if (gpu.service_type === 'inference') serviceVariant = 'cyan';
    else if (gpu.service_type === 'training') serviceVariant = 'amber';
    else if (gpu.service_type === 'image') serviceVariant = 'purple';
  }

  // VRAM bar variant
  let vramVariant = 'cyan';
  if (gpu.temp_c > 75) vramVariant = 'amber';
  if (gpu.vram_used_gb < 1.0) vramVariant = 'green';

  // Util bar variant
  const utilVariant = gpu.utilization_pct > 20 ? 'cyan' : 'green';

  const vramPct = (gpu.vram_used_gb / gpu.vram_total_gb) * 100;

  return (
    <div className={`gpu-card ${borderClass}`}>
      {gpu.nvlink_bridge && (
        <div className="gpu-card-bridge-badge">
          {gpu.nvlink_bridge}
        </div>
      )}
      
      <div className="gpu-card-header">
        <div className="gpu-card-label">{`GPU ${gpu.index} · bus ${gpu.bus_id}`}</div>
        <div className="gpu-card-name">RTX A5500</div>
      </div>

      <div className="gpu-card-metric">
        <div className="gpu-card-metric-label">VRAM</div>
        <VBar pct={vramPct} variant={vramVariant} />
        <div className="gpu-card-metric-value">
          {gpu.vram_used_gb.toFixed(1)} / {gpu.vram_total_gb} GB
        </div>
      </div>

      <div className="gpu-card-metric">
        <div className="gpu-card-metric-label">Util</div>
        <VBar pct={gpu.utilization_pct} variant={utilVariant} />
        <div className="gpu-card-metric-value">{gpu.utilization_pct}%</div>
      </div>

      <div className="gpu-card-metric">
        <div className="gpu-card-metric-label">Temp</div>
        <div className="gpu-card-metric-value" style={{ color: `var(${tempColor})` }}>
          {gpu.temp_c}°C
        </div>
      </div>

      <div className="gpu-card-metric">
        <div className="gpu-card-metric-label">Power</div>
        <div className="gpu-card-metric-value">{gpu.power_w} W</div>
      </div>

      {serviceTag && (
        <div className="gpu-card-service">
          <Tag variant={serviceVariant}>{serviceTag}</Tag>
        </div>
      )}
    </div>
  );
}

export const GpuCard = React.memo(({ gpu, activeProfile }) => (
  <GpuCardContent gpu={gpu} activeProfile={activeProfile} />
));
