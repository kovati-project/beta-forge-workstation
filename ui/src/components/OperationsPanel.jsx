/**
 * Operations Panel - System Health, Diagnostics & Maintenance
 */

import { useState, useEffect } from 'react';
import { operationsAPI } from '../utils/operationsAPI';
import './OperationsPanel.css';

export function OperationsPanel() {
  const [tab, setTab] = useState('health');
  const [health, setHealth] = useState(null);
  const [services, setServices] = useState([]);
  const [diagnostics, setDiagnostics] = useState(null);
  const [runbook, setRunbook] = useState([]);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionInProgress, setActionInProgress] = useState(null);

  useEffect(() => {
    const init = async () => {
      try {
        setError(null);
        const [healthData, serviceData, diagnosticsData, runbookData, logsData] = await Promise.all([
          operationsAPI.getHealth(),
          operationsAPI.getServices(),
          operationsAPI.runDiagnostics(),
          operationsAPI.getRunbook(),
          operationsAPI.getLogs(),
        ]);

        setHealth(healthData);
        setServices(serviceData.services || []);
        setDiagnostics(diagnosticsData);
        setRunbook(runbookData.runbook || []);
        setLogs(logsData.logs || []);
        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };

    init();
  }, []);

  const handleBackup = async () => {
    setActionInProgress('backup');
    try {
      await operationsAPI.triggerBackup('full');
      setError(null);
      setTimeout(() => setActionInProgress(null), 2000);
    } catch (err) {
      setError(err.message);
      setActionInProgress(null);
    }
  };

  const handleUpdate = async () => {
    if (!window.confirm('This will update the system. Continue?')) return;
    setActionInProgress('update');
    try {
      await operationsAPI.triggerUpdate();
      setError(null);
      setTimeout(() => setActionInProgress(null), 2000);
    } catch (err) {
      setError(err.message);
      setActionInProgress(null);
    }
  };

  const handleRestartService = async (service) => {
    if (!window.confirm(`Restart ${service}?`)) return;
    setActionInProgress(`restart-${service}`);
    try {
      await operationsAPI.restartService(service);
      setError(null);
      setTimeout(() => setActionInProgress(null), 2000);
    } catch (err) {
      setError(err.message);
      setActionInProgress(null);
    }
  };

  const renderHealth = () => (
    <div className="ops-section">
      <h2>System Health</h2>
      
      {health && (
        <div className="health-grid">
          <div className="health-card">
            <h3>Status</h3>
            <div className={`health-status ${health.status}`}>
              {health.status === 'healthy' ? '● Healthy' : '● Error'}
            </div>
          </div>

          <div className="health-card">
            <h3>Uptime</h3>
            <div className="health-value">
              {Math.floor(health.uptime_seconds / 86400)}d {Math.floor((health.uptime_seconds % 86400) / 3600)}h
            </div>
          </div>

          <div className="health-card">
            <h3>Storage</h3>
            <div className="health-value">{health.disk_used_gb} GB / {health.disk_total_gb} GB</div>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${health.disk_percent}%` }}></div>
              <span className="progress-text">{health.disk_percent}%</span>
            </div>
          </div>

          <div className="health-card">
            <h3>Last Updated</h3>
            <div className="health-timestamp">{new Date(health.timestamp).toLocaleString()}</div>
          </div>
        </div>
      )}
    </div>
  );

  const renderServices = () => (
    <div className="ops-section">
      <h2>Services Status</h2>
      
      <div className="services-grid">
        {services.map((svc) => (
          <div key={svc.name} className="service-card">
            <div className="service-header">
              <h3>{svc.name}</h3>
              <span className={`service-status ${svc.status}`}>
                {svc.status === 'running' ? '● Running' : '● Stopped'}
              </span>
            </div>
            <p className="service-port">:{svc.port}</p>
            <button
              className="btn-restart"
              onClick={() => handleRestartService(svc.name)}
              disabled={actionInProgress === `restart-${svc.name}`}
            >
              {actionInProgress === `restart-${svc.name}` ? 'Restarting...' : 'Restart'}
            </button>
          </div>
        ))}
      </div>
    </div>
  );

  const renderDiagnostics = () => (
    <div className="ops-section">
      <h2>System Diagnostics</h2>
      
      {diagnostics && (
        <>
          <div className={`diagnostics-summary ${diagnostics.overall}`}>
            <strong>Overall Status:</strong> {diagnostics.overall.toUpperCase()}
          </div>
          
          <div className="diagnostics-list">
            {diagnostics.diagnostics.map((check, idx) => (
              <div key={idx} className={`diagnostic-item ${check.status}`}>
                <div className="diagnostic-check">
                  <span className="check-icon">{check.status === 'pass' ? '✓' : '✗'}</span>
                  <span className="check-name">{check.check}</span>
                </div>
                <p className="check-detail">{check.detail}</p>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );

  const renderRunbook = () => (
    <div className="ops-section">
      <h2>Operations Runbook</h2>
      
      <div className="runbook-sections">
        {runbook.map((section, idx) => (
          <div key={idx} className="runbook-section">
            <h3>{section.section}</h3>
            <ol className="runbook-steps">
              {section.steps.map((step, stepIdx) => (
                <li key={stepIdx}>{step}</li>
              ))}
            </ol>
          </div>
        ))}
      </div>
    </div>
  );

  const renderMaintenance = () => (
    <div className="ops-section">
      <h2>Maintenance & Operations</h2>
      
      <div className="maintenance-grid">
        <div className="maintenance-card">
          <h3>System Backup</h3>
          <p>Create a full backup of configs, models, and data.</p>
          <button
            className="btn-action"
            onClick={handleBackup}
            disabled={actionInProgress === 'backup'}
          >
            {actionInProgress === 'backup' ? 'Backing up...' : 'Start Backup'}
          </button>
        </div>

        <div className="maintenance-card">
          <h3>System Update</h3>
          <p>Update OS, Docker, and application packages.</p>
          <button
            className="btn-action btn-update"
            onClick={handleUpdate}
            disabled={actionInProgress === 'update'}
          >
            {actionInProgress === 'update' ? 'Updating...' : 'Check & Update'}
          </button>
        </div>

        <div className="maintenance-card">
          <h3>Diagnostics</h3>
          <p>Run full system diagnostics and health checks.</p>
          <button className="btn-action" onClick={() => setTab('diagnostics')}>
            View Results
          </button>
        </div>

        <div className="maintenance-card">
          <h3>Documentation</h3>
          <p>Operations runbook and troubleshooting guide.</p>
          <button className="btn-action" onClick={() => setTab('runbook')}>
            Open Runbook
          </button>
        </div>
      </div>
    </div>
  );

  const renderLogs = () => (
    <div className="ops-section">
      <h2>Operation Logs</h2>
      
      {logs.length === 0 ? (
        <p className="empty">No logs available.</p>
      ) : (
        <div className="logs-table">
          <div className="table-header">
            <span className="col-time">Timestamp</span>
            <span className="col-level">Level</span>
            <span className="col-message">Message</span>
          </div>
          {logs.slice(0, 20).map((log, idx) => (
            <div key={idx} className={`table-row ${log.level.toLowerCase()}`}>
              <span className="col-time">{new Date(log.timestamp).toLocaleString()}</span>
              <span className="col-level">{log.level}</span>
              <span className="col-message">{log.message}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  if (loading) {
    return (
      <div className="ops-container">
        <div className="loading">
          <div className="spinner"></div>
          <p>Loading operations data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="ops-container">
      <div className="ops-header">
        <h1>Operations & Maintenance</h1>
        {error && <div className="error-banner">{error}</div>}
      </div>

      <div className="ops-tabs">
        <button className={`tab ${tab === 'health' ? 'active' : ''}`} onClick={() => setTab('health')}>
          Health
        </button>
        <button className={`tab ${tab === 'services' ? 'active' : ''}`} onClick={() => setTab('services')}>
          Services ({services.filter(s => s.status === 'running').length}/{services.length})
        </button>
        <button className={`tab ${tab === 'diagnostics' ? 'active' : ''}`} onClick={() => setTab('diagnostics')}>
          Diagnostics
        </button>
        <button className={`tab ${tab === 'runbook' ? 'active' : ''}`} onClick={() => setTab('runbook')}>
          Runbook
        </button>
        <button className={`tab ${tab === 'maintenance' ? 'active' : ''}`} onClick={() => setTab('maintenance')}>
          Maintenance
        </button>
        <button className={`tab ${tab === 'logs' ? 'active' : ''}`} onClick={() => setTab('logs')}>
          Logs
        </button>
      </div>

      <div className="ops-content">
        {tab === 'health' && renderHealth()}
        {tab === 'services' && renderServices()}
        {tab === 'diagnostics' && renderDiagnostics()}
        {tab === 'runbook' && renderRunbook()}
        {tab === 'maintenance' && renderMaintenance()}
        {tab === 'logs' && renderLogs()}
      </div>
    </div>
  );
}
