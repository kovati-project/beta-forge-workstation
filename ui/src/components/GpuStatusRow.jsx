import { useEffect, useState } from 'react';
import { useApp } from '../context/AppContext';
import { GpuCard } from './GpuCard';
import './GpuStatusRow.css';

// /status carries `gpu_telemetry: { available, error }`, but the shared reducer
// only keeps the fields it knows about, so the signal never reaches app state.
// While there are no GPUs to show (the only time the signal matters) ask /status
// directly. Polling stops as soon as real GPU data arrives.
function useGpuTelemetryStatus(enabled) {
  const [telemetry, setTelemetry] = useState(null);

  useEffect(() => {
    if (!enabled) {
      setTelemetry(null);
      return undefined;
    }
    let cancelled = false;
    const poll = async () => {
      try {
        const response = await fetch('/status');
        if (!response.ok) return;
        const data = await response.json();
        if (!cancelled) setTelemetry(data.gpu_telemetry || null);
      } catch (error) {
        // Backend unreachable: keep whatever we last knew (skeleton if nothing).
      }
    };
    poll();
    const id = setInterval(poll, 3000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [enabled]);

  return telemetry;
}

export function GpuStatusRow() {
  const { state } = useApp();
  const hasGpus = Boolean(state.gpus && state.gpus.length > 0);
  const telemetry = useGpuTelemetryStatus(!hasGpus);

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
