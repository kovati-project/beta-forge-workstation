/**
 * Step 3: Secret Generation
 */

import { useState, useEffect } from 'react';
import { setupAPI } from '../../utils/setupAPI';

export default function Step3Secrets({ onComplete, onData }) {
  const [loading, setLoading] = useState(true);
  const [secrets, setSecrets] = useState(null);
  const [checked, setChecked] = useState(false);
  const [revealed, setRevealed] = useState(false);

  useEffect(() => {
    const generate = async () => {
      try {
        const data = await setupAPI.generateSecrets();
        setSecrets(data.secrets);
        onData(data);
      } catch (err) {
        console.error('Secret generation failed:', err);
      } finally {
        setLoading(false);
      }
    };

    generate();
  }, [onData]);

  const downloadSecrets = () => {
    const content = Object.entries(secrets)
      .map(([k, v]) => `${k}=${v}`)
      .join('\n');
    
    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = '.env.backup';
    a.click();
  };

  return (
    <div className="setup-step">
      <h2>Step 3: Secret Generation</h2>

      {loading ? (
        <p>Generating secrets...</p>
      ) : (
        <>
          <p className="step-description">
            14 cryptographic secrets will be generated and written to docker/.env
          </p>

          <div className="secrets-list">
            {Object.entries(secrets).map(([key, value]) => (
              <div key={key} className="secret-item">
                <span className="secret-key">{key}</span>
                <code className={revealed ? 'revealed' : 'redacted'}>
                  {revealed ? value : '••••••••••••••••••••••••••'}
                </code>
              </div>
            ))}
          </div>

          <button className="btn-secondary" onClick={() => setRevealed(!revealed)}>
            {revealed ? 'Hide Values' : 'Reveal All'}
          </button>

          <button className="btn-secondary" onClick={downloadSecrets}>
            ⬇ Download .env Backup
          </button>

          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) => setChecked(e.target.checked)}
            />
            I have saved a secure backup of my secrets
          </label>

          <div className="step-actions">
            <button
              className="btn-primary"
              onClick={() => onComplete()}
              disabled={!checked}
            >
              Next: Network →
            </button>
          </div>
        </>
      )}
    </div>
  );
}
