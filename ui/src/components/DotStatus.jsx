import './DotStatus.css';

export function DotStatus({ status = 'gray' }) {
  return <span className={`dot-status dot-${status}`}></span>;
}
