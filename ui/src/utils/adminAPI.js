/**
 * Admin API Client
 * Wrapper for Authentik and security management endpoints
 */

export const adminAPI = {
  async getStatus() {
    const res = await fetch('/api/admin/status');
    if (!res.ok) throw new Error(`Status: ${res.status}`);
    return res.json();
  },

  async listUsers() {
    const res = await fetch('/api/admin/users');
    if (!res.ok) throw new Error(`Users: ${res.status}`);
    return res.json();
  },

  async createUser(payload) {
    const res = await fetch('/api/admin/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Create user: ${res.status}`);
    }
    return res.json();
  },

  async updateUser(userId, payload) {
    const res = await fetch(`/api/admin/users/${userId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Update user: ${res.status}`);
    }
    return res.json();
  },

  async deleteUser(userId) {
    const res = await fetch(`/api/admin/users/${userId}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Delete user: ${res.status}`);
    }
    return res.json();
  },

  async listOAuth2Apps() {
    const res = await fetch('/api/admin/oauth2-apps');
    if (!res.ok) throw new Error(`OAuth2 apps: ${res.status}`);
    return res.json();
  },

  async getSecurityPolicies() {
    const res = await fetch('/api/admin/security-policies');
    if (!res.ok) throw new Error(`Policies: ${res.status}`);
    return res.json();
  },

  async getAuthLogs(limit = 50) {
    const res = await fetch(`/api/admin/auth-logs?limit=${limit}`);
    if (!res.ok) throw new Error(`Logs: ${res.status}`);
    return res.json();
  },

  // API Key management
  async listKeys() {
    const res = await fetch('/api/keys');
    if (!res.ok) throw new Error(`Keys: ${res.status}`);
    return res.json();
  },

  async generateKey(name) {
    const res = await fetch(`/api/keys/generate?name=${encodeURIComponent(name)}`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Generate key: ${res.status}`);
    }
    return res.json();
  },

  async deleteKey(name) {
    const res = await fetch(`/api/keys/${encodeURIComponent(name)}`, { method: 'DELETE' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `Delete key: ${res.status}`);
    }
    return res.json();
  },
};
