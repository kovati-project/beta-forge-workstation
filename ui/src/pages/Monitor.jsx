import { useState, useEffect } from 'react';
import { useApp } from '../context/AppContext';
import { Panel } from '../components/Panel';
import { ActiveAlertsBanner } from '../components/ActiveAlertsBanner';
import { GPUTelemetrySection } from '../components/GPUTelemetrySection';
import { SystemMetricsSection } from '../components/SystemMetricsSection';
import { LLMTracesSection } from '../components/LLMTracesSection';
import { ContainerHealthSection } from '../components/ContainerHealthSection';
import { LogViewerSection } from '../components/LogViewerSection';
import { AlertHistorySection } from '../components/AlertHistorySection';
import { getAlerts } from '../utils/monitorAPI';
import './Monitor.css';

const DEFAULT_OPEN = new Set(['gpu', 'system']);

export function Monitor() {
  const { state } = useApp();
  const [alerts, setAlerts] = useState([]);
  const [openSections, setOpenSections] = useState(DEFAULT_OPEN);

  useEffect(() => {
    const loadAlerts = async () => {
      const data = await getAlerts();
      setAlerts(data.active || []);
    };
    loadAlerts();
    const interval = setInterval(loadAlerts, 30000);
    return () => clearInterval(interval);
  }, []);

  const toggle = (key) =>
    setOpenSections((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  const handleViewAlertHistory = () =>
    setOpenSections((prev) => new Set([...prev, 'alerts']));

  return (
    <div className="monitor-page">
      <header className="page-header">
        <h1>Monitor</h1>
        <span className="system-mode">{state?.systemMode || 'workstation'}</span>
      </header>

      {alerts.length > 0 && (
        <ActiveAlertsBanner alerts={alerts} onViewHistory={handleViewAlertHistory} />
      )}

      <div className="sections-grid">
        <div className="sections-col sections-col--primary">
          <Panel
            title="GPU Telemetry"
            icon="📊"
            expanded={openSections.has('gpu')}
            onToggle={() => toggle('gpu')}
          >
            <GPUTelemetrySection />
          </Panel>

          <Panel
            title="System Metrics"
            icon="💻"
            expanded={openSections.has('system')}
            onToggle={() => toggle('system')}
          >
            <SystemMetricsSection />
          </Panel>

          <Panel
            title="Container Health"
            icon="🐳"
            expanded={openSections.has('containers')}
            onToggle={() => toggle('containers')}
          >
            <ContainerHealthSection />
          </Panel>
        </div>

        <div className="sections-col sections-col--secondary">
          <Panel
            title="Log Viewer"
            icon="📝"
            expanded={openSections.has('logs')}
            onToggle={() => toggle('logs')}
          >
            <LogViewerSection />
          </Panel>

          <Panel
            title="LLM Traces"
            icon="🔍"
            expanded={openSections.has('traces')}
            onToggle={() => toggle('traces')}
          >
            <LLMTracesSection />
          </Panel>

          <Panel
            title="Alert History"
            icon="⚠️"
            expanded={openSections.has('alerts')}
            onToggle={() => toggle('alerts')}
          >
            <AlertHistorySection />
          </Panel>
        </div>
      </div>
    </div>
  );
}
