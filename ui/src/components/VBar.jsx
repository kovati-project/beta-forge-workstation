import './VBar.css';

export function VBar({ pct = 0, variant = 'cyan' }) {
  // Clamp percentage between 0 and 100
  const percentage = Math.min(Math.max(pct, 0), 100);

  return (
    <div className={`vbar vbar-${variant}`}>
      <div className="vbar-fill" style={{ width: `${percentage}%` }}></div>
    </div>
  );
}
