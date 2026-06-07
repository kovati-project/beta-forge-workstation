import { useState } from 'react';
import { ProgressIndicator } from './ProgressIndicator';
import { TextLoRA1Dataset } from './TextLoRA1Dataset';
import { TextLoRA2BaseModel } from './TextLoRA2BaseModel';
import { TextLoRA3Config } from './TextLoRA3Config';
import { TextLoRA4GPU } from './TextLoRA4GPU';
import { TextLoRA5Launch } from './TextLoRA5Launch';
import './TextLoRAWorkflow.css';

const STEPS = ['Dataset', 'Base Model', 'LoRA Config', 'GPU Assign', 'Launch'];

export function TextLoRAWorkflow({ onSuccess, onBack }) {
  const [step, setStep] = useState(1);
  const [config, setConfig] = useState({
    dataset: null,
    model: null,
    lora_config: null,
    profile: null,
  });

  const handleNext = (data) => {
    setConfig((prev) => ({ ...prev, ...data }));
    setStep((prev) => prev + 1);
  };

  const handleBack = () => {
    setStep((prev) => Math.max(1, prev - 1));
  };

  const handleLaunchSuccess = (trainingConfig) => {
    onSuccess?.(trainingConfig);
  };

  return (
    <div className="text-lora-workflow">
      <ProgressIndicator currentStep={step} totalSteps={STEPS.length} stepNames={STEPS} />

      <div className="workflow-content">
        {step === 1 && <TextLoRA1Dataset onNext={handleNext} initialValue={config} />}
        {step === 2 && (
          <TextLoRA2BaseModel
            onNext={handleNext}
            onBack={handleBack}
            initialValue={config}
          />
        )}
        {step === 3 && (
          <TextLoRA3Config
            onNext={handleNext}
            onBack={handleBack}
            initialValue={config}
          />
        )}
        {step === 4 && (
          <TextLoRA4GPU
            onNext={handleNext}
            onBack={handleBack}
            initialValue={config}
          />
        )}
        {step === 5 && (
          <TextLoRA5Launch
            onNext={handleNext}
            onBack={handleBack}
            config={config}
            onLaunchSuccess={handleLaunchSuccess}
          />
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
