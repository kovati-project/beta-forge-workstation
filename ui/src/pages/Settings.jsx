import { useApp } from '../context/AppContext';
import { Panel } from '../components/Panel';
import { SecretsSection } from '../components/SecretsSection';
import { NetworkSection } from '../components/NetworkSection';
import { AuthSection } from '../components/AuthSection';
import { StackManagementSection } from '../components/StackManagementSection';
import { BackupsSection } from '../components/BackupsSection';
import { PlatformSetupSection } from '../components/PlatformSetupSection';
import { ConfigSection } from '../components/ConfigSection';
import './Settings.css';

export function Settings() {
  const { state } = useApp();
  const isAppliance = state?.systemMode === 'appliance';

  return (
    <div className="settings-page">
      <header className="page-header">
        <h1>Settings</h1>
        <span className="mode-indicator">
          [{isAppliance ? 'appliance' : 'workstation'}]
        </span>
      </header>

      <div className="settings-grid">
        <div className="left-column">
          <Panel
            title="Secrets"
            icon="🔑"
            expanded={true}
            onToggle={() => {}}
          >
            <SecretsSection isAppliance={isAppliance} />
          </Panel>
        </div>

        <div className="right-column">
          <Panel
            title="Network"
            icon="🌐"
            expanded={true}
            onToggle={() => {}}
          >
            <NetworkSection isAppliance={isAppliance} />
          </Panel>

          <Panel
            title="Auth"
            icon="🔐"
            expanded={true}
            onToggle={() => {}}
          >
            <AuthSection isAppliance={isAppliance} />
          </Panel>
        </div>
      </div>

      <div className="full-width-sections">
        <Panel
          title="Configuration"
          icon="⚙️"
          expanded={true}
          onToggle={() => {}}
        >
          <ConfigSection isAppliance={isAppliance} />
        </Panel>

        <Panel
          title="Stack Management"
          icon="📦"
          expanded={true}
          onToggle={() => {}}
        >
          <StackManagementSection isAppliance={isAppliance} />
        </Panel>

        <Panel
          title="Backups"
          icon="💾"
          expanded={true}
          onToggle={() => {}}
        >
          <BackupsSection isAppliance={isAppliance} />
        </Panel>

        <Panel
          title="Platform Setup"
          icon="🛠️"
          expanded={true}
          onToggle={() => {}}
        >
          <PlatformSetupSection isAppliance={isAppliance} />
        </Panel>
      </div>
    </div>
  );
}
