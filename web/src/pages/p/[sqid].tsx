import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';
import CommentsAndReactions from '../../components/CommentsAndReactions';
import StatsPanel from '../../components/StatsPanel';
import SendToPlayerModal from '../../components/SendToPlayerModal';
import { authenticatedFetch, authenticatedRequestJson, authenticatedPostJson, clearTokens } from '../../lib/api';
import { 
  getNavigationContext, 
  setNavigationContext, 
  updateContextIndex, 
  extendContext, 
  findPostIndex,
  NavigationContext,
  NavigationContextPost 
} from '../../lib/navigation-context';
import { useSwipeNavigation } from '../../hooks/useSwipeNavigation';
import { listPlayers, Player } from '../../lib/api';

interface Post {
  id: number;
  storage_key: string;
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
    public_sqid: string;
  };
}

export default function PostPage() {
  const router = useRouter();
  const { sqid } = router.query;
  const [post, setPost] = useState<Post | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<{ id: string; public_sqid: string } | null>(null);
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
  
  // Player state
  const [players, setPlayers] = useState<Player[]>([]);
  const [showSendModal, setShowSendModal] = useState(false);
  
  // Image error state
  const [imageError, setImageError] = useState(false);
  
  // Navigation context state
  const [navContext, setNavContext] = useState<NavigationContext | null>(null);
  const [isMobile, setIsMobile] = useState(false);
  const extendingRef = useRef(false);
  
  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  useEffect(() => {
    if (!sqid || typeof sqid !== 'string') return;

    const fetchPost = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // Fetch post by public_sqid using the new canonical endpoint
        const response = await authenticatedFetch(`${API_BASE_URL}/api/p/${sqid}`);
        
        if (response.status === 401) {
          // Token refresh failed - treat as unauthenticated
          setCurrentUser(null);
          setIsOwner(false);
          setIsModerator(false);
        }
        
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
        
        // Try to get current user info if authenticated
        try {
          const userResponse = await authenticatedFetch(`${API_BASE_URL}/api/auth/me`);
          if (userResponse.status === 401) {
            // Not authenticated or token refresh failed
            setCurrentUser(null);
            setIsOwner(false);
            setIsModerator(false);
          } else if (userResponse.ok) {
            const userData = await userResponse.json();
            setCurrentUser({ id: userData.user.id, public_sqid: userData.user.public_sqid });
            setIsOwner(userData.user.id === data.owner_id);
            const roles = userData.user.roles || userData.roles || [];
            setIsModerator(roles.includes('moderator') || roles.includes('owner'));
            
            // Load players if user is authenticated
            try {
              const playersData = await listPlayers(userData.user.public_sqid);
              setPlayers(playersData.items);
            } catch (err) {
              // Silently fail - user might not have players
            }
          }
        } catch (err) {
          setCurrentUser(null);
          setIsOwner(false);
          setIsModerator(false);
        }
      } catch (err) {
        setError('Failed to load post');
        console.error('Error fetching post:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchPost();
  }, [sqid, API_BASE_URL]);

  // Check if device is mobile
  useEffect(() => {
    if (typeof window === 'undefined') return;
    
    const checkMobile = () => {
      const hasTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
      const isSmallScreen = window.innerWidth <= 768;
      setIsMobile(hasTouch && isSmallScreen);
    };
    
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Load or create navigation context
  useEffect(() => {
    if (!sqid || typeof sqid !== 'string' || !post) return;

    const loadContext = async () => {
      // Try to get existing context
      let context = getNavigationContext();
      
      // Validate context matches current post
      if (context) {
        const index = findPostIndex(context, sqid);
        if (index >= 0) {
          // Context is valid, update index
          updateContextIndex(index);
          setNavContext({ ...context, currentIndex: index });
          return;
        }
        // Context exists but doesn't contain current post - clear it
        context = null;
      }

      // No valid context - fetch default (author's profile posts)
      if (!context && post.owner_id) {
        await fetchDefaultContext(post.owner_id, sqid);
      }
    };

    loadContext();
  }, [sqid, post, API_BASE_URL]);

  // Fetch default context from author's profile
  const fetchDefaultContext = async (ownerId: string, currentSqid: string) => {
    try {
      const url = `${API_BASE_URL}/api/post?owner_id=${ownerId}&limit=100&sort=created_at&order=desc`;
      const response = await authenticatedFetch(url);
      
      if (!response.ok) return;
      
      const data = await response.json();
      const posts: NavigationContextPost[] = data.items.map((p: any) => ({
        public_sqid: p.public_sqid,
        id: p.id,
        owner_id: p.owner_id,
      }));
      
      const index = posts.findIndex((p) => p.public_sqid === currentSqid);
      if (index >= 0) {
        const context: NavigationContext = {
          posts,
          currentIndex: index,
          source: { type: 'profile', id: ownerId },
          cursor: data.next_cursor,
          timestamp: Date.now(),
        };
        setNavigationContext(posts, index, context.source, context.cursor);
        setNavContext(context);
      }
    } catch (err) {
      console.error('Failed to fetch default context:', err);
    }
  };

  // Navigate with View Transition API
  const navigateWithTransition = (url: string, direction: 'left' | 'right') => {
    if (typeof document === 'undefined') {
      router.push(url);
      return;
    }

    // Use View Transitions API if available
    if ('startViewTransition' in document) {
      // Inject dynamic CSS for the transition direction
      const styleId = 'swipe-transition-style';
      let styleEl = document.getElementById(styleId) as HTMLStyleElement | null;
      if (!styleEl) {
        styleEl = document.createElement('style');
        styleEl.id = styleId;
        document.head.appendChild(styleEl);
      }
      
      // Set animations based on swipe direction (targeting main-content to keep header static)
      if (direction === 'left') {
        // Swiping left = going to next post
        // Old page slides out to the left, new page slides in from right
        styleEl.textContent = `
          ::view-transition-old(main-content) {
            animation: swipe-slide-out-left 0.25s ease-out forwards;
          }
          ::view-transition-new(main-content) {
            animation: swipe-slide-in-from-right 0.25s ease-out forwards;
          }
        `;
      } else {
        // Swiping right = going to previous post
        // Old page slides out to the right, new page slides in from left
        styleEl.textContent = `
          ::view-transition-old(main-content) {
            animation: swipe-slide-out-right 0.25s ease-out forwards;
          }
          ::view-transition-new(main-content) {
            animation: swipe-slide-in-from-left 0.25s ease-out forwards;
          }
        `;
      }

      const transition = (document as any).startViewTransition(() => {
        router.push(url);
      });
      
      // Clean up style after transition
      transition.finished.finally(() => {
        if (styleEl) {
          styleEl.textContent = '';
        }
      });
    } else {
      // Fallback: regular navigation without animation
      router.push(url);
    }
  };

  // Extend context at boundaries
  const extendContextAtBoundary = async (direction: 'forward' | 'backward'): Promise<NavigationContext | null> => {
    if (extendingRef.current || !navContext) return null;
    
    extendingRef.current = true;
    
    try {
      let url = '';
      if (direction === 'forward') {
        if (!navContext.cursor) return null;
        url = buildApiUrl(navContext.source, navContext.cursor);
      } else {
        // For backward, we'd need prevCursor - simplified for now
        return null;
      }
      
      const response = await authenticatedFetch(url);
      if (!response.ok) return null;
      
      const data = await response.json();
      const newPosts: NavigationContextPost[] = data.items.map((p: any) => ({
        public_sqid: p.public_sqid,
        id: p.id,
        owner_id: p.owner_id,
      }));
      
      if (newPosts.length > 0) {
        extendContext(newPosts, direction, data.next_cursor);
        const updatedContext: NavigationContext = {
          ...navContext,
          posts: direction === 'forward' 
            ? [...navContext.posts, ...newPosts]
            : [...newPosts, ...navContext.posts],
          cursor: direction === 'forward' ? data.next_cursor : navContext.cursor,
          timestamp: Date.now(),
        };
        setNavContext(updatedContext);
        return updatedContext;
      }
      
      return null;
    } catch (err) {
      console.error('Failed to extend context:', err);
      return null;
    } finally {
      extendingRef.current = false;
    }
  };

  // Build API URL based on source type
  const buildApiUrl = (source: NavigationContext['source'], cursor: string | null): string => {
    const base = `${API_BASE_URL}/api/post`;
    const params = new URLSearchParams();
    params.append('limit', '20');
    params.append('sort', 'created_at');
    params.append('order', 'desc');
    
    if (cursor) {
      params.append('cursor', cursor);
    }
    
    switch (source.type) {
      case 'recent':
        // No additional params needed
        break;
      case 'recommended':
        return `${API_BASE_URL}/api/feed/promoted?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`;
      case 'profile':
        if (source.id) {
          params.append('owner_id', source.id);
        }
        break;
      case 'hashtag':
        if (source.id) {
          params.append('hashtag', source.id);
        }
        break;
    }
    
    return `${base}?${params.toString()}`;
  };

  // Swipe handlers
  const handleSwipeLeft = async () => {
    if (!navContext || !isMobile) return;
    
    const nextIndex = navContext.currentIndex + 1;
    
    // Check if we need to extend context
    if (nextIndex >= navContext.posts.length) {
      const updatedContext = await extendContextAtBoundary('forward');
      if (!updatedContext || nextIndex >= updatedContext.posts.length) {
        // Reached true end - ignore swipe
        return;
      }
      // Context was extended, navigate to next post
      const nextPost = updatedContext.posts[nextIndex];
      updateContextIndex(nextIndex);
      navigateWithTransition(`/p/${nextPost.public_sqid}`, 'left');
      return;
    }
    
    // Navigate to next post
    const nextPost = navContext.posts[nextIndex];
    updateContextIndex(nextIndex);
    navigateWithTransition(`/p/${nextPost.public_sqid}`, 'left');
  };

  const handleSwipeRight = async () => {
    if (!navContext || !isMobile) return;
    
    const prevIndex = navContext.currentIndex - 1;
    
    if (prevIndex < 0) {
      // Reached true beginning - ignore swipe
      return;
    }
    
    // Navigate to previous post
    const prevPost = navContext.posts[prevIndex];
    updateContextIndex(prevIndex);
    navigateWithTransition(`/p/${prevPost.public_sqid}`, 'right');
  };

  // Enable swipe navigation on mobile
  useSwipeNavigation(
    {
      onSwipeLeft: handleSwipeLeft,
      onSwipeRight: handleSwipeRight,
    },
    isMobile && !!navContext
  );

  // Set API URL for widget
  useEffect(() => {
    if (typeof window === 'undefined') return;
    
    if ((window as any).MAKAPIX_API_URL === undefined) {
      (window as any).MAKAPIX_API_URL = `${API_BASE_URL}/api`;
    }
  }, [API_BASE_URL]);

  // Reset image error when post changes
  useEffect(() => {
    setImageError(false);
  }, [post?.id]);

  // Initialize widget
  useEffect(() => {
    if (!post || !sqid || typeof sqid !== 'string') return;

    const initializeWidget = () => {
      if (typeof (window as any).MakapixWidget === 'undefined') {
        setTimeout(initializeWidget, 100);
        return;
      }

      const container = document.getElementById(`makapix-widget-${post.public_sqid}`);
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
  }, [post, sqid]);

  const handleDelete = async () => {
    if (!post) return;
    
    const confirmed = confirm(
      'Are you sure you want to delete this post?\n\n' +
      'This action cannot be undone.'
    );
    
    if (!confirmed) return;
    
    try {
      // Use the integer ID for API operations
      const response = await authenticatedFetch(`${API_BASE_URL}/api/post/${post.id}`, {
        method: 'DELETE',
      });
      
      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      
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
    if (!post) return;
    
    const isHidden = post.hidden_by_user;
    const action = isHidden ? 'unhide' : 'hide';
    const confirmed = confirm(
      isHidden
        ? 'Unhide this post? It will become visible again in feeds.'
        : 'Hide this post? It will be removed from feeds temporarily.'
    );
    
    if (!confirmed) return;
    
    try {
      const url = `${API_BASE_URL}/api/post/${post.id}/hide`;
      const method = isHidden ? 'DELETE' : 'POST';
      
      const response = await authenticatedFetch(url, {
        method: method,
        headers: {
          'Content-Type': 'application/json'
        }
      });
      
      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      
      if (response.ok || response.status === 201 || response.status === 204) {
        const refreshResponse = await authenticatedFetch(`${API_BASE_URL}/api/p/${post.public_sqid}`);
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
    if (!post) return;
    
    setIsSaving(true);
    setSaveError(null);
    
    // Parse hashtags from comma-separated string
    const hashtagsArray = editHashtags
      .split(',')
      .map(tag => tag.trim().toLowerCase().replace(/^#/, ''))
      .filter(tag => tag.length > 0);
    
    try {
      const updatedPost = await authenticatedRequestJson<Post>(
        `/api/post/${post.id}`,
        {
          body: JSON.stringify({
            title: editTitle.trim(),
            description: editDescription,
            hashtags: hashtagsArray
          })
        },
        'PATCH'
      );
      
      setPost(updatedPost);
      setIsEditing(false);
    } catch (err) {
      console.error('Error saving post:', err);
      if (err instanceof Error && err.message.includes('401')) {
        clearTokens();
        router.push('/auth');
        return;
      }
      setSaveError('Failed to save changes.');
    } finally {
      setIsSaving(false);
    }
  };

  // Moderator: Hide/Unhide as moderator
  const handleModHide = async () => {
    if (!post) return;
    
    const isHidden = post.hidden_by_mod;
    const action = isHidden ? 'unhide' : 'hide';
    const confirmed = confirm(
      isHidden
        ? 'Unhide this post (moderator action)? It will become visible again.'
        : 'Hide this post as moderator? This is a moderation action that will be logged.'
    );
    
    if (!confirmed) return;
    
    try {
      const url = `${API_BASE_URL}/api/post/${post.id}/hide`;
      const method = isHidden ? 'DELETE' : 'POST';
      
      const response = await authenticatedFetch(url, {
        method: method,
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ by: 'mod' })
      });
      
      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      
      if (response.ok || response.status === 201 || response.status === 204) {
        const refreshResponse = await authenticatedFetch(`${API_BASE_URL}/api/p/${post.public_sqid}`);
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
    if (!post) return;
    
    const isPromoted = post.promoted;
    const action = isPromoted ? 'demote' : 'promote';
    const confirmed = confirm(
      isPromoted
        ? 'Remove this post from promoted posts?'
        : 'Promote this post to the frontpage?'
    );
    
    if (!confirmed) return;
    
    try {
      const url = `${API_BASE_URL}/api/post/${post.id}/promote`;
      const method = isPromoted ? 'DELETE' : 'POST';
      
      const response = await authenticatedFetch(url, {
        method: method,
        headers: {
          'Content-Type': 'application/json'
        },
        body: isPromoted ? undefined : JSON.stringify({ category: 'frontpage' })
      });
      
      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      
      if (response.ok || response.status === 201 || response.status === 204) {
        const refreshResponse = await authenticatedFetch(`${API_BASE_URL}/api/p/${post.public_sqid}`);
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
    if (!post) return;
    
    // Only allow approving, not revoking
    if (post.public_visibility) return;
    
    const confirmed = confirm(
      'Approve public visibility? This artwork will appear in Recent Artworks and search results.\n\n' +
      'Note: This is a one-time action. To hide the artwork later, use the "Hide (Mod)" action instead.'
    );
    
    if (!confirmed) return;
    
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/post/${post.id}/approve-public`, {
        method: 'POST',
      });
      
      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      
      if (response.ok || response.status === 201) {
        const refreshResponse = await authenticatedFetch(`${API_BASE_URL}/api/p/${post.public_sqid}`);
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
    if (!post) return;
    
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
    
    try {
      const response = await authenticatedFetch(`${API_BASE_URL}/api/post/${post.id}/permanent`, {
        method: 'DELETE',
      });
      
      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      
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
    <Layout title={post.title} description={post.description || post.title}>
      <div className="post-container">
        {!imageError ? (
          <img
            src={post.art_url}
            alt={post.title}
            className="artwork-image pixel-art"
            onError={() => {
              setImageError(true);
            }}
          />
        ) : (
          <div className="image-error-message">
            <span className="error-icon">🖼️</span>
            <p>Image not available</p>
          </div>
        )}

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
              <Link href={`/u/${post.owner.public_sqid}`} className="author-link">
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

          {/* Send to Player button - visible to authenticated users with players */}
          {currentUser && players.length > 0 && (
            <div className="player-action">
              <button
                onClick={() => setShowSendModal(true)}
                className="action-button player"
                title="Send to Player"
              >
                🖼️ Send to Player
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
          <CommentsAndReactions
            contentType="artwork"
            contentId={post.id}
            API_BASE_URL={API_BASE_URL}
            currentUserId={currentUser?.id || null}
            isModerator={isModerator}
          />
        </div>
      </div>

      {/* Stats Panel Modal */}
      <StatsPanel
        postId={post.id}
        isOpen={showStats}
        onClose={() => setShowStats(false)}
      />

      {/* Send to Player Modal */}
      {currentUser && post && (
        <SendToPlayerModal
          isOpen={showSendModal}
          onClose={() => setShowSendModal(false)}
          players={players}
          sqid={currentUser.public_sqid}
          postId={post.id}
        />
      )}


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

        .image-error-message {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 3rem 2rem;
          margin-bottom: 24px;
          background: var(--bg-secondary);
          border-radius: 12px;
          color: var(--text-secondary);
          text-align: center;
        }

        .image-error-message .error-icon {
          font-size: 3rem;
          margin-bottom: 1rem;
          opacity: 0.5;
        }

        .image-error-message p {
          margin: 0;
          font-size: 1rem;
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

        .action-button.player {
          background: rgba(78, 159, 255, 0.2);
          color: #4e9fff;
        }

        .action-button.player:hover:not(:disabled) {
          background: rgba(78, 159, 255, 0.3);
          box-shadow: 0 0 12px rgba(78, 159, 255, 0.3);
        }

        .stats-action {
          margin-top: 16px;
          padding-top: 16px;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        .player-action {
          margin-top: 16px;
          padding-top: 16px;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        .player-action {
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


