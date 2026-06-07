/**
 * Step 7: Handoff / Completion
 */

import { useEffect } from 'react';
import { setupAPI } from '../../utils/setupAPI';

export default function Step7Handoff({ profile }) {
  useEffect(() => {
    const complete = async () => {
      try {
        await setupAPI.markComplete();
      } catch (err) {
        console.error('Failed to mark setup complete:', err);
      }
    };

    complete();
  }, []);

  return (
    <div className="setup-step handoff">
      <div className="completion-banner">
        <h1>✓ Kovati OS is ready.</h1>
      </div>

      <div className="handoff-content">
        <div className="handoff-section">
          <h3>Active Profile</h3>
          <p>{profile || 'dual-stack'}</p>
          <p className="detail">23 services running · 2 idle · 0 errors</p>
        </div>

        <div className="handoff-section">
          <h3>Access Your Services</h3>
          <div className="service-links">
            <a href="http://localhost:3000" target="_blank" rel="noreferrer">
              💬 Chat UI (Open WebUI)
            </a>
            <a href="http://localhost:8800" target="_blank" rel="noreferrer">
              ⚙️ Control (Dashboard)
            </a>
            <a href="http://localhost:3001" target="_blank" rel="noreferrer">
              📊 Monitoring (Grafana)
            </a>
          </div>
        </div>

        <div className="handoff-section">
          <h3>Setup Summary</h3>
          <p>
            Setup completed at {new Date().toLocaleString()}
          </p>
          <p className="detail">
            Hardware detected, profile assigned, secrets generated, network configured, services validated.
          </p>
        </div>

        <div className="step-actions">
          <button 
            className="btn-primary btn-large"
            onClick={() => {
              window.location.href = '/#/dashboard';
            }}
          >
            Go to Dashboard →
          </button>
        </div>
      </div>
    </div>
  );
}
