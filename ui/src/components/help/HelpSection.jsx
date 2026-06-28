export function HelpSection({ title, subtitle, children }) {
  return (
    <div className="help-section">
      <div className="help-section-header">
        <h2 className="help-section-title">{title}</h2>
        {subtitle && <p className="help-section-subtitle">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}
