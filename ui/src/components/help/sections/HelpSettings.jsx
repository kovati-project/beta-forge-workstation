import { Panel } from '../../Panel';

export function HelpSettings() {
  return (
    <div className="help-section">
      <div className="help-section-header">
        <h2 className="help-section-title">Settings</h2>
        <p className="help-section-subtitle">
          Platform configuration for secrets, networking, authentication, Docker stack management, backups, and initial setup. Changes here affect all services on the workstation.
        </p>
      </div>

      <Panel title="Secrets">
        <div className="help-body">
          <p>Manages the 14 environment variables and cryptographic secrets used across all services. Examples: PostgreSQL password, encryption keys, API tokens for external integrations.</p>
          <ul>
            <li><strong>Mask/Reveal</strong> — secrets are hidden by default. Click the eye icon on a specific secret to reveal its value temporarily.</li>
            <li><strong>Download Backup</strong> — exports all secrets as a <span className="help-code">.env</span> file for offline safekeeping.</li>
          </ul>
          <div className="help-warn">
            <strong>Security:</strong> Never share the downloaded <span className="help-code">.env</span> backup. It contains all credentials needed to fully access the system. Store it encrypted (e.g., in a password manager).
          </div>
        </div>
      </Panel>

      <Panel title="Network">
        <div className="help-body">
          <p>Network configuration for external access:</p>
          <ul>
            <li><strong>Jumpbox IP</strong> — the IP address of the external access point (if using a cloud jumpbox or VPN relay)</li>
            <li><strong>WireGuard public/private keys</strong> — VPN tunnel credentials for secure remote access</li>
            <li><strong>Caddy toggle</strong> — enable or disable the Caddy reverse proxy</li>
            <li><strong>TLS certificate info</strong> — current certificate status and expiration date</li>
          </ul>
          <div className="help-tip">
            <strong>Tip:</strong> Changes to network settings require restarting the affected services (Caddy, WireGuard). Use Operations → Services to restart them after saving changes here.
          </div>
        </div>
      </Panel>

      <Panel title="Auth">
        <div className="help-body">
          <p>Authentication provider configuration:</p>
          <ul>
            <li><strong>Authentik URL</strong> — the base URL for the Authentik identity provider. Must be reachable from the browser for login flows to work.</li>
            <li><strong>OAuth2 client registration</strong> — register new client applications here or in the Authentik console.</li>
            <li><strong>MFA enforcement</strong> — toggle multi-factor authentication requirement for all users (also configurable in Admin → Security Policies).</li>
          </ul>
        </div>
      </Panel>

      <Panel title="Stack Management">
        <div className="help-body">
          <p>Controls the Docker Compose stacks that make up the Kovati OS service layer:</p>
          <ul>
            <li><strong>List stacks</strong> — shows all compose stacks and their current state (running, stopped, degraded)</li>
            <li><strong>Update from repo</strong> — pulls the latest compose file definitions from the Git repository and applies changes (equivalent to <span className="help-code">docker compose pull && docker compose up -d</span>)</li>
            <li><strong>Force rebuild</strong> — rebuilds service images from scratch, ignoring the layer cache</li>
            <li><strong>Prune unused</strong> — removes dangling images and orphaned volumes to free disk space</li>
          </ul>
          <div className="help-warn">
            <strong>Warning:</strong> Force rebuilding images is time-consuming (15–45 minutes) and will take the affected services offline. Only use this if standard updates are failing.
          </div>
        </div>
      </Panel>

      <Panel title="Backups">
        <div className="help-body">
          <p>Backup and restore configuration:</p>
          <ul>
            <li><strong>Manual backup</strong> — trigger an immediate backup of all configs, model metadata, and data. Choose between full backup or config-only.</li>
            <li><strong>Backup history</strong> — list of completed backups with dates and sizes</li>
            <li><strong>Restore from backup</strong> — select a backup and restore. Data is validated before the restore is applied.</li>
            <li><strong>Retention policy</strong> — set how many days backups are kept before automatic deletion</li>
            <li><strong>Auto-backup schedule</strong> — configure a daily/weekly automatic backup time</li>
          </ul>
          <div className="help-tip">
            <strong>Best practice:</strong> Take a manual backup before any major change (loadout switch, system update, new user setup). Set the retention policy to at least 7 days so you have a week of daily backups available.
          </div>
        </div>
      </Panel>

      <Panel title="Platform Setup">
        <div className="help-body">
          <p>Re-runs or resets the first-boot setup wizard:</p>
          <ul>
            <li><strong>Re-run Setup Wizard</strong> — navigate back to <span className="help-code">/#/setup</span> to step through hardware detection, profile selection, secrets generation, and network configuration again</li>
            <li><strong>Verify Prerequisites</strong> — checks that all system requirements are still met (GPU drivers, Docker, required ports free)</li>
            <li><strong>Reset Setup State</strong> — clears the setup completion flag, allowing the wizard to run again on next page load. Use this if setup was interrupted or the system was reconfigured from scratch.</li>
          </ul>
        </div>
      </Panel>
    </div>
  );
}
