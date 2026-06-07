/**
 * Admin Panel - Authentication & Security Management
 */

import { useState, useEffect } from 'react';
import { adminAPI } from '../utils/adminAPI';
import './AdminPanel.css';

export function AdminPanel() {
  const [tab, setTab] = useState('overview');
  const [status, setStatus] = useState(null);
  const [users, setUsers] = useState([]);
  const [apps, setApps] = useState([]);
  const [policies, setPolicies] = useState(null);
  const [logs, setLogs] = useState([]);
  const [apiKeys, setApiKeys] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Create-user form state
  const [showCreateUser, setShowCreateUser] = useState(false);
  const [newUser, setNewUser] = useState({ username: '', email: '', password: '' });
  const [userFormError, setUserFormError] = useState(null);
  const [userFormBusy, setUserFormBusy] = useState(false);

  // Create-key form state
  const [newKeyName, setNewKeyName] = useState('');
  const [createdKey, setCreatedKey] = useState(null);
  const [keyFormError, setKeyFormError] = useState(null);
  const [keyFormBusy, setKeyFormBusy] = useState(false);

  useEffect(() => {
    const init = async () => {
      try {
        setError(null);
        const [authStatus, userList, appList, secPolicies, authLogs, keyList] = await Promise.all([
          adminAPI.getStatus(),
          adminAPI.listUsers(),
          adminAPI.listOAuth2Apps(),
          adminAPI.getSecurityPolicies(),
          adminAPI.getAuthLogs(),
          adminAPI.listKeys(),
        ]);

        setStatus(authStatus);
        setUsers(userList.users || []);
        setApps(appList.applications || []);
        setPolicies(secPolicies);
        setLogs(authLogs.logs || []);
        setApiKeys(keyList.keys || []);
        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };

    init();
  }, []);

  const handleCreateUser = async (e) => {
    e.preventDefault();
    if (!newUser.username || !newUser.email || !newUser.password) {
      setUserFormError('All fields are required');
      return;
    }
    setUserFormBusy(true);
    setUserFormError(null);
    try {
      const created = await adminAPI.createUser(newUser);
      setUsers(prev => [...prev, created]);
      setNewUser({ username: '', email: '', password: '' });
      setShowCreateUser(false);
    } catch (err) {
      setUserFormError(err.message);
    } finally {
      setUserFormBusy(false);
    }
  };

  const handleDeleteUser = async (userId, username) => {
    if (!window.confirm(`Delete user "${username}"? This cannot be undone.`)) return;
    try {
      await adminAPI.deleteUser(userId);
      setUsers(prev => prev.filter(u => u.pk !== userId));
    } catch (err) {
      setError(`Delete failed: ${err.message}`);
    }
  };

  const handleGenerateKey = async (e) => {
    e.preventDefault();
    if (!newKeyName.trim()) {
      setKeyFormError('Key name is required');
      return;
    }
    setKeyFormBusy(true);
    setKeyFormError(null);
    setCreatedKey(null);
    try {
      const result = await adminAPI.generateKey(newKeyName.trim());
      setCreatedKey(result);
      setApiKeys(prev => [...prev, { name: result.name, created: result.created, last_used: null, prefix: result.key.slice(0, 10) + '...' }]);
      setNewKeyName('');
    } catch (err) {
      setKeyFormError(err.message);
    } finally {
      setKeyFormBusy(false);
    }
  };

  const handleDeleteKey = async (name) => {
    if (!window.confirm(`Delete API key "${name}"?`)) return;
    try {
      await adminAPI.deleteKey(name);
      setApiKeys(prev => prev.filter(k => k.name !== name));
    } catch (err) {
      setError(`Delete key failed: ${err.message}`);
    }
  };

  const renderOverview = () => (
    <div className="admin-section">
      <h2>System Overview</h2>
      
      <div className="status-grid">
        <div className="status-card">
          <h3>Authentication Service</h3>
          <div className={`status-indicator ${status?.authentik === 'ready' ? 'ready' : 'error'}`}>
            {status?.authentik === 'ready' ? '● Ready' : '● Offline'}
          </div>
          <p className="status-detail">{status?.url || 'Not configured'}</p>
        </div>

        <div className="status-card">
          <h3>Active Users</h3>
          <div className="status-value">{users.length}</div>
          <p className="status-detail">Registered accounts</p>
        </div>

        <div className="status-card">
          <h3>OAuth2 Applications</h3>
          <div className="status-value">{apps.length}</div>
          <p className="status-detail">Configured apps</p>
        </div>

        <div className="status-card">
          <h3>Recent Logins</h3>
          <div className="status-value">{logs.length}</div>
          <p className="status-detail">Past 24 hours</p>
        </div>
      </div>

      <div className="quick-links">
        <h3>Quick Access</h3>
        <a href={`${status?.url}/if/admin/`} target="_blank" rel="noopener noreferrer" className="btn-link">
          Open Authentik Admin Panel
        </a>
        <p className="muted">Configure users, apps, and policies in the web admin interface</p>
      </div>
    </div>
  );

  const renderUsers = () => (
    <div className="admin-section">
      <div className="section-header">
        <h2>User Management</h2>
        <button className="btn-primary" onClick={() => { setShowCreateUser(v => !v); setUserFormError(null); }}>
          {showCreateUser ? 'Cancel' : '+ Create User'}
        </button>
      </div>

      {showCreateUser && (
        <form className="create-form" onSubmit={handleCreateUser}>
          <h3>New User</h3>
          {userFormError && <div className="form-error">{userFormError}</div>}
          <label>Username
            <input
              type="text" value={newUser.username} autoComplete="off"
              onChange={e => setNewUser(v => ({ ...v, username: e.target.value }))}
            />
          </label>
          <label>Email
            <input
              type="email" value={newUser.email}
              onChange={e => setNewUser(v => ({ ...v, email: e.target.value }))}
            />
          </label>
          <label>Password
            <input
              type="password" value={newUser.password} autoComplete="new-password"
              onChange={e => setNewUser(v => ({ ...v, password: e.target.value }))}
            />
          </label>
          <button type="submit" className="btn-primary" disabled={userFormBusy}>
            {userFormBusy ? 'Creating…' : 'Create User'}
          </button>
        </form>
      )}

      {users.length === 0 ? (
        <p className="empty">No users configured. Create one above or visit the Authentik admin panel.</p>
      ) : (
        <div className="users-table">
          <div className="table-header">
            <span className="col-username">Username</span>
            <span className="col-email">Email</span>
            <span className="col-created">Created</span>
            <span className="col-last">Last Login</span>
            <span className="col-actions"></span>
          </div>
          {users.slice(0, 50).map((user) => (
            <div key={user.pk || user.id} className="table-row">
              <span className="col-username">{user.username || 'N/A'}</span>
              <span className="col-email">{user.email || 'N/A'}</span>
              <span className="col-created">{user.date_joined ? new Date(user.date_joined).toLocaleDateString() : '—'}</span>
              <span className="col-last">{user.last_login ? new Date(user.last_login).toLocaleString() : 'Never'}</span>
              <span className="col-actions">
                <button
                  className="btn-danger-sm"
                  onClick={() => handleDeleteUser(user.pk || user.id, user.username)}
                  title="Delete user"
                >
                  Delete
                </button>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const renderApiKeys = () => (
    <div className="admin-section">
      <h2>API Keys</h2>

      <form className="create-form" onSubmit={handleGenerateKey}>
        <h3>Generate New Key</h3>
        {keyFormError && <div className="form-error">{keyFormError}</div>}
        {createdKey && (
          <div className="key-reveal">
            <p>Key generated — copy it now, it will not be shown again:</p>
            <code className="key-value">{createdKey.key}</code>
          </div>
        )}
        <div className="inline-form">
          <input
            type="text" placeholder="Key name (e.g. ci-runner)"
            value={newKeyName} onChange={e => setNewKeyName(e.target.value)}
          />
          <button type="submit" className="btn-primary" disabled={keyFormBusy}>
            {keyFormBusy ? 'Generating…' : 'Generate'}
          </button>
        </div>
      </form>

      {apiKeys.length === 0 ? (
        <p className="empty">No API keys configured.</p>
      ) : (
        <div className="users-table">
          <div className="table-header">
            <span className="col-username">Name</span>
            <span className="col-email">Key (prefix)</span>
            <span className="col-created">Created</span>
            <span className="col-last">Last Used</span>
            <span className="col-actions"></span>
          </div>
          {apiKeys.map((k) => (
            <div key={k.name} className="table-row">
              <span className="col-username">{k.name}</span>
              <span className="col-email"><code>{k.prefix}</code></span>
              <span className="col-created">{k.created || '—'}</span>
              <span className="col-last">{k.last_used || 'Never'}</span>
              <span className="col-actions">
                <button className="btn-danger-sm" onClick={() => handleDeleteKey(k.name)}>Delete</button>
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const renderApps = () => (
    <div className="admin-section">
      <h2>OAuth2 Applications</h2>
      
      {apps.length === 0 ? (
        <p className="empty">No applications configured.</p>
      ) : (
        <div className="apps-grid">
          {apps.map((app) => (
            <div key={app.client_id} className="app-card">
              <h3>{app.name}</h3>
              <div className={`app-status ${app.enabled ? 'enabled' : 'disabled'}`}>
                {app.enabled ? '✓ Enabled' : '○ Disabled'}
              </div>
              <div className="app-details">
                <p><strong>Client ID:</strong> {app.client_id}</p>
                <p><strong>Redirect URIs:</strong></p>
                <code>{app.redirect_uris}</code>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  const renderPolicies = () => (
    <div className="admin-section">
      <h2>Security Policies</h2>
      
      {policies && (
        <div className="policies-grid">
          <div className="policy-item">
            <span className="policy-key">MFA Enabled</span>
            <span className={`policy-value ${policies.mfa_enabled ? 'yes' : 'no'}`}>
              {policies.mfa_enabled ? 'Yes' : 'No'}
            </span>
          </div>
          
          <div className="policy-item">
            <span className="policy-key">Min Password Length</span>
            <span className="policy-value">{policies.password_min_length} chars</span>
          </div>
          
          <div className="policy-item">
            <span className="policy-key">Require Uppercase</span>
            <span className={`policy-value ${policies.password_require_uppercase ? 'yes' : 'no'}`}>
              {policies.password_require_uppercase ? 'Yes' : 'No'}
            </span>
          </div>
          
          <div className="policy-item">
            <span className="policy-key">Require Special Chars</span>
            <span className={`policy-value ${policies.password_require_special ? 'yes' : 'no'}`}>
              {policies.password_require_special ? 'Yes' : 'No'}
            </span>
          </div>
          
          <div className="policy-item">
            <span className="policy-key">Session Timeout</span>
            <span className="policy-value">{policies.session_timeout_minutes} min</span>
          </div>
          
          <div className="policy-item">
            <span className="policy-key">Login Attempts Limit</span>
            <span className="policy-value">{policies.login_attempts_limit} attempts</span>
          </div>
          
          <div className="policy-item">
            <span className="policy-key">IP Whitelist</span>
            <span className={`policy-value ${policies.ip_whitelist_enabled ? 'yes' : 'no'}`}>
              {policies.ip_whitelist_enabled ? 'Enabled' : 'Disabled'}
            </span>
          </div>
          
          <div className="policy-item">
            <span className="policy-key">TLS Enforced</span>
            <span className={`policy-value ${policies.tls_enforced ? 'yes' : 'no'}`}>
              {policies.tls_enforced ? 'Yes' : 'No'}
            </span>
          </div>
          
          <div className="policy-item">
            <span className="policy-key">Network Isolation</span>
            <span className={`policy-value ${policies.network_isolation ? 'yes' : 'no'}`}>
              {policies.network_isolation ? 'Enabled' : 'Disabled'}
            </span>
          </div>
        </div>
      )}
    </div>
  );

  const renderLogs = () => (
    <div className="admin-section">
      <h2>Authentication Logs</h2>
      
      {logs.length === 0 ? (
        <p className="empty">No auth logs available.</p>
      ) : (
        <div className="logs-table">
          <div className="table-header">
            <span className="col-time">Timestamp</span>
            <span className="col-user">User</span>
            <span className="col-event">Event</span>
            <span className="col-ip">IP Address</span>
            <span className="col-app">Application</span>
          </div>
          {logs.slice(0, 20).map((log, idx) => (
            <div key={idx} className={`table-row ${log.event.includes('error') ? 'error' : ''}`}>
              <span className="col-time">{new Date(log.timestamp).toLocaleString()}</span>
              <span className="col-user">{log.user}</span>
              <span className="col-event">{log.event}</span>
              <span className="col-ip">{log.ip}</span>
              <span className="col-app">{log.application}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );

  if (loading) {
    return (
      <div className="admin-container">
        <div className="loading">
          <div className="spinner"></div>
          <p>Loading admin data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="admin-container">
      <div className="admin-header">
        <h1>Admin & Security</h1>
        {error && <div className="error-banner">{error}</div>}
      </div>

      <div className="admin-tabs">
        <button className={`tab ${tab === 'overview' ? 'active' : ''}`} onClick={() => setTab('overview')}>
          Overview
        </button>
        <button className={`tab ${tab === 'users' ? 'active' : ''}`} onClick={() => setTab('users')}>
          Users ({users.length})
        </button>
        <button className={`tab ${tab === 'apps' ? 'active' : ''}`} onClick={() => setTab('apps')}>
          OAuth2 Apps ({apps.length})
        </button>
        <button className={`tab ${tab === 'policies' ? 'active' : ''}`} onClick={() => setTab('policies')}>
          Security Policies
        </button>
        <button className={`tab ${tab === 'logs' ? 'active' : ''}`} onClick={() => setTab('logs')}>
          Auth Logs
        </button>
        <button className={`tab ${tab === 'keys' ? 'active' : ''}`} onClick={() => setTab('keys')}>
          API Keys ({apiKeys.length})
        </button>
      </div>

      <div className="admin-content">
        {tab === 'overview' && renderOverview()}
        {tab === 'users' && renderUsers()}
        {tab === 'apps' && renderApps()}
        {tab === 'policies' && renderPolicies()}
        {tab === 'logs' && renderLogs()}
        {tab === 'keys' && renderApiKeys()}
      </div>
    </div>
  );
}
