import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { Tag } from './Tag';

export function Topbar() {
  const { state } = useApp();
  const location = useLocation();
  const [clock, setClock] = useState(new Date().toLocaleTimeString('en-US', { hour12: false }));

  // Extract page name from route
  const routeMap = {
    '/dashboard': 'Dashboard',
    '/loadout': 'Loadout',
    '/tools': 'Tools',
    '/training': 'Training',
    '/resources': 'Resources',
    '/expose': 'Expose',
    '/monitor': 'Monitor',
    '/settings': 'Settings',
    '/setup': 'Setup',
    '/help': 'Help',
  };

  const currentPath = location.pathname;
  const pageName = routeMap[currentPath] || 'Dashboard';

  // Update clock every second
  useEffect(() => {
    const interval = setInterval(() => {
      setClock(new Date().toLocaleTimeString('en-US', { hour12: false }));
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  // Count running and idle services
  const services = Object.values(state.services || {});
  const runningCount = services.filter(s => s.status === 'running').length;
  const idleCount = services.filter(s => s.status !== 'running').length;

  return (
    <div className="topbar">
      <div className="topbar-left">
        <span className="topbar-breadcrumb">Kovati OS ›</span>
        <span className="topbar-page-name">{pageName}</span>
      </div>

      <div className="topbar-right">
        {state.activeProfile && (
          <Tag variant="cyan">{state.activeProfile}</Tag>
        )}
        {runningCount > 0 && (
          <Tag variant="green">{runningCount} running</Tag>
        )}
        {idleCount > 0 && (
          <Tag variant="amber">{idleCount} idle</Tag>
        )}
        <div className="topbar-clock">{clock}</div>
      </div>
    </div>
  );
}
