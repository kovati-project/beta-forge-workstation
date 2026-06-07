import './ProgressIndicator.css';

export function ProgressIndicator({ currentStep, totalSteps, stepNames }) {
  return (
    <div className="progress-indicator">
      {stepNames.map((name, idx) => {
        const stepNum = idx + 1;
        let status = 'future';
        if (stepNum < currentStep) status = 'completed';
        if (stepNum === currentStep) status = 'current';

        return (
          <div key={stepNum} className={`progress-step progress-${status}`}>
            <span className="step-number">{stepNum}</span>
            <span className="step-name">{name}</span>
            {stepNum < totalSteps && <div className="step-connector" />}
          </div>
        );
      })}
    </div>
  );
}
