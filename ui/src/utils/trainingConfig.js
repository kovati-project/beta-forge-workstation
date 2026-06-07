// Training configuration constants

export const VRAM_ESTIMATES = {
  'qwen2.5-32b-instruct': 65,
  'qwen2.5-7b-instruct': 8,
  'qwen3-30b-a3b': 20,
  'llama-70b': 80,
  'mistral-large': 50,
};

export const BASE_MODELS_TEXT = [
  { id: 'qwen2.5-32b-instruct', label: 'Qwen2.5-32B (recommended)', size: '32B' },
  { id: 'qwen2.5-7b-instruct', label: 'Qwen2.5-7B', size: '7B' },
  { id: 'qwen3-30b-a3b', label: 'Qwen3-30B-A3B', size: '30B' },
  { id: 'llama-70b', label: 'Llama 2 70B', size: '70B' },
  { id: 'mistral-large', label: 'Mistral Large', size: '34B' },
];

export const BASE_MODELS_IMAGE = [
  { id: 'sdxl-1.0', label: 'SDXL 1.0 (recommended)', size: 'SDXL' },
  { id: 'sdxl-turbo', label: 'SDXL Turbo', size: 'SDXL' },
  { id: 'sd-3.5-medium', label: 'Stable Diffusion 3.5 Medium', size: 'SD3.5' },
];

export const TEXT_LORA_DEFAULTS = {
  rank: 64,
  alpha: 128,
  lr: '2e-5',
  epochs: 3,
  microBatch: 2,
  gradAccum: 4,
};

export const IMAGE_LORA_DEFAULTS = {
  rank: 32,
  steps: 1000,
  lr: '1e-4',
  resolution: 1024,
  clipSkip: 2,
};

export const TRAINING_PROFILES = {
  text: {
    name: 'training-lora-text',
    gpus: [0, 1, 2, 3],
    vram: 90,
    engine: 'axolotl',
    accent: 'amber',
  },
  image: {
    name: 'training-lora-image',
    gpus: [1, 2],
    vram: 48,
    engine: 'kohya',
    accent: 'purple',
  },
};

export function getVramEstimate(modelId) {
  return VRAM_ESTIMATES[modelId] || 0;
}
