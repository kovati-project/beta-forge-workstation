/**
 * First-Boot Wizard Container
 */

import { useState, useEffect } from 'react';
import ProgressBar from './ProgressBar';
import Step1Hardware from './Step1Hardware';
import Step2Profile from './Step2Profile';
import Step3Secrets from './Step3Secrets';
import Step4Network from './Step4Network';
import Step5Provision from './Step5Provision';
import Step6Validate from './Step6Validate';
import Step7Handoff from './Step7Handoff';
import './SetupWizard.css';

const STEPS = [
  { name: 'Hardware', component: Step1Hardware },
  { name: 'Profile', component: Step2Profile },
  { name: 'Secrets', component: Step3Secrets },
  { name: 'Network', component: Step4Network },
  { name: 'Provision', component: Step5Provision },
  { name: 'Validate', component: Step6Validate },
  { name: 'Complete', component: Step7Handoff },
];

export default function SetupWizard() {
  const [currentStep, setCurrentStep] = useState(0);
  const [completed, setCompleted] = useState([]);
  const [stepData, setStepData] = useState({});

  // Restore state from sessionStorage
  useEffect(() => {
    const savedStep = sessionStorage.getItem('setup_step');
    const savedData = sessionStorage.getItem('setup_data');
    
    if (savedStep) {
      setCurrentStep(parseInt(savedStep));
    }
    if (savedData) {
      setStepData(JSON.parse(savedData));
    }
  }, []);

  const handleStepComplete = () => {
    // Mark step as completed
    const newCompleted = [...completed, currentStep];
    setCompleted(newCompleted);

    // Move to next step
    if (currentStep < STEPS.length - 1) {
      const nextStep = currentStep + 1;
      setCurrentStep(nextStep);
      sessionStorage.setItem('setup_step', nextStep.toString());
    }
  };

  const handleStepData = (data) => {
    const newData = { ...stepData, ...data };
    setStepData(newData);
    sessionStorage.setItem('setup_data', JSON.stringify(newData));
  };

  const CurrentStepComponent = STEPS[currentStep].component;

  return (
    <div className="setup-wizard-container">
      <ProgressBar currentStep={currentStep} completed={completed} />

      <div className="setup-wizard-main">
        <CurrentStepComponent
          onComplete={handleStepComplete}
          onData={handleStepData}
          {...stepData}
        />
      </div>
    </div>
  );
}
