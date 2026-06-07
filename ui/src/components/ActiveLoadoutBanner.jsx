import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { Btn } from './Btn';
import { Tag } from './Tag';
import './ActiveLoadoutBanner.css';

function formatTimeSince(timestamp) {
  if (!timestamp) return '';
  const now = Date.now() / 1000;
  const diff = now - timestamp;
  
  const mins = Math.floor(diff / 60);
  const hours = Math.floor(diff / 3600);
  const days = Math.floor(diff / 86400);
  
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  if (hours < 24) {
    const remainingMins = mins % 60;
    return remainingMins > 0 ? `${hours}h ${remainingMins}m ago` : `${hours}h ago`;
  }
  return `${days}d ago`;
}

export function ActiveLoadoutBanner() {
  const navigate = useNavigate();
  const { state } = useApp();

  const handleStopAll = async () => {
    const confirmed = window.confirm('Stop all running services?');
    if (confirmed) {
      try {
        const response = await fetch('/stop', { method: 'POST' });
        if (!response.ok) {
          alert('Failed to stop services');
        }
      } catch (error) {
        alert('Error stopping services');
      }
    }
  };

  if (!state.activeProfile) {
    return (
      <div className="loadout-banner loadout-banner-empty">
        <div className="loadout-banner-content">
          <div className="loadout-empty-text">
            No active profile — select a loadout to begin
          </div>
          <Btn variant="cyan" onClick={() => navigate('/#/loadout')}>
            Go to Loadout
          </Btn>
        </div>
      </div>
    );
  }

  if (state.switching) {
    return (
      <div className="loadout-banner loadout-banner-switching">
        <div className="loadout-banner-content">
          <div className="loadout-switching-header">
            <span className="loadout-switching-icon">⟳</span>
            <span>SWITCHING PROFILE</span>
          </div>
          <div className="loadout-switching-desc">
            stopping services → draining VRAM → starting services
          </div>
          <div className="loadout-progress-bar">
            <div className="loadout-progress-fill"></div>
          </div>
        </div>
      </div>
    );
  }

  const timeSince = formatTimeSince(state.lastSwitched);

  return (
    <div className="loadout-banner">
      <div className="loadout-banner-content">
        <div className="loadout-banner-title">ACTIVE LOADOUT</div>
        
        <div className="loadout-profile-name">{state.activeProfile}</div>
        
        <div className="loadout-profile-meta">
          Tensor-parallel 32B–40B · 48 GB · switched {timeSince}
        </div>

        <div className="loadout-services">
          {state.runningServices && state.runningServices.map((service) => (
            <Tag key={service} variant="cyan">
              {service}
            </Tag>
          ))}
        </div>

        <div className="loadout-banner-buttons">
          <Btn variant="cyan" onClick={() => navigate('/#/loadout')}>
            Switch Profile →
          </Btn>
          <Btn variant="red" onClick={handleStopAll}>
            Stop All
          </Btn>
        </div>
      </div>
    </div>
  );
}
