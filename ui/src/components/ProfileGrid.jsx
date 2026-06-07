import { useState } from 'react';
import { useApp } from '../context/AppContext';
import { ProfileCard } from './ProfileCard';
import './ProfileGrid.css';

export function ProfileGrid({ profiles, loading, error }) {
  const { state } = useApp();
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [selectedProfile, setSelectedProfile] = useState(null);

  const handleActivate = async (profileName) => {
    setSelectedProfile(profileName);
    
    // For now, skip confirmation and activate directly
    // In a full implementation, check if confirmation is needed
    await activateProfile(profileName);
  };

  const activateProfile = async (profileName) => {
    try {
      const response = await fetch(`/activate/${profileName}`, { method: 'POST' });
      if (!response.ok) {
        alert('Failed to activate profile');
      }
    } catch (error) {
      alert('Error activating profile');
    }
  };

  if (error) {
    return (
      <div className="profile-grid-error">
        <div className="error-message">⚠ Failed to load profiles</div>
      </div>
    );
  }

  if (loading || !profiles) {
    return (
      <div className="profile-grid">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={`skeleton-${i}`} className="profile-card skeleton">
            <div className="skeleton-bar"></div>
            <div className="skeleton-bar" style={{ width: '70%' }}></div>
          </div>
        ))}
      </div>
    );
  }

  if (profiles.length === 0) {
    return (
      <div className="profile-grid-empty">
        No profiles found — check profiles.yaml
      </div>
    );
  }

  return (
    <div className="profile-grid">
      {profiles.map((profile) => {
        const isActive = profile.active || profile.name === state.activeProfile;
        const isIncompatible =
          !isActive &&
          state.activeProfile &&
          profile.incompatible_with &&
          profile.incompatible_with.includes(state.activeProfile);

        return (
          <ProfileCard
            key={profile.name}
            profile={profile}
            isActive={isActive}
            isIncompatible={isIncompatible}
            onActivate={handleActivate}
            switching={state.switching}
          />
        );
      })}
    </div>
  );
}
