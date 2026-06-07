import { useState, useEffect } from 'react';
import { getPlatformSetup } from '../utils/settingsAPI';
import './PlatformSetupSection.css';

export function PlatformSetupSection({ isAppliance }) {
  const [setup, setSetup] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadSetup = async () => {
      const data = await getPlatformSetup();
      setSetup(data);
      setLoading(false);
    };
    loadSetup();
  }, []);

  if (loading) {
    return <div className="platform-section loading">Loading platform setup...</div>;
  }

  if (!setup) {
    return <div className="platform-section empty">No platform setup data</div>;
  }

  return (
    <div className="platform-section">
      <div className="wizard-status">
        <span className="label">First-boot wizard:</span>
        {setup.completed ? (
          <span className="completed">
            ✓ Completed {setup.completed_date}
          </span>
        ) : (
          <span className="pending">○ Pending setup</span>
        )}
      </div>

      <div className="setup-details">
        <div className="detail-row">
          <span className="label">Hardware detected:</span>
          <span className="value">{setup.hardware || '—'}</span>
        </div>

        <div className="detail-row">
          <span className="label">Profile assigned:</span>
          <span className="value">{setup.profile || '—'}</span>
        </div>

        <div className="detail-row">
          <span className="label">Secrets:</span>
          <span className={`status ${setup.secrets_generated ? 'ok' : 'pending'}`}>
            {setup.secrets_generated ? '✓' : '○'} generated
          </span>
        </div>

        <div className="detail-row">
          <span className="label">Network:</span>
          <span className={`status ${setup.network_configured ? 'ok' : 'pending'}`}>
            {setup.network_configured ? '✓' : '○'} configured
          </span>
        </div>

        <div className="detail-row">
          <span className="label">Stack:</span>
          <span className={`status ${setup.stack_provisioned ? 'ok' : 'pending'}`}>
            {setup.stack_provisioned ? '✓' : '○'} provisioned
          </span>
        </div>
      </div>

      {!isAppliance && setup.completed && (
        <button className="rerun-wizard-btn">
          Re-run First-Boot Wizard
        </button>
      )}
    </div>
  );
}
