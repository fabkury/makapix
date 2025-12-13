import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';
import CardGrid from '../../components/CardGrid';
import { authenticatedFetch, authenticatedRequestJson, authenticatedPostJson, clearTokens, logout } from '../../lib/api';

interface User {
  id: number;
  user_key: string;
  public_sqid: string | null;
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
  id: number;
  public_sqid: string;
  title: string;
  description?: string;
  hashtags?: string[];
  art_url: string;
  canvas: string;
  width: number;
  height: number;
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
  const [isUploadingAvatar, setIsUploadingAvatar] = useState(false);
  const [avatarUploadError, setAvatarUploadError] = useState<string | null>(null);
  const avatarInputRef = useRef<HTMLInputElement>(null);
  const [isAvatarDragOver, setIsAvatarDragOver] = useState(false);
  const [isOwnProfile, setIsOwnProfile] = useState(false);
  const [isOwner, setIsOwner] = useState(false);
  const [isModerator, setIsModerator] = useState(false);
  const [isViewerOwner, setIsViewerOwner] = useState(false);
  const [isBlogPostsCollapsed, setIsBlogPostsCollapsed] = useState(false);
  
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
        const currentUserId = localStorage.getItem('user_id');
        const response = await authenticatedFetch(`${API_BASE_URL}/api/user/${id}`);
        
        if (response.status === 401) {
          // Token refresh failed - treat as unauthenticated
          setIsModerator(false);
        }
        
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
        
        // Redirect to canonical URL if public_sqid is available
        if (data.public_sqid) {
          router.replace(`/u/${data.public_sqid}`);
          return;
        }
        
        setUser(data);
        setEditHandle(data.handle);
        setEditBio(data.bio || '');
        setIsOwnProfile(currentUserId === String(data.id));
        setIsOwner(data.roles?.includes('owner') || false);
        
        // Check if current viewer is a moderator
        try {
          const meResponse = await authenticatedFetch(`${API_BASE_URL}/api/auth/me`);
          if (meResponse.status === 401) {
            setIsModerator(false);
            setIsViewerOwner(false);
          } else if (meResponse.ok) {
            const meData = await meResponse.json();
            const roles = meData.roles || [];
            setIsModerator(roles.includes('moderator') || roles.includes('owner'));
            setIsViewerOwner(roles.includes('owner'));
          }
        } catch (err) {
          console.error('Error checking moderator status:', err);
          setIsModerator(false);
          setIsViewerOwner(false);
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
      const url = `${API_BASE_URL}/api/post?owner_id=${user?.id || id}&limit=20&sort=created_at&order=desc${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`;
      const response = await authenticatedFetch(url);
      
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
  }, [id, user?.id, API_BASE_URL]);

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

  // Load user's blog posts (stats are returned by the API)
  const loadBlogPosts = async () => {
    if (!id || typeof id !== 'string') return;
    
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/user/${id}/blog-post?limit=2`);
      
      if (response.ok) {
        const data = await response.json();
        setBlogPosts(data.items || []);
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
      setAvatarUploadError(null);
      setIsEditing(true);
    }
  };

  // Handle canceling edit mode
  const handleCancelEdit = () => {
    if (user) {
      setEditHandle(user.handle);
      setEditBio(user.bio || '');
      setSaveError(null);
      setAvatarUploadError(null);
      setIsEditing(false);
    }
  };

  const uploadAvatarFile = async (file: File) => {
    if (!user) return;
    setAvatarUploadError(null);
    setIsUploadingAvatar(true);
    try {
      const form = new FormData();
      form.append('image', file);
      const res = await authenticatedFetch(`${API_BASE_URL}/api/user/${user.user_key}/avatar`, {
        method: 'POST',
        body: form,
      });
      if (res.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setAvatarUploadError(err.detail || 'Failed to upload avatar');
        return;
      }
      const updatedUser = await res.json();
      setUser(updatedUser);
    } catch (e) {
      console.error('Error uploading avatar:', e);
      setAvatarUploadError('Failed to upload avatar');
    } finally {
      setIsUploadingAvatar(false);
      setIsAvatarDragOver(false);
    }
  };

  // Handle saving profile changes
  const handleSaveProfile = async () => {
    if (!user) return;
    
    setIsSaving(true);
    setSaveError(null);
    
    try {
      const payload: { handle?: string; bio?: string; avatar_url?: string | null } = {};
      
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
      
      try {
        const updatedUser = await authenticatedRequestJson<User>(
          `/api/user/${user.user_key}`,
          { body: JSON.stringify(payload) },
          'PATCH'
        );
        
        setUser(updatedUser);
        setIsEditing(false);
      } catch (err) {
        if (err instanceof Error) {
          if (err.message.includes('409')) {
            setSaveError('This handle is already taken');
          } else if (err.message.includes('400')) {
            setSaveError('Invalid handle format');
          } else if (err.message.includes('401')) {
            clearTokens();
            router.push('/auth');
            return;
          } else {
            setSaveError('Failed to save changes');
          }
        } else {
          setSaveError('Failed to save changes');
        }
      }
    } catch (err) {
      console.error('Error saving profile:', err);
      setSaveError('Failed to save changes');
    } finally {
      setIsSaving(false);
    }
  };

  // Handle logout with confirmation
  const handleLogout = async () => {
    if (window.confirm('Are you sure you want to log out?')) {
      // Call logout API to revoke refresh token and clear cookie
      await logout();
      router.push('/');
    }
  };

  // Trust/Distrust functions for moderators
  const trustUser = async () => {
    if (!user) return;
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/admin/user/${user.id}/auto-approval`, {
        method: 'POST',
      });
      
      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      
      // Refresh user data
      const refreshResponse = await authenticatedFetch(`${API_BASE_URL}/api/user/${user.user_key}`);
      if (refreshResponse.ok) {
        const updatedUser = await refreshResponse.json();
        setUser(updatedUser);
      }
    } catch (error) {
      console.error('Error trusting user:', error);
    }
  };

  const distrustUser = async () => {
    if (!user) return;
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/admin/user/${user.id}/auto-approval`, {
        method: 'DELETE',
      });
      
      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      
      // Refresh user data
      const refreshResponse = await authenticatedFetch(`${API_BASE_URL}/api/user/${user.user_key}`);
      if (refreshResponse.ok) {
        const updatedUser = await refreshResponse.json();
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
      const response = await authenticatedFetch(`${API_BASE_URL}/api/admin/user/${user.id}/ban`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ duration_days: null })
      });
      
      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      
      // Refresh user data
      const refreshResponse = await authenticatedFetch(`${API_BASE_URL}/api/user/${user.user_key}`);
      if (refreshResponse.ok) {
        const updatedUser = await refreshResponse.json();
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
      const response = await authenticatedFetch(`${API_BASE_URL}/api/admin/user/${user.id}/ban`, {
        method: 'DELETE',
      });
      
      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      
      // Refresh user data
      const refreshResponse = await authenticatedFetch(`${API_BASE_URL}/api/user/${user.user_key}`);
      if (refreshResponse.ok) {
        const updatedUser = await refreshResponse.json();
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
      // Document scrolling: observe relative to viewport
      { threshold: 0.1, root: null }
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
            min-height: calc(100vh - var(--header-offset));
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
            min-height: calc(100vh - var(--header-offset));
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
        <div className="profile-header-wrapper">
          <div className="profile-header">
            <div className="profile-header-left">
            <div className="avatar-container">
              {user.avatar_url ? (
                <img src={user.avatar_url} alt={user.handle} className="avatar" />
              ) : (
                <div className="avatar-placeholder">
                  {user.handle.charAt(0).toUpperCase()}
                </div>
              )}

              {isEditing && (
                <>
                  <input
                    ref={avatarInputRef}
                    type="file"
                    accept="image/png,image/jpeg,image/jpg,image/gif,image/webp"
                    style={{ display: 'none' }}
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) void uploadAvatarFile(f);
                      e.currentTarget.value = '';
                    }}
                  />
                  <div
                    className={`avatar-dropzone ${isAvatarDragOver ? 'dragover' : ''}`}
                    onDragOver={(e) => {
                      e.preventDefault();
                      setIsAvatarDragOver(true);
                    }}
                    onDragLeave={() => setIsAvatarDragOver(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      const f = e.dataTransfer.files?.[0];
                      if (f) void uploadAvatarFile(f);
                    }}
                    onClick={() => avatarInputRef.current?.click()}
                    role="button"
                    tabIndex={0}
                    aria-label="Upload profile picture"
                    title="Drop an image or click to upload"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        avatarInputRef.current?.click();
                      }
                    }}
                  >
                    {isUploadingAvatar ? 'Uploading…' : 'Drop image or click'}
                  </div>
                </>
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
                  {avatarUploadError && (
                    <p className="save-error">{avatarUploadError}</p>
                  )}
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
              
              {isEditing && (
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
              )}
              
              {!isEditing && isOwnProfile && (
                <div className="profile-actions">
                  <Link href="/blog/write" className="write-blog-btn">
                    ✍️ Write Blog
                  </Link>
                  <Link href={`/u/${user.public_sqid}/player`} className="players-btn">
                    📺 Players
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
                </div>
              )}

              {!isEditing && isModerator && !isOwnProfile && (
                <div className="profile-actions">
                  {(isViewerOwner || !(user.roles?.includes('moderator') || user.roles?.includes('owner'))) && (
                    <button
                      className="edit-profile-btn"
                      onClick={handleEditClick}
                      aria-label="Edit profile"
                      title="Edit profile"
                    >
                      ✏️
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
          
          <div className="profile-header-right">
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
            
            {isModerator && !isOwnProfile && (
              <div className="moderation-buttons">
                {user.auto_public_approval ? (
                  <button 
                    className="distrust-btn"
                    onClick={distrustUser}
                    aria-label="Distrust user"
                    title="Distrust"
                  >
                    ⚠️
                  </button>
                ) : (
                  <button 
                    className="trust-btn"
                    onClick={trustUser}
                    aria-label="Trust user"
                    title="Trust"
                  >
                    🫱🏽‍🫲🏼
                  </button>
                )}
                {user.banned_until ? (
                  <button 
                    className="unban-btn"
                    onClick={unbanUser}
                    aria-label="Unban user"
                    title="Unban"
                  >
                    ✅
                  </button>
                ) : (
                  <button 
                    className="ban-btn"
                    onClick={banUser}
                    aria-label="Ban user"
                    title="Ban"
                  >
                    🚷
                  </button>
                )}
              </div>
            )}
          </div>
          </div>
        </div>

        {blogPosts.length > 0 && (
          <div className={`blog-posts-section ${isBlogPostsCollapsed ? 'collapsed' : ''}`}>
            <div className="blog-posts-content">
              <div className="blog-posts-header">
                <h2 className="section-title">Recent Blog Posts</h2>
                <button 
                  className="blog-posts-toggle"
                  onClick={() => setIsBlogPostsCollapsed(!isBlogPostsCollapsed)}
                  aria-label={isBlogPostsCollapsed ? 'Expand blog posts' : 'Collapse blog posts'}
                >
                  {isBlogPostsCollapsed ? '▶' : '▼'}
                </button>
              </div>
              {!isBlogPostsCollapsed && (
                <div className="blog-posts-list">
                  {blogPosts.map((blogPost) => {
                    const displayDate = blogPost.updated_at || blogPost.created_at;
                    // Use counts from API response (batch-fetched on backend)
                    const reactionCount = blogPost.reaction_count ?? 0;
                    const commentCount = blogPost.comment_count ?? 0;
                    
                    return (
                      <Link key={blogPost.id} href={`/b/${blogPost.public_sqid}`} className="blog-post-item">
                        <h3 className="blog-post-item-title">{blogPost.title}</h3>
                        <div className="blog-post-item-meta">
                          <span className="blog-post-item-date">
                            {new Date(displayDate).toLocaleDateString()}
                          </span>
                          <span className="meta-separator">•</span>
                          <span className="blog-post-item-reactions">⚡ {reactionCount}</span>
                          <span className="meta-separator">•</span>
                          <span className="blog-post-item-comments">💬 {commentCount}</span>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              )}
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
            <CardGrid 
              posts={posts} 
              API_BASE_URL={API_BASE_URL}
              source={{ type: 'profile', id: user ? String(user.id) : (typeof id === 'string' ? id : undefined) }}
              cursor={nextCursor}
            />
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
                  <div className="end-spacer" aria-hidden="true" />
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
          padding: 0 24px 24px 24px;
        }

        .profile-header-wrapper {
          position: relative;
          left: 50%;
          right: 50%;
          width: 100vw;
          margin-left: -50vw;
          margin-right: -50vw;
          margin-top: 0;
          /* No gap between header and the next full-bleed section */
          margin-bottom: 0;
          background: var(--bg-secondary);
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .profile-header {
          max-width: 1200px;
          margin: 0 auto;
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 32px;
          /* Avoid visible "empty" band at the bottom of the header section */
          padding: 24px;
        }

        @media (max-width: 600px) {
          .profile-header {
            flex-direction: column;
            align-items: flex-start;
            gap: 24px;
          }
        }

        .profile-header-left {
          display: flex;
          gap: 24px;
          align-items: flex-start;
          flex: 1;
          min-width: 0;
        }

        @media (max-width: 600px) {
          .profile-header-left {
            width: 100%;
          }
        }

        .avatar-container {
          flex-shrink: 0;
          position: relative;
          width: 128px;
          height: 128px;
        }

        .avatar {
          width: 128px;
          height: 128px;
          border-radius: 0;
          object-fit: cover;
          border: 3px solid var(--bg-tertiary);
        }

        .avatar-dropzone {
          position: absolute;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          background: rgba(0, 0, 0, 0.45);
          color: white;
          font-size: 0.8rem;
          font-weight: 600;
          text-align: center;
          padding: 10px;
          cursor: pointer;
          opacity: 0;
          transition: opacity var(--transition-fast), background var(--transition-fast);
        }

        .avatar-container:hover .avatar-dropzone {
          opacity: 1;
        }

        .avatar-dropzone.dragover {
          opacity: 1;
          background: rgba(0, 0, 0, 0.65);
        }

        .avatar-placeholder {
          width: 128px;
          height: 128px;
          border-radius: 0;
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
          display: flex;
          flex-direction: column;
          justify-content: center;
          min-height: 128px;
        }

        .profile-header-right {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 16px;
          flex-shrink: 0;
        }

        @media (max-width: 600px) {
          .profile-header-right {
            width: 100%;
            align-items: flex-start;
          }
        }

        .moderation-buttons {
          display: flex;
          gap: 8px;
        }

        .profile-actions {
          display: flex;
          gap: 16px;
          margin-top: 20px;
          flex-wrap: wrap;
        }

        @media (max-width: 600px) {
          .profile-actions {
            justify-content: flex-start;
          }
        }

        .profile-actions :global(.write-blog-btn),
        .profile-actions :global(.players-btn) {
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

        .profile-actions :global(.write-blog-btn:hover),
        .profile-actions :global(.players-btn:hover) {
          transform: translateY(-2px);
          box-shadow: var(--glow-pink);
          color: white;
        }

        .edit-profile-btn,
        .logout-btn {
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

        .trust-btn,
        .distrust-btn,
        .ban-btn,
        .unban-btn {
          background: var(--bg-tertiary);
          border: none;
          border-radius: 8px;
          padding: 8px 12px;
          font-size: 1.2rem;
          cursor: pointer;
          transition: all var(--transition-fast);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--text-secondary);
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
          margin: 0 0 8px 0;
          line-height: 1.2;
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
          flex-direction: column;
          gap: 16px;
          align-items: flex-end;
        }

        @media (max-width: 600px) {
          .stats {
            align-items: flex-start;
          }
        }

        .stat {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
        }

        @media (max-width: 600px) {
          .stat {
            align-items: flex-start;
          }
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
          position: relative;
          left: 50%;
          right: 50%;
          width: 100vw;
          margin-left: -50vw;
          margin-right: -50vw;
          background: var(--bg-secondary);
          margin-bottom: 24px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
          transition: all var(--transition-normal);
          overflow: hidden;
        }

        .blog-posts-content {
          max-width: 1200px;
          margin: 0 auto;
          padding: 24px;
        }

        .blog-posts-section.collapsed {
          padding-top: 16px;
          padding-bottom: 16px;
        }

        .blog-posts-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16px;
        }

        .blog-posts-section.collapsed .blog-posts-header {
          margin-bottom: 0;
        }

        .blog-posts-toggle {
          background: transparent;
          border: none;
          color: var(--text-secondary);
          font-size: 1rem;
          cursor: pointer;
          padding: 4px 8px;
          border-radius: 4px;
          transition: all var(--transition-fast);
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .blog-posts-toggle:hover {
          background: var(--bg-tertiary);
          color: var(--text-primary);
        }

        .section-title {
          font-size: 1.25rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0;
        }

        .blog-posts-list {
          display: flex;
          flex-direction: column;
          gap: 16px;
          transition: opacity var(--transition-normal);
        }

        .blog-posts-section.collapsed .blog-posts-list {
          display: none;
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
          /* No artificial gap below the header/blog-posts section */
          margin-top: 0;
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
          min-height: 100px;
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
          display: flex;
          flex-direction: column;
          align-items: center;
          padding-top: 24px;
        }

        .end-spacer {
          height: max(25vh, 200px);
          width: 1px;
        }
      `}</style>
    </Layout>
  );
}

