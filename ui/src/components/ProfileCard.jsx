import { Btn } from './Btn';
import { Tag } from './Tag';
import { useApp } from '../context/AppContext';
import './ProfileCard.css';

function MiniGpuDiagram({ profile }) {
  const claimedGpus = profile.gpus || [];
  const gpuList = [0, 1, 2, 3];

  // Check if profile uses NVLink pair
  const nvlinkPair = profile.nvlink_pairs?.[0];

  return (
    <div className="mini-gpu-diagram">
      <div className="mini-gpu-row">
        {gpuList.map((gpu) => (
          <div
            key={gpu}
            className={`mini-gpu-box ${claimedGpus.includes(gpu) ? 'claimed' : ''}`}
          >
            {gpu}
          </div>
        ))}
      </div>
      {nvlinkPair && (
        <div className="mini-bridge-indicator">
          {profile.accent === 'amber' ? 'Bridge A' : 'Bridge B'}
          {' '}━━━━━
        </div>
      )}
    </div>
  );
}

function VramCheck({ profile, gpuMap }) {
  if (!profile.gpus || profile.gpus.length === 0) {
    return (
      <div className="vram-check">
        <span className="vram-check-label">CPU-only profile</span>
      </div>
    );
  }

  const availableVram = profile.gpus.reduce((sum, gpuIdx) => {
    const gpu = gpuMap[gpuIdx];
    return sum + (gpu ? gpu.vram_total_gb - gpu.vram_used_gb : 0);
  }, 0);

  const required = profile.vram_required_gb || 0;
  const hasSpace = availableVram >= required;

  return (
    <div className={`vram-check ${hasSpace ? 'available' : 'unavailable'}`}>
      <span className="vram-label">
        ~{required} GB · {Math.round(availableVram)} GB avail
      </span>
      <span className="vram-check-icon">
        {hasSpace ? '✓' : '✗'}
      </span>
    </div>
  );
}

export function ProfileCard({ profile, isActive, isIncompatible, onActivate, switching }) {
  const { state } = useApp();

  // Build GPU map from current status
  const gpuMap = {};
  if (state.gpus) {
    state.gpus.forEach((gpu) => {
      gpuMap[gpu.index] = gpu;
    });
  }

  const handleActivate = () => {
    if (isActive || isIncompatible || switching) {
      return;
    }
    onActivate(profile.name);
  };

  const getAccentColor = () => {
    if (profile.accent === 'amber') return '--amber';
    if (profile.accent === 'purple') return '--purple';
    return '--cyan';
  };

  return (
    <div
      className={`profile-card ${isActive ? 'active' : ''} ${isIncompatible ? 'incompatible' : ''}`}
      style={isActive ? { borderColor: `var(${getAccentColor()})` } : {}}
    >
      {isActive && <div className="profile-badge">ACTIVE</div>}
      {isIncompatible && <div className="profile-badge lock">🔒</div>}

      <div className="profile-header">
        <div className="profile-name">{profile.name}</div>
        <div className="profile-description">{profile.description}</div>
      </div>

      <MiniGpuDiagram profile={profile} />

      <div className="profile-services">
        {profile.services && profile.services.map((service) => (
          <Tag key={service} variant={profile.accent || 'cyan'}>
            {service}
          </Tag>
        ))}
      </div>

      <VramCheck profile={profile} gpuMap={gpuMap} />

      <Btn
        variant={profile.accent || 'cyan'}
        onClick={handleActivate}
        disabled={isActive || isIncompatible || switching}
      >
        {isActive ? '✓ Active' : 'Activate'}
      </Btn>

      {isIncompatible && (
        <div className="incompatible-tooltip">
          Incompatible with {state.activeProfile} — stop {state.activeProfile} first
        </div>
      )}
    </div>
  );
}
