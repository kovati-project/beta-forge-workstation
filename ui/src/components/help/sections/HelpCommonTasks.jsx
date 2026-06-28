export function HelpCommonTasks({ onNavigate }) {
  const tasks = [
    {
      title: 'Run a large language model',
      desc: 'Select the right GPU loadout for your model size, then start the vLLM service.',
      section: 'loadout',
      tags: [{ label: '/#/loadout', color: 'cyan' }, { label: '/#/tools', color: 'cyan' }],
    },
    {
      title: 'Fine-tune a model with my own data',
      desc: 'Upload a dataset and run the 5-step Text LoRA wizard to train a custom model.',
      section: 'training',
      tags: [{ label: '/#/training', color: 'purple' }],
    },
    {
      title: 'Train an image LoRA (Stable Diffusion)',
      desc: 'Use the Image LoRA workflow to fine-tune a diffusion model on your image dataset.',
      section: 'training',
      tags: [{ label: '/#/training', color: 'purple' }],
    },
    {
      title: 'Connect an AI client to Kovati',
      desc: 'Copy the OpenAI-compatible endpoint URL and paste it into your client (e.g. Claude, Cursor, Open WebUI).',
      section: 'expose',
      tags: [{ label: '/#/expose', color: 'green' }],
    },
    {
      title: 'Use Kovati as an MCP server',
      desc: 'Start an MCP server and export its config to claude_desktop_config.json.',
      section: 'expose',
      tags: [{ label: '/#/expose', color: 'green' }],
    },
    {
      title: 'Generate an API key',
      desc: 'Create a named API key for programmatic access. The key is shown once — copy it before dismissing.',
      section: 'expose',
      tags: [{ label: '/#/expose', color: 'green' }],
    },
    {
      title: 'Upload or manage a dataset',
      desc: 'Drag-and-drop or URL-import datasets. Supports JSONL, CSV, and Parquet formats.',
      section: 'resources',
      tags: [{ label: '/#/resources', color: 'amber' }],
    },
    {
      title: 'Run a ComfyUI image generation session',
      desc: 'Switch to the image-studio loadout, then start ComfyUI from the Tools page.',
      section: 'loadout',
      tags: [{ label: '/#/loadout', color: 'cyan' }, { label: '/#/tools', color: 'cyan' }],
    },
    {
      title: 'View GPU usage and temperatures',
      desc: 'Monitor real-time per-GPU metrics: temperature, VRAM, power draw, and clock speeds.',
      section: 'monitor',
      tags: [{ label: '/#/monitor', color: 'amber' }],
    },
    {
      title: 'Check why a service is not working',
      desc: 'Run the 25-point diagnostics check or view logs for the specific service.',
      section: 'operations',
      tags: [{ label: '/#/operations', color: 'amber' }],
    },
    {
      title: 'Restart a stuck service',
      desc: 'Go to Operations → Services and click the restart button for the affected service.',
      section: 'operations',
      tags: [{ label: '/#/operations', color: 'amber' }],
    },
    {
      title: 'Add a new user to the system',
      desc: 'Create a user account via the Authentik-backed user management panel.',
      section: 'admin',
      tags: [{ label: '/#/admin', color: 'purple' }],
    },
    {
      title: 'Back up my configuration',
      desc: 'Trigger a manual backup of configs, model metadata, and data from the Settings page.',
      section: 'settings',
      tags: [{ label: '/#/settings', color: 'green' }],
    },
    {
      title: 'Use voice transcription (speech-to-text)',
      desc: 'Ensure Whisper STT is running, then record audio from your browser microphone.',
      section: 'voice',
      tags: [{ label: '/#/voice', color: 'purple' }],
    },
  ];

  const tagColorMap = { cyan: 'help-tag-cyan', purple: 'help-tag-purple', amber: 'help-tag-amber', green: 'help-tag-green' };

  return (
    <div className="help-section">
      <div className="help-section-header">
        <h2 className="help-section-title">Common Tasks</h2>
        <p className="help-section-subtitle">
          Quick links to the most common workflows on Kovati OS. Click a card to jump to the relevant documentation section.
        </p>
      </div>

      <div className="help-tasks-grid">
        {tasks.map((task) => (
          <div
            key={task.title}
            className="help-task-card"
            onClick={() => onNavigate(task.section)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === 'Enter' && onNavigate(task.section)}
          >
            <div className="help-task-card-title">
              <span>{task.title}</span>
              <span className="help-task-card-arrow">›</span>
            </div>
            <div className="help-task-card-desc">{task.desc}</div>
            <div className="help-task-card-tags">
              {task.tags.map((t) => (
                <span key={t.label} className={`help-tag ${tagColorMap[t.color]}`}>
                  {t.label}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
