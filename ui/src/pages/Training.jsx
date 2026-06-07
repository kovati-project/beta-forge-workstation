import { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { useTrainingStatus } from '../hooks/useTraining';
import { TrainingModeSelector } from '../components/TrainingModeSelector';
import { TextLoRAWorkflow } from '../components/TextLoRAWorkflow';
import { ImageLoRAWorkflow } from '../components/ImageLoRAWorkflow';
import { LiveTrainingView } from '../components/LiveTrainingView';
import './Training.css';

export function Training() {
  const [mode, setMode] = useState(null); // 'text' | 'image' | null
  const [isLive, setIsLive] = useState(false);
  const [currentConfig, setCurrentConfig] = useState(null);
  const { status } = useTrainingStatus();

  // Check if training is active on mount
  useEffect(() => {
    if (status?.running) {
      setIsLive(true);
      setMode(status.engine === 'axolotl' ? 'text' : 'image');
      setCurrentConfig(status.config);
    }
  }, [status?.running]);

  const handleModeSelect = (selectedMode) => {
    setMode(selectedMode);
  };

  const handleWorkflowSuccess = (config) => {
    setCurrentConfig(config);
    setIsLive(true);
  };

  const handleStopTraining = () => {
    setIsLive(false);
    setMode(null);
    setCurrentConfig(null);
  };

  return (
    <div className="training-page">
      {isLive && currentConfig ? (
        <LiveTrainingView
          mode={mode}
          config={currentConfig}
          onStop={handleStopTraining}
        />
      ) : mode === null ? (
        <TrainingModeSelector onSelect={handleModeSelect} />
      ) : mode === 'text' ? (
        <TextLoRAWorkflow
          onSuccess={handleWorkflowSuccess}
          onBack={() => setMode(null)}
        />
      ) : (
        <ImageLoRAWorkflow
          onSuccess={handleWorkflowSuccess}
          onBack={() => setMode(null)}
        />
      )}
    </div>
  );
}
