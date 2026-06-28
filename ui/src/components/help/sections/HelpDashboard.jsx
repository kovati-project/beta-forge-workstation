import { Panel } from '../../Panel';

export function HelpDashboard() {
  return (
    <div className="help-section">
      <div className="help-section-header">
        <h2 className="help-section-title">Dashboard</h2>
        <p className="help-section-subtitle">
          The Dashboard is your real-time system overview. It shows GPU status, service health, system metrics, and recent activity at a glance.
        </p>
      </div>

      <Panel title="GPU Status Cards">
        <div className="help-body">
          <p>Each card represents one GPU (GPU 0–3). Cards show:</p>
          <ul>
            <li><strong>VRAM bar</strong> — current memory usage vs. total (24 GB per A5500)</li>
            <li><strong>Utilization %</strong> — compute load at the current moment</li>
            <li><strong>Temperature</strong> — GPU core temperature in °C</li>
            <li><strong>NVLink pairs</strong> — which GPUs are linked (0+3 and 1+2)</li>
          </ul>
          <div className="help-tip">
            <strong>Tip:</strong> A VRAM bar that is consistently above 90% means the active model is close to its memory limit. Consider switching to a profile with more combined VRAM.
          </div>
        </div>
      </Panel>

      <Panel title="Active Loadout Banner">
        <div className="help-body">
          <p>The banner at the top of the dashboard shows the currently active GPU loadout profile name (e.g., <span className="help-code">inference-pair-a</span>). If no profile is active, the banner is hidden.</p>
          <p>A spinning indicator appears while a profile switch is in progress — avoid starting new workloads during this time.</p>
        </div>
      </Panel>

      <Panel title="System Metrics">
        <div className="help-body">
          <p>Shows host-level resource utilization:</p>
          <ul>
            <li><strong>CPU</strong> — percentage across all cores (Threadripper Pro 5955WX, 16 cores)</li>
            <li><strong>RAM</strong> — used vs. total (512 GB)</li>
            <li><strong>Disk</strong> — storage pool utilization</li>
          </ul>
          <p>These update automatically every few seconds via polling.</p>
        </div>
      </Panel>

      <Panel title="Service Health Grid">
        <div className="help-body">
          <p>A compact grid showing the run state of every managed service. Colors:</p>
          <ul>
            <li><strong style={{color: 'var(--green)'}}>Green dot</strong> — service is running</li>
            <li><strong style={{color: 'var(--amber)'}}>Amber dot</strong> — service is starting or stopping</li>
            <li><strong style={{color: 'var(--red)'}}>Red dot</strong> — service is stopped or in error</li>
          </ul>
          <p>Click any service to jump to the Tools page for detailed controls.</p>
        </div>
      </Panel>

      <Panel title="Activity Feed">
        <div className="help-body">
          <p>A chronological log of recent system events: model loads, training job starts and completions, profile switches, and user actions. Useful for quickly seeing what changed on the system.</p>
        </div>
      </Panel>

      <Panel title="Topbar Alert Indicator">
        <div className="help-body">
          <p>When active alerts are present, the Monitor link in the sidebar shows a red badge with the count. The topbar also shows a service status summary (running / idle counts). Go to Monitor → Alert History to review and dismiss alerts.</p>
        </div>
      </Panel>
    </div>
  );
}
