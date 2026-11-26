/**
 * Step 5: Container Provisioning
 *
 * The backend pulls one compose file at a time. "✗" lines are failures; the
 * step only offers Next when the stream ends with "✓ All images provisioned".
 */

import { useState, useEffect, useCallback } from 'react';
import { setupAPI } from '../../utils/setupAPI';
import { readSSE } from './sseLines';

export default function Step5Provision({ onComplete }) {
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState([]);
  const [status, setStatus] = useState('running'); // running | ok | failed

  const provision = useCallback(async () => {
    setStatus('running');
    setProgress(0);
    setLogs([]);
    let ok = false;
    try {
      await readSSE(await setupAPI.provisionStack(), (msg) => {
        setLogs(prev => [...prev, msg].slice(-50));
        const match = msg.startsWith('Progress:') && msg.match(/(\d+)\/(\d+)/);
        if (match) setProgress(Math.round((parseInt(match[1]) / parseInt(match[2])) * 100));
        if (msg.startsWith('✓ All images provisioned')) ok = true;
      });
    } catch (err) {
      setLogs(prev => [...prev, `✗ Error: ${err.message}`]);
    }
    setStatus(ok ? 'ok' : 'failed');
  }, []);

  useEffect(() => { provision(); }, [provision]);

  return (
    <div className="setup-step">
      <h2>Step 5: Container Provisioning</h2>
      <p className="step-description">
        Pulling container images (~15–40 GB depending on configuration)...
      </p>

      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${progress}%` }}></div>
        <span className="progress-text">{progress}%</span>
      </div>

      <div className="logs-display">
        {logs.map((log, i) => (
          <div key={i} className="log-line">
            {log.startsWith('✓') || log.startsWith('✗') ? log : `→ ${log}`}
          </div>
        ))}
      </div>

      {status === 'ok' && (
        <div className="step-actions">
          <button className="btn-primary" onClick={() => onComplete()}>
            Next: Validate →
          </button>
        </div>
      )}
      {status === 'failed' && (
        <div className="step-actions">
          <button className="btn-primary" onClick={provision}>Retry pull</button>
        </div>
      )}
    </div>
  );
}
