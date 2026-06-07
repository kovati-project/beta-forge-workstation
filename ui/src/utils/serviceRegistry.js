export const SERVICE_GROUPS = [
  {
    name: 'Text Inference',
    services: ['vllm-pair-a', 'ollama', 'vllm-pair-b', 'vllm-4gpu'],
  },
  {
    name: 'Image Studio',
    services: ['comfyui', 'invokeai', 'real-esrgan', 'rembg'],
  },
  {
    name: 'Training',
    services: ['kohya', 'axolotl', 'unsloth', 'label-studio', 'jupyterlab'],
  },
  {
    name: 'Agentic & Workflow',
    services: ['n8n', 'dify', 'openhands', 'mcp-filesystem', 'mcp-browser', 'mcp-code-exec', 'mcp-fetch'],
  },
  {
    name: 'Voice I/O',
    services: ['faster-whisper', 'piper-tts'],
  },
  {
    name: 'Chat UI',
    services: ['open-webui', 'searxng'],
  },
  {
    name: 'Storage & Vector',
    services: ['minio', 'qdrant', 'postgres', 'langfuse'],
  },
  {
    name: 'Observability',
    services: ['prometheus', 'grafana', 'dcgm-exporter', 'node-exporter', 'cadvisor'],
  },
  {
    name: 'Auth & Security',
    services: ['authentik'],
  },
];

export const SERVICE_URLS = {
  'vllm-pair-a': 'http://{host}:8000',
  'vllm-pair-b': 'http://{host}:8001',
  'vllm-4gpu': 'http://{host}:8002',
  'ollama': 'http://{host}:11434',
  'comfyui': 'http://{host}:8188',
  'invokeai': 'http://{host}:9090',
  'real-esrgan': 'http://{host}:8686',
  'rembg': 'http://{host}:5000',
  'kohya': 'http://{host}:7860',
  'axolotl': 'http://{host}:6006',
  'unsloth': 'http://{host}:8889',
  'label-studio': 'http://{host}:8080',
  'jupyterlab': 'http://{host}:8888',
  'n8n': 'http://{host}:5678',
  'dify': 'http://{host}:80',
  'openhands': 'http://{host}:3000',
  'faster-whisper': 'http://{host}:5000',
  'piper-tts': 'http://{host}:5001',
  'open-webui': 'http://{host}:3000',
  'searxng': 'http://{host}:8888',
  'minio': 'http://{host}:9000',
  'minio-console': 'http://{host}:9001',
  'qdrant': 'http://{host}:6333',
  'postgres': 'http://{host}:5432',
  'langfuse': 'http://{host}:3002',
  'prometheus': 'http://{host}:9091',
  'grafana': 'http://{host}:3001',
  'authentik': 'http://{host}:9080',
};

export function getServiceUrl(serviceName) {
  const baseUrl = SERVICE_URLS[serviceName];
  if (!baseUrl) return null;
  return baseUrl.replace('{host}', window.location.hostname);
}
