import '../shell.css';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
import { useGpuStatus } from '../hooks/useGpuStatus';
import { useServices } from '../hooks/useServices';
import { useAlerts } from '../hooks/useAlerts';

export function Shell({ children }) {
  // Start polling hooks
  useGpuStatus();
  useServices();
  useAlerts();

  return (
    <div className="shell">
      <Sidebar />
      <div className="main-column">
        <Topbar />
        <div className="main-content">
          {children}
        </div>
      </div>
    </div>
  );
}
