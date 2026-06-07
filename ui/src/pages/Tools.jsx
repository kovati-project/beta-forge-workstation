import { useState, useCallback } from 'react';
import { useApp } from '../context/AppContext';
import { ServiceGroup } from '../components/ServiceGroup';
import { SERVICE_GROUPS } from '../utils/serviceRegistry';
import './Tools.css';

export function Tools() {
  const { state, setServices } = useApp();
  const [error, setError] = useState(null);

  const handleToggleService = useCallback(
    async (serviceName, shouldStart) => {
      const action = shouldStart ? 'start' : 'stop';

      // Optimistic UI update
      const updated = {
        ...state.services,
        [serviceName]: {
          ...state.services[serviceName],
          status: shouldStart ? 'starting' : 'stopping',
        },
      };
      setServices({ services: updated });

      try {
        const response = await fetch(
          `/api/services/${serviceName}/${action}`,
          { method: 'POST' }
        );

        if (!response.ok) {
          throw new Error(`Failed to ${action} service`);
        }

        // Trigger a services poll to refresh
        const servicesResponse = await fetch('/api/services');
        if (servicesResponse.ok) {
          const data = await servicesResponse.json();
          setServices({ services: data });
        }

        setError(null);
      } catch (err) {
        setError(`Error ${action}ing ${serviceName}: ${err.message}`);
        // Revert optimistic update
        const servicesResponse = await fetch('/api/services');
        if (servicesResponse.ok) {
          const data = await servicesResponse.json();
          setServices({ services: data });
        }
      }
    },
    [state.services, setServices]
  );

  const totalServices = Object.keys(state.services || {}).length;

  return (
    <div className="tools-page">
      <div className="tools-header">
        <span className="tools-title">Service Catalog</span>
        <span className="tools-subtitle">
          {SERVICE_GROUPS.length} groups · {totalServices} services
        </span>
      </div>

      {error && (
        <div className="tools-error">
          <span className="error-icon">⚠</span>
          <span className="error-message">{error}</span>
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      <div className="tools-groups">
        {SERVICE_GROUPS.map((group) => (
          <ServiceGroup
            key={group.name}
            group={group}
            onToggleService={handleToggleService}
          />
        ))}
      </div>
    </div>
  );
}
