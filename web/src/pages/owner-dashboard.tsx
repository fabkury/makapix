import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';

interface User {
  id: string;
  handle: string;
  display_name: string;
  email?: string;
  roles: string[];
  created_at: string;
  github_username?: string;
}

interface PageResponse<T> {
  items: T[];
  next_cursor: string | null;
}

export default function OwnerDashboardPage() {
  const router = useRouter();
  const [isOwner, setIsOwner] = useState(false);
  const [loading, setLoading] = useState(true);
  const [users, setUsers] = useState<User[]>([]);
  const [anonymousUsers, setAnonymousUsers] = useState<User[]>([]);
  const [showAnonymous, setShowAnonymous] = useState(false);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [anonymousCursor, setAnonymousCursor] = useState<string | null>(null);
  const [loadingUsers, setLoadingUsers] = useState(false);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);

  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const timer = setTimeout(() => {
        checkOwnerStatus();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, []);

  useEffect(() => {
    if (isOwner) {
      loadAuthenticatedUsers();
    }
  }, [isOwner]);

  const checkOwnerStatus = async () => {
    try {
      const accessToken = localStorage.getItem('access_token');
      
      if (!accessToken) {
        router.push('/');
        return;
      }

      const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });

      if (!response.ok) {
        setLoading(false);
        router.push('/');
        return;
      }

      const data = await response.json();
      const userRoles = Array.isArray(data.roles) ? data.roles : [];
      
      if (!userRoles.includes('owner')) {
        setLoading(false);
        router.push('/');
        return;
      }

      setIsOwner(true);
      setCurrentUserId(data.user?.id || null);
      setLoading(false);
    } catch (error) {
      console.error('Error checking owner status:', error);
      setLoading(false);
      router.push('/');
    }
  };

  const loadAuthenticatedUsers = async (cursor: string | null = null) => {
    setLoadingUsers(true);
    try {
      const accessToken = localStorage.getItem('access_token');
      const url = cursor 
        ? `${API_BASE_URL}/api/admin/owner/users?cursor=${encodeURIComponent(cursor)}&limit=50`
        : `${API_BASE_URL}/api/admin/owner/users?limit=50`;

      const response = await fetch(url, {
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });

      if (!response.ok) throw new Error('Failed to load users');

      const data: PageResponse<User> = await response.json();
      if (cursor) {
        setUsers([...users, ...data.items]);
      } else {
        setUsers(data.items);
      }
      setNextCursor(data.next_cursor);
    } catch (error) {
      console.error('Error loading users:', error);
    } finally {
      setLoadingUsers(false);
    }
  };

  const loadAnonymousUsers = async (cursor: string | null = null) => {
    setLoadingUsers(true);
    try {
      const accessToken = localStorage.getItem('access_token');
      const url = cursor 
        ? `${API_BASE_URL}/api/admin/owner/users/anonymous?cursor=${encodeURIComponent(cursor)}&limit=50`
        : `${API_BASE_URL}/api/admin/owner/users/anonymous?limit=50`;

      const response = await fetch(url, {
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });

      if (!response.ok) {
        if (!cursor) {
          setAnonymousUsers([]);
          setAnonymousCursor(null);
        }
        return;
      }

      const data: PageResponse<User> = await response.json();
      if (cursor) {
        setAnonymousUsers([...anonymousUsers, ...data.items]);
      } else {
        setAnonymousUsers(data.items);
      }
      setAnonymousCursor(data.next_cursor);
    } catch (error) {
      console.error('Error loading anonymous users:', error);
      if (!cursor) {
        setAnonymousUsers([]);
        setAnonymousCursor(null);
      }
    } finally {
      setLoadingUsers(false);
    }
  };

  const promoteModerator = async (userId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/api/admin/users/${userId}/moderator`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${accessToken}`, 'Content-Type': 'application/json' }
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to promote user');
      }

      loadAuthenticatedUsers();
    } catch (error: any) {
      console.error('Error promoting user:', error);
      alert(error.message || 'Failed to promote user');
    }
  };

  const demoteModerator = async (userId: string) => {
    try {
      const accessToken = localStorage.getItem('access_token');
      const response = await fetch(`${API_BASE_URL}/api/admin/users/${userId}/moderator`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${accessToken}` }
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to demote user');
      }

      loadAuthenticatedUsers();
    } catch (error: any) {
      console.error('Error demoting user:', error);
      alert(error.message || 'Failed to demote user');
    }
  };

  const handleShowAnonymous = () => {
    setShowAnonymous(true);
    if (anonymousUsers.length === 0) {
      loadAnonymousUsers();
    }
  };

  if (loading) {
    return (
      <Layout title="Site Owner Dashboard">
        <div className="loading-container">
          <div className="loading-spinner"></div>
          <p>Checking owner status...</p>
        </div>
        <style jsx>{`
          .loading-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: calc(100vh - var(--header-height));
            gap: 16px;
          }
          .loading-container p {
            color: var(--text-muted);
            font-size: 0.9rem;
          }
          .loading-spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--bg-tertiary);
            border-top-color: var(--accent-cyan);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
          }
          @keyframes spin { to { transform: rotate(360deg); } }
        `}</style>
      </Layout>
    );
  }

  if (!isOwner) return null;

  const displayUsers = showAnonymous ? anonymousUsers : users;
  const currentCursor = showAnonymous ? anonymousCursor : nextCursor;

  return (
    <Layout title="Site Owner Dashboard">
      <div className="dashboard">
        <h1>Site Owner Dashboard</h1>
        
        <div className="tabs">
          <button 
            onClick={() => setShowAnonymous(false)}
            className={`tab ${!showAnonymous ? 'active' : ''}`}
          >
            Authenticated Users
          </button>
          <button 
            onClick={handleShowAnonymous}
            className={`tab ${showAnonymous ? 'active' : ''}`}
          >
            Anonymous Users
          </button>
        </div>

        <p className="description">
          {showAnonymous 
            ? 'Users without GitHub authentication. These cannot be promoted to moderator.'
            : 'Users with GitHub authentication. Only these can be promoted to moderator.'}
        </p>

        {loadingUsers && displayUsers.length === 0 && (
          <div className="loading-state">
            <div className="loading-spinner-small"></div>
            <span>Loading users...</span>
          </div>
        )}

        {!loadingUsers && displayUsers.length === 0 && (
          <div className="empty-state">
            <p>No users found.</p>
          </div>
        )}

        {displayUsers.length > 0 && (
          <div className="table-container">
            <table className="users-table">
              <thead>
                <tr>
                  <th>Handle</th>
                  <th>Display Name</th>
                  {!showAnonymous && <th>Email</th>}
                  {!showAnonymous && <th>GitHub</th>}
                  <th>Roles</th>
                  <th>Created</th>
                  {!showAnonymous && <th>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {displayUsers.map((user) => {
                  const isCurrentUser = user.id === currentUserId;
                  const userRoles = user.roles || [];
                  const isModerator = userRoles.includes('moderator');
                  const isOwnerUser = userRoles.includes('owner');

                  return (
                    <tr key={user.id}>
                      <td>@{user.handle}</td>
                      <td>{user.display_name}</td>
                      {!showAnonymous && <td>{user.email || '-'}</td>}
                      {!showAnonymous && <td>{user.github_username || '-'}</td>}
                      <td>
                        <div className="roles">
                          {userRoles.map(role => (
                            <span key={role} className={`role-badge role-${role}`}>{role}</span>
                          ))}
                        </div>
                      </td>
                      <td>{new Date(user.created_at).toLocaleDateString()}</td>
                      {!showAnonymous && (
                        <td>
                          {isOwnerUser ? (
                            <span className="owner-badge">Owner</span>
                          ) : isModerator ? (
                            <button
                              onClick={() => demoteModerator(user.id)}
                              disabled={isCurrentUser}
                              className="action-btn danger"
                            >
                              Demote
                            </button>
                          ) : (
                            <button
                              onClick={() => promoteModerator(user.id)}
                              className="action-btn success"
                            >
                              Promote
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {currentCursor && (
          <button
            onClick={() => {
              if (showAnonymous) {
                loadAnonymousUsers(currentCursor);
              } else {
                loadAuthenticatedUsers(currentCursor);
              }
            }}
            disabled={loadingUsers}
            className="load-more"
          >
            {loadingUsers ? 'Loading...' : 'Load More'}
          </button>
        )}
      </div>

      <style jsx>{`
        .dashboard {
          max-width: 1200px;
          margin: 0 auto;
          padding: 24px;
        }

        h1 {
          font-size: 1.75rem;
          color: var(--text-primary);
          margin-bottom: 24px;
        }

        .tabs {
          display: flex;
          gap: 8px;
          margin-bottom: 16px;
        }

        .tab {
          padding: 10px 20px;
          background: var(--bg-secondary);
          color: var(--text-muted);
          border-radius: 8px;
          transition: all var(--transition-fast);
        }

        .tab:hover {
          background: var(--bg-tertiary);
        }

        .tab.active {
          background: var(--accent-cyan);
          color: var(--bg-primary);
        }

        .description {
          color: var(--text-secondary);
          font-size: 0.9rem;
          margin-bottom: 24px;
        }

        .loading-state,
        .empty-state {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 12px;
          padding: 48px;
          color: var(--text-muted);
        }

        .loading-spinner-small {
          width: 24px;
          height: 24px;
          border: 2px solid var(--bg-tertiary);
          border-top-color: var(--accent-cyan);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin { to { transform: rotate(360deg); } }

        .table-container {
          overflow-x: auto;
          border-radius: 12px;
          background: var(--bg-secondary);
        }

        .users-table {
          width: 100%;
          border-collapse: collapse;
        }

        .users-table th {
          text-align: left;
          padding: 16px;
          color: var(--text-muted);
          font-size: 0.85rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .users-table td {
          padding: 14px 16px;
          color: var(--text-secondary);
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .users-table tr:hover td {
          background: rgba(255, 255, 255, 0.02);
        }

        .roles {
          display: flex;
          gap: 6px;
          flex-wrap: wrap;
        }

        .role-badge {
          font-size: 0.75rem;
          padding: 2px 8px;
          border-radius: 10px;
          background: var(--bg-tertiary);
          color: var(--text-muted);
        }

        .role-owner {
          background: rgba(255, 110, 180, 0.2);
          color: var(--accent-pink);
        }

        .role-moderator {
          background: rgba(0, 212, 255, 0.2);
          color: var(--accent-cyan);
        }

        .owner-badge {
          font-size: 0.8rem;
          color: var(--accent-pink);
          font-style: italic;
        }

        .action-btn {
          padding: 6px 14px;
          border-radius: 6px;
          font-size: 0.85rem;
          font-weight: 500;
          transition: all var(--transition-fast);
        }

        .action-btn.success {
          background: rgba(16, 185, 129, 0.2);
          color: #10b981;
        }

        .action-btn.success:hover {
          background: #10b981;
          color: white;
        }

        .action-btn.danger {
          background: rgba(239, 68, 68, 0.2);
          color: #ef4444;
        }

        .action-btn.danger:hover:not(:disabled) {
          background: #ef4444;
          color: white;
        }

        .action-btn:disabled {
          opacity: 0.4;
          cursor: not-allowed;
        }

        .load-more {
          display: block;
          width: 100%;
          padding: 14px;
          margin-top: 16px;
          background: var(--bg-secondary);
          color: var(--accent-cyan);
          border-radius: 8px;
          font-weight: 500;
          transition: all var(--transition-fast);
        }

        .load-more:hover:not(:disabled) {
          background: var(--bg-tertiary);
        }

        .load-more:disabled {
          opacity: 0.5;
        }
      `}</style>
    </Layout>
  );
}
