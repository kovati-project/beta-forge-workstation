/**
 * Setup Wizard API - First-boot configuration
 */

export const setupAPI = {
  async probeHardware() {
    const res = await fetch('/api/setup/probe', { method: 'POST' });
    return res.json();
  },

  async recommendProfile(hardware) {
    const res = await fetch('/api/setup/recommend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(hardware),
    });
    return res.json();
  },

  async generateSecrets() {
    const res = await fetch('/api/setup/generate-secrets', { method: 'POST' });
    return res.json();
  },

  async setupNetwork(jumpboxIp, enableCaddy) {
    const res = await fetch('/api/setup/network', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jumpbox_ip: jumpboxIp, enable_caddy: enableCaddy }),
    });
    return res.json();
  },

  async provisionStack() {
    return fetch('/api/setup/provision', { method: 'POST' });
  },

  async validateStack() {
    return fetch('/api/setup/validate', { method: 'POST' });
  },

  async markComplete() {
    const res = await fetch('/api/setup/complete', { method: 'POST' });
    return res.json();
  },

  async getStatus() {
    const res = await fetch('/api/setup/status');
    return res.json();
  },

  async deleteCompletionFlag() {
    const res = await fetch('/api/setup/completion-flag', { method: 'DELETE' });
    return res.json();
  },
};
