import { Panel } from '../../Panel';

export function HelpTraining() {
  return (
    <div className="help-section">
      <div className="help-section-header">
        <h2 className="help-section-title">Training</h2>
        <p className="help-section-subtitle">
          The Training page provides a guided wizard for fine-tuning models. Text LoRA uses Axolotl to fine-tune LLMs; Image LoRA uses Kohya to fine-tune diffusion models.
        </p>
      </div>

      <Panel title="Choosing a Training Mode">
        <div className="help-body">
          <table className="help-table">
            <thead>
              <tr>
                <th>Mode</th>
                <th>Engine</th>
                <th>Input</th>
                <th>Output</th>
                <th>Required Loadout</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td><strong>Text LoRA</strong></td>
                <td>Axolotl (FSDP)</td>
                <td>JSONL instruction dataset</td>
                <td>LoRA adapter weights</td>
                <td><span className="help-code">training-lora-text</span></td>
              </tr>
              <tr>
                <td><strong>Image LoRA</strong></td>
                <td>Kohya SS</td>
                <td>Image folder + captions</td>
                <td>LoRA adapter weights</td>
                <td><span className="help-code">training-lora-image</span></td>
              </tr>
            </tbody>
          </table>
          <div className="help-warn" style={{marginTop: 10}}>
            <strong>Prerequisite:</strong> Switch to the required loadout before launching a training job. Training uses all GPUs in the profile — inference and image generation will not be available during training.
          </div>
        </div>
      </Panel>

      <Panel title="Text LoRA Wizard — Step by Step">
        <ol className="help-steps">
          <li className="help-step">
            <span className="help-step-number">1</span>
            <div className="help-step-body">
              <strong>Dataset</strong>
              Select an existing dataset from <span className="help-code">/data/datasets/</span> or upload a new file. Supported formats: JSONL (instruction-tuning format), CSV. The file must be accessible in the Resources → Datasets browser before it appears here.
            </div>
          </li>
          <li className="help-step">
            <span className="help-step-number">2</span>
            <div className="help-step-body">
              <strong>Base Model</strong>
              Choose the pretrained model to fine-tune. Models must already be downloaded into MinIO. Common choices: Mistral 7B, Qwen 2.5, Llama 3 8B, etc.
            </div>
          </li>
          <li className="help-step">
            <span className="help-step-number">3</span>
            <div className="help-step-body">
              <strong>LoRA Config</strong>
              Set training hyperparameters:
              <ul style={{marginTop: 6}}>
                <li><strong>LoRA Rank (r)</strong> — controls adapter capacity. 8–32 for most tasks; 64+ for complex fine-tuning.</li>
                <li><strong>LoRA Alpha</strong> — scaling factor, usually 2× the rank.</li>
                <li><strong>Learning Rate</strong> — start with 2e-4; lower if training loss is unstable.</li>
                <li><strong>Epochs</strong> — number of full passes over the dataset. 1–3 is typical for instruction tuning.</li>
                <li><strong>Batch Size</strong> — set as high as VRAM allows without OOM errors.</li>
              </ul>
            </div>
          </li>
          <li className="help-step">
            <span className="help-step-number">4</span>
            <div className="help-step-body">
              <strong>GPU Assignment</strong>
              Select the GPU profile to use. Use <span className="help-code">training-lora-text</span> (all 4 GPUs) for maximum throughput. Ensure this loadout is active before launching.
            </div>
          </li>
          <li className="help-step">
            <span className="help-step-number">5</span>
            <div className="help-step-body">
              <strong>Launch</strong>
              Review the configuration summary and click Launch. The training job starts and the Live Training View opens automatically.
            </div>
          </li>
        </ol>
      </Panel>

      <Panel title="Reading the Live Training View">
        <div className="help-body">
          <p>Once a training job starts, the live view shows:</p>
          <ul>
            <li><strong>Step counter</strong> — current step / total steps</li>
            <li><strong>Loss</strong> — training loss. Should decrease over time. Flat or increasing loss means the learning rate may need adjustment.</li>
            <li><strong>Gradient norm</strong> — if this spikes above 1–2, the training may be unstable. Reduce the learning rate.</li>
            <li><strong>ETA</strong> — estimated time to completion</li>
            <li><strong>VRAM usage</strong> — per-GPU memory utilization during training</li>
          </ul>
          <p>The log stream shows raw Axolotl output. Filter for <strong>WARN</strong> or <strong>ERROR</strong> to spot issues quickly.</p>
        </div>
      </Panel>

      <Panel title="Stopping a Run and Exporting Checkpoints">
        <div className="help-body">
          <p>Click <strong>Stop</strong> in the Live Training View to halt training. The run saves the latest checkpoint before stopping.</p>
          <p>After training completes (or is stopped), click <strong>Export Checkpoint</strong> to move the adapter weights to <span className="help-code">/data/checkpoints/</span>. From there it can be loaded in vLLM as an adapter on top of the base model.</p>
          <div className="help-tip">
            <strong>Tip:</strong> Find your checkpoints in Resources → Checkpoints after export. You can view the config and download the weights from there.
          </div>
        </div>
      </Panel>

      <Panel title="Image LoRA Workflow">
        <div className="help-body">
          <p>The Image LoRA wizard follows the same 5-step structure as Text LoRA, but inputs and outputs differ:</p>
          <ul>
            <li><strong>Input:</strong> A folder of images with corresponding caption files (<span className="help-code">.txt</span>) or auto-generated captions via BLIP.</li>
            <li><strong>Base Model:</strong> A Stable Diffusion checkpoint (SDXL, SD 1.5, etc.) stored in MinIO.</li>
            <li><strong>Output:</strong> A <span className="help-code">.safetensors</span> LoRA adapter that can be loaded into ComfyUI or InvokeAI.</li>
          </ul>
          <p>Required loadout: <span className="help-code">training-lora-image</span> (uses GPU 1+2, leaving GPU 0 available for inference).</p>
        </div>
      </Panel>
    </div>
  );
}
