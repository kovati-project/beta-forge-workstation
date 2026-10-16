import { useState, useEffect } from 'react';
import { getSecrets, rotateSecret, rotateAllSecrets } from '../utils/settingsAPI';
import './SecretsSection.css';

export function SecretsSection({ isAppliance }) {
  const [secrets, setSecrets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAll, setShowAll] = useState(false);
  const [rotating, setRotating] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    const loadSecrets = async () => {
      try {
        const data = await getSecrets();
        setSecrets(data.secrets || []);
      } catch (err) {
        setError(`Could not load secrets: ${err.message}`);
      } finally {
        setLoading(false);
      }
    };
    loadSecrets();
  }, []);

  const failedServices = (result) =>
    (result.services || []).filter((s) => s.status === 'error').map((s) => s.service);

  const handleRotate = async (key) => {
    if (!window.confirm(`Rotate ${key}? Running services that use it will be recreated.`)) return;

    setRotating(key);
    setError(null);
    try {
      const result = await rotateSecret(key);
      if (result.status !== 'rotated') {
        setError(`${key} was rotated, but recreating ${failedServices(result).join(', ')} failed. Recreate them manually.`);
      }
      // Reload secrets after rotation
      const data = await getSecrets();
      setSecrets(data.secrets || []);
    } catch (err) {
      setError(`Failed to rotate ${key}: ${err.message}`);
    } finally {
      setRotating(null);
    }
  };

  const handleRotateAll = async () => {
    const rotatable = secrets.filter((s) => s.rotatable);
    if (!window.confirm(`Rotate ${rotatable.length} secrets? Running services that use them will be recreated.`)) return;

    const confirmation = prompt(
      'This will temporarily restart the affected services. Type "rotate all" to confirm:'
    );
    if (confirmation !== 'rotate all') return;

    setRotating('all');
    setError(null);
    try {
      const result = await rotateAllSecrets();
      if (result.status !== 'rotated') {
        const failedKeys = (result.failed || []).map((f) => f.key);
        const parts = [];
        if (failedKeys.length) parts.push(`not rotated: ${failedKeys.join(', ')}`);
        if (failedServices(result).length) parts.push(`recreate failed: ${failedServices(result).join(', ')}`);
        setError(`Rotation incomplete (${parts.join('; ')}).`);
      }
      const data = await getSecrets();
      setSecrets(data.secrets || []);
    } catch (err) {
      setError(`Failed to rotate all secrets: ${err.message}`);
    } finally {
      setRotating(null);
    }
  };

  if (isAppliance) {
    return (
      <div className="secrets-section appliance">
        <p>Secrets managed by administrator. Contact your administrator to rotate keys.</p>
      </div>
    );
  }

  if (loading) {
    return <div className="secrets-section loading">Loading secrets...</div>;
  }

  const displayedSecrets = showAll ? secrets : secrets.slice(0, 8);
  const hiddenCount = secrets.length - 8;

  return (
    <div className="secrets-section">
      {error && <div className="error-banner">{error}</div>}

      <table className="secrets-table">
        <thead>
          <tr>
            <th>Key Name</th>
            <th>Last Rotated</th>
            <th>Affects</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {displayedSecrets.length === 0 ? (
            <tr>
              <td colSpan="4" className="empty">
                No secrets found
              </td>
            </tr>
          ) : (
            displayedSecrets.map((secret) => (
              <tr key={secret.key}>
                <td className="key-name">{secret.key}</td>
                <td className="last-rotated">{secret.last_rotated || '—'}</td>
                <td className="affects">
                  {secret.affects?.join(', ') || '—'}
                </td>
                <td className="action">
                  <button
                    className="rotate-btn"
                    onClick={() => handleRotate(secret.key)}
                    disabled={rotating !== null || !secret.rotatable}
                    title={secret.rotatable ? undefined : secret.note}
                  >
                    {rotating === secret.key ? (
                      <>
                        ⟳ Rotating...
                      </>
                    ) : (
                      'Rotate'
                    )}
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      {hiddenCount > 0 && !showAll && (
        <div className="show-more">
          + {hiddenCount} more{' '}
          <button className="show-all-btn" onClick={() => setShowAll(true)}>
            [Show All]
          </button>
        </div>
      )}

      <button
        className="rotate-all-btn"
        onClick={handleRotateAll}
        disabled={rotating !== null || secrets.length === 0}
      >
        {rotating === 'all' ? '⟳ Rotating all...' : 'Rotate All Secrets'}
      </button>
    </div>
  );
}
