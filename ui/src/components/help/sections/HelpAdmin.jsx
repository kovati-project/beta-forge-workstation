import { Panel } from '../../Panel';

export function HelpAdmin() {
  return (
    <div className="help-section">
      <div className="help-section-header">
        <h2 className="help-section-title">Admin</h2>
        <p className="help-section-subtitle">
          The Admin panel manages users, OAuth2 applications, security policies, authentication logs, and API keys. All user identity is backed by Authentik — changes here are reflected in Authentik in real time.
        </p>
      </div>

      <Panel title="Overview Tab">
        <div className="help-body">
          <p>A status dashboard for the identity and access system:</p>
          <ul>
            <li><strong>Authentik status</strong> — ready (green) or offline (red). If offline, users cannot log in to any service.</li>
            <li><strong>Active users</strong> — total registered accounts</li>
            <li><strong>OAuth2 applications</strong> — number of connected applications</li>
            <li><strong>Recent logins</strong> — count of successful logins in the past 24 hours</li>
          </ul>
          <p>The <strong>Open Authentik Admin</strong> button links to the Authentik web console for advanced configuration not exposed by this panel.</p>
        </div>
      </Panel>

      <Panel title="Users Tab — Creating and Managing Accounts">
        <div className="help-body">
          <h3>Creating a new user</h3>
          <ol className="help-steps" style={{marginTop: 6}}>
            <li className="help-step">
              <span className="help-step-number">1</span>
              <div className="help-step-body">Fill in <strong>Username</strong>, <strong>Email</strong>, and <strong>Password</strong> in the Create User form.</div>
            </li>
            <li className="help-step">
              <span className="help-step-number">2</span>
              <div className="help-step-body">Click <strong>Create User</strong>. The account is created in Authentik immediately and appears in the users table.</div>
            </li>
            <li className="help-step">
              <span className="help-step-number">3</span>
              <div className="help-step-body">Share the credentials with the user. They can change their password on first login if MFA is configured.</div>
            </li>
          </ol>
          <h3 style={{marginTop: 12}}>Deleting a user</h3>
          <p>Click the delete button (trash icon) next to the user's row. A confirmation dialog prevents accidental deletions. Deleted accounts lose access to all services immediately.</p>
          <div className="help-warn" style={{marginTop: 8}}>
            <strong>Note:</strong> Deleting a user does not delete their data (datasets, checkpoints, etc.) stored in MinIO. Remove those separately from Resources → Storage if needed.
          </div>
        </div>
      </Panel>

      <Panel title="OAuth2 Apps Tab">
        <div className="help-body">
          <p>Lists all OAuth2 client applications registered with Authentik. These allow third-party tools (Open WebUI, Grafana, n8n, etc.) to authenticate via "Sign in with Authentik."</p>
          <p>Each app entry shows:</p>
          <ul>
            <li><strong>Client ID</strong> — the application identifier</li>
            <li><strong>Status</strong> — enabled or disabled</li>
            <li><strong>Redirect URIs</strong> — allowed callback URLs after login</li>
          </ul>
          <p>To register a new application, use the Authentik web console (link in the Overview tab).</p>
        </div>
      </Panel>

      <Panel title="Security Policies Tab">
        <div className="help-body">
          <p>Configure authentication rules for all users:</p>
          <table className="help-table">
            <thead>
              <tr>
                <th>Setting</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              <tr><td><strong>MFA Required</strong></td><td>Force all users to enroll in TOTP or WebAuthn multi-factor authentication.</td></tr>
              <tr><td><strong>Min Password Length</strong></td><td>Minimum character count for new passwords.</td></tr>
              <tr><td><strong>Require Uppercase</strong></td><td>Passwords must contain at least one uppercase letter.</td></tr>
              <tr><td><strong>Require Special Characters</strong></td><td>Passwords must contain at least one special character.</td></tr>
              <tr><td><strong>Session Timeout</strong></td><td>Idle session expiration in minutes.</td></tr>
              <tr><td><strong>Login Attempt Limit</strong></td><td>Number of failed attempts before account lockout.</td></tr>
              <tr><td><strong>IP Whitelist</strong></td><td>Restrict logins to specific IP ranges.</td></tr>
              <tr><td><strong>TLS Enforcement</strong></td><td>Redirect all HTTP traffic to HTTPS.</td></tr>
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="Auth Logs Tab">
        <div className="help-body">
          <p>A chronological record of authentication events. Each entry shows:</p>
          <ul>
            <li><strong>Timestamp</strong></li>
            <li><strong>Username</strong></li>
            <li><strong>Event type</strong> — login success, login failure, logout, password change, MFA challenge</li>
            <li><strong>Source IP</strong></li>
            <li><strong>Target application</strong> — which service the user authenticated into</li>
          </ul>
          <p>Failed login events are highlighted in red. A spike in failed logins from an external IP may indicate a brute-force attempt — enable IP whitelist in Security Policies if needed.</p>
        </div>
      </Panel>

      <Panel title="API Keys Tab">
        <div className="help-body">
          <p>Manage programmatic API keys from the admin perspective. This tab mirrors the functionality of Expose → API Keys but also shows keys created by other users (admins only).</p>
          <p>Admins can delete any key, which immediately revokes access for that key across all services.</p>
        </div>
      </Panel>
    </div>
  );
}
