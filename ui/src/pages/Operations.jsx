/**
 * Operations Page - System Operations & Maintenance
 * Routes to /#/operations in the main dashboard
 */

import { OperationsPanel } from '../components/OperationsPanel';
import './Operations.css';

export function Operations() {
  return (
    <div className="operations-page">
      <OperationsPanel />
    </div>
  );
}
