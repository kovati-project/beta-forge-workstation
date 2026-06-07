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

export function Monitor() {
  const { state } = useApp();
  const [alerts, setAlerts] = useState([]);
  const [expandedSection, setExpandedSection] = useState('gpu');

  useEffect(() => {
    const loadAlerts = async () => {
      const data = await getAlerts();
      setAlerts(data.active || []);
    };

    loadAlerts();
    const interval = setInterval(loadAlerts, 30000); // Every 30s

    return () => clearInterval(interval);
  }, []);

  const handleViewAlertHistory = () => {
    setExpandedSection('alerts');
  };

  return (
    <div className="monitor-page">
      <header className="page-header">
        <h1>Monitor</h1>
        <span className="system-mode">{state?.systemMode || 'unknown'}</span>
      </header>

      {alerts.length > 0 && (
        <ActiveAlertsBanner
          alerts={alerts}
          onViewHistory={handleViewAlertHistory}
        />
      )}

      <div className="sections-container">
        <Panel
          title="GPU Telemetry"
          icon="📊"
          expanded={expandedSection === 'gpu'}
          onToggle={() =>
            setExpandedSection(
              expandedSection === 'gpu' ? null : 'gpu'
            )
          }
        >
          <GPUTelemetrySection />
        </Panel>

        <Panel
          title="System Metrics"
          icon="💻"
          expanded={expandedSection === 'system'}
          onToggle={() =>
            setExpandedSection(
              expandedSection === 'system' ? null : 'system'
            )
          }
        >
          <SystemMetricsSection />
        </Panel>

        <Panel
          title="LLM Traces"
          icon="🔍"
          expanded={expandedSection === 'traces'}
          onToggle={() =>
            setExpandedSection(
              expandedSection === 'traces' ? null : 'traces'
            )
          }
        >
          <LLMTracesSection />
        </Panel>

        <Panel
          title="Container Health"
          icon="🐳"
          expanded={expandedSection === 'containers'}
          onToggle={() =>
            setExpandedSection(
              expandedSection === 'containers' ? null : 'containers'
            )
          }
        >
          <ContainerHealthSection />
        </Panel>

        <Panel
          title="Log Viewer"
          icon="📝"
          expanded={expandedSection === 'logs'}
          onToggle={() =>
            setExpandedSection(
              expandedSection === 'logs' ? null : 'logs'
            )
          }
        >
          <LogViewerSection />
        </Panel>

        <Panel
          title="Alert History"
          icon="⚠️"
          expanded={expandedSection === 'alerts'}
          onToggle={() =>
            setExpandedSection(
              expandedSection === 'alerts' ? null : 'alerts'
            )
          }
        >
          <AlertHistorySection />
        </Panel>
      </div>
    </div>
  );
}
