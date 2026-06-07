import { useApp } from '../context/AppContext';
import { NavItem } from './NavItem';
import { DotStatus } from './DotStatus';

export function Sidebar() {
  const { state } = useApp();
  const productName = process.env.VITE_PRODUCT_NAME || 'Kovati OS';

  // Determine uptime display
  const formatUptime = (seconds) => {
    if (!seconds) return '0s';
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    if (days > 0) return `${days}d ${hours}h ${mins}m`;
    if (hours > 0) return `${hours}h ${mins}m`;
    return `${mins}m`;
  };

  const gpuCount = state.gpus?.length || 4;
  const totalVram = gpuCount * 24; // Assuming 24GB per A5500
  const isAppliance = state.systemMode === 'appliance';

  return (
    <div className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logomark">◆</div>
        <div className="sidebar-product-name">{productName}</div>
        <div className="sidebar-product-sub">
          {isAppliance ? 'Managed Appliance' : `v1.0.0-beta · ${gpuCount}× A5500`}
        </div>
      </div>

      <div className="sidebar-nav">
        <div className="sidebar-section">
          <div className="sidebar-section-header">CONTROL</div>
          <NavItem to="/dashboard">Dashboard</NavItem>
          <NavItem to="/loadout">Loadout</NavItem>
          <NavItem to="/tools">Tools</NavItem>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-header">WORKLOADS</div>
          <NavItem to="/training">Training</NavItem>
          <NavItem to="/resources">Resources</NavItem>
        </div>

        <div className="sidebar-section">
          <div className="sidebar-section-header">PLATFORM</div>
          <NavItem to="/expose">Expose</NavItem>
          <NavItem to="/voice">Voice</NavItem>
          <NavItem to="/monitor" badge={state.alertCount || null}>
            Monitor
          </NavItem>
          <NavItem to="/operations">Operations</NavItem>
          <NavItem to="/admin">Admin</NavItem>
          <NavItem to="/settings">Settings</NavItem>
        </div>
      </div>

      <div className="sidebar-footer">
        <div className="sidebar-footer-item">
          <DotStatus status="green" />
          <span>{gpuCount}× A5500 · {totalVram} GB</span>
        </div>
        <div className="sidebar-footer-item">
          uptime {formatUptime(state.gpus?.[0]?.uptime || 0)}
        </div>
      </div>
    </div>
  );
}
