import './Toggle.css';

export function Toggle({ checked = false, disabled = false, onChange, title, ...props }) {
  const handleChange = (e) => onChange?.(e.target.checked);
  return (
    <label className={`toggle ${checked ? 'toggle-checked' : ''} ${disabled ? 'toggle-disabled' : ''}`} title={title}>
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={handleChange}
        {...props}
      />
      <span className="toggle-track">
        <span className="toggle-thumb"></span>
      </span>
    </label>
  );
}
