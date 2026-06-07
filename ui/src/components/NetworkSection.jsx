import { useState, useEffect } from 'react';
import { getNetwork, updateJumpboxIP } from '../utils/settingsAPI';
import { DotStatus } from './DotStatus';
import './NetworkSection.css';

export function NetworkSection({ isAppliance }) {
  const [network, setNetwork] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editingIP, setEditingIP] = useState(false);
  const [tempIP, setTempIP] = useState('');
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadNetwork = async () => {
      const data = await getNetwork();
      setNetwork(data);
      setTempIP(data.jumpbox_ip || '');
      setLoading(false);
    };
    loadNetwork();
  }, []);

  const handleEditIP = () => {
    setTempIP(network.jumpbox_ip || '');
    setEditingIP(true);
  };

  const handleSaveIP = async () => {
    try {
      await updateJumpboxIP(tempIP);
      setNetwork((prev) => ({ ...prev, jumpbox_ip: tempIP }));
      setEditingIP(false);
      setError(null);
    } catch (err) {
      setError(`Failed to update jumpbox IP: ${err.message}`);
    }
  };

  const handleCancelIP = () => {
    setEditingIP(false);
  };

  if (loading) {
    return <div className="network-section loading">Loading network config...</div>;
  }

  if (!network) {
    return <div className="network-section empty">No network data</div>;
  }

  const wireGuardStatus = network.wireguard_connected ? 'connected' : 'disconnected';
  const caddyStatus = network.caddy_running ? 'running' : 'stopped';

  return (
    <div className="network-section">
      {error && <div className="error-banner">{error}</div>}

      <div className="config-item">
        <span className="label">Jumpbox IP</span>
        {editingIP ? (
          <div className="edit-mode">
            <input
              type="text"
              value={tempIP}
              onChange={(e) => setTempIP(e.target.value)}
              className="ip-input"
            />
            <button className="save-btn" onClick={handleSaveIP}>
              Save
            </button>
            <button className="cancel-btn" onClick={handleCancelIP}>
              Cancel
            </button>
          </div>
        ) : (
          <div className="view-mode">
            <span className="value">{network.jumpbox_ip}</span>
            {!isAppliance && (
              <button className="edit-btn" onClick={handleEditIP}>
                Edit
              </button>
            )}
          </div>
        )}
      </div>

      <div className="config-item">
        <span className="label">WireGuard</span>
        <span className="status">
          <DotStatus active={network.wireguard_connected} />
          {wireGuardStatus} · {network.wireguard_peers || 0} peers
          <a href="#" className="link">
            Config ↗
          </a>
        </span>
      </div>

      <div className="config-item">
        <span className="label">Caddy Proxy</span>
        <span className="status">
          <DotStatus active={network.caddy_running} />
          {caddyStatus}
          <a href="#" className="link">
            Config ↗
          </a>
        </span>
      </div>

      <div className="config-item">
        <span className="label">Management IF</span>
        <span className="value">
          {network.management_if?.name || 'eth1'} ·{' '}
          {network.management_if?.ip || '192.168.1.100'} (1GbE)
        </span>
      </div>

      <div className="config-item">
        <span className="label">Data IF</span>
        <span className="value">
          {network.data_if?.name || 'eth0'} · {network.data_if?.ip || '10.0.0.5'}{' '}
          (10GbE)
        </span>
      </div>

      <div className="config-item">
        <span className="label">Mode</span>
        <span className={`mode-badge ${isAppliance ? 'appliance' : 'workstation'}`}>
          [{isAppliance ? 'appliance' : 'workstation'}]
        </span>
      </div>
    </div>
  );
}
