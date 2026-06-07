import { useApp } from '../context/AppContext';
import './SwitchingBanner.css';

export function SwitchingBanner() {
  const { state } = useApp();

  if (!state.switching) {
    return null;
  }

  return (
    <div className="switching-banner">
      <div className="switching-banner-content">
        <div className="switching-header">
          <span className="switching-icon">⟳</span>
          <span className="switching-text">
            SWITCHING TO {state.activeProfile || 'profile'}
          </span>
        </div>

        <div className="switching-progress">
          <div className="switching-progress-bar">
            <div className="switching-progress-fill"></div>
          </div>
          <div className="switching-phase">stopping services…</div>
        </div>

        <div className="switching-note">
          GPU VRAM draining — do not power off
        </div>
      </div>
    </div>
  );
}
