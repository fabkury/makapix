import { useState, useEffect } from 'react';
import Head from 'next/head';
import { useRouter } from 'next/router';

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

  // Debug: Log immediately when component mounts
  if (typeof window !== 'undefined') {
    console.log('Owner Dashboard: Component mounted', {
      pathname: window.location.pathname,
      apiBaseUrl: API_BASE_URL,
      hasAccessToken: !!localStorage.getItem('access_token')
    });
  }

  useEffect(() => {
    // Only check owner status on client side
    if (typeof window !== 'undefined') {
      console.log('Owner Dashboard: useEffect running');
      // Small delay to ensure router is ready
      const timer = setTimeout(() => {
        console.log('Owner Dashboard: Calling checkOwnerStatus');
        checkOwnerStatus();
      }, 100);
      return () => clearTimeout(timer);
    }
  }, []);

  useEffect(() => {
    if (isOwner) {
      console.log('Owner Dashboard: isOwner is true, loading authenticated users...');
      loadAuthenticatedUsers();
    } else {
      console.log('Owner Dashboard: isOwner is false, not loading users');
    }
  }, [isOwner]);

  const checkOwnerStatus = async () => {
    try {
      console.log('Owner Dashboard: checkOwnerStatus called');
      const accessToken = localStorage.getItem('access_token');
      console.log('Owner Dashboard: Checking owner status...', {
        hasAccessToken: !!accessToken,
        accessTokenLength: accessToken?.length || 0,
        apiBaseUrl: API_BASE_URL,
        localStorageKeys: Object.keys(localStorage)
      });
      
      if (!accessToken) {
        console.error('Owner Dashboard: No access token found in localStorage');
        console.log('Owner Dashboard: Available localStorage keys:', Object.keys(localStorage));
        console.log('Owner Dashboard: About to redirect to home');
        // Add a small delay to ensure console logs are visible
        setTimeout(() => {
          router.push('/');
        }, 1000);
        return;
      }

      // Get current user info to check if owner
      const meUrl = `${API_BASE_URL}/api/auth/me`;
      console.log('Owner Dashboard: Fetching user info from:', meUrl);
      
      const response = await fetch(meUrl, {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      });

      console.log('Owner Dashboard: Auth response status:', response.status);

      if (!response.ok) {
        const errorText = await response.text();
        console.error('Owner Dashboard: Auth check failed:', response.status, errorText);
        setLoading(false);
        // Don't redirect immediately - show error message
        alert(`Failed to verify owner status: ${response.status} ${errorText}`);
        router.push('/');
        return;
      }

      const data = await response.json();
      console.log('Owner Dashboard: Full API response:', JSON.stringify(data, null, 2));
      console.log('Owner Dashboard: User data received:', {
        userId: data.user?.id,
        handle: data.user?.handle,
        roles: data.roles,
        userRoles: data.user?.roles
      });
      
      // API returns roles at top level: {roles: [...], user: {...}}
      const userRoles = Array.isArray(data.roles) ? data.roles : [];
      
      console.log('Owner Dashboard: Checking roles:', userRoles, 'Type:', typeof userRoles, 'includes owner?', userRoles.includes('owner'));
      
      if (!Array.isArray(userRoles) || !userRoles.includes('owner')) {
        console.error('Owner Dashboard: User is not owner', {
          roles: userRoles,
          rolesType: typeof userRoles,
          isArray: Array.isArray(userRoles),
          fullResponse: data
        });
        setLoading(false);
        alert(`Access denied. You need the 'owner' role. Current roles: ${JSON.stringify(userRoles)}`);
        // Add delay to ensure alert is visible
        setTimeout(() => {
          router.push('/');
        }, 2000);
        return;
      }

      console.log('Owner Dashboard: User is owner, proceeding...');
      setIsOwner(true);
      setCurrentUserId(data.user?.id || null);
      setLoading(false);
    } catch (error) {
      console.error('Owner Dashboard: Error checking owner status:', error);
      setLoading(false);
      alert(`Error checking owner status: ${error instanceof Error ? error.message : String(error)}`);
      router.push('/');
    }
  };

  const loadAuthenticatedUsers = async (cursor: string | null = null) => {
    console.log('Owner Dashboard: loadAuthenticatedUsers called', { cursor, isOwner });
    setLoadingUsers(true);
    try {
      const accessToken = localStorage.getItem('access_token');
      console.log('Owner Dashboard: loadAuthenticatedUsers - has access token:', !!accessToken);
      const url = cursor 
        ? `${API_BASE_URL}/api/admin/owner/users?cursor=${encodeURIComponent(cursor)}&limit=50`
        : `${API_BASE_URL}/api/admin/owner/users?limit=50`;

      console.log('Owner Dashboard: Fetching users from:', url);
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      });

      console.log('Owner Dashboard: Users API response status:', response.status);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Owner Dashboard: Users API error:', response.status, errorText);
        throw new Error(`Failed to load users: ${response.status} ${errorText}`);
      }

      const data: PageResponse<User> = await response.json();
      console.log('Owner Dashboard: Users data received:', data);
      if (cursor) {
        setUsers([...users, ...data.items]);
      } else {
        setUsers(data.items);
      }
      setNextCursor(data.next_cursor);
    } catch (error) {
      console.error('Error loading users:', error);
      alert('Failed to load users');
    } finally {
      setLoadingUsers(false);
    }
  };

  const loadAnonymousUsers = async (cursor: string | null = null) => {
    console.log('Owner Dashboard: Loading anonymous users...', { cursor });
    setLoadingUsers(true);
    try {
      const accessToken = localStorage.getItem('access_token');
      const url = cursor 
        ? `${API_BASE_URL}/api/admin/owner/users/anonymous?cursor=${encodeURIComponent(cursor)}&limit=50`
        : `${API_BASE_URL}/api/admin/owner/users/anonymous?limit=50`;

      console.log('Owner Dashboard: Fetching anonymous users from:', url);
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      });

      console.log('Owner Dashboard: Anonymous users API response status:', response.status);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Owner Dashboard: Anonymous users API error:', response.status, errorText);
        // Only show alert for actual errors (not empty results)
        if (response.status >= 500) {
          alert(`Failed to load anonymous users: ${response.status} ${errorText}`);
        }
        // For 4xx errors, just silently fail and show empty list
        if (cursor) {
          // If loading more, don't update state
          return;
        } else {
          setAnonymousUsers([]);
          setAnonymousCursor(null);
        }
        return;
      }

      const data: PageResponse<User> = await response.json();
      console.log('Owner Dashboard: Anonymous users data received:', data);
      
      if (cursor) {
        setAnonymousUsers([...anonymousUsers, ...data.items]);
      } else {
        setAnonymousUsers(data.items);
      }
      setAnonymousCursor(data.next_cursor);
    } catch (error) {
      console.error('Owner Dashboard: Error loading anonymous users:', error);
      // Only show alert for unexpected errors (network issues, etc.)
      if (error instanceof TypeError && error.message.includes('fetch')) {
        alert('Network error: Failed to load anonymous users. Please check your connection.');
      } else {
        // For other errors, silently fail and show empty list
        console.warn('Owner Dashboard: Silently handling error, showing empty list');
      }
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
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to promote user');
      }

      // Reload users
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
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to demote user');
      }

      // Reload users
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

  const handleBackToAuthenticated = () => {
    setShowAnonymous(false);
  };

  if (loading) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <p>Loading...</p>
        <p style={{ fontSize: '12px', color: '#666', marginTop: '10px' }}>
          Checking owner status...
        </p>
      </div>
    );
  }

  if (!isOwner) {
    return (
      <div style={{ padding: '20px', textAlign: 'center' }}>
        <p>Access denied. Owner role required.</p>
        <p style={{ fontSize: '12px', color: '#666', marginTop: '10px' }}>
          Please ensure you are logged in as the site owner.
        </p>
      </div>
    );
  }

  const displayUsers = showAnonymous ? anonymousUsers : users;
  const currentCursor = showAnonymous ? anonymousCursor : nextCursor;

  return (
    <>
      <Head>
        <title>Site Owner Dashboard - Makapix</title>
      </Head>
      <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
        <h1>Site Owner Dashboard</h1>
        
        {!showAnonymous && (
          <>
            <div style={{ marginBottom: '20px' }}>
              <button 
                onClick={handleShowAnonymous}
                style={{ padding: '10px 20px', marginRight: '10px' }}
              >
                View Anonymous Users
              </button>
            </div>
            
            <h2>Authenticated Users</h2>
            <p>Users with GitHub authentication. Only these can be promoted to moderator.</p>
          </>
        )}

        {showAnonymous && (
          <>
            <div style={{ marginBottom: '20px' }}>
              <button 
                onClick={handleBackToAuthenticated}
                style={{ padding: '10px 20px', marginRight: '10px' }}
              >
                Back to Authenticated Users
              </button>
            </div>
            
            <h2>Anonymous Users</h2>
            <p>Users without GitHub authentication. These cannot be promoted to moderator.</p>
          </>
        )}

        {loadingUsers && displayUsers.length === 0 && (
          <p>Loading users...</p>
        )}

        {!loadingUsers && displayUsers.length === 0 && (
          <p>No users found.</p>
        )}

        {displayUsers.length > 0 && (
          <>
            <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '20px' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #ddd' }}>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Handle</th>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Display Name</th>
                  {!showAnonymous && <th style={{ padding: '10px', textAlign: 'left' }}>Email</th>}
                  {!showAnonymous && <th style={{ padding: '10px', textAlign: 'left' }}>GitHub</th>}
                  <th style={{ padding: '10px', textAlign: 'left' }}>Roles</th>
                  <th style={{ padding: '10px', textAlign: 'left' }}>Created</th>
                  {!showAnonymous && <th style={{ padding: '10px', textAlign: 'left' }}>Actions</th>}
                </tr>
              </thead>
              <tbody>
                {displayUsers.map((user) => {
                  const isCurrentUser = user.id === currentUserId;
                  const userRoles = user.roles || [];
                  const isModerator = userRoles.includes('moderator');
                  const isOwnerUser = userRoles.includes('owner');

                  return (
                    <tr key={user.id} style={{ borderBottom: '1px solid #eee' }}>
                      <td style={{ padding: '10px' }}>{user.handle}</td>
                      <td style={{ padding: '10px' }}>{user.display_name}</td>
                      {!showAnonymous && (
                        <td style={{ padding: '10px' }}>{user.email || '-'}</td>
                      )}
                      {!showAnonymous && (
                        <td style={{ padding: '10px' }}>{user.github_username || '-'}</td>
                      )}
                      <td style={{ padding: '10px' }}>
                        {(user.roles || []).join(', ')}
                      </td>
                      <td style={{ padding: '10px' }}>
                        {new Date(user.created_at).toLocaleDateString()}
                      </td>
                      {!showAnonymous && (
                        <td style={{ padding: '10px' }}>
                          {isOwnerUser ? (
                            <span style={{ color: '#666', fontStyle: 'italic' }}>
                              Owner (cannot modify)
                            </span>
                          ) : (
                            <>
                              {isModerator ? (
                                <button
                                  onClick={() => demoteModerator(user.id)}
                                  disabled={isCurrentUser}
                                  style={{
                                    padding: '5px 10px',
                                    backgroundColor: '#dc3545',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '4px',
                                    cursor: isCurrentUser ? 'not-allowed' : 'pointer',
                                    opacity: isCurrentUser ? 0.5 : 1
                                  }}
                                >
                                  Demote Moderator
                                </button>
                              ) : (
                                <button
                                  onClick={() => promoteModerator(user.id)}
                                  style={{
                                    padding: '5px 10px',
                                    backgroundColor: '#28a745',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '4px',
                                    cursor: 'pointer'
                                  }}
                                >
                                  Promote Moderator
                                </button>
                              )}
                            </>
                          )}
                        </td>
                      )}
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {currentCursor && (
              <div style={{ marginTop: '20px', textAlign: 'center' }}>
                <button
                  onClick={() => {
                    if (showAnonymous) {
                      loadAnonymousUsers(currentCursor);
                    } else {
                      loadAuthenticatedUsers(currentCursor);
                    }
                  }}
                  disabled={loadingUsers}
                  style={{
                    padding: '10px 20px',
                    backgroundColor: '#007bff',
                    color: 'white',
                    border: 'none',
                    borderRadius: '4px',
                    cursor: loadingUsers ? 'not-allowed' : 'pointer',
                    opacity: loadingUsers ? 0.5 : 1
                  }}
                >
                  {loadingUsers ? 'Loading...' : 'Load More'}
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}

