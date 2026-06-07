import './Btn.css';

export function Btn({ variant = 'gray', size = 'md', disabled = false, children, ...props }) {
  return (
    <button 
      className={`btn btn-${variant} btn-${size}`}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
}
