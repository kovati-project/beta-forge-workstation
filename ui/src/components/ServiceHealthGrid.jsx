import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useApp } from '../context/AppContext';
import { DotStatus } from './DotStatus';
import './ServiceHealthGrid.css';

// Service categories for ordering
const SERVICE_CATEGORIES = {
  'vllm-pair-a': 'inference',
  'vllm-pair-b': 'inference',
  'ollama': 'inference',
  'comfyui': 'image',
  'kohya': 'training',
  'axolotl': 'training',
  'qdrant': 'storage',
  'minio': 'storage',
  'postgres': 'storage',
  'redis': 'storage',
  'open-webui': 'inference',
  'searxng': 'search',
  'caddy': 'networking',
  'grafana': 'monitoring',
  'prometheus': 'monitoring',
  'loki': 'monitoring',
};

function getServiceStatus(service) {
  if (!service || !service.status) return 'gray';
  if (service.status === 'running') return 'green';
  if (service.status === 'starting' || service.status === 'degraded') return 'amber';
  return 'red';
}

export function ServiceHealthGrid() {
  const { state } = useApp();
  const navigate = useNavigate();

  const orderedServices = useMemo(() => {
    if (!state.services) return [];
    
    const entries = Object.entries(state.services);
    
    // Sort by category then name
    return entries.sort(([nameA], [nameB]) => {
      const catA = SERVICE_CATEGORIES[nameA] || 'other';
      const catB = SERVICE_CATEGORIES[nameB] || 'other';
      
      if (catA !== catB) {
        return Object.keys(SERVICE_CATEGORIES).indexOf(nameA) - 
               Object.keys(SERVICE_CATEGORIES).indexOf(nameB);
      }
      return nameA.localeCompare(nameB);
    });
  }, [state.services]);

  const handleServiceClick = (serviceName) => {
    navigate(`/#/tools?focus=${serviceName}`);
  };

  return (
    <div className="service-health-grid">
      {orderedServices.length === 0 ? (
        <div className="service-grid-empty">Loading services…</div>
      ) : (
        orderedServices.map(([name, service]) => (
          <div
            key={name}
            className="service-tile"
            onClick={() => handleServiceClick(name)}
          >
            <div className="service-tile-header">
              <DotStatus status={getServiceStatus(service)} />
              <span className="service-tile-name">{name}</span>
            </div>
            <div className="service-tile-port">
              {service.port ? `:${service.port}` : '—'}
            </div>
          </div>
        ))
      )}
    </div>
  );
}
