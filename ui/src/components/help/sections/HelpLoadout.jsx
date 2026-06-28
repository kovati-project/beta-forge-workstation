import { Panel } from '../../Panel';

export function HelpLoadout() {
  const profiles = [
    { name: 'inference-small', gpus: 'GPU 0', vram: '24 GB', useCase: '7B–13B models (single-GPU inference)' },
    { name: 'inference-pair-a', gpus: 'GPU 0 + 3', vram: '48 GB NVLink', useCase: '34B–40B models (tensor parallelism)' },
    { name: 'inference-pair-b', gpus: 'GPU 1 + 2', vram: '48 GB NVLink', useCase: 'Second parallel inference stack (run two models simultaneously with pair-a)' },
    { name: 'inference-4gpu', gpus: 'All 4 GPUs', vram: '96 GB NVLink', useCase: '70B+ models at full precision' },
    { name: 'image-studio', gpus: 'GPU 0', vram: '24 GB', useCase: 'ComfyUI / InvokeAI image generation; frees GPUs 1, 2, 3 for other work' },
    { name: 'training-lora-image', gpus: 'GPU 1 + 2', vram: '48 GB', useCase: 'Kohya image LoRA training; GPU 0 available for inference' },
    { name: 'training-lora-text', gpus: 'All 4 GPUs', vram: '96 GB', useCase: 'Axolotl FSDP fine-tuning at maximum capacity' },
    { name: 'dual-stack', gpus: '0+3 / 1+2', vram: '48+48 GB', useCase: 'Run two independent inference models simultaneously' },
  ];

  return (
    <div className="help-section">
      <div className="help-section-header">
        <h2 className="help-section-title">Loadout</h2>
        <p className="help-section-subtitle">
          A loadout is a named GPU allocation profile. Switching loadouts reallocates the 4× RTX A5500 GPUs (96 GB total NVLink VRAM) between inference, training, and imaging workloads.
        </p>
      </div>

      <Panel title="What is a Loadout?">
        <div className="help-body">
          <p>Each loadout defines which GPUs are assigned to which stack (vLLM, Kohya, ComfyUI, etc.) and which Docker Compose services are started. Only one loadout is active at a time.</p>
          <p>Switching a loadout stops the services in the current profile and starts the services defined in the new one. This takes 30–120 seconds depending on which containers need to start.</p>
          <div className="help-warn">
            <strong>Warning:</strong> Switching a loadout while a model is actively serving requests or a training job is running will interrupt those jobs. Finish or stop any active work before switching.
          </div>
        </div>
      </Panel>

      <Panel title="Available Profiles">
        <table className="help-table">
          <thead>
            <tr>
              <th>Profile</th>
              <th>GPUs</th>
              <th>VRAM</th>
              <th>Best for</th>
            </tr>
          </thead>
          <tbody>
            {profiles.map((p) => (
              <tr key={p.name}>
                <td><span className="help-code">{p.name}</span></td>
                <td>{p.gpus}</td>
                <td>{p.vram}</td>
                <td>{p.useCase}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>

      <Panel title="How to Switch Profiles">
        <ol className="help-steps">
          <li className="help-step">
            <span className="help-step-number">1</span>
            <div className="help-step-body">
              <strong>Go to /#/loadout</strong>
              Navigate to the Loadout page from the sidebar.
            </div>
          </li>
          <li className="help-step">
            <span className="help-step-number">2</span>
            <div className="help-step-body">
              <strong>Click the profile card</strong>
              Each card shows GPU assignment, VRAM budget, and active services. Click the card for the profile you want.
            </div>
          </li>
          <li className="help-step">
            <span className="help-step-number">3</span>
            <div className="help-step-body">
              <strong>Wait for the switching banner</strong>
              A yellow banner appears at the top of the dashboard while the switch is in progress. The banner clears when the new profile is fully active.
            </div>
          </li>
          <li className="help-step">
            <span className="help-step-number">4</span>
            <div className="help-step-body">
              <strong>Verify on Dashboard</strong>
              The active loadout banner updates to the new profile name and the service health grid reflects the new running services.
            </div>
          </li>
        </ol>
      </Panel>

      <Panel title="NVLink Topology">
        <div className="help-body">
          <p>The workstation has two NVLink bridges connecting GPUs in pairs:</p>
          <ul>
            <li><strong>Bridge A:</strong> GPU 0 ↔ GPU 3 (48 GB unified memory)</li>
            <li><strong>Bridge B:</strong> GPU 1 ↔ GPU 2 (48 GB unified memory)</li>
          </ul>
          <p>When using a paired or 4-GPU profile, vLLM uses tensor parallelism across the bridged GPUs — this is faster than PCIe because NVLink has much higher bandwidth. The topology diagram on the Loadout page visualizes which GPUs are linked.</p>
          <div className="help-tip">
            <strong>Tip:</strong> For 34B–40B models, <span className="help-code">inference-pair-a</span> (GPU 0+3) is the optimal single-stack profile because it uses the NVLink bridge for maximum bandwidth.
          </div>
        </div>
      </Panel>
    </div>
  );
}
