import { useState } from 'react';
import { Btn } from './Btn';
import { startTraining, activateProfile } from '../utils/trainingAPI';
import { useApp } from '../context/AppContext';
import './TextLoRA5Launch.css';

export function TextLoRA5Launch({ onNext, onBack, config, onLaunchSuccess }) {
  const { state } = useApp();
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState(null);

  const handleLaunch = async () => {
    setLaunching(true);
    setError(null);

    try {
      // Step 1: Activate training profile
      await activateProfile(config.profile);

      // Wait for switching to complete (poll status)
      let attempts = 0;
      while (state.switching && attempts < 60) {
        await new Promise((resolve) => setTimeout(resolve, 1000));
        attempts++;
      }

      // Step 2: Start training
      const trainingConfig = {
        engine: 'axolotl',
        model: config.model,
        dataset_path: config.dataset,
        lora_config: config.lora_config,
      };

      await startTraining(trainingConfig);

      // Success - transition to live view
      onLaunchSuccess?.(trainingConfig);
    } catch (err) {
      setError(err.message || 'Failed to start training');
    } finally {
      setLaunching(false);
    }
  };

  // Estimate duration (very rough)
  const estimatedMinutes = (config.lora_config?.epochs || 3) * 50; // ~50 min per epoch
  const hours = Math.floor(estimatedMinutes / 60);
  const minutes = estimatedMinutes % 60;

  return (
    <div className="text-lora-launch">
      <div className="launch-header">READY TO LAUNCH</div>

      <div className="summary-box">
        <div className="summary-section">
          <div className="summary-label">Model:</div>
          <div className="summary-value">{config.model}</div>
        </div>

        <div className="summary-section">
          <div className="summary-label">Dataset:</div>
          <div className="summary-value">{config.dataset}</div>
        </div>

        <div className="summary-section">
          <div className="summary-label">LoRA Config:</div>
          <div className="summary-value">
            r={config.lora_config?.rank} α={config.lora_config?.alpha} · LR=
            {config.lora_config?.lr} · {config.lora_config?.epochs} epochs
          </div>
        </div>

        <div className="summary-section">
          <div className="summary-label">GPU:</div>
          <div className="summary-value">{config.profile} (all 4, FSDP)</div>
        </div>

        <div className="summary-section">
          <div className="summary-label">Est. duration:</div>
          <div className="summary-value">
            ~{hours}h {minutes}m
          </div>
        </div>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="button-row">
        <Btn variant="gray" size="sm" onClick={onBack} disabled={launching}>
          ← Back
        </Btn>
        <Btn
          variant="amber"
          size="sm"
          onClick={handleLaunch}
          disabled={launching}
        >
          {launching ? 'Starting...' : 'Start Training'}
        </Btn>
      </div>
    </div>
  );
}
