import './MetricRow.css';

export function MetricRow({ label, value, unit }) {
  return (
    <div className="metric-row">
      <div className="metric-label">{label}</div>
      <div className="metric-value">
        {value}
        {unit && <span className="metric-unit">{unit}</span>}
      </div>
    </div>
  );
}
