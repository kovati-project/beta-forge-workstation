import './Panel.css';

export function Panel({ title, subtitle, children }) {
  return (
    <div className="panel">
      {(title || subtitle) && (
        <div className="panel-header">
          <div>
            {title && <div className="panel-title">{title}</div>}
            {subtitle && <div className="panel-subtitle">{subtitle}</div>}
          </div>
        </div>
      )}
      <div className="panel-body">
        {children}
      </div>
    </div>
  );
}
