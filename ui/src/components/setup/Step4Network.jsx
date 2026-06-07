/**
 * Step 4: Network Configuration
 */

import { useState } from 'react';
import { setupAPI } from '../../utils/setupAPI';

export default function Step4Network({ onComplete, onData }) {
  const [jumpboxIp, setJumpboxIp] = useState('10.0.0.1');
  const [enableCaddy, setEnableCaddy] = useState(true);
  const [pubkey, setPubkey] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSetup = async () => {
    setLoading(true);
    try {
      const data = await setupAPI.setupNetwork(jumpboxIp, enableCaddy);
      setPubkey(data.wireguard_pubkey);
      onData(data);
    } catch (err) {
      console.error('Network setup failed:', err);
    } finally {
      setLoading(false);
    }
  };

  if (pubkey) {
    return (
      <div className="setup-step">
        <h2>Step 4: Network Configuration</h2>
        <p className="step-description">Network configured successfully</p>

        <div className="network-summary">
          <div className="config-item">
            <h4>Jumpbox IP</h4>
            <code>{jumpboxIp}</code>
          </div>

          <div className="config-item">
            <h4>WireGuard Public Key</h4>
            <code>{pubkey}</code>
            <button className="btn-small" onClick={() => navigator.clipboard.writeText(pubkey)}>
              Copy
            </button>
          </div>

          <div className="config-item">
            <h4>Caddy Reverse Proxy</h4>
            <p>{enableCaddy ? 'Enabled' : 'Disabled'}</p>
          </div>
        </div>

        <div className="step-actions">
          <button className="btn-primary" onClick={() => onComplete()}>
            Next: Provision →
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="setup-step">
      <h2>Step 4: Network Configuration</h2>

      <div className="network-form">
        <div className="form-group">
          <label>Jumpbox / Reverse Proxy IP</label>
          <input
            type="text"
            value={jumpboxIp}
            onChange={(e) => setJumpboxIp(e.target.value)}
            placeholder="10.0.0.1"
          />
        </div>

        <div className="form-group">
          <label>Enable Caddy Reverse Proxy</label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={enableCaddy}
              onChange={(e) => setEnableCaddy(e.target.checked)}
            />
            Enable (recommended for external access)
          </label>
        </div>

        <div className="step-actions">
          <button
            className="btn-primary"
            onClick={handleSetup}
            disabled={loading}
          >
            {loading ? 'Configuring...' : 'Continue →'}
          </button>
        </div>
      </div>
    </div>
  );
}
