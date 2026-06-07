import { Link, useLocation } from 'react-router-dom';
import './NavItem.css';

export function NavItem({ to, badge, children }) {
  const location = useLocation();
  const isActive = location.hash === `#${to}`;

  return (
    <Link to={to} className={`sidebar-nav-item ${isActive ? 'active' : ''}`}>
      <span>{children}</span>
      {badge && <span className="sidebar-nav-item-badge">{badge}</span>}
    </Link>
  );
}
