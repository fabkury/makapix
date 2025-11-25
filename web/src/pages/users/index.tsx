import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';

interface User {
  id: string;
  handle: string;
  bio: string | null;
  avatar_url: string | null;
  reputation: number;
  created_at: string;
}

interface UserListResponse {
  items: User[];
  next_cursor: string | null;
}

export default function UsersDirectoryPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedQuery, setDebouncedQuery] = useState('');
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<'alphabetical' | 'recent' | 'reputation'>('alphabetical');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
    : '';

  // Check authentication
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/auth');
      return;
    }
    setIsAuthenticated(true);
  }, [router]);

  // Debounce search query
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const fetchUsers = useCallback(async (cursor?: string, append = false) => {
    if (!append) {
      setLoading(true);
    } else {
      setLoadingMore(true);
    }
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set('limit', '50');
      params.set('sort', sortBy);
      
      if (debouncedQuery.trim()) {
        params.set('q', debouncedQuery.trim());
      }
      if (cursor) {
        params.set('cursor', cursor);
      }

      const token = localStorage.getItem('access_token');
      if (!token) {
        throw new Error('Not authenticated');
      }

      const response = await fetch(`${API_BASE_URL}/api/users/browse?${params.toString()}`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          localStorage.removeItem('access_token');
          localStorage.removeItem('user_id');
          router.push('/auth');
          return;
        }
        if (response.status === 404) {
          setUsers([]);
          setNextCursor(null);
          return;
        }
        throw new Error(`Failed to fetch users: ${response.statusText}`);
      }

      const data: UserListResponse = await response.json();
      const items = data.items || [];

      if (append) {
        setUsers(prev => [...prev, ...items]);
      } else {
        setUsers(items);
      }
      setNextCursor(data.next_cursor);
    } catch (err) {
      console.error('Error fetching users:', err);
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to load users');
      }
    } finally {
      setLoading(false);
      setLoadingMore(false);
    }
  }, [API_BASE_URL, debouncedQuery, sortBy, router]);

  // Fetch users when query or sort changes
  useEffect(() => {
    if (isAuthenticated) {
      fetchUsers();
    }
  }, [fetchUsers, isAuthenticated]);

  const handleLoadMore = () => {
    if (nextCursor && !loadingMore) {
      fetchUsers(nextCursor, true);
    }
  };

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
  };

  const handleSortChange = (newSort: 'alphabetical' | 'recent' | 'reputation') => {
    setSortBy(newSort);
    setUsers([]);
    setNextCursor(null);
  };

  const getAvatarUrl = (avatarUrl: string | null): string | null => {
    if (!avatarUrl) return null;
    if (avatarUrl.startsWith('http')) return avatarUrl;
    return `${API_BASE_URL}${avatarUrl}`;
  };

  // Don't render until authenticated
  if (!isAuthenticated) {
    return (
      <Layout title="Browse Users">
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '50vh' }}>
          <div className="loading-spinner" style={{ width: 40, height: 40, border: '3px solid var(--bg-tertiary)', borderTopColor: 'var(--accent-cyan)', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }}></div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout title="Browse Users" description="Discover pixel art creators">
      <div className="users-container">
        <div className="users-header">
          <h1>Users</h1>
        </div>

        <div className="controls">
          <div className="search-box">
            <span className="search-icon">🔍</span>
            <input
              type="text"
              placeholder="Search users..."
              value={searchQuery}
              onChange={handleSearchChange}
              className="search-input"
            />
            {searchQuery && (
              <button 
                className="clear-search"
                onClick={() => setSearchQuery('')}
              >
                ✕
              </button>
            )}
          </div>

          <div className="sort-buttons">
            <button
              className={`sort-btn ${sortBy === 'alphabetical' ? 'active' : ''}`}
              onClick={() => handleSortChange('alphabetical')}
            >
              A-Z
            </button>
            <button
              className={`sort-btn ${sortBy === 'recent' ? 'active' : ''}`}
              onClick={() => handleSortChange('recent')}
            >
              Recent
            </button>
            <button
              className={`sort-btn ${sortBy === 'reputation' ? 'active' : ''}`}
              onClick={() => handleSortChange('reputation')}
            >
              Reputation
            </button>
          </div>
        </div>

        {error && (
          <div className="error-message">
            <span className="error-icon">⚠️</span>
            <p>{error}</p>
            <button onClick={() => fetchUsers()} className="retry-button">
              Retry
            </button>
          </div>
        )}

        {loading && (
          <div className="loading-state">
            <div className="loading-spinner"></div>
          </div>
        )}

        {!loading && !error && users.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon-container">
              <span className="empty-icon">👥</span>
            </div>
            {debouncedQuery ? (
              <>
                <h2>No users found</h2>
                <p className="empty-description">
                  No users match &quot;{debouncedQuery}&quot;
                </p>
                <button onClick={() => setSearchQuery('')} className="browse-link">
                  Clear Search
                </button>
              </>
            ) : (
              <>
                <h2>No users yet</h2>
                <Link href="/" className="browse-link">
                  Browse Recent Art →
                </Link>
              </>
            )}
          </div>
        )}

        {!loading && !error && users.length > 0 && (
          <>
            <div className="users-count">
              {users.length} user{users.length !== 1 ? 's' : ''}
              {debouncedQuery && ` matching "${debouncedQuery}"`}
            </div>

            <div className="users-grid">
              {users.map((user) => {
                const avatarUrl = getAvatarUrl(user.avatar_url);
                return (
                  <Link 
                    key={user.id} 
                    href={`/users/${user.id}`}
                    className="user-card"
                  >
                    <div className="user-avatar-container">
                      {avatarUrl ? (
                        <img 
                          src={avatarUrl} 
                          alt={user.handle}
                          className="user-avatar"
                        />
                      ) : (
                        <svg width="32" height="32" viewBox="0 0 24 24" fill="currentColor" className="user-avatar-icon">
                          <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                        </svg>
                      )}
                    </div>
                    <div className="user-info">
                      <span className="user-handle">{user.handle}</span>
                      {user.reputation > 0 && (
                        <span className="user-reputation">⭐ {user.reputation}</span>
                      )}
                    </div>
                  </Link>
                );
              })}
            </div>

            {nextCursor && (
              <div className="load-more-container">
                <button 
                  onClick={handleLoadMore} 
                  disabled={loadingMore}
                  className="load-more-btn"
                >
                  {loadingMore ? 'Loading...' : 'Load More'}
                </button>
              </div>
            )}
          </>
        )}
      </div>

      <style jsx>{`
        .users-container {
          width: 100%;
          min-height: calc(100vh - var(--header-height));
          padding: 24px;
          max-width: 1200px;
          margin: 0 auto;
        }

        .users-header {
          text-align: center;
          margin-bottom: 32px;
        }

        .users-header h1 {
          font-size: 2rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0;
        }

        .controls {
          display: flex;
          flex-wrap: wrap;
          gap: 16px;
          margin-bottom: 24px;
          align-items: center;
          justify-content: space-between;
        }

        .search-box {
          flex: 1;
          min-width: 250px;
          max-width: 400px;
          position: relative;
          display: flex;
          align-items: center;
        }

        .search-icon {
          position: absolute;
          left: 16px;
          font-size: 1rem;
          opacity: 0.6;
        }

        .search-input {
          width: 100%;
          padding: 12px 40px 12px 44px;
          background: var(--bg-secondary);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 12px;
          color: var(--text-primary);
          font-size: 1rem;
          transition: all var(--transition-fast);
        }

        .search-input:focus {
          outline: none;
          border-color: var(--accent-cyan);
          box-shadow: 0 0 0 3px rgba(78, 205, 196, 0.15);
        }

        .search-input::placeholder {
          color: var(--text-muted);
        }

        .clear-search {
          position: absolute;
          right: 12px;
          width: 24px;
          height: 24px;
          border-radius: 50%;
          background: var(--bg-tertiary);
          color: var(--text-muted);
          font-size: 0.8rem;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all var(--transition-fast);
          border: none;
          cursor: pointer;
        }

        .clear-search:hover {
          background: var(--accent-pink);
          color: white;
        }

        .sort-buttons {
          display: flex;
          gap: 8px;
        }

        .sort-btn {
          padding: 10px 20px;
          background: var(--bg-secondary);
          color: var(--text-secondary);
          border-radius: 8px;
          font-size: 0.9rem;
          font-weight: 500;
          transition: all var(--transition-fast);
          border: none;
          cursor: pointer;
        }

        .sort-btn:hover {
          background: var(--bg-tertiary);
        }

        .sort-btn.active {
          background: var(--accent-cyan);
          color: var(--bg-primary);
        }

        .error-message {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 3rem;
          text-align: center;
          color: var(--text-secondary);
        }

        .error-icon {
          font-size: 3rem;
          margin-bottom: 1rem;
        }

        .retry-button {
          margin-top: 1rem;
          padding: 0.75rem 1.5rem;
          background: var(--accent-pink);
          color: white;
          border-radius: 8px;
          font-weight: 600;
          transition: all var(--transition-fast);
          border: none;
          cursor: pointer;
        }

        .retry-button:hover {
          box-shadow: var(--glow-pink);
        }

        .loading-state {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 4rem;
        }

        .loading-spinner {
          width: 40px;
          height: 40px;
          border: 3px solid var(--bg-tertiary);
          border-top-color: var(--accent-cyan);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }

        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 4rem 2rem;
          text-align: center;
          max-width: 500px;
          margin: 0 auto;
        }

        .empty-icon-container {
          width: 120px;
          height: 120px;
          border-radius: 50%;
          background: var(--bg-secondary);
          display: flex;
          align-items: center;
          justify-content: center;
          margin-bottom: 24px;
        }

        .empty-icon {
          font-size: 4rem;
        }

        .empty-state h2 {
          font-size: 1.5rem;
          color: var(--text-primary);
          margin: 0 0 12px 0;
        }

        .empty-description {
          font-size: 1rem;
          color: var(--text-secondary);
          line-height: 1.6;
          margin: 0 0 24px 0;
        }

        .browse-link {
          display: inline-block;
          padding: 12px 24px;
          background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
          color: white;
          font-weight: 600;
          border-radius: 10px;
          transition: all var(--transition-fast);
          text-decoration: none;
        }

        .browse-link:hover {
          box-shadow: var(--glow-purple);
          transform: translateY(-2px);
        }

        .users-count {
          font-size: 0.9rem;
          color: var(--text-muted);
          margin-bottom: 16px;
        }

        .users-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
          gap: 12px;
        }

        @media (min-width: 768px) {
          .users-grid {
            grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
          }
        }

        .user-card {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 16px 20px;
          background: var(--bg-secondary);
          border-radius: 12px;
          text-decoration: none;
          transition: all var(--transition-fast);
          border: 1px solid transparent;
        }

        .user-card:hover {
          background: var(--bg-tertiary);
          border-color: var(--accent-purple);
          box-shadow: var(--glow-purple);
          transform: translateY(-2px);
        }

        .user-avatar-container {
          width: 40px;
          height: 40px;
          border-radius: 50%;
          background: var(--bg-tertiary);
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          overflow: hidden;
        }

        .user-avatar {
          width: 100%;
          height: 100%;
          object-fit: cover;
          border-radius: 50%;
        }

        .user-avatar-icon {
          width: 24px;
          height: 24px;
          color: var(--text-muted);
        }

        .user-info {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 4px;
          min-width: 0;
        }

        .user-handle {
          font-size: 0.95rem;
          font-weight: 500;
          color: var(--text-primary);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .user-reputation {
          font-size: 0.8rem;
          color: var(--text-muted);
        }

        .load-more-container {
          display: flex;
          justify-content: center;
          margin-top: 32px;
        }

        .load-more-btn {
          padding: 14px 32px;
          background: var(--bg-secondary);
          color: var(--accent-cyan);
          border-radius: 10px;
          font-size: 1rem;
          font-weight: 600;
          transition: all var(--transition-fast);
          border: none;
          cursor: pointer;
        }

        .load-more-btn:hover:not(:disabled) {
          background: var(--bg-tertiary);
          box-shadow: var(--glow-cyan);
        }

        .load-more-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        @media (max-width: 600px) {
          .controls {
            flex-direction: column;
            align-items: stretch;
          }

          .search-box {
            max-width: 100%;
          }

          .sort-buttons {
            justify-content: center;
          }
        }
      `}</style>
    </Layout>
  );
}

