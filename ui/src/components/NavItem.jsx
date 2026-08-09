import { Link, useLocation } from 'react-router-dom';
import './NavItem.css';

export function NavItem({ to, badge, children }) {
  const location = useLocation();
  // Under HashRouter, useLocation() reports the route *inside* the hash, so
  // location.hash is empty and only pathname carries the current route.
  // Prefix-match so nested routes keep their parent nav item highlighted.
  const isActive =
    location.pathname === to ||
    (to !== '/' && location.pathname.startsWith(`${to}/`));

  return (
    <Link to={to} className={`sidebar-nav-item ${isActive ? 'active' : ''}`}>
      <span>{children}</span>
      {badge && <span className="sidebar-nav-item-badge">{badge}</span>}
    </Link>
  );
}
