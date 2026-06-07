/**
 * Admin Page - Security & User Management
 * Routes to /#/admin in the main dashboard
 */

import { AdminPanel } from '../components/AdminPanel';
import './Admin.css';

export function Admin() {
  return (
    <div className="admin-page">
      <AdminPanel />
    </div>
  );
}
