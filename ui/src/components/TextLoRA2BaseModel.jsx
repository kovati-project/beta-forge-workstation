import { useState } from 'react';
import { Btn } from './Btn';
import { BASE_MODELS_TEXT, VRAM_ESTIMATES } from '../utils/trainingConfig';
import './TextLoRA2BaseModel.css';

export function TextLoRA2BaseModel({ onNext, onBack, initialValue }) {
  const [selected, setSelected] = useState(initialValue?.model || 'qwen2.5-32b-instruct');

  const selectedModel = BASE_MODELS_TEXT.find((m) => m.id === selected);
  const vramRequired = VRAM_ESTIMATES[selected] || 0;
  const vramAvailable = 96; // 4× A5500, 24GB each
  const isAvailable = vramRequired <= vramAvailable;

  return (
    <div className="text-lora-base-model">
      <div className="model-header">BASE MODEL</div>

      <div className="model-select-wrapper">
        <select
          className="model-select"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
        >
          {BASE_MODELS_TEXT.map((model) => (
            <option key={model.id} value={model.id}>
              {model.label}
            </option>
          ))}
        </select>
      </div>

      <div className="model-info">
        <div className="info-row">
          <span className="info-label">VRAM estimate:</span>
          <span className="info-value">
            ~{vramRequired} GB for QLoRA (4-bit base)
          </span>
        </div>

        <div className={`info-row ${isAvailable ? 'available' : 'unavailable'}`}>
          <span className="info-label">Available:</span>
          <span className="info-value">
            {vramAvailable} GB via training-lora-text profile{' '}
            <span className="status-icon">{isAvailable ? '✓' : '✗'}</span>
          </span>
        </div>

        <div className="info-hint">
          ⓘ Default: {selectedModel?.label} — pre-configured in axolotl/config.yml
        </div>
      </div>

      <div className="button-row">
        <Btn variant="gray" size="sm" onClick={onBack}>
          ← Back
        </Btn>
        <Btn
          variant="cyan"
          size="sm"
          onClick={() => onNext({ model: selected })}
          disabled={!isAvailable}
        >
          Next →
        </Btn>
      </div>
    </div>
  );
}
