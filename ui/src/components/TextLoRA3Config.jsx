import { useState } from 'react';
import { Btn } from './Btn';
import { TEXT_LORA_DEFAULTS } from '../utils/trainingConfig';
import './TextLoRA3Config.css';

export function TextLoRA3Config({ onNext, onBack, initialValue }) {
  const [config, setConfig] = useState({
    rank: initialValue?.rank ?? TEXT_LORA_DEFAULTS.rank,
    alpha: initialValue?.alpha ?? TEXT_LORA_DEFAULTS.alpha,
    lr: initialValue?.lr ?? TEXT_LORA_DEFAULTS.lr,
    epochs: initialValue?.epochs ?? TEXT_LORA_DEFAULTS.epochs,
    microBatch: initialValue?.microBatch ?? TEXT_LORA_DEFAULTS.microBatch,
    gradAccum: initialValue?.gradAccum ?? TEXT_LORA_DEFAULTS.gradAccum,
  });

  const effectiveBatchSize = config.microBatch * config.gradAccum * 4; // 4 GPUs

  const handleSliderChange = (field, value) => {
    setConfig((prev) => ({ ...prev, [field]: parseInt(value) }));
  };

  const handleInputChange = (field, value) => {
    if (field === 'lr') {
      setConfig((prev) => ({ ...prev, [field]: value }));
    } else {
      setConfig((prev) => ({
        ...prev,
        [field]: Math.max(1, parseInt(value) || 0),
      }));
    }
  };

  return (
    <div className="text-lora-config">
      <div className="config-header">LoRA CONFIG</div>

      <div className="config-grid">
        {/* LoRA Rank */}
        <div className="config-field">
          <label className="field-label">LoRA Rank</label>
          <div className="slider-group">
            <span className="slider-min">8</span>
            <input
              type="range"
              min="8"
              max="128"
              step="8"
              value={config.rank}
              onChange={(e) => handleSliderChange('rank', e.target.value)}
              className="slider"
            />
            <span className="slider-max">128</span>
          </div>
          <div className="field-value">{config.rank}</div>
        </div>

        {/* LoRA Alpha */}
        <div className="config-field">
          <label className="field-label">LoRA Alpha</label>
          <div className="slider-group">
            <span className="slider-min">16</span>
            <input
              type="range"
              min="16"
              max="256"
              step="16"
              value={config.alpha}
              onChange={(e) => handleSliderChange('alpha', e.target.value)}
              className="slider"
            />
            <span className="slider-max">256</span>
          </div>
          <div className="field-value">{config.alpha}</div>
        </div>

        {/* Learning Rate */}
        <div className="config-field">
          <label className="field-label">Learning Rate</label>
          <input
            type="text"
            value={config.lr}
            onChange={(e) => handleInputChange('lr', e.target.value)}
            placeholder="e.g. 2e-5"
            className="text-input"
          />
        </div>

        {/* Epochs */}
        <div className="config-field">
          <label className="field-label">Epochs</label>
          <input
            type="number"
            min="1"
            max="20"
            value={config.epochs}
            onChange={(e) => handleInputChange('epochs', e.target.value)}
            className="number-input"
          />
        </div>

        {/* Micro Batch Size */}
        <div className="config-field">
          <label className="field-label">Micro Batch Size</label>
          <input
            type="number"
            min="1"
            max="8"
            value={config.microBatch}
            onChange={(e) => handleInputChange('microBatch', e.target.value)}
            className="number-input"
          />
        </div>

        {/* Gradient Accumulation */}
        <div className="config-field">
          <label className="field-label">Gradient Accumulation</label>
          <input
            type="number"
            min="1"
            max="16"
            value={config.gradAccum}
            onChange={(e) => handleInputChange('gradAccum', e.target.value)}
            className="number-input"
          />
        </div>
      </div>

      <div className="effective-batch">
        <span className="batch-label">Effective batch size:</span>
        <span className="batch-value">
          {config.microBatch} × {config.gradAccum} × 4 = {effectiveBatchSize}
        </span>
      </div>

      <div className="button-row">
        <Btn variant="gray" size="sm" onClick={onBack}>
          ← Back
        </Btn>
        <Btn
          variant="cyan"
          size="sm"
          onClick={() => onNext({ lora_config: config })}
        >
          Next →
        </Btn>
      </div>
    </div>
  );
}
