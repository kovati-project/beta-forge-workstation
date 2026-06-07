import { useState } from 'react';
import { Btn } from './Btn';
import { ProgressIndicator } from './ProgressIndicator';
import './ImageLoRAWorkflow.css';

const STEPS = ['Dataset', 'Annotation', 'Config', 'GPU Assign', 'Launch'];

export function ImageLoRAWorkflow({ onSuccess, onBack }) {
  const [step, setStep] = useState(1);
  const [config, setConfig] = useState({
    dataset: null,
    model: 'sdxl-1.0',
    rank: 32,
    steps: 1000,
    lr: '1e-4',
    resolution: 1024,
  });

  const handleNext = () => {
    setStep((prev) => Math.min(STEPS.length, prev + 1));
  };

  const handleStepBack = () => {
    setStep((prev) => Math.max(1, prev - 1));
  };

  const handleLaunch = () => {
    onSuccess?.(config);
  };

  return (
    <div className="image-lora-workflow">
      <ProgressIndicator currentStep={step} totalSteps={STEPS.length} stepNames={STEPS} />

      <div className="workflow-content">
        {step === 1 && (
          <div className="workflow-step">
            <div className="step-header">DATASET</div>
            <p style={{ color: 'var(--text3)', fontSize: '10px' }}>
              Upload images or browse MinIO /data/training/images/
            </p>
            <div style={{ marginTop: '12px' }}>
              <Btn variant="cyan" size="sm" onClick={handleNext}>
                Continue →
              </Btn>
            </div>
          </div>
        )}

        {step === 2 && (
          <div className="workflow-step">
            <div className="step-header">ANNOTATION (OPTIONAL)</div>
            <p style={{ color: 'var(--text3)', fontSize: '10px' }}>
              Open Label Studio for image captioning
            </p>
            <div style={{ marginTop: '12px', display: 'flex', gap: '8px' }}>
              <Btn variant="gray" size="sm" onClick={handleStepBack}>
                ← Back
              </Btn>
              <Btn variant="cyan" size="sm" onClick={handleNext}>
                Continue →
              </Btn>
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="workflow-step">
            <div className="step-header">TRAINING CONFIG</div>
            <div className="config-fields">
              <div className="config-item">
                <label>Base Model:</label>
                <select value={config.model} onChange={(e) => setConfig({...config, model: e.target.value})}>
                  <option value="sdxl-1.0">SDXL 1.0 (recommended)</option>
                  <option value="sdxl-turbo">SDXL Turbo</option>
                  <option value="sd-3.5-medium">SD 3.5 Medium</option>
                </select>
              </div>
              <div className="config-item">
                <label>LoRA Rank:</label>
                <input type="number" min="8" max="128" value={config.rank} onChange={(e) => setConfig({...config, rank: parseInt(e.target.value)})} />
              </div>
              <div className="config-item">
                <label>Training Steps:</label>
                <input type="number" min="100" max="5000" value={config.steps} onChange={(e) => setConfig({...config, steps: parseInt(e.target.value)})} />
              </div>
              <div className="config-item">
                <label>Learning Rate:</label>
                <input type="text" value={config.lr} onChange={(e) => setConfig({...config, lr: e.target.value})} placeholder="1e-4" />
              </div>
              <div className="config-item">
                <label>Resolution:</label>
                <select value={config.resolution} onChange={(e) => setConfig({...config, resolution: parseInt(e.target.value)})}>
                  <option value="1024">1024</option>
                  <option value="768">768</option>
                  <option value="512">512</option>
                </select>
              </div>
            </div>
            <div style={{ marginTop: '12px', display: 'flex', gap: '8px' }}>
              <Btn variant="gray" size="sm" onClick={handleStepBack}>
                ← Back
              </Btn>
              <Btn variant="cyan" size="sm" onClick={handleNext}>
                Continue →
              </Btn>
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="workflow-step">
            <div className="step-header">GPU ASSIGNMENT</div>
            <p style={{ color: 'var(--text3)', fontSize: '10px' }}>
              Using training-lora-image (GPU 1+2) · GPU 0+3 remain available for inference
            </p>
            <div style={{ marginTop: '12px', display: 'flex', gap: '8px' }}>
              <Btn variant="gray" size="sm" onClick={handleStepBack}>
                ← Back
              </Btn>
              <Btn variant="cyan" size="sm" onClick={handleNext}>
                Continue →
              </Btn>
            </div>
          </div>
        )}

        {step === 5 && (
          <div className="workflow-step">
            <div className="step-header">LAUNCH</div>
            <div className="summary-box">
              <div>Model: {config.model}</div>
              <div>Rank: {config.rank}</div>
              <div>Steps: {config.steps}</div>
              <div>LR: {config.lr}</div>
            </div>
            <div style={{ marginTop: '12px', display: 'flex', gap: '8px' }}>
              <Btn variant="gray" size="sm" onClick={handleStepBack}>
                ← Back
              </Btn>
              <Btn variant="purple" size="sm" onClick={handleLaunch}>
                Launch Training
              </Btn>
            </div>
          </div>
        )}
      </div>

      {step === 1 && (
        <button className="workflow-back-btn" onClick={onBack}>
          ← Back to mode selection
        </button>
      )}
    </div>
  );
}
