import { useState, useMemo } from 'react';
import { useApp } from '../context/AppContext';
import { ServiceCard } from './ServiceCard';
import './ServiceGroup.css';

export function ServiceGroup({ group, onToggleService }) {
  const [expanded, setExpanded] = useState(true);
  const { state } = useApp();

  // Get services from this group
  const groupServices = useMemo(() => {
    if (!state.services) return [];
    return group.services
      .map((serviceName) => {
        if (!state.services[serviceName]) return null;
        return {
          name: serviceName,
          ...state.services[serviceName],
        };
      })
      .filter(Boolean);
  }, [state.services, group.services]);

  return (
    <div className="service-group">
      <button
        className="service-group-header"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="group-arrow">{expanded ? '▾' : '▸'}</span>
        <span className="group-name">{group.name}</span>
        <span className="group-count">({groupServices.length} services)</span>
      </button>

      {expanded && (
        <div className="service-group-content">
          {groupServices.length === 0 ? (
            <div className="group-empty">No services in this group</div>
          ) : (
            groupServices.map((service) => (
              <ServiceCard
                key={service.name}
                serviceName={service.name}
                service={service}
                onToggleService={onToggleService}
                isManaged={!!service.managed_by_loadout}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}
