import { GpuStatusRow } from '../components/GpuStatusRow';
import { ActiveLoadoutBanner } from '../components/ActiveLoadoutBanner';
import { SystemMetrics } from '../components/SystemMetrics';
import { ServiceHealthGrid } from '../components/ServiceHealthGrid';
import { ActivityFeed } from '../components/ActivityFeed';
import './Dashboard.css';

export function Dashboard() {
  return (
    <div className="dashboard">
      {/* GPU Status Row */}
      <GpuStatusRow />

      {/* Active Loadout + System Metrics */}
      <div className="dashboard-row-2">
        <ActiveLoadoutBanner />
        <SystemMetrics />
      </div>

      {/* Service Health + Activity Feed */}
      <div className="dashboard-row-3">
        <ServiceHealthGrid />
        <ActivityFeed />
      </div>
    </div>
  );
}
