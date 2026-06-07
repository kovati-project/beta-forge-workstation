/**
 * Operations API Client
 * Wrapper for system operations and maintenance endpoints
 */

export const operationsAPI = {
  async getHealth() {
    const res = await fetch('/api/operations/health');
    if (!res.ok) throw new Error(`Health: ${res.status}`);
    return res.json();
  },

  async getServices() {
    const res = await fetch('/api/operations/services');
    if (!res.ok) throw new Error(`Services: ${res.status}`);
    return res.json();
  },

  async triggerBackup(backupType = 'full') {
    const res = await fetch('/api/operations/backup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ backup_type: backupType }),
    });
    if (!res.ok) throw new Error(`Backup: ${res.status}`);
    return res.json();
  },

  async restartService(service) {
    const res = await fetch('/api/operations/restart-service', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service }),
    });
    if (!res.ok) throw new Error(`Restart: ${res.status}`);
    return res.json();
  },

  async triggerUpdate() {
    const res = await fetch('/api/operations/system-update', {
      method: 'POST',
    });
    if (!res.ok) throw new Error(`Update: ${res.status}`);
    return res.json();
  },

  async runDiagnostics() {
    const res = await fetch('/api/operations/diagnostics');
    if (!res.ok) throw new Error(`Diagnostics: ${res.status}`);
    return res.json();
  },

  async getRunbook() {
    const res = await fetch('/api/operations/runbook');
    if (!res.ok) throw new Error(`Runbook: ${res.status}`);
    return res.json();
  },

  async getLogs(service = null, limit = 50) {
    const url = new URL('/api/operations/logs', window.location.origin);
    if (service) url.searchParams.set('service', service);
    url.searchParams.set('limit', limit);

    const res = await fetch(url);
    if (!res.ok) throw new Error(`Logs: ${res.status}`);
    return res.json();
  },
};
