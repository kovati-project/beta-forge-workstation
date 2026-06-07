import { useState, useEffect } from 'react';
import { getAuthStatus, getAuthUsers, promoteUser, demoteUser, deleteUser } from '../utils/settingsAPI';
import { DotStatus } from './DotStatus';
import './AuthSection.css';

export function AuthSection({ isAppliance }) {
  const [authStatus, setAuthStatus] = useState(null);
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedUser, setExpandedUser] = useState(null);

  useEffect(() => {
    const loadAuth = async () => {
      const status = await getAuthStatus();
      const usersData = await getAuthUsers();
      setAuthStatus(status);
      setUsers(usersData.users || []);
      setLoading(false);
    };
    loadAuth();
  }, []);

  const handlePromote = async (userId) => {
    if (!window.confirm('Promote this user to admin?')) return;
    try {
      await promoteUser(userId);
      const usersData = await getAuthUsers();
      setUsers(usersData.users || []);
    } catch (err) {
      alert(`Failed: ${err.message}`);
    }
  };

  const handleDemote = async (userId) => {
    if (!window.confirm('Demote this user to regular user?')) return;
    try {
      await demoteUser(userId);
      const usersData = await getAuthUsers();
      setUsers(usersData.users || []);
    } catch (err) {
      alert(`Failed: ${err.message}`);
    }
  };

  const handleDelete = async (userId) => {
    if (!window.confirm('Delete this user? This cannot be undone.')) return;
    try {
      await deleteUser(userId);
      const usersData = await getAuthUsers();
      setUsers(usersData.users || []);
    } catch (err) {
      alert(`Failed: ${err.message}`);
    }
  };

  if (loading) {
    return <div className="auth-section loading">Loading auth config...</div>;
  }

  return (
    <div className="auth-section">
      <div className="auth-status">
        <span className="label">Authentik SSO</span>
        <span className="status">
          <DotStatus active={authStatus?.running} />
          {authStatus?.running ? 'running' : 'stopped'} :
          {authStatus?.port || '9080'}
          <a href="http://localhost:9080" target="_blank" rel="noopener noreferrer" className="open-link">
            Open ↗
          </a>
        </span>
      </div>

      {authStatus?.forward_auth && (
        <div className="forward-auth">
          <span className="label">Forward Auth</span>
          <span className="services">
            enabled: {authStatus.forward_auth.join(', ')}
          </span>
        </div>
      )}

      <div className="users-section">
        <div className="users-header">
          <span className="header-label">Users</span>
          {!isAppliance && (
            <a href="http://localhost:9080" target="_blank" rel="noopener noreferrer" className="add-user-btn">
              + Add User
            </a>
          )}
        </div>

        <table className="users-table">
          <thead>
            <tr>
              <th>Username</th>
              <th>Email</th>
              <th>Last Login</th>
              <th>Role</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.length === 0 ? (
              <tr>
                <td colSpan="5" className="empty">
                  No users
                </td>
              </tr>
            ) : (
              users.map((user) => (
                <tr key={user.id}>
                  <td className="username">{user.username}</td>
                  <td className="email">{user.email}</td>
                  <td className="last-login">{user.last_login || '—'}</td>
                  <td className="role">
                    <span className={`role-badge ${user.role}`}>
                      {user.role}
                    </span>
                  </td>
                  <td className="actions">
                    {!isAppliance && (
                      <div className="action-menu">
                        {user.role === 'user' ? (
                          <button
                            className="action-item promote"
                            onClick={() => handlePromote(user.id)}
                            title="Promote to admin"
                          >
                            ↑ Promote
                          </button>
                        ) : (
                          <button
                            className="action-item demote"
                            onClick={() => handleDemote(user.id)}
                            title="Demote to user"
                          >
                            ↓ Demote
                          </button>
                        )}
                        <button
                          className="action-item delete"
                          onClick={() => handleDelete(user.id)}
                          title="Delete user"
                        >
                          ✕ Delete
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
