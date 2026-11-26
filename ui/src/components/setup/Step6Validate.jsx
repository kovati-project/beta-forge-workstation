/**
 * Step 6: Stack Validation
 */

import { useState, useEffect, useCallback } from 'react';
import { setupAPI } from '../../utils/setupAPI';
import { readSSE } from './sseLines';

export default function Step6Validate({ onComplete }) {
  const [checks, setChecks] = useState([]);
  const [status, setStatus] = useState('running'); // running | ok | failed
  const [passed, setPassed] = useState(0);
  const [total, setTotal] = useState(0);

  const validate = useCallback(async () => {
    setStatus('running');
    setChecks([]);
    setPassed(0);
    setTotal(0);
    let ok = false;
    try {
      await readSSE(await setupAPI.validateStack(), (msg) => {
        const match = msg.startsWith('Progress:') && msg.match(/(\d+)\/(\d+)/);
        if (match) {
          setPassed(parseInt(match[1]));
          setTotal(parseInt(match[2]));
          return;
        }
        if (msg.startsWith('✓ Validation complete')) ok = true;
        if (msg.startsWith('✓') || msg.startsWith('✗')) setChecks(prev => [...prev, msg].slice(-60));
      });
    } catch (err) {
      setChecks(prev => [...prev, `✗ Error: ${err.message}`]);
    }
    setStatus(ok ? 'ok' : 'failed');
  }, []);

  useEffect(() => { validate(); }, [validate]);

  return (
    <div className="setup-step">
      <h2>Step 6: Stack Validation</h2>
      <p className="step-description">
        Checking secrets and the core services' health...
      </p>

      <div className="checks-list">
        {checks.map((check, i) => (
          <div key={i} className={`check-item ${check.includes('✓') ? 'passed' : ''}`}>
            {check}
          </div>
        ))}
      </div>

      <div className="validation-summary">
        <p>{status === 'running' ? 'Checking…' : `${passed} / ${total} checks passing`}</p>
        <div className="progress-dots">
          {Array.from({ length: total }).map((_, i) => (
            <span key={i} className={i < passed ? 'dot passed' : 'dot pending'}></span>
          ))}
        </div>
      </div>

      {status === 'ok' && (
        <div className="step-actions">
          <button className="btn-primary" onClick={() => onComplete()}>
            Next: Complete →
          </button>
        </div>
      )}
      {status === 'failed' && (
        <div className="step-actions">
          <button className="btn-primary" onClick={validate}>Re-run checks</button>
        </div>
      )}
    </div>
  );
}
