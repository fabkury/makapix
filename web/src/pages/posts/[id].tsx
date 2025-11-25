import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Script from 'next/script';
import Layout from '../../components/Layout';
import StatsPanel from '../../components/StatsPanel';

interface Post {
  id: string;
  title: string;
  description?: string;
  hashtags?: string[];
  art_url: string;
  canvas: string;
  owner_id: string;
  created_at: string;
  kind?: string;
  hidden_by_user?: boolean;
  hidden_by_mod?: boolean;
  public_visibility?: boolean;
  promoted?: boolean;
  promoted_category?: string;
  owner?: {
    id: string;
    handle: string;
    display_name: string;
  };
}

export default function PostPage() {
  const router = useRouter();
  const { id } = router.query;
  const [post, setPost] = useState<Post | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<{ id: string } | null>(null);
  const [isOwner, setIsOwner] = useState(false);
  const [isModerator, setIsModerator] = useState(false);
  
  // Edit mode state
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editHashtags, setEditHashtags] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  
  // Stats panel state
  const [showStats, setShowStats] = useState(false);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
    : '';

  useEffect(() => {
    if (!id || typeof id !== 'string') return;

    const fetchPost = async () => {
      setLoading(true);
      setError(null);
      
      try {
        const accessToken = localStorage.getItem('access_token');
        const headers: HeadersInit = {};
        if (accessToken) {
          headers['Authorization'] = `Bearer ${accessToken}`;
        }
        
        const response = await fetch(`${API_BASE_URL}/api/posts/${id}`, { headers });
        
        if (!response.ok) {
          if (response.status === 404) {
            setError('Post not found');
          } else {
            setError(`Failed to load post: ${response.statusText}`);
          }
          setLoading(false);
          return;
        }
        
        const data = await response.json();
        setPost(data);
        
        if (accessToken) {
          try {
            const userResponse = await fetch(`${API_BASE_URL}/api/auth/me`, {
              headers: {
                'Authorization': `Bearer ${accessToken}`
              }
            });
            if (userResponse.ok) {
              const userData = await userResponse.json();
              setCurrentUser({ id: userData.user.id });
              setIsOwner(userData.user.id === data.owner_id);
              const roles = userData.user.roles || userData.roles || [];
              setIsModerator(roles.includes('moderator') || roles.includes('owner'));
            }
          } catch (err) {
            setCurrentUser(null);
            setIsOwner(false);
            setIsModerator(false);
          }
        }
      } catch (err) {
        setError('Failed to load post');
        console.error('Error fetching post:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchPost();
  }, [id, API_BASE_URL]);

  // Set API URL for widget
  useEffect(() => {
    if (typeof window === 'undefined') return;
    
    if ((window as any).MAKAPIX_API_URL === undefined) {
      (window as any).MAKAPIX_API_URL = `${API_BASE_URL}/api`;
    }
  }, [API_BASE_URL]);

  // Initialize widget
  useEffect(() => {
    if (!post || !id || typeof id !== 'string') return;

    const initializeWidget = () => {
      if (typeof (window as any).MakapixWidget === 'undefined') {
        setTimeout(initializeWidget, 100);
        return;
      }

      const container = document.getElementById(`makapix-widget-${post.id}`);
      if (!container) {
        setTimeout(initializeWidget, 100);
        return;
      }

      if ((container as any).__makapix_initialized) {
        return;
      }

      try {
        new (window as any).MakapixWidget(container);
        (container as any).__makapix_initialized = true;
      } catch (error) {
        console.error('Failed to initialize Makapix widget:', error);
      }
    };

    const timer = setTimeout(initializeWidget, 100);

    return () => {
      clearTimeout(timer);
    };
  }, [post, id]);

  const handleDelete = async () => {
    if (!post || !id || typeof id !== 'string') return;
    
    const confirmed = confirm(
      'Are you sure you want to delete this post?\n\n' +
      'This action cannot be undone.'
    );
    
    if (!confirmed) return;
    
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
      alert('You must be logged in to delete posts.');
      return;
    }
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/posts/${id}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      });
      
      if (response.ok || response.status === 204) {
        router.push('/');
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to delete post' }));
        alert(errorData.detail || 'Failed to delete post.');
      }
    } catch (err) {
      console.error('Error deleting post:', err);
      alert('Failed to delete post.');
    }
  };

  const handleHide = async () => {
    if (!post || !id || typeof id !== 'string') return;
    
    const isHidden = post.hidden_by_user;
    const action = isHidden ? 'unhide' : 'hide';
    const confirmed = confirm(
      isHidden
        ? 'Unhide this post? It will become visible again in feeds.'
        : 'Hide this post? It will be removed from feeds temporarily.'
    );
    
    if (!confirmed) return;
    
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
      alert('You must be logged in.');
      return;
    }
    
    try {
      const url = `${API_BASE_URL}/api/posts/${id}/hide`;
      const method = isHidden ? 'DELETE' : 'POST';
      
      const response = await fetch(url, {
        method: method,
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        }
      });
      
      if (response.ok || response.status === 201 || response.status === 204) {
        const refreshResponse = await fetch(`${API_BASE_URL}/api/posts/${id}`, {
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        });
        if (refreshResponse.ok) {
          const updatedPost = await refreshResponse.json();
          setPost(updatedPost);
        }
      } else {
        const errorData = await response.json().catch(() => ({ detail: `Failed to ${action} post` }));
        alert(errorData.detail || `Failed to ${action} post.`);
      }
    } catch (err) {
      console.error(`Error ${action}ing post:`, err);
      alert(`Failed to ${action} post.`);
    }
  };

  // Owner: Edit title, description and hashtags
  const handleEditClick = () => {
    if (!post) return;
    setEditTitle(post.title || '');
    setEditDescription(post.description || '');
    setEditHashtags(post.hashtags?.join(', ') || '');
    setSaveError(null);
    setIsEditing(true);
  };

  const handleCancelEdit = () => {
    setIsEditing(false);
    setSaveError(null);
  };

  const handleSaveEdit = async () => {
    if (!post || !id || typeof id !== 'string') return;
    
    setIsSaving(true);
    setSaveError(null);
    
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
      setSaveError('You must be logged in.');
      setIsSaving(false);
      return;
    }
    
    // Parse hashtags from comma-separated string
    const hashtagsArray = editHashtags
      .split(',')
      .map(tag => tag.trim().toLowerCase().replace(/^#/, ''))
      .filter(tag => tag.length > 0);
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/posts/${id}`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          title: editTitle.trim(),
          description: editDescription,
          hashtags: hashtagsArray
        })
      });
      
      if (response.ok) {
        const updatedPost = await response.json();
        setPost(updatedPost);
        setIsEditing(false);
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to save changes' }));
        setSaveError(errorData.detail || 'Failed to save changes.');
      }
    } catch (err) {
      console.error('Error saving post:', err);
      setSaveError('Failed to save changes.');
    } finally {
      setIsSaving(false);
    }
  };

  // Moderator: Hide/Unhide as moderator
  const handleModHide = async () => {
    if (!post || !id || typeof id !== 'string') return;
    
    const isHidden = post.hidden_by_mod;
    const action = isHidden ? 'unhide' : 'hide';
    const confirmed = confirm(
      isHidden
        ? 'Unhide this post (moderator action)? It will become visible again.'
        : 'Hide this post as moderator? This is a moderation action that will be logged.'
    );
    
    if (!confirmed) return;
    
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) return;
    
    try {
      const url = `${API_BASE_URL}/api/posts/${id}/hide`;
      const method = isHidden ? 'DELETE' : 'POST';
      
      const response = await fetch(url, {
        method: method,
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ by: 'mod' })
      });
      
      if (response.ok || response.status === 201 || response.status === 204) {
        const refreshResponse = await fetch(`${API_BASE_URL}/api/posts/${id}`, {
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        });
        if (refreshResponse.ok) {
          setPost(await refreshResponse.json());
        }
      } else {
        const errorData = await response.json().catch(() => ({}));
        alert(errorData.detail || `Failed to ${action} post.`);
      }
    } catch (err) {
      console.error(`Error ${action}ing post:`, err);
    }
  };

  // Moderator: Promote/Demote
  const handlePromote = async () => {
    if (!post || !id || typeof id !== 'string') return;
    
    const isPromoted = post.promoted;
    const action = isPromoted ? 'demote' : 'promote';
    const confirmed = confirm(
      isPromoted
        ? 'Remove this post from promoted posts?'
        : 'Promote this post to the frontpage?'
    );
    
    if (!confirmed) return;
    
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) return;
    
    try {
      const url = `${API_BASE_URL}/api/posts/${id}/promote`;
      const method = isPromoted ? 'DELETE' : 'POST';
      
      const response = await fetch(url, {
        method: method,
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        },
        body: isPromoted ? undefined : JSON.stringify({ category: 'frontpage' })
      });
      
      if (response.ok || response.status === 201 || response.status === 204) {
        const refreshResponse = await fetch(`${API_BASE_URL}/api/posts/${id}`, {
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        });
        if (refreshResponse.ok) {
          setPost(await refreshResponse.json());
        }
      } else {
        const errorData = await response.json().catch(() => ({}));
        alert(errorData.detail || `Failed to ${action} post.`);
      }
    } catch (err) {
      console.error(`Error ${action}ing post:`, err);
    }
  };

  // Moderator: Approve public visibility (one-time action, cannot be revoked)
  const handleApprovePublicVisibility = async () => {
    if (!post || !id || typeof id !== 'string') return;
    
    // Only allow approving, not revoking
    if (post.public_visibility) return;
    
    const confirmed = confirm(
      'Approve public visibility? This artwork will appear in Recent Artworks and search results.\n\n' +
      'Note: This is a one-time action. To hide the artwork later, use the "Hide (Mod)" action instead.'
    );
    
    if (!confirmed) return;
    
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/posts/${id}/approve-public`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      });
      
      if (response.ok || response.status === 201) {
        const refreshResponse = await fetch(`${API_BASE_URL}/api/posts/${id}`, {
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        });
        if (refreshResponse.ok) {
          setPost(await refreshResponse.json());
        }
      } else {
        const errorData = await response.json().catch(() => ({}));
        alert(errorData.detail || 'Failed to approve public visibility.');
      }
    } catch (err) {
      console.error('Error approving public visibility:', err);
    }
  };

  // Moderator: Permanent delete (only for hidden posts)
  const handlePermanentDelete = async () => {
    if (!post || !id || typeof id !== 'string') return;
    
    // Only allow deletion of hidden posts
    if (!post.hidden_by_mod && !post.hidden_by_user) {
      alert('Post must be hidden before it can be permanently deleted.');
      return;
    }
    
    const confirmed = confirm(
      '⚠️ PERMANENT DELETE ⚠️\n\n' +
      'This will permanently delete this artwork and cannot be undone.\n\n' +
      'Are you absolutely sure you want to proceed?'
    );
    
    if (!confirmed) return;
    
    // Double confirmation for safety
    const doubleConfirmed = confirm(
      'This is your final warning.\n\n' +
      'Click OK to permanently delete this artwork.'
    );
    
    if (!doubleConfirmed) return;
    
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) return;
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/posts/${id}/permanent`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      });
      
      if (response.ok || response.status === 204) {
        alert('Artwork has been permanently deleted.');
        // Redirect to home page
        window.location.href = '/';
      } else {
        const errorData = await response.json().catch(() => ({}));
        alert(errorData.detail || 'Failed to delete artwork.');
      }
    } catch (err) {
      console.error('Error deleting artwork:', err);
      alert('Failed to delete artwork.');
    }
  };

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
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
        `}</style>
      </Layout>
    );
  }

  if (error || !post) {
    return (
      <Layout title="Not Found">
        <div className="error-container">
          <span className="error-icon">😢</span>
          <h1>{error || 'Post not found'}</h1>
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
    <Layout title={post.title} description={post.description || post.title}>
      <div className="post-container">
        <img
          src={post.art_url}
          alt={post.title}
          className="artwork-image pixel-art"
        />

        <div className="post-info">
          {isOwner && isEditing ? (
            <div className="edit-field">
              <label htmlFor="edit-title">Title</label>
              <input
                id="edit-title"
                type="text"
                value={editTitle}
                onChange={(e) => setEditTitle(e.target.value)}
                placeholder="Artwork title..."
                maxLength={200}
                disabled={isSaving}
                className="edit-title-input"
              />
            </div>
          ) : (
            <h1 className="post-title">{post.title}</h1>
          )}
          
          <div className="post-meta">
            {post.owner && (
              <Link href={`/users/${post.owner.id}`} className="author-link">
                {post.owner.display_name || post.owner.handle}
              </Link>
            )}
            <span className="meta-separator">•</span>
            <span className="post-date">{new Date(post.created_at).toLocaleDateString()}</span>
            <span className="meta-separator">•</span>
            <span className="post-canvas">{post.canvas}</span>
          </div>

          {post.description && (
            <div className="post-description">
              {post.description.split('\n').map((line, i) => (
                <p key={i}>{line}</p>
              ))}
            </div>
          )}

          {post.hashtags && post.hashtags.length > 0 && (
            <div className="hashtags">
              {post.hashtags.map((tag) => (
                <Link
                  key={tag}
                  href={`/hashtags/${encodeURIComponent(tag)}`}
                  className="hashtag"
                >
                  #{tag}
                </Link>
              ))}
            </div>
          )}

          {/* Stats button - visible to owner and moderators */}
          {(isOwner || isModerator) && (
            <div className="stats-action">
              <button
                onClick={() => setShowStats(true)}
                className="action-button stats"
                title="View Statistics"
              >
                📈 Statistics
              </button>
            </div>
          )}

          {isOwner && !isEditing && (
            <div className="owner-actions">
              <button
                onClick={handleHide}
                className={`action-button ${post.hidden_by_user ? 'unhide' : 'hide'}`}
              >
                {post.hidden_by_user ? '👁️ Unhide' : '🙈 Hide'}
              </button>
              {post.hidden_by_user && (
                <button
                  onClick={handleDelete}
                  className="action-button delete"
                >
                  🗑 Delete
                </button>
              )}
              <button
                onClick={handleEditClick}
                className="action-button edit"
              >
                ✏️ Edit
              </button>
            </div>
          )}

          {isOwner && isEditing && (
            <div className="edit-section">
              <h3 className="edit-title">Edit Artwork</h3>
              
              <div className="edit-field">
                <label htmlFor="edit-description">Description</label>
                <textarea
                  id="edit-description"
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  placeholder="Describe your artwork..."
                  rows={4}
                  maxLength={5000}
                  disabled={isSaving}
                />
              </div>
              
              <div className="edit-field">
                <label htmlFor="edit-hashtags">Hashtags</label>
                <input
                  id="edit-hashtags"
                  type="text"
                  value={editHashtags}
                  onChange={(e) => setEditHashtags(e.target.value)}
                  placeholder="art, pixel, game (comma-separated)"
                  disabled={isSaving}
                />
                <span className="field-hint">Separate hashtags with commas</span>
              </div>
              
              {saveError && (
                <p className="save-error">{saveError}</p>
              )}
              
              <div className="edit-actions">
                <button
                  onClick={handleSaveEdit}
                  className="action-button save"
                  disabled={isSaving}
                >
                  {isSaving ? 'Saving...' : '💾 Save Changes'}
                </button>
                <button
                  onClick={handleCancelEdit}
                  className="action-button cancel"
                  disabled={isSaving}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {isModerator && (
            <div className="moderator-actions">
              <div className="mod-actions-grid">
                <button
                  onClick={handleModHide}
                  className={`mod-button ${post.hidden_by_mod ? 'active' : ''}`}
                >
                  {post.hidden_by_mod ? '👁️ Unhide' : '🙈 Hide'}
                </button>
                <button
                  onClick={handlePromote}
                  className={`mod-button ${post.promoted ? 'active' : ''}`}
                >
                  {post.promoted ? '⬇️ Demote' : '⭐ Promote'}
                </button>
                {!post.public_visibility && (
                  <button
                    onClick={handleApprovePublicVisibility}
                    className="mod-button"
                  >
                    ✅ Approve
                  </button>
                )}
                {(post.hidden_by_mod || post.hidden_by_user) && (
                  <button
                    onClick={handlePermanentDelete}
                    className="mod-button danger"
                  >
                    🗑️ Delete Permanently
                  </button>
                )}
              </div>
              {(post.hidden_by_mod || post.promoted || !post.public_visibility) && (
                <div className="mod-status-badges">
                  {post.hidden_by_mod && <span className="status-badge hidden">Hidden by mod</span>}
                  {post.promoted && <span className="status-badge promoted">Promoted</span>}
                  {!post.public_visibility && <span className="status-badge pending">Pending approval</span>}
                </div>
              )}
            </div>
          )}
        </div>

        <div className="widget-section">
          <div id={`makapix-widget-${post.id}`} data-post-id={post.id}></div>
        </div>
      </div>

      {/* Stats Panel Modal */}
      <StatsPanel
        postId={post.id}
        isOpen={showStats}
        onClose={() => setShowStats(false)}
      />

      <Script
        src={`${API_BASE_URL}/makapix-widget.js`}
        strategy="afterInteractive"
        onLoad={() => {
          if (post && id && typeof id === 'string') {
            setTimeout(() => {
              const container = document.getElementById(`makapix-widget-${post.id}`);
              if (container && typeof (window as any).MakapixWidget !== 'undefined') {
                if (!(container as any).__makapix_initialized) {
                  try {
                    new (window as any).MakapixWidget(container);
                    (container as any).__makapix_initialized = true;
                  } catch (error) {
                    console.error('Failed to initialize Makapix widget:', error);
                  }
                }
              }
            }, 100);
          }
        }}
      />

      <style jsx>{`
        .post-container {
          max-width: 1000px;
          margin: 0 auto;
          padding: 24px;
        }

        .artwork-image {
          display: block;
          width: 100%;
          height: auto;
          margin-bottom: 24px;
          image-rendering: -webkit-optimize-contrast !important;
          image-rendering: -moz-crisp-edges !important;
          image-rendering: crisp-edges !important;
          image-rendering: pixelated !important;
          -ms-interpolation-mode: nearest-neighbor !important;
        }

        .post-info {
          background: var(--bg-secondary);
          border-radius: 12px;
          padding: 24px;
          margin-bottom: 24px;
        }

        .post-title {
          font-size: 1.75rem;
          font-weight: 700;
          color: var(--text-primary);
          margin-bottom: 12px;
        }

        .post-meta {
          display: flex;
          align-items: center;
          flex-wrap: wrap;
          gap: 8px;
          font-size: 0.9rem;
          color: var(--text-muted);
          margin-bottom: 16px;
        }

        .author-link {
          color: var(--accent-cyan);
          font-weight: 500;
        }

        .author-link:hover {
          color: var(--accent-pink);
        }

        .meta-separator {
          opacity: 0.5;
        }

        .post-description {
          color: var(--text-secondary);
          line-height: 1.6;
          margin-bottom: 16px;
        }

        .post-description p {
          margin-bottom: 0.5rem;
        }

        .post-description p:last-child {
          margin-bottom: 0;
        }

        .hashtags {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }

        .hashtag {
          background: linear-gradient(135deg, rgba(180, 78, 255, 0.2), rgba(78, 159, 255, 0.2));
          color: var(--accent-purple);
          padding: 6px 14px;
          border-radius: 20px;
          font-size: 0.85rem;
          font-weight: 500;
          transition: all var(--transition-fast);
        }

        .hashtag:hover {
          background: linear-gradient(135deg, rgba(180, 78, 255, 0.4), rgba(78, 159, 255, 0.4));
          box-shadow: var(--glow-purple);
        }

        .owner-actions {
          display: flex;
          gap: 12px;
          margin-top: 24px;
          padding-top: 24px;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
          justify-content: flex-start;
        }

        .action-button {
          padding: 10px 20px;
          border-radius: 8px;
          font-size: 0.9rem;
          font-weight: 600;
          transition: all var(--transition-fast);
          cursor: pointer;
          border: none;
        }

        .action-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .action-button.hide {
          background: var(--bg-tertiary);
          color: var(--text-secondary);
        }

        .action-button.hide:hover:not(:disabled) {
          background: rgba(245, 158, 11, 0.2);
          color: #f59e0b;
        }

        .action-button.unhide {
          background: rgba(16, 185, 129, 0.2);
          color: #10b981;
        }

        .action-button.unhide:hover:not(:disabled) {
          background: rgba(16, 185, 129, 0.3);
        }

        .action-button.delete {
          background: rgba(239, 68, 68, 0.2);
          color: #ef4444;
        }

        .action-button.delete:hover:not(:disabled) {
          background: rgba(239, 68, 68, 0.3);
        }

        .action-button.edit {
          background: rgba(78, 159, 255, 0.2);
          color: #4e9fff;
        }

        .action-button.edit:hover:not(:disabled) {
          background: rgba(78, 159, 255, 0.3);
        }

        .action-button.stats {
          background: rgba(180, 78, 255, 0.2);
          color: #b44eff;
        }

        .action-button.stats:hover:not(:disabled) {
          background: rgba(180, 78, 255, 0.3);
          box-shadow: 0 0 12px rgba(180, 78, 255, 0.3);
        }

        .stats-action {
          margin-top: 16px;
          padding-top: 16px;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        .action-button.save {
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
        }

        .action-button.save:hover:not(:disabled) {
          box-shadow: var(--glow-pink);
        }

        .action-button.cancel {
          background: var(--bg-tertiary);
          color: var(--text-secondary);
        }

        .action-button.cancel:hover:not(:disabled) {
          background: var(--bg-primary);
        }

        /* Edit Section Styles */
        .edit-section {
          margin-top: 24px;
          padding-top: 24px;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        .edit-title {
          font-size: 1.1rem;
          font-weight: 600;
          color: var(--text-primary);
          margin-bottom: 16px;
        }

        .edit-field {
          margin-bottom: 16px;
        }

        .edit-field label {
          display: block;
          font-size: 0.9rem;
          font-weight: 500;
          color: var(--text-secondary);
          margin-bottom: 8px;
        }

        .edit-field textarea,
        .edit-field input {
          width: 100%;
          padding: 12px;
          border-radius: 8px;
          border: 2px solid var(--bg-tertiary);
          background: var(--bg-primary);
          color: var(--text-primary);
          font-size: 0.95rem;
          font-family: inherit;
          transition: border-color var(--transition-fast);
        }

        .edit-title-input {
          font-size: 1.75rem;
          font-weight: 700;
          padding: 12px;
        }

        .edit-field textarea:focus,
        .edit-field input:focus {
          outline: none;
          border-color: var(--accent-cyan);
        }

        .edit-field textarea:disabled,
        .edit-field input:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .edit-field textarea {
          min-height: 100px;
          resize: vertical;
        }

        .field-hint {
          display: block;
          font-size: 0.8rem;
          color: var(--text-muted);
          margin-top: 6px;
        }

        .save-error {
          color: #ef4444;
          font-size: 0.9rem;
          margin-bottom: 12px;
        }

        .edit-actions {
          display: flex;
          gap: 12px;
          margin-top: 16px;
        }

        .moderator-actions {
          margin-top: 16px;
        }

        .mod-actions-grid {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
          justify-content: flex-end;
        }

        .mod-button {
          padding: 10px 16px;
          border-radius: 8px;
          font-size: 0.85rem;
          font-weight: 600;
          background: var(--bg-tertiary);
          color: var(--text-secondary);
          transition: all var(--transition-fast);
          border: 1px solid transparent;
        }

        .mod-button:hover {
          background: rgba(180, 78, 255, 0.2);
          color: var(--accent-purple);
          border-color: var(--accent-purple);
        }

        .mod-button.active {
          background: rgba(180, 78, 255, 0.15);
          color: var(--accent-purple);
          border-color: rgba(180, 78, 255, 0.3);
        }

        .mod-button.danger {
          background: rgba(239, 68, 68, 0.15);
          color: #ef4444;
          border-color: rgba(239, 68, 68, 0.3);
        }

        .mod-button.danger:hover {
          background: rgba(239, 68, 68, 0.3);
          color: #f87171;
          border-color: #ef4444;
          box-shadow: 0 0 12px rgba(239, 68, 68, 0.3);
        }

        .mod-status-badges {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-top: 16px;
        }

        .status-badge {
          font-size: 0.75rem;
          font-weight: 600;
          padding: 4px 10px;
          border-radius: 12px;
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .status-badge.hidden {
          background: rgba(239, 68, 68, 0.2);
          color: #ef4444;
        }

        .status-badge.promoted {
          background: rgba(245, 158, 11, 0.2);
          color: #f59e0b;
        }

        .status-badge.pending {
          background: rgba(59, 130, 246, 0.2);
          color: #3b82f6;
        }

        .widget-section {
          background: var(--bg-secondary);
          border-radius: 12px;
          padding: 24px;
        }

        /* Ensure widget inherits dark theme properly */
        .widget-section :global(.makapix-widget) {
          background: transparent;
        }
      `}</style>
    </Layout>
  );
}
