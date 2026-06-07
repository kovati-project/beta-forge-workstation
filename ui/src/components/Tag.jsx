import './Tag.css';

export function Tag({ variant = 'gray', children }) {
  return (
    <span className={`tag tag-${variant}`}>
      {children}
    </span>
  );
}
