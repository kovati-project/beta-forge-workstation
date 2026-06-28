import { Panel } from '../../Panel';

export function HelpOperations() {
  const diagnosticChecks = [
    'CPU load within acceptable range',
    'Available RAM above threshold',
    'Disk usage below 90%',
    'All required containers running',
    'GPU temperatures normal',
    'VRAM usage not critically high',
    'Network interfaces reachable',
    'MinIO (S3) accessible',
    'Qdrant accessible',
    'PostgreSQL accessible',
    'Authentik accessible',
    'Caddy reverse proxy healthy',
    'Prometheus scraping endpoints',
    'DCGM exporter active',
    'vLLM endpoints responding',
  ];

  return (
    <div className="help-section">
      <div className="help-section-header">
        <h2 className="help-section-title">Operations</h2>
        <p className="help-section-subtitle">
          Operations is the maintenance and diagnostics panel. It provides system health status, per-service restarts, automated diagnostics, a runbook, and maintenance actions — organized across six tabs.
        </p>
      </div>

      <Panel title="Health Tab">
        <div className="help-body">
          <p>A quick-glance summary of overall system state:</p>
          <ul>
            <li><strong>Status indicator</strong> — green (healthy) or red (error). Driven by the diagnostic check results.</li>
            <li><strong>Uptime</strong> — time since the workstation last booted, shown in days, hours, and minutes</li>
            <li><strong>Disk usage gauge</strong> — percentage of total storage consumed</li>
            <li><strong>Last updated</strong> — when the health status was last refreshed</li>
          </ul>
        </div>
      </Panel>

      <Panel title="Services Tab">
        <div className="help-body">
          <p>Lists all running services with per-service restart controls. Use this tab to restart a specific service without cycling it through the Tools page.</p>
          <div className="help-tip">
            <strong>When to restart:</strong> If a service's log shows repeated errors, a crash loop, or if the service is responding slowly and you want to clear its state, a restart is the first remedy to try.
          </div>
          <p style={{marginTop: 8}}>Each card shows the service name, port, and current status. The <strong>Restart</strong> button prompts for confirmation before restarting the Docker container.</p>
        </div>
      </Panel>

      <Panel title="Diagnostics Tab">
        <div className="help-body">
          <p>Runs 25 automated health checks across the system and shows pass/fail status for each. Run diagnostics when something feels wrong but you don't know where to start.</p>
          <p>Checks include:</p>
          <ul>
            {diagnosticChecks.map((c) => (
              <li key={c}>{c}</li>
            ))}
            <li>…and 10 more network and service-specific checks</li>
          </ul>
          <p>A failing check includes a brief explanation of what failed and how to resolve it. Fix the underlying issue and re-run diagnostics to verify.</p>
        </div>
      </Panel>

      <Panel title="Runbook Tab">
        <div className="help-body">
          <p>Contains step-by-step recovery procedures for common failure scenarios. The runbook is pulled from <span className="help-code">docs/troubleshooting-runbook.md</span> and covers:</p>
          <ul>
            <li>Service won't start</li>
            <li>vLLM OOM (out of memory) errors</li>
            <li>GPU not detected after reboot</li>
            <li>Authentik login broken</li>
            <li>MinIO unreachable</li>
            <li>Training job crashed mid-run</li>
            <li>Docker compose stack diverged from expected state</li>
          </ul>
          <p>Each procedure is numbered and self-contained — follow the steps in order before escalating.</p>
        </div>
      </Panel>

      <Panel title="Maintenance Tab">
        <div className="help-body">
          <p>Action cards for administrative operations:</p>
          <ul>
            <li><strong>System Backup</strong> — triggers an immediate full backup (configs, model metadata, datasets). Monitor progress in the Logs tab.</li>
            <li><strong>System Update</strong> — checks for and applies OS package updates, Docker updates, and Kovati component updates.</li>
            <li><strong>Run Diagnostics</strong> — shortcut to the Diagnostics tab.</li>
            <li><strong>Documentation</strong> — shortcut to the Runbook tab.</li>
          </ul>
          <div className="help-warn">
            <strong>Warning:</strong> System Update may restart services. Schedule it during low-activity periods. A backup is automatically taken before updates are applied.
          </div>
        </div>
      </Panel>

      <Panel title="Logs Tab">
        <div className="help-body">
          <p>A time-ordered log of operation events (not container logs — use Monitor → Log Viewer for those). Events recorded here include service starts/stops, backup triggers, update completions, and diagnostic runs.</p>
          <p>Filter by severity: <strong>INFO</strong> (normal operations), <strong>WARN</strong> (potential issues), <strong>ERROR</strong> (failures requiring attention).</p>
        </div>
      </Panel>
    </div>
  );
}
