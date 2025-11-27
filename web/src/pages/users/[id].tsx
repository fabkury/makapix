import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';
import CardGrid from '../../components/CardGrid';

interface User {
  id: string;
  handle: string;
  bio?: string;
  avatar_url?: string;
  reputation: number;
  created_at: string;
  roles?: string[];
  auto_public_approval?: boolean;
  banned_until?: string | null;
}

interface PostOwner {
  id: string;
  handle: string;
}

interface Post {
  id: string;
  title: string;
  description?: string;
  hashtags?: string[];
  art_url: string;
  canvas: string;
  owner_id: string;
  created_at: string;
  owner?: PostOwner;
}

interface PageResponse<T> {
  items: T[];
  next_cursor: string | null;
}

export default function UserProfilePage() {
  const router = useRouter();
  const { id } = router.query;
  
  const [user, setUser] = useState<User | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [blogPosts, setBlogPosts] = useState<any[]>([]);
  const [blogPostStats, setBlogPostStats] = useState<Record<string, { reactions: number; comments: number }>>({});
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [postsLoading, setPostsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  
  // Edit mode state
  const [isEditing, setIsEditing] = useState(false);
  const [editHandle, setEditHandle] = useState('');
  const [editBio, setEditBio] = useState('');
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isOwnProfile, setIsOwnProfile] = useState(false);
  const [isOwner, setIsOwner] = useState(false);
  const [isModerator, setIsModerator] = useState(false);
  
  const observerTarget = useRef<HTMLDivElement>(null);
  const loadingRef = useRef(false);
  const hasMoreRef = useRef(true);
  const nextCursorRef = useRef<string | null>(null);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  // Fetch user profile
  useEffect(() => {
    if (!id || typeof id !== 'string') return;

    const fetchUser = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const token = localStorage.getItem('access_token');
        const currentUserId = localStorage.getItem('user_id');
        const headers: HeadersInit = token ? { 'Authorization': `Bearer ${token}` } : {};
        
        const response = await fetch(`${API_BASE_URL}/api/users/${id}`, { headers });
        
        if (!response.ok) {
          if (response.status === 404) {
            setError('User not found');
          } else {
            setError(`Failed to load profile: ${response.statusText}`);
          }
          setLoading(false);
          return;
        }
        
        const data = await response.json();
        setUser(data);
        setEditHandle(data.handle);
        setEditBio(data.bio || '');
        setIsOwnProfile(currentUserId === data.id);
        setIsOwner(data.roles?.includes('owner') || false);
        
        // Check if current viewer is a moderator
        if (token) {
          try {
            const meResponse = await fetch(`${API_BASE_URL}/api/auth/me`, {
              headers: { 'Authorization': `Bearer ${token}` }
            });
            if (meResponse.ok) {
              const meData = await meResponse.json();
              const roles = meData.roles || [];
              setIsModerator(roles.includes('moderator') || roles.includes('owner'));
            }
          } catch (err) {
            console.error('Error checking moderator status:', err);
          }
        }
      } catch (err) {
        setError('Failed to load profile');
        console.error('Error fetching user:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchUser();
  }, [id, API_BASE_URL]);

  // Load user's posts
  const loadPosts = useCallback(async (cursor: string | null = null) => {
    if (!id || typeof id !== 'string') return;
    if (loadingRef.current || (cursor !== null && !hasMoreRef.current)) return;
    
    loadingRef.current = true;
    setPostsLoading(true);
    
    try {
      const token = localStorage.getItem('access_token');
      const headers: HeadersInit = token ? { 'Authorization': `Bearer ${token}` } : {};
      
      const url = `${API_BASE_URL}/api/posts?owner_id=${id}&limit=20&sort=created_at&order=desc${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`;
      const response = await fetch(url, { headers });
      
      if (!response.ok) {
        throw new Error('Failed to load posts');
      }
      
      const data: PageResponse<Post> = await response.json();
      
      if (cursor) {
        setPosts(prev => [...prev, ...data.items]);
      } else {
        setPosts(data.items);
      }
      
      setNextCursor(data.next_cursor);
      nextCursorRef.current = data.next_cursor;
      const hasMoreValue = data.next_cursor !== null;
      hasMoreRef.current = hasMoreValue;
      setHasMore(hasMoreValue);
    } catch (err) {
      console.error('Error loading posts:', err);
    } finally {
      loadingRef.current = false;
      setPostsLoading(false);
    }
  }, [id, API_BASE_URL]);

  // Load posts when user is loaded
  useEffect(() => {
    if (user) {
      loadPosts();
    }
  }, [user, loadPosts]);

  // Load blog posts when user is loaded
  useEffect(() => {
    if (user && id && typeof id === 'string') {
      loadBlogPosts();
    }
  }, [user, id, API_BASE_URL]);

  // Load user's blog posts
  const loadBlogPosts = async () => {
    if (!id || typeof id !== 'string') return;
    
    try {
      const token = localStorage.getItem('access_token');
      const headers: HeadersInit = token ? { 'Authorization': `Bearer ${token}` } : {};
      
      const response = await fetch(`${API_BASE_URL}/api/users/${id}/blog-posts?limit=2`, { headers });
      
      if (response.ok) {
        const data = await response.json();
        setBlogPosts(data.items || []);
        
        // Fetch stats for each blog post
        if (data.items && data.items.length > 0) {
          const statsPromises = data.items.map(async (post: any) => {
            try {
              const [reactionsRes, commentsRes] = await Promise.all([
                fetch(`${API_BASE_URL}/api/blog-posts/${post.id}/reactions`, { headers }),
                fetch(`${API_BASE_URL}/api/blog-posts/${post.id}/comments`, { headers })
              ]);
              
              if (reactionsRes.ok && commentsRes.ok) {
                const reactionsData = await reactionsRes.json();
                const commentsData = await commentsRes.json();
                
                const reactionCount = Object.values(reactionsData.totals || {}).reduce((sum: number, count) => sum + (count as number), 0);
                const commentCount = commentsData.items?.length || 0;
                
                return { postId: post.id, reactions: reactionCount, comments: commentCount };
              }
            } catch (err) {
              console.error(`Error fetching stats for blog post ${post.id}:`, err);
            }
            return null;
          });
          
          const results = await Promise.all(statsPromises);
          const statsMap: Record<string, { reactions: number; comments: number }> = {};
          results.forEach(result => {
            if (result) {
              statsMap[result.postId] = { reactions: result.reactions, comments: result.comments };
            }
          });
          setBlogPostStats(statsMap);
        }
      }
    } catch (err) {
      console.error('Error loading blog posts:', err);
    }
  };

  // Handle entering edit mode
  const handleEditClick = () => {
    if (user) {
      setEditHandle(user.handle);
      setEditBio(user.bio || '');
      setSaveError(null);
      setIsEditing(true);
    }
  };

  // Handle canceling edit mode
  const handleCancelEdit = () => {
    if (user) {
      setEditHandle(user.handle);
      setEditBio(user.bio || '');
      setSaveError(null);
      setIsEditing(false);
    }
  };

  // Handle saving profile changes
  const handleSaveProfile = async () => {
    if (!user) return;
    
    setIsSaving(true);
    setSaveError(null);
    
    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        setSaveError('You must be logged in to edit your profile');
        setIsSaving(false);
        return;
      }
      
      const payload: { handle?: string; bio?: string } = {};
      
      // Only include handle if it changed
      if (editHandle.trim() !== user.handle) {
        payload.handle = editHandle.trim();
      }
      
      // Only include bio if it changed
      if (editBio !== (user.bio || '')) {
        payload.bio = editBio;
      }
      
      // If nothing changed, just exit edit mode
      if (Object.keys(payload).length === 0) {
        setIsEditing(false);
        setIsSaving(false);
        return;
      }
      
      const response = await fetch(`${API_BASE_URL}/api/users/${user.id}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        if (response.status === 409) {
          setSaveError('This handle is already taken');
        } else if (response.status === 400) {
          setSaveError(errorData.detail || 'Invalid handle format');
        } else {
          setSaveError(errorData.detail || 'Failed to save changes');
        }
        setIsSaving(false);
        return;
      }
      
      const updatedUser = await response.json();
      setUser(updatedUser);
      setIsEditing(false);
    } catch (err) {
      console.error('Error saving profile:', err);
      setSaveError('Failed to save changes');
    } finally {
      setIsSaving(false);
    }
  };

  // Handle logout with confirmation
  const handleLogout = () => {
    if (window.confirm('Are you sure you want to log out?')) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user_id');
      localStorage.removeItem('user_handle');
      localStorage.removeItem('user_display_name');
      router.push('/');
    }
  };

  // Trust/Distrust functions for moderators
  const trustUser = async () => {
    if (!user) return;
    try {
      const token = localStorage.getItem('access_token');
      if (!token) return;
      
      await fetch(`${API_BASE_URL}/api/admin/users/${user.id}/auto-approval`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      // Refresh user data
      const response = await fetch(`${API_BASE_URL}/api/users/${user.id}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const updatedUser = await response.json();
        setUser(updatedUser);
      }
    } catch (error) {
      console.error('Error trusting user:', error);
    }
  };

  const distrustUser = async () => {
    if (!user) return;
    try {
      const token = localStorage.getItem('access_token');
      if (!token) return;
      
      await fetch(`${API_BASE_URL}/api/admin/users/${user.id}/auto-approval`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      // Refresh user data
      const response = await fetch(`${API_BASE_URL}/api/users/${user.id}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const updatedUser = await response.json();
        setUser(updatedUser);
      }
    } catch (error) {
      console.error('Error distrusting user:', error);
    }
  };

  // Ban/Unban functions for moderators
  const banUser = async () => {
    if (!user) return;
    if (!confirm('Are you sure you want to ban this user? Bans persist until revoked by a moderator.')) {
      return;
    }
    try {
      const token = localStorage.getItem('access_token');
      if (!token) return;
      
      await fetch(`${API_BASE_URL}/api/admin/users/${user.id}/ban`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ duration_days: null })
      });
      
      // Refresh user data
      const response = await fetch(`${API_BASE_URL}/api/users/${user.id}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const updatedUser = await response.json();
        setUser(updatedUser);
      }
    } catch (error) {
      console.error('Error banning user:', error);
    }
  };

  const unbanUser = async () => {
    if (!user) return;
    if (!confirm('Are you sure you want to unban this user?')) {
      return;
    }
    try {
      const token = localStorage.getItem('access_token');
      if (!token) return;
      
      await fetch(`${API_BASE_URL}/api/admin/users/${user.id}/ban`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      // Refresh user data
      const response = await fetch(`${API_BASE_URL}/api/users/${user.id}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (response.ok) {
        const updatedUser = await response.json();
        setUser(updatedUser);
      }
    } catch (error) {
      console.error('Error unbanning user:', error);
    }
  };

  // Intersection Observer for infinite scroll
  useEffect(() => {
    if (!user || posts.length === 0 || !hasMoreRef.current) return;
    
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMoreRef.current && !loadingRef.current) {
          loadPosts(nextCursorRef.current);
        }
      },
      { threshold: 0.1 }
    );

    const currentTarget = observerTarget.current;
    if (currentTarget) {
      observer.observe(currentTarget);
    }

    return () => {
      if (currentTarget) {
        observer.unobserve(currentTarget);
      }
    };
  }, [user, posts.length, loadPosts]);

  if (loading) {
    return (
      <Layout title="Loading...">
        <div className="loading-container">
          <div className="loading-spinner"></div>
        </div>
        <style jsx>{`
          .loading-container {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: calc(100vh - var(--header-height));
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

  if (error || !user) {
    return (
      <Layout title="Not Found">
        <div className="error-container">
          <span className="error-icon">😢</span>
          <h1>{error || 'User not found'}</h1>
          <Link href="/" className="back-link">← Back to Home</Link>
        </div>
        <style jsx>{`
          .error-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: calc(100vh - var(--header-height));
            padding: 2rem;
            text-align: center;
          }
          .error-icon {
            font-size: 4rem;
            margin-bottom: 1rem;
          }
          h1 {
            font-size: 1.5rem;
            color: var(--text-primary);
            margin-bottom: 1rem;
          }
          .back-link {
            color: var(--accent-cyan);
            font-size: 1rem;
          }
        `}</style>
      </Layout>
    );
  }

  return (
    <Layout title={user.handle} description={user.bio || `${user.handle}'s profile on Makapix Club`}>
      <div className="profile-container">
        <div className="profile-header">
          <div className="avatar-container">
            {user.avatar_url ? (
              <img src={user.avatar_url} alt={user.handle} className="avatar" />
            ) : (
              <div className="avatar-placeholder">
                {user.handle.charAt(0).toUpperCase()}
              </div>
            )}
          </div>
          
          <div className="profile-info">
            {isEditing ? (
              <>
                {!isOwner && (
                  <input
                    type="text"
                    className="edit-handle-input"
                    value={editHandle}
                    onChange={(e) => setEditHandle(e.target.value)}
                    placeholder="Handle"
                    maxLength={50}
                  />
                )}
                {isOwner && (
                  <h1 className="display-name">{user.handle}</h1>
                )}
                <textarea
                  className="edit-bio-input"
                  value={editBio}
                  onChange={(e) => setEditBio(e.target.value)}
                  placeholder="Write something about yourself..."
                  maxLength={1000}
                  rows={3}
                />
                {saveError && (
                  <p className="save-error">{saveError}</p>
                )}
              </>
            ) : (
              <>
                <h1 className="display-name">{user.handle}</h1>
                {user.bio && (
                  <p className="bio">{user.bio}</p>
                )}
              </>
            )}
            
            <div className="stats">
              <div className="stat">
                <span className="stat-value">{posts.length}</span>
                <span className="stat-label">artworks</span>
              </div>
              <div className="stat">
                <span className="stat-value">{user.reputation}</span>
                <span className="stat-label">reputation</span>
              </div>
              <div className="stat">
                <span className="stat-value">{new Date(user.created_at).getFullYear()}</span>
                <span className="stat-label">joined</span>
              </div>
            </div>
            
            {isEditing ? (
              <div className="edit-actions">
                <button 
                  className="save-btn"
                  onClick={handleSaveProfile}
                  disabled={isSaving}
                >
                  {isSaving ? 'Saving...' : 'Save changes'}
                </button>
                <button 
                  className="cancel-btn"
                  onClick={handleCancelEdit}
                  disabled={isSaving}
                >
                  Cancel
                </button>
              </div>
            ) : (
              <div className="profile-actions">
                {isOwnProfile && (
                  <>
                    <Link href="/blog/write" className="write-blog-btn">
                      ✍️ Write Blog
                    </Link>
                    <button 
                      className="edit-profile-btn"
                      onClick={handleEditClick}
                      aria-label="Edit profile"
                    >
                      ✏️
                    </button>
                    <button 
                      className="logout-btn"
                      onClick={handleLogout}
                      aria-label="Log out"
                    >
                      🚪
                    </button>
                  </>
                )}
                {isModerator && !isOwnProfile && (
                  <>
                    {user.auto_public_approval ? (
                      <button 
                        className="distrust-btn"
                        onClick={distrustUser}
                        aria-label="Distrust user"
                      >
                        ⚠️ Distrust
                      </button>
                    ) : (
                      <button 
                        className="trust-btn"
                        onClick={trustUser}
                        aria-label="Trust user"
                      >
                        🫱🏽‍🫲🏼 Trust
                      </button>
                    )}
                    {user.banned_until ? (
                      <button 
                        className="unban-btn"
                        onClick={unbanUser}
                        aria-label="Unban user"
                      >
                        ✅ Unban
                      </button>
                    ) : (
                      <button 
                        className="ban-btn"
                        onClick={banUser}
                        aria-label="Ban user"
                      >
                        🚷 Ban
                      </button>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>

        {blogPosts.length > 0 && (
          <div className="blog-posts-section">
            <h2 className="section-title">Recent Blog Posts</h2>
            <div className="blog-posts-list">
              {blogPosts.map((blogPost) => {
                const stats = blogPostStats[blogPost.id] || { reactions: 0, comments: 0 };
                const displayDate = blogPost.updated_at || blogPost.created_at;
                
                return (
                  <Link key={blogPost.id} href={`/blog/${blogPost.id}`} className="blog-post-item">
                    <h3 className="blog-post-item-title">{blogPost.title}</h3>
                    <div className="blog-post-item-meta">
                      <span className="blog-post-item-date">
                        {new Date(displayDate).toLocaleDateString()}
                      </span>
                      <span className="meta-separator">•</span>
                      <span className="blog-post-item-reactions">❤️ {stats.reactions}</span>
                      <span className="meta-separator">•</span>
                      <span className="blog-post-item-comments">💬 {stats.comments}</span>
                    </div>
                  </Link>
                );
              })}
            </div>
          </div>
        )}

        <div className="artworks-section">
          {posts.length === 0 && !postsLoading && (
            <div className="empty-state">
              <span className="empty-icon">🎨</span>
              <p>No artworks yet</p>
            </div>
          )}

          {posts.length > 0 && (
            <CardGrid posts={posts} API_BASE_URL={API_BASE_URL} />
          )}

          {posts.length > 0 && (
            <div ref={observerTarget} className="load-more-trigger">
              {postsLoading && (
                <div className="loading-indicator">
                  <div className="loading-spinner-small"></div>
                </div>
              )}
              {!hasMore && (
                <div className="end-message">
                  <span>✨</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <style jsx>{`
        .profile-container {
          max-width: 1200px;
          margin: 0 auto;
          padding: 24px;
        }

        .profile-header {
          display: flex;
          gap: 24px;
          align-items: flex-start;
          background: var(--bg-secondary);
          border-radius: 16px;
          padding: 32px;
          margin-bottom: 24px;
        }

        @media (max-width: 600px) {
          .profile-header {
            flex-direction: column;
            align-items: center;
            text-align: center;
          }
        }

        .avatar-container {
          flex-shrink: 0;
        }

        .avatar {
          width: 120px;
          height: 120px;
          border-radius: 50%;
          object-fit: cover;
          border: 3px solid var(--bg-tertiary);
        }

        .avatar-placeholder {
          width: 120px;
          height: 120px;
          border-radius: 50%;
          background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 3rem;
          font-weight: 700;
          color: white;
          text-transform: uppercase;
        }

        .profile-info {
          flex: 1;
        }

        .profile-actions {
          display: flex;
          gap: 16px;
          margin-top: 20px;
        }

        @media (max-width: 600px) {
          .profile-actions {
            justify-content: center;
          }
        }

        .profile-actions :global(.write-blog-btn) {
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          border: none;
          border-radius: 8px;
          padding: 10px 16px;
          font-size: 0.95rem;
          cursor: pointer;
          transition: all var(--transition-fast);
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          text-decoration: none;
          font-weight: 600;
          gap: 6px;
        }

        .profile-actions :global(.write-blog-btn:hover) {
          transform: translateY(-2px);
          box-shadow: var(--glow-pink);
          color: white;
        }

        .edit-profile-btn,
        .logout-btn,
        .trust-btn,
        .distrust-btn,
        .ban-btn,
        .unban-btn {
          background: var(--bg-tertiary);
          border: none;
          border-radius: 8px;
          padding: 10px 16px;
          font-size: 1rem;
          cursor: pointer;
          transition: all var(--transition-fast);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--text-secondary);
        }

        .edit-profile-btn {
          font-size: 1.3rem;
        }

        .edit-profile-btn:hover {
          background: var(--accent-cyan);
          transform: scale(1.05);
        }

        .logout-btn:hover {
          background: var(--accent-pink);
          transform: scale(1.05);
        }

        .trust-btn:hover {
          background: #10b981;
          color: white;
          transform: scale(1.05);
        }

        .distrust-btn:hover {
          background: #ef4444;
          color: white;
          transform: scale(1.05);
        }

        .ban-btn:hover {
          background: #ef4444;
          color: white;
          transform: scale(1.05);
        }

        .unban-btn:hover {
          background: #10b981;
          color: white;
          transform: scale(1.05);
        }

        .edit-handle-input {
          font-size: 1.75rem;
          font-weight: 700;
          color: var(--text-primary);
          background: var(--bg-tertiary);
          border: 2px solid var(--bg-tertiary);
          border-radius: 8px;
          padding: 8px 12px;
          width: 100%;
          max-width: 300px;
          margin-bottom: 12px;
          transition: border-color var(--transition-fast);
        }

        .edit-handle-input:focus {
          outline: none;
          border-color: var(--accent-cyan);
        }

        .edit-bio-input {
          font-size: 1rem;
          color: var(--text-secondary);
          background: var(--bg-tertiary);
          border: 2px solid var(--bg-tertiary);
          border-radius: 8px;
          padding: 12px;
          width: 100%;
          max-width: 600px;
          resize: vertical;
          min-height: 80px;
          margin-bottom: 12px;
          font-family: inherit;
          line-height: 1.6;
          transition: border-color var(--transition-fast);
        }

        .edit-bio-input:focus {
          outline: none;
          border-color: var(--accent-cyan);
        }

        .save-error {
          color: var(--accent-pink);
          font-size: 0.9rem;
          margin: 0 0 12px 0;
        }

        .edit-actions {
          display: flex;
          gap: 12px;
          margin-top: 16px;
        }

        .save-btn {
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
          border: none;
          border-radius: 8px;
          padding: 12px 32px;
          font-size: 1rem;
          font-weight: 600;
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .save-btn:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 4px 20px rgba(255, 110, 180, 0.4);
        }

        .save-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .cancel-btn {
          background: var(--bg-tertiary);
          color: var(--text-secondary);
          border: none;
          border-radius: 8px;
          padding: 12px 24px;
          font-size: 1rem;
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .cancel-btn:hover:not(:disabled) {
          background: var(--bg-secondary);
          color: var(--text-primary);
        }

        .cancel-btn:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .display-name {
          font-size: 1.75rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0 0 4px 0;
        }

        .handle {
          font-size: 1rem;
          color: var(--accent-cyan);
          margin: 0 0 16px 0;
        }

        .bio {
          font-size: 1rem;
          color: var(--text-secondary);
          line-height: 1.6;
          margin: 0 0 20px 0;
          max-width: 600px;
        }

        .stats {
          display: flex;
          gap: 32px;
        }

        @media (max-width: 600px) {
          .stats {
            justify-content: center;
          }
        }

        .stat {
          display: flex;
          flex-direction: column;
          align-items: center;
        }

        .stat-value {
          font-size: 1.5rem;
          font-weight: 700;
          color: var(--text-primary);
        }

        .stat-label {
          font-size: 0.8rem;
          color: var(--text-muted);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .blog-posts-section {
          background: var(--bg-secondary);
          border-radius: 16px;
          padding: 24px;
          margin-bottom: 24px;
        }

        .section-title {
          font-size: 1.25rem;
          font-weight: 700;
          color: var(--text-primary);
          margin-bottom: 16px;
        }

        .blog-posts-list {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .blog-posts-list :global(.blog-post-item) {
          display: block;
          padding: 16px;
          background: var(--bg-tertiary);
          border-radius: 8px;
          text-decoration: none;
          transition: all var(--transition-fast);
        }

        .blog-posts-list :global(.blog-post-item:hover) {
          background: var(--bg-primary);
          transform: translateX(4px);
        }

        .blog-posts-list :global(.blog-post-item) .blog-post-item-title {
          font-size: 1.1rem;
          font-weight: 600;
          color: var(--text-primary);
          margin-bottom: 8px;
        }

        .blog-posts-list :global(.blog-post-item) .blog-post-item-meta {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 8px;
          font-size: 0.85rem;
          color: var(--text-muted);
        }

        .blog-posts-list :global(.blog-post-item) .blog-post-item-date {
          color: var(--text-secondary);
        }

        .artworks-section {
          min-height: 400px;
        }

        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 4rem 2rem;
          text-align: center;
          color: var(--text-muted);
        }

        .empty-icon {
          font-size: 4rem;
          margin-bottom: 1rem;
          opacity: 0.5;
        }

        .load-more-trigger {
          height: 100px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .loading-indicator {
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .loading-spinner-small {
          width: 32px;
          height: 32px;
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

        .end-message {
          color: var(--text-muted);
          font-size: 1.5rem;
        }
      `}</style>
    </Layout>
  );
}

