import { Panel } from '../../Panel';

export function HelpMonitor() {
  return (
    <div className="help-section">
      <div className="help-section-header">
        <h2 className="help-section-title">Monitor</h2>
        <p className="help-section-subtitle">
          The Monitor page is the observability hub. It provides real-time GPU telemetry, system metrics, container health, a live log viewer, LLM traces, and an alert history — organized into six collapsible panels.
        </p>
      </div>

      <Panel title="GPU Telemetry">
        <div className="help-body">
          <p>Per-GPU metrics updated in real time:</p>
          <ul>
            <li><strong>Temperature</strong> — GPU core temp in °C. Normal operating range: 60–80°C under load. Above 85°C is a warning sign.</li>
            <li><strong>Power draw</strong> — watts consumed. A5500 TDP is 230W.</li>
            <li><strong>VRAM usage</strong> — used vs. 24 GB total. Red when above 90%.</li>
            <li><strong>SM clock</strong> — GPU shader clock speed (MHz)</li>
            <li><strong>Memory clock</strong> — memory bus speed (MHz)</li>
            <li><strong>NVLink bandwidth</strong> — data transferred between bridged GPU pairs (GB/s)</li>
          </ul>
          <p>Historical line charts show trends over the last few minutes, helping you spot thermal or VRAM spikes.</p>
        </div>
      </Panel>

      <Panel title="System Metrics">
        <div className="help-body">
          <p>Host-level performance counters:</p>
          <ul>
            <li><strong>CPU</strong> — per-core utilization breakdown across the 16-core Threadripper Pro 5955WX</li>
            <li><strong>RAM</strong> — used / free of 512 GB system memory</li>
            <li><strong>Disk I/O</strong> — read and write throughput in MB/s</li>
            <li><strong>Network I/O</strong> — bytes in / out per second across all interfaces</li>
          </ul>
        </div>
      </Panel>

      <Panel title="Container Health">
        <div className="help-body">
          <p>Shows Docker container health states for all managed services:</p>
          <ul>
            <li><strong>Health state</strong> — healthy, unhealthy, or starting (based on Docker HEALTHCHECK)</li>
            <li><strong>Restart count</strong> — how many times the container has auto-restarted since last deploy</li>
            <li><strong>Uptime</strong> — time since the container last started</li>
            <li><strong>Resource limits vs. actual</strong> — CPU and memory usage compared to container limits</li>
          </ul>
          <div className="help-warn">
            <strong>Action needed:</strong> A container with a high restart count (5+) indicates a crash loop. Check the Log Viewer for that container to find the root cause.
          </div>
        </div>
      </Panel>

      <Panel title="Log Viewer">
        <div className="help-body">
          <p>Streams live log output from any running service container.</p>
          <ol className="help-steps">
            <li className="help-step">
              <span className="help-step-number">1</span>
              <div className="help-step-body">Select a service from the dropdown. Only running services are listed.</div>
            </li>
            <li className="help-step">
              <span className="help-step-number">2</span>
              <div className="help-step-body">The last 200 lines of log output are shown and auto-refreshed.</div>
            </li>
            <li className="help-step">
              <span className="help-step-number">3</span>
              <div className="help-step-body">Use the search box to filter lines by keyword. Use the level filter (ALL / INFO / WARN / ERROR) to focus on issues.</div>
            </li>
            <li className="help-step">
              <span className="help-step-number">4</span>
              <div className="help-step-body">Click <strong>Download</strong> to save the log as a text file for offline analysis.</div>
            </li>
          </ol>
        </div>
      </Panel>

      <Panel title="LLM Traces">
        <div className="help-body">
          <p>Shows inference request telemetry from Langfuse. Each trace represents one LLM call and includes:</p>
          <ul>
            <li><strong>Latency</strong> — time-to-first-token (TTFT) and total generation time</li>
            <li><strong>Token counts</strong> — prompt tokens, completion tokens, total</li>
            <li><strong>Input / output samples</strong> — truncated previews of the request and response</li>
            <li><strong>Model</strong> — which model served the request</li>
          </ul>
          <p>Langfuse must be running (Storage & Vector group in Tools) for traces to appear. Configure your inference clients to send telemetry to the Langfuse endpoint.</p>
        </div>
      </Panel>

      <Panel title="Alert History">
        <div className="help-body">
          <p>Displays all active and historical alerts raised by the monitoring system:</p>
          <ul>
            <li><strong>Active alerts banner</strong> — appears at the top of the page when there are unresolved alerts. Count is also shown on the Monitor nav badge in the sidebar.</li>
            <li><strong>Severity levels</strong> — INFO (blue), WARN (amber), ERROR (red)</li>
            <li><strong>Quick fixes</strong> — some alerts include a suggested action button (e.g., "Restart service")</li>
          </ul>
          <p>Historical alerts are stored in the table below the banner with timestamps and descriptions. Dismiss an alert after resolving the underlying issue.</p>
        </div>
      </Panel>
    </div>
  );
}
