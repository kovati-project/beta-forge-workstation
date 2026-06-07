import { useState, useEffect } from 'react';
import { getAlertHistory } from '../utils/monitorAPI';
import { Tag } from './Tag';
import './AlertHistorySection.css';

export function AlertHistorySection() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadAlerts = async () => {
      const data = await getAlertHistory();
      setAlerts(data.alerts || []);
      setLoading(false);
    };
    loadAlerts();
  }, []);

  const getSeverityColor = (severity) => {
    switch (severity?.toLowerCase()) {
      case 'critical':
      case 'crit':
        return 'red';
      case 'warning':
      case 'warn':
        return 'amber';
      case 'info':
        return 'cyan';
      default:
        return 'green';
    }
  };

  const formatDuration = (seconds) => {
    if (seconds < 60) return `${seconds}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
    return `${Math.floor(seconds / 3600)}h`;
  };

  if (loading) {
    return <div className="loading">Loading alert history...</div>;
  }

  return (
    <div className="alert-history-section">
      <table className="alerts-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Severity</th>
            <th>Fired</th>
            <th>Duration</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {alerts.length === 0 ? (
            <tr>
              <td colSpan="5" className="empty">
                No alerts (last 7 days)
              </td>
            </tr>
          ) : (
            alerts.map((alert, idx) => {
              const color = getSeverityColor(alert.severity);
              const duration =
                alert.duration || (Date.now() - new Date(alert.fired_at)) / 1000;

              return (
                <tr key={idx}>
                  <td className="alert-name">{alert.name}</td>
                  <td>
                    <Tag
                      label={alert.severity?.toUpperCase()}
                      variant={color}
                    />
                  </td>
                  <td className="timestamp">{alert.fired_at}</td>
                  <td className="duration">
                    {formatDuration(Math.round(duration))}
                  </td>
                  <td className="description">
                    {alert.description?.substring(0, 60)}
                    {alert.description?.length > 60 ? '...' : ''}
                  </td>
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}
