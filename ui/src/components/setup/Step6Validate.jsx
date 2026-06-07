/**
 * Step 6: Stack Validation
 */

import { useState, useEffect } from 'react';
import { setupAPI } from '../../utils/setupAPI';

export default function Step6Validate({ onComplete }) {
  const [checks, setChecks] = useState([]);
  const [completed, setCompleted] = useState(false);
  const [passed, setPassed] = useState(0);

  useEffect(() => {
    const validate = async () => {
      try {
        const response = await setupAPI.validateStack();
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let passCount = 0;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const text = decoder.decode(value);
          const lines = text.split('\n');
          
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const msg = line.slice(6);
              if (msg.includes('✓')) {
                passCount++;
                setPassed(passCount);
              }
              setChecks(prev => [...prev, msg].slice(-30));
            }
          }
        }

        setCompleted(true);
      } catch (err) {
        setChecks(prev => [...prev, `Error: ${err.message}`]);
      }
    };

    validate();
  }, []);

  return (
    <div className="setup-step">
      <h2>Step 6: Stack Validation</h2>
      <p className="step-description">
        Starting services and running health checks...
      </p>

      <div className="checks-list">
        {checks.map((check, i) => (
          <div key={i} className={`check-item ${check.includes('✓') ? 'passed' : ''}`}>
            {check}
          </div>
        ))}
      </div>

      <div className="validation-summary">
        <p>{passed} / 25 checks passing</p>
        <div className="progress-dots">
          {Array.from({ length: 25 }).map((_, i) => (
            <span key={i} className={i < passed ? 'dot passed' : 'dot pending'}></span>
          ))}
        </div>
      </div>

      {completed && (
        <div className="step-actions">
          <button className="btn-primary" onClick={() => onComplete()}>
            Next: Complete →
          </button>
        </div>
      )}
    </div>
  );
}
