import { Tag } from './Tag';
import './TrainingModeSelector.css';

export function TrainingModeSelector({ onSelect }) {
  return (
    <div className="training-mode-selector">
      <div className="mode-header">Choose a Training Workflow</div>

      <div className="mode-cards">
        {/* Text LoRA */}
        <button
          className="mode-card mode-text"
          onClick={() => onSelect('text')}
        >
          <div className="mode-icon">◉</div>
          <div className="mode-title">Text Model</div>
          <div className="mode-subtitle">LLM LoRA via<br />Axolotl / Unsloth</div>
          <div className="mode-gpu-tag">
            <Tag variant="amber">GPU 0+1+2+3</Tag>
          </div>
        </button>

        {/* Image LoRA */}
        <button
          className="mode-card mode-image"
          onClick={() => onSelect('image')}
        >
          <div className="mode-icon">◈</div>
          <div className="mode-title">Image Model</div>
          <div className="mode-subtitle">Diffusion LoRA via<br />Kohya_ss</div>
          <div className="mode-gpu-tag">
            <Tag variant="purple">GPU 1+2</Tag>
          </div>
        </button>
      </div>
    </div>
  );
}
