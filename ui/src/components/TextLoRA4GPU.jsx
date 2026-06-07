import { useState } from 'react';
import { Btn } from './Btn';
import { Tag } from './Tag';
import { TRAINING_PROFILES } from '../utils/trainingConfig';
import './TextLoRA4GPU.css';

export function TextLoRA4GPU({ onNext, onBack, initialValue }) {
  const [acknowledged, setAcknowledged] = useState(false);
  const profile = TRAINING_PROFILES.text;

  return (
    <div className="text-lora-gpu">
      <div className="gpu-header">GPU ASSIGNMENT</div>

      <div className="gpu-info">
        <div className="info-row">
          <span className="info-label">Recommended:</span>
          <span className="info-value">{profile.name}</span>
        </div>
        <div className="info-row">
          <span className="info-label">GPU Configuration:</span>
          <span className="info-value">All 4 GPUs · FSDP · {profile.vram} GB VRAM</span>
        </div>
      </div>

      {/* Mini GPU Diagram */}
      <div className="gpu-diagram">
        {[0, 1, 2, 3].map((gpu) => (
          <div key={gpu} className="gpu-mini-box">
            {gpu}■
          </div>
        ))}
        <div className="bridge-line">
          Bridge A ━━━━━ Bridge B ━━━━━
        </div>
      </div>

      {/* Warning */}
      <div className="warning-box">
        <span className="warning-icon">⚠</span>
        <div className="warning-text">
          <div className="warning-title">This will stop active services:</div>
          <div className="warning-services">
            • vllm-pair-a
            <br />• ollama
          </div>
        </div>
      </div>

      {/* Acknowledgement */}
      <div className="acknowledge-row">
        <input
          type="checkbox"
          id="ack-checkbox"
          checked={acknowledged}
          onChange={(e) => setAcknowledged(e.target.checked)}
          className="ack-checkbox"
        />
        <label htmlFor="ack-checkbox" className="ack-label">
          I understand active inference will be interrupted
        </label>
      </div>

      <div className="button-row">
        <Btn variant="gray" size="sm" onClick={onBack}>
          ← Back
        </Btn>
        <Btn
          variant="cyan"
          size="sm"
          onClick={() => onNext({ profile: profile.name })}
          disabled={!acknowledged}
        >
          Next →
        </Btn>
      </div>
    </div>
  );
}
