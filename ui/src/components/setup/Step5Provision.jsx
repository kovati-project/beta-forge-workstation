/**
 * Step 5: Container Provisioning
 */

import { useState, useEffect } from 'react';
import { setupAPI } from '../../utils/setupAPI';

export default function Step5Provision({ onComplete }) {
  const [progress, setProgress] = useState(0);
  const [logs, setLogs] = useState([]);
  const [completed, setCompleted] = useState(false);

  useEffect(() => {
    const provision = async () => {
      try {
        const response = await setupAPI.provisionStack();
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const text = decoder.decode(value);
          const lines = text.split('\n');
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const msg = line.slice(6);
              setLogs(prev => [...prev, msg].slice(-50));
              
              if (msg.includes('Progress:')) {
                const match = msg.match(/(\d+)\/(\d+)/);
                if (match) {
                  setProgress(Math.round((parseInt(match[1]) / parseInt(match[2])) * 100));
                }
              }
            }
          }
        }

        setProgress(100);
        setCompleted(true);
      } catch (err) {
        setLogs(prev => [...prev, `Error: ${err.message}`]);
      }
    };

    provision();
  }, []);

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
            {log.includes('✓') ? '✓' : '→'} {log}
          </div>
        ))}
      </div>

      {completed && (
        <div className="step-actions">
          <button className="btn-primary" onClick={() => onComplete()}>
            Next: Validate →
          </button>
        </div>
      )}
    </div>
  );
}
