import { useApp } from '../context/AppContext';
import { GpuCard } from './GpuCard';
import './GpuStatusRow.css';

export function GpuStatusRow() {
  const { state } = useApp();

  return (
    <div className="gpu-status-row">
      {state.gpus && state.gpus.length > 0 ? (
        state.gpus.map((gpu) => (
          <GpuCard key={gpu.index} gpu={gpu} activeProfile={state.activeProfile} />
        ))
      ) : (
        // Show 4 skeleton cards
        Array.from({ length: 4 }).map((_, i) => (
          <GpuCard key={`skeleton-${i}`} gpu={null} activeProfile={null} />
        ))
      )}
    </div>
  );
}
