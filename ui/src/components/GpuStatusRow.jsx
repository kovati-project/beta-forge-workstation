import { useApp } from '../context/AppContext';
import { GpuCard } from './GpuCard';
import './GpuStatusRow.css';

export function GpuStatusRow() {
  const { state } = useApp();
  const hasGpus = Boolean(state.gpus && state.gpus.length > 0);
  // `gpu_telemetry` from /status, kept by the shared reducer (null before the first poll).
  const telemetry = state.gpuTelemetry;

  if (hasGpus) {
    return (
      <div className="gpu-status-row">
        {state.gpus.map((gpu) => (
          <GpuCard key={gpu.index} gpu={gpu} activeProfile={state.activeProfile} />
        ))}
      </div>
    );
  }

  if (telemetry && telemetry.available === false) {
    const message = telemetry.error || 'NVML could not be read';
    return (
      <div className="gpu-status-row">
        {Array.from({ length: 4 }).map((_, i) => (
          <GpuCard
            key={`unavailable-${i}`}
            gpu={null}
            index={i}
            telemetryError={message}
            activeProfile={null}
          />
        ))}
      </div>
    );
  }

  // Not heard from the backend yet: show 4 skeleton cards
  return (
    <div className="gpu-status-row">
      {Array.from({ length: 4 }).map((_, i) => (
        <GpuCard key={`skeleton-${i}`} gpu={null} activeProfile={null} />
      ))}
    </div>
  );
}
