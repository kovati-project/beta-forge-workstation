import { useApp } from '../context/AppContext';
import './NVLinkTopology.css';

export function NVLinkTopology() {
  const { state } = useApp();

  if (!state.gpus || state.gpus.length === 0) {
    return (
      <div className="nvlink-topology skeleton">
        <div className="skeleton-bar" style={{ width: '100%', height: '160px' }}></div>
      </div>
    );
  }

  // Map GPUs by index for quick access
  const gpuMap = {};
  state.gpus.forEach((gpu) => {
    gpuMap[gpu.index] = gpu;
  });

  // Get GPUs for each row (Bridge pairs)
  const bridgeA = [gpuMap[0], gpuMap[3]]; // GPU 0 and 3
  const bridgeB = [gpuMap[1], gpuMap[2]]; // GPU 1 and 2

  const getServiceType = (gpu) => {
    if (!gpu || gpu.vram_used_gb < 1) return null;
    return gpu.service_type || 'inference'; // Default to inference
  };

  const getGpuColors = (gpu) => {
    if (!gpu || gpu.vram_used_gb < 5) {
      return {
        fill: '#2e3560',
        stroke: '#2e3560',
      };
    }
    const serviceType = getServiceType(gpu);
    if (serviceType === 'training') {
      return {
        fill: '#ffb347',
        stroke: '#ffb347',
      };
    }
    if (serviceType === 'image') {
      return {
        fill: '#c084fc',
        stroke: '#c084fc',
      };
    }
    return {
      fill: '#00d9ff',
      stroke: '#00d9ff',
    };
  };

  const getBridgeStroke = (bridgeGpus) => {
    const activeGpu = bridgeGpus.find((g) => g && g.vram_used_gb > 1);
    if (!activeGpu) return '#2e3560';
    const serviceType = getServiceType(activeGpu);
    if (serviceType === 'training') return '#ffb347';
    if (serviceType === 'image') return '#c084fc';
    return '#00d9ff';
  };

  const isActiveBridge = (bridgeGpus) => {
    return bridgeGpus.some((g) => g && g.vram_used_gb > 1);
  };

  const renderGpuBox = (gpu, x, y) => {
    if (!gpu) return null;

    const colors = getGpuColors(gpu);
    const vramPct = (gpu.vram_used_gb / gpu.vram_total_gb) * 100;

    // Determine fill color with opacity
    let fillColor;
    if (gpu.vram_used_gb < 5) {
      fillColor = 'rgba(46, 53, 96, 0.2)';
    } else {
      const serviceType = getServiceType(gpu);
      if (serviceType === 'training') {
        fillColor = 'rgba(255, 179, 71, 0.12)';
      } else if (serviceType === 'image') {
        fillColor = 'rgba(192, 132, 252, 0.12)';
      } else {
        fillColor = 'rgba(0, 217, 255, 0.12)';
      }
    }

    return (
      <g key={`gpu-${gpu.index}`}>
        {/* GPU Box */}
        <rect
          x={x}
          y={y}
          width="80"
          height="56"
          fill={fillColor}
          stroke={colors.stroke}
          strokeWidth="1"
          rx="3"
          className="gpu-box"
        />

        {/* VRAM Fill Bar */}
        <rect
          x={x}
          y={y + 50}
          width={(vramPct / 100) * 80}
          height="6"
          fill={colors.stroke}
          rx="1"
        />

        {/* GPU Label */}
        <text
          x={x + 40}
          y={y + 14}
          textAnchor="middle"
          fontSize="10"
          fontWeight="600"
          fill="#e0e0e0"
          className="gpu-label"
        >
          GPU {gpu.index}
        </text>

        {/* VRAM Text */}
        <text
          x={x + 40}
          y={y + 28}
          textAnchor="middle"
          fontSize="9"
          fill="#9aa0c0"
          className="gpu-vram"
        >
          {gpu.vram_used_gb.toFixed(1)}/{gpu.vram_total_gb}GB
        </text>

        {/* Util + Temp */}
        <text
          x={x + 40}
          y={y + 40}
          textAnchor="middle"
          fontSize="8"
          fill="#6b7298"
          className="gpu-util"
        >
          {gpu.utilization_pct}% · {gpu.temp_c}°C
        </text>
      </g>
    );
  };

  return (
    <div className="nvlink-topology">
      <svg viewBox="0 0 680 160" className="nvlink-svg">
        {/* Bridge A Row */}
        {renderGpuBox(bridgeA[0], 10, 10)}

        {/* Bridge A Line */}
        <line
          x1="90"
          y1="38"
          x2="270"
          y2="38"
          stroke={getBridgeStroke(bridgeA)}
          strokeWidth="2"
          strokeDasharray={isActiveBridge(bridgeA) ? '6,3' : '4,4'}
          className={isActiveBridge(bridgeA) ? 'bridge-active' : 'bridge-idle'}
        />

        {/* Bridge A Label */}
        <text
          x="180"
          y="32"
          textAnchor="middle"
          fontSize="9"
          fill={getBridgeStroke(bridgeA)}
          className="bridge-label"
        >
          Bridge A · 56.25 GB/s
        </text>

        {renderGpuBox(bridgeA[1], 270, 10)}

        {/* Bridge B Row */}
        {renderGpuBox(bridgeB[0], 10, 80)}

        {/* Bridge B Line */}
        <line
          x1="90"
          y1="108"
          x2="270"
          y2="108"
          stroke={getBridgeStroke(bridgeB)}
          strokeWidth="2"
          strokeDasharray={isActiveBridge(bridgeB) ? '6,3' : '4,4'}
          className={isActiveBridge(bridgeB) ? 'bridge-active' : 'bridge-idle'}
        />

        {/* Bridge B Label */}
        <text
          x="180"
          y="102"
          textAnchor="middle"
          fontSize="9"
          fill={getBridgeStroke(bridgeB)}
          className="bridge-label"
        >
          Bridge B · 56.25 GB/s
        </text>

        {renderGpuBox(bridgeB[1], 270, 80)}
      </svg>
    </div>
  );
}
