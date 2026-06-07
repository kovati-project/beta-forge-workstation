/**
 * Step 2: Profile Selection
 */

import { useState, useEffect } from 'react';
import { setupAPI } from '../../utils/setupAPI';

export default function Step2Profile({ onComplete, onData, hardware }) {
  const [loading, setLoading] = useState(true);
  const [recommended, setRecommended] = useState(null);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    const recommend = async () => {
      try {
        const data = await setupAPI.recommendProfile(hardware);
        setRecommended(data.recommended);
        setSelected(data.recommended);
        onData({ profile: data.recommended });
      } catch (err) {
        console.error('Profile recommendation failed:', err);
      } finally {
        setLoading(false);
      }
    };

    recommend();
  }, [hardware, onData]);

  const profiles = [
    { id: 'inference-small', name: 'Single GPU', desc: '7B-13B models, lowest latency' },
    { id: 'inference-pair-a', name: 'NVLink Pair A', desc: '32B-40B models, fast inference' },
    { id: 'inference-pair-b', name: 'NVLink Pair B', desc: '32B-40B models, fast inference' },
    { id: 'inference-4gpu', name: 'All 4 GPUs', desc: 'Tensor parallel 70B+ models' },
    { id: 'dual-stack', name: 'Dual Stack', desc: 'Two simultaneous 32B models' },
  ];

  return (
    <div className="setup-step">
      <h2>Step 2: Recommended Profile</h2>
      
      {loading ? (
        <p>Analyzing hardware...</p>
      ) : (
        <>
          <p className="step-description">
            Based on your hardware ({hardware.total_vram_gb}GB VRAM, {hardware.gpus.length} GPU{hardware.gpus.length > 1 ? 's' : ''}),
            we recommend:
          </p>

          <div className="profiles-grid">
            {profiles.map(p => (
              <div
                key={p.id}
                className={`profile-card ${p.id === recommended ? 'recommended' : ''} ${p.id === selected ? 'selected' : ''}`}
                onClick={() => setSelected(p.id)}
              >
                {p.id === recommended && <span className="badge">★ Recommended</span>}
                <h3>{p.name}</h3>
                <p>{p.desc}</p>
              </div>
            ))}
          </div>

          <div className="step-actions">
            <button className="btn-primary" onClick={() => onComplete()}>
              Next: Secrets →
            </button>
          </div>
        </>
      )}
    </div>
  );
}
