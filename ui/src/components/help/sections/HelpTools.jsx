import { Panel } from '../../Panel';

export function HelpTools() {
  const groups = [
    {
      name: 'Text Inference',
      services: ['vLLM (pair-a, port 8000)', 'vLLM (pair-b, port 8001)', 'vLLM (4-GPU, port 8002)', 'Ollama (port 11434)'],
      desc: 'OpenAI-compatible LLM inference servers. vLLM is optimized for throughput; Ollama is simpler and works with any GGUF model.',
    },
    {
      name: 'Image Studio',
      services: ['ComfyUI', 'InvokeAI', 'Rembg (background removal)'],
      desc: 'Diffusion model image generation. Requires the image-studio loadout to dedicate a GPU.',
    },
    {
      name: 'Training',
      services: ['Axolotl', 'Kohya SS', 'Unsloth', 'JupyterLab', 'Label Studio'],
      desc: 'Model fine-tuning and dataset tooling. Axolotl handles text LoRA; Kohya handles image LoRA. JupyterLab provides interactive notebook access.',
    },
    {
      name: 'Agentic',
      services: ['n8n (workflow automation)', 'Dify (low-code LLM apps)', 'OpenHands (AI coding agent)', 'MCP servers (filesystem, browser, code-exec, fetch)'],
      desc: 'Orchestration and agent tooling. n8n and Dify allow building LLM-powered workflows without code.',
    },
    {
      name: 'Voice I/O',
      services: ['Whisper STT (port 9099)', 'Piper TTS (port 5000)'],
      desc: 'Speech-to-text and text-to-speech. Both expose OpenAI-compatible /v1/audio endpoints.',
    },
    {
      name: 'Chat UI',
      services: ['Open WebUI', 'SearXNG (private search)'],
      desc: 'Open WebUI provides a ChatGPT-like frontend connecting to your local vLLM or Ollama. SearXNG enables web search without telemetry.',
    },
    {
      name: 'Storage & Vector',
      services: ['MinIO (S3-compatible)', 'Qdrant (vector DB)', 'PostgreSQL', 'Langfuse (LLM tracing)'],
      desc: 'Data infrastructure. MinIO stores models, datasets, and checkpoints. Qdrant stores embeddings for RAG. Langfuse tracks inference telemetry.',
    },
    {
      name: 'Observability',
      services: ['Prometheus', 'Grafana', 'DCGM (GPU metrics)', 'cAdvisor (container metrics)'],
      desc: 'Monitoring stack. Prometheus scrapes all services; Grafana provides dashboards. DCGM exports detailed GPU telemetry.',
    },
    {
      name: 'Auth & Security',
      services: ['Authentik'],
      desc: 'Identity provider. All external-facing services route auth through Authentik. Users and OAuth2 apps are managed in the Admin panel.',
    },
  ];

  return (
    <div className="help-section">
      <div className="help-section-header">
        <h2 className="help-section-title">Tools</h2>
        <p className="help-section-subtitle">
          The Tools page is a service catalog for all 50+ Docker containers managed by Kovati OS. You can start, stop, and monitor individual services from here.
        </p>
      </div>

      <Panel title="Starting and Stopping Services">
        <ol className="help-steps">
          <li className="help-step">
            <span className="help-step-number">1</span>
            <div className="help-step-body">
              <strong>Find the service</strong>
              Services are grouped by function. Scroll down or look for the group name (e.g., Text Inference, Agentic).
            </div>
          </li>
          <li className="help-step">
            <span className="help-step-number">2</span>
            <div className="help-step-body">
              <strong>Click Start or Stop</strong>
              Each service card has a toggle button. The UI optimistically updates the status immediately while the backend confirms the change.
            </div>
          </li>
          <li className="help-step">
            <span className="help-step-number">3</span>
            <div className="help-step-body">
              <strong>Wait for status confirmation</strong>
              The status dot changes: amber = starting/stopping, green = running, gray = stopped. If it stays amber for more than 30 seconds, check Operations → Diagnostics.
            </div>
          </li>
        </ol>
        <div className="help-warn" style={{marginTop: 10}}>
          <strong>Warning:</strong> Some services (Authentik, PostgreSQL, MinIO) are marked "always on" and cannot be stopped via this page. They are required for core functionality.
        </div>
      </Panel>

      <Panel title="Service Groups">
        <table className="help-table">
          <thead>
            <tr>
              <th>Group</th>
              <th>Key Services</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {groups.map((g) => (
              <tr key={g.name}>
                <td><strong>{g.name}</strong></td>
                <td>{g.services.map((s, i) => <span key={i}>{s}{i < g.services.length - 1 ? ', ' : ''}</span>)}</td>
                <td>{g.desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <Panel title="Service Card Details">
        <div className="help-body">
          <p>Each service card shows:</p>
          <ul>
            <li><strong>Status dot</strong> — green (running), amber (transitioning), gray (stopped)</li>
            <li><strong>Port</strong> — the local port this service listens on</li>
            <li><strong>Uptime</strong> — how long the container has been running</li>
            <li><strong>Resource usage</strong> — CPU and memory consumption (when running)</li>
          </ul>
          <div className="help-tip">
            <strong>Tip:</strong> If a service fails to start, go to Monitor → Log Viewer, select the failing service, and look for error messages near the bottom of the log.
          </div>
        </div>
      </Panel>
    </div>
  );
}
