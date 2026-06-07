/**
 * Wizard Progress Bar
 */

import './ProgressBar.css';

const STEPS = [
  'Hardware',
  'Profile',
  'Secrets',
  'Network',
  'Provision',
  'Validate',
  'Complete'
];

export default function ProgressBar({ currentStep, completed }) {
  return (
    <div className="wizard-progress-container">
      <div className="wizard-progress-bar">
        {STEPS.map((step, i) => (
          <div
            key={i}
            className={`wizard-progress-step ${
              i === currentStep ? 'active' : ''
            } ${i < currentStep || completed.includes(i) ? 'completed' : ''}`}
          >
            <div className="step-circle">
              {i < currentStep || completed.includes(i) ? '✓' : i + 1}
            </div>
            <div className="step-label">{step}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
