import { useState, useEffect } from 'react';
import { getNetworkRoutes, updateNetworkRoute } from '../utils/exposeAPI';
import { DotStatus } from './DotStatus';
import './ExternalAccessSection.css';

export function ExternalAccessSection() {
  const [routes, setRoutes] = useState([]);
  const [caddyStatus, setCaddyStatus] = useState('running');
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(null);
  const [warnings, setWarnings] = useState({});

  useEffect(() => {
    loadRoutes();
  }, []);

  const loadRoutes = async () => {
    setLoading(true);
    const data = await getNetworkRoutes();
    setRoutes(data.routes || []);
    setCaddyStatus(data.caddy_status || 'running');
    setLoading(false);
  };

  const handleToggleExposure = async (service, currentlyExposed) => {
    setUpdating(service);
    try {
      await updateNetworkRoute(service, !currentlyExposed);

      // Check for security warnings
      if (!currentlyExposed && (service.includes('vllm') || service.includes('ollama'))) {
        setWarnings((prev) => ({
          ...prev,
          [service]: '⚠ Ensure API key authentication is configured',
        }));
        setTimeout(() => {
          setWarnings((prev) => {
            const copy = { ...prev };
            delete copy[service];
            return copy;
          });
        }, 5000);
      }

      await loadRoutes();
    } catch (error) {
      console.error('Failed to update route:', error);
    } finally {
      setUpdating(null);
    }
  };

  return (
    <div className="external-access-section">
      <div className="caddy-status">
        <span>Caddy reverse proxy:</span>
        <div className="status-indicator">
          <DotStatus status={caddyStatus} />
          <span>{caddyStatus}</span>
        </div>
      </div>

      {loading ? (
        <div className="loading">Loading routes...</div>
      ) : (
        <>
          <table className="routes-table">
            <thead>
              <tr>
                <th>Service</th>
                <th>External Path</th>
                <th>Exposed</th>
                <th>Toggle</th>
              </tr>
            </thead>
            <tbody>
              {routes.length === 0 ? (
                <tr>
                  <td colSpan="4" className="empty">
                    No routes configured
                  </td>
                </tr>
              ) : (
                routes.map((route) => {
                  const warning = warnings[route.service];
                  return (
                    <tr key={route.service}>
                      <td className="service-name">{route.service}</td>
                      <td className="path">{route.path}</td>
                      <td>
                        <span className={`exposed-badge ${route.exposed ? 'yes' : 'no'}`}>
                          {route.exposed ? '●yes' : '○no'}
                        </span>
                      </td>
                      <td>
                        <button
                          className={`toggle-btn ${route.exposed ? 'exposed' : ''}`}
                          onClick={() =>
                            handleToggleExposure(route.service, route.exposed)
                          }
                          disabled={updating === route.service}
                          title={route.exposed ? 'Hide service' : 'Expose service'}
                        >
                          {route.exposed ? '●' : '○'}
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>

          {Object.keys(warnings).length > 0 && (
            <div className="warning-banner">
              ⚠ Exposing inference endpoints externally requires API key auth
            </div>
          )}
        </>
      )}
    </div>
  );
}
