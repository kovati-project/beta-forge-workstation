export function HelpNav({ active, onChange }) {
  const sections = [
    { id: 'common-tasks', label: 'Common Tasks' },
    'divider',
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'loadout', label: 'Loadout' },
    { id: 'tools', label: 'Tools' },
    { id: 'training', label: 'Training' },
    { id: 'resources', label: 'Resources' },
    { id: 'expose', label: 'Expose' },
    { id: 'voice', label: 'Voice' },
    { id: 'monitor', label: 'Monitor' },
    { id: 'operations', label: 'Operations' },
    { id: 'admin', label: 'Admin' },
    { id: 'settings', label: 'Settings' },
  ];

  return (
    <nav className="help-nav">
      <div className="help-nav-section-header">Documentation</div>
      {sections.map((item, i) =>
        item === 'divider' ? (
          <hr key={i} className="help-nav-divider" />
        ) : (
          <button
            key={item.id}
            className={`help-nav-item ${active === item.id ? 'active' : ''}`}
            onClick={() => onChange(item.id)}
          >
            {item.label}
          </button>
        )
      )}
    </nav>
  );
}
