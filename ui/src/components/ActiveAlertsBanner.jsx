import './ActiveAlertsBanner.css';

export function ActiveAlertsBanner({ alerts, onViewHistory }) {
  if (!alerts || alerts.length === 0) return null;

  return (
    <div className="active-alerts-banner">
      <div className="banner-header">
        ⚠ {alerts.length} active {alerts.length === 1 ? 'alert' : 'alerts'}
      </div>
      <div className="banner-alerts">
        {alerts.slice(0, 5).map((alert, idx) => (
          <div key={idx} className="alert-item">
            {alert.description?.substring(0, 80)}
            {alert.description?.length > 80 ? '...' : ''}
          </div>
        ))}
      </div>
      <button className="view-history-btn" onClick={onViewHistory}>
        View Alert History ↓
      </button>
    </div>
  );
}
