import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../../components/Layout';
import CommentsAndReactions from '../../components/CommentsAndReactions';
import SPOReactionUsersOverlay from '../../components/SPOReactionUsersOverlay';
import StatsPanel from '../../components/StatsPanel';
import PlayerBar from '../../components/PlayerBarDynamic';
import { authenticatedFetch, authenticatedRequestJson, authenticatedPostJson, clearTokens } from '../../lib/api';
import { ensureCompatibleArtUrl } from '../../utils/imageCompat';
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
import { usePlayerBarOptional } from '../../contexts/PlayerBarContext';

interface License {
  id: number;
  identifier: string;
  title: string;
  canonical_url: string;
  badge_path: string;
}

interface Post {
  id: number;
  storage_key: string;
  public_sqid: string;
  title: string;
  description?: string;
  hashtags?: string[];
  art_url: string;
  width: number;
  height: number;
  frame_count?: number;
  owner_id: string;
  created_at: string;
  kind?: string;
  hidden_by_user?: boolean;
  hidden_by_mod?: boolean;
  public_visibility?: boolean;
  promoted?: boolean;
  promoted_category?: string;
  license_id?: number | null;
  license?: License | null;
  files?: Array<{ format: string; file_bytes: number; is_native: boolean }>;
  owner?: {
    id: string;
    handle: string;
    display_name: string;
    public_sqid: string;
    avatar_url?: string | null;
  };
}

interface ReactionTotals {
  totals: Record<string, number>;
  authenticated_totals: Record<string, number>;
  anonymous_totals: Record<string, number>;
  mine: string[];
}

interface WidgetData {
  reactions: ReactionTotals;
  comments: Array<unknown>;
  views_count: number;
}

function formatFileSizeCompact(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const k = 1000;
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const value = bytes / Math.pow(k, i);
  if (value >= 100) return `${Math.round(value)} ${units[i]}`;
  if (value >= 10) return `${value.toFixed(1)} ${units[i]}`;
  return `${value.toFixed(2)} ${units[i]}`;
}

function formatDateTime(isoString: string): string {
  const date = new Date(isoString);
  const year = date.getFullYear();
  const month = date.getMonth() + 1;
  const day = date.getDate();
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  return `${year}/${month}/${day} ${hours}:${minutes}`;
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

  // Widget data (reactions + comments + views counts) for the header stats row
  const [widgetData, setWidgetData] = useState<WidgetData | null>(null);

  // Reaction users overlay (opened via ⚡ stat click)
  const [showReactionUsersOverlay, setShowReactionUsersOverlay] = useState(false);

  // Kebab menu state
  const [showMoreMenu, setShowMoreMenu] = useState(false);
  const [activeSubMenu, setActiveSubMenu] = useState<string | null>(null);
  const [showFormatSubPanel, setShowFormatSubPanel] = useState(false);
  const [menuPosition, setMenuPosition] = useState<{ top: number; right: number } | null>(null);
  const moreMenuRef = useRef<HTMLDivElement>(null);
  const moreButtonRef = useRef<HTMLButtonElement>(null);
  const subPanelCloseTimeoutRef = useRef<number | null>(null);

  // Image error state
  const [imageError, setImageError] = useState(false);
  
  // Navigation context state
  const [navContext, setNavContext] = useState<NavigationContext | null>(null);
  const [isMobile, setIsMobile] = useState(false);
  const extendingRef = useRef(false);
  
  const playerBarContext = usePlayerBarOptional();

  const API_BASE_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  // Set selected artwork in PlayerBar when post loads
  useEffect(() => {
    if (post && playerBarContext) {
      playerBarContext.setSelectedArtwork({
        id: post.id,
        public_sqid: post.public_sqid,
        title: post.title,
        art_url: post.art_url,
      });
    }
    return () => {
      if (playerBarContext) {
        playerBarContext.setSelectedArtwork(null);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [post?.id]);

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

  // Fetch widget data (stats counts) once per post
  useEffect(() => {
    if (!post) return;
    const postId = post.id;
    let cancelled = false;
    (async () => {
      try {
        const url = `${API_BASE_URL}/api/post/${postId}/widget-data`;
        const response = await authenticatedFetch(url);
        if (cancelled) return;
        if (response.ok) {
          const data: WidgetData = await response.json();
          setWidgetData(data);
        }
      } catch (err) {
        console.error('Failed to load widget data:', err);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [post?.id, API_BASE_URL]);

  // Kebab submenu open/close helpers (mirror SPO behavior)
  const openSubMenu = (menu: string) => {
    if (subPanelCloseTimeoutRef.current) {
      window.clearTimeout(subPanelCloseTimeoutRef.current);
      subPanelCloseTimeoutRef.current = null;
    }
    setActiveSubMenu(menu);
    if (menu !== 'download') setShowFormatSubPanel(false);
  };

  const closeSubMenuDelayed = (delay: number = 300) => {
    if (subPanelCloseTimeoutRef.current) {
      window.clearTimeout(subPanelCloseTimeoutRef.current);
    }
    subPanelCloseTimeoutRef.current = window.setTimeout(() => {
      setActiveSubMenu(null);
      setShowFormatSubPanel(false);
      subPanelCloseTimeoutRef.current = null;
    }, delay);
  };

  // Closes only the format sub-panel; leaves the parent Download submenu
  // open so the cursor can continue down to "Native format".
  const closeFormatSubPanelDelayed = (delay: number = 300) => {
    if (subPanelCloseTimeoutRef.current) {
      window.clearTimeout(subPanelCloseTimeoutRef.current);
    }
    subPanelCloseTimeoutRef.current = window.setTimeout(() => {
      setShowFormatSubPanel(false);
      subPanelCloseTimeoutRef.current = null;
    }, delay);
  };

  const openFormatSub = () => {
    if (subPanelCloseTimeoutRef.current) {
      window.clearTimeout(subPanelCloseTimeoutRef.current);
      subPanelCloseTimeoutRef.current = null;
    }
    setShowFormatSubPanel(true);
  };

  const closeMoreMenu = () => {
    if (subPanelCloseTimeoutRef.current) {
      window.clearTimeout(subPanelCloseTimeoutRef.current);
      subPanelCloseTimeoutRef.current = null;
    }
    setShowMoreMenu(false);
    setActiveSubMenu(null);
    setShowFormatSubPanel(false);
  };

  // Cleanup pending submenu timeout on unmount
  useEffect(() => {
    return () => {
      if (subPanelCloseTimeoutRef.current) {
        window.clearTimeout(subPanelCloseTimeoutRef.current);
      }
    };
  }, []);

  // Close kebab menu on outside click
  useEffect(() => {
    if (!showMoreMenu) return;
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        moreMenuRef.current && !moreMenuRef.current.contains(target) &&
        moreButtonRef.current && !moreButtonRef.current.contains(target)
      ) {
        closeMoreMenu();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [showMoreMenu]);

  // Close kebab menu on Escape
  useEffect(() => {
    if (!showMoreMenu) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') closeMoreMenu();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [showMoreMenu]);

  // Open the kebab menu, positioning it just below the button
  const handleMoreMenuToggle = () => {
    if (!showMoreMenu && moreButtonRef.current) {
      const rect = moreButtonRef.current.getBoundingClientRect();
      const viewportWidth = window.innerWidth;
      const menuWidth = 200;
      const margin = 8;
      let rightPos = viewportWidth - rect.right;
      if (rect.right - menuWidth < margin) {
        rightPos = viewportWidth - menuWidth - margin;
      }
      setMenuPosition({ top: rect.bottom + 4, right: Math.max(margin, rightPos) });
      setShowMoreMenu(true);
    } else {
      closeMoreMenu();
    }
  };

  // Kebab action handlers (Edit-in-editor, Share, Download — visible to all)
  const handleEditInPiskel = () => {
    if (!post) return;
    closeMoreMenu();
    router.push(`/editor?edit=${post.public_sqid}`);
  };

  const handleEditInPixelc = () => {
    if (!post) return;
    closeMoreMenu();
    router.push(`/pixelc?edit=${post.public_sqid}`);
  };

  const handleDownloadNative = async () => {
    if (!post) return;
    closeMoreMenu();
    try {
      const resp = await fetch(`${API_BASE_URL}/api/d/${post.public_sqid}`);
      if (!resp.ok) throw new Error('Download failed');
      const blob = await resp.blob();
      const nativeFile = post.files?.find(f => f.is_native) || post.files?.[0];
      const ext = nativeFile?.format || 'png';
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${post.title || post.public_sqid}.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
    }
  };

  const handleDownloadUpscaled = async () => {
    if (!post) return;
    closeMoreMenu();
    try {
      const resp = await fetch(`${API_BASE_URL}/api/d/${post.public_sqid}/upscaled`);
      if (!resp.ok) throw new Error('Download failed');
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${post.title || post.public_sqid}_upscaled.webp`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
    }
  };

  const handleDownloadFormat = async (format: string) => {
    if (!post) return;
    closeMoreMenu();
    try {
      const resp = await fetch(`${API_BASE_URL}/api/d/${post.public_sqid}.${format}`);
      if (!resp.ok) throw new Error('Download failed');
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${post.title || post.public_sqid}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
    }
  };

  const shareOrCopy = async (blob: Blob, filename: string, mimeType: string) => {
    if (!post) return;
    const file = new File([blob], filename, { type: mimeType });
    if (navigator.share && navigator.canShare?.({ files: [file] })) {
      await navigator.share({ files: [file], title: post.title });
      return;
    }
    const postUrl = `${window.location.origin}/p/${post.public_sqid}`;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(postUrl);
    } else {
      const ta = document.createElement('textarea');
      ta.value = postUrl;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }
    alert('Link copied to clipboard');
  };

  const handleShareUpscaled = async () => {
    if (!post) return;
    closeMoreMenu();
    try {
      const resp = await fetch(`${API_BASE_URL}/api/d/${post.public_sqid}/upscaled`);
      if (!resp.ok) throw new Error('Fetch failed');
      const blob = await resp.blob();
      await shareOrCopy(blob, `${post.title || post.public_sqid}_upscaled.webp`, 'image/webp');
    } catch (err) {
      if ((err as Error).name !== 'AbortError') console.error('Share failed:', err);
    }
  };

  const handleShareNative = async () => {
    if (!post) return;
    closeMoreMenu();
    try {
      const resp = await fetch(`${API_BASE_URL}/api/d/${post.public_sqid}`);
      if (!resp.ok) throw new Error('Fetch failed');
      const blob = await resp.blob();
      const nativeFile = post.files?.find(f => f.is_native) || post.files?.[0];
      const ext = nativeFile?.format || 'png';
      const mimeType = ext === 'webp' ? 'image/webp' : ext === 'gif' ? 'image/gif' : 'image/png';
      await shareOrCopy(blob, `${post.title || post.public_sqid}.${ext}`, mimeType);
    } catch (err) {
      if ((err as Error).name !== 'AbortError') console.error('Share failed:', err);
    }
  };

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
      <div className="post-page">
        <div className="post-container">
          {!imageError ? (
            <img
              src={ensureCompatibleArtUrl(post.art_url, post.frame_count)}
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

            <div className="post-tech-info">
              {formatDateTime(post.created_at)}
              <span className="tech-separator">•</span>
              <span className={(post.frame_count ?? 1) > 256 ? 'frame-count-warn' : undefined}>
                {post.frame_count ?? 1}
              </span>
              ×({post.width}×{post.height})
              <span className="tech-separator">•</span>
              {formatFileSizeCompact(post.files?.find(f => f.is_native)?.file_bytes || 0)}{' '}
              {(post.files?.find(f => f.is_native)?.format || 'png').toUpperCase()}
            </div>

            <div className="post-info-header">
              {post.owner ? (
                <Link href={`/u/${post.owner.public_sqid}`} className="post-info-author">
                  {post.owner.avatar_url ? (
                    <img
                      src={post.owner.avatar_url.startsWith('http')
                        ? post.owner.avatar_url
                        : `${API_BASE_URL}${post.owner.avatar_url}`}
                      alt={post.owner.handle || 'Author'}
                      className="post-info-avatar"
                    />
                  ) : (
                    <div className="post-info-avatar post-info-avatar-placeholder">
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
                      </svg>
                    </div>
                  )}
                  <span className="post-info-handle">
                    {post.owner.display_name || post.owner.handle}
                  </span>
                </Link>
              ) : (
                <span className="post-info-author" />
              )}

              <div className="post-info-stats">
                <button
                  type="button"
                  className="stat-item stat-reactions"
                  onClick={() => setShowReactionUsersOverlay(true)}
                  title="See who reacted"
                  aria-label="See who reacted"
                >
                  <span className="stat-icon">⚡</span>
                  <span className="stat-count">
                    {widgetData
                      ? Object.values(widgetData.reactions.totals).reduce((s, n) => s + n, 0)
                      : 0}
                  </span>
                </button>
                <div className="stat-item">
                  <span className="stat-icon">💬</span>
                  <span className="stat-count">{widgetData?.comments.length ?? 0}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-icon">👁</span>
                  <span className="stat-count">{widgetData?.views_count ?? 0}</span>
                </div>
                <button
                  ref={moreButtonRef}
                  type="button"
                  className="more-button"
                  onClick={handleMoreMenuToggle}
                  aria-label="More options"
                >
                  &#8942;
                </button>
              </div>
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

            {/* License badge */}
            <div className="license-section">
              {post.license ? (
                <a
                  href={post.license.canonical_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="license-link"
                  title={post.license.title}
                >
                  <img
                    src={post.license.badge_path}
                    alt={post.license.identifier}
                    className="license-badge"
                  />
                </a>
              ) : (
                <span className="license-text">All rights reserved</span>
              )}
            </div>

            {isModerator && (post.hidden_by_mod || post.promoted || !post.public_visibility) && (
              <div className="mod-status-badges">
                {post.hidden_by_mod && <span className="status-badge hidden">Hidden by mod</span>}
                {post.promoted && <span className="status-badge promoted">Promoted</span>}
                {!post.public_visibility && <span className="status-badge pending">Pending approval</span>}
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
      </div>

      {/* Kebab three-dot menu */}
      {showMoreMenu && (
        <div className="more-menu-backdrop" onClick={closeMoreMenu}>
          <div
            ref={moreMenuRef}
            className="more-menu"
            style={{
              right: menuPosition?.right ?? 16,
              top: menuPosition?.top ?? 64,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <button className="menu-item disabled" disabled>
              Use as profile photo
            </button>
            <button className="menu-item disabled" disabled>
              Add to my favorites
            </button>

            <div className="menu-divider" />

            {/* Edit submenu */}
            <div
              onMouseEnter={() => openSubMenu('edit')}
              onMouseLeave={() => closeSubMenuDelayed()}
            >
              <button
                className="menu-item submenu-trigger"
                onClick={() => (activeSubMenu === 'edit' ? setActiveSubMenu(null) : openSubMenu('edit'))}
              >
                <span>Edit</span>
                <span className="submenu-arrow">{activeSubMenu === 'edit' ? '▼' : '▶'}</span>
              </button>
              {activeSubMenu === 'edit' && (
                <div className="submenu">
                  <button className="menu-item" onClick={handleEditInPiskel}>
                    In Piskel
                  </button>
                  {['png', 'webp', 'gif', 'bmp'].includes(
                    (post.files?.find(f => f.is_native)?.format || '').toLowerCase()
                  ) ? (
                    <button className="menu-item" onClick={handleEditInPixelc}>
                      In Pixelc
                    </button>
                  ) : (
                    <button className="menu-item disabled" disabled>
                      In Pixelc
                    </button>
                  )}
                </div>
              )}
            </div>

            {/* Share submenu */}
            <div
              onMouseEnter={() => openSubMenu('share')}
              onMouseLeave={() => closeSubMenuDelayed()}
            >
              <button
                className="menu-item submenu-trigger"
                onClick={() => (activeSubMenu === 'share' ? setActiveSubMenu(null) : openSubMenu('share'))}
              >
                <span>Share</span>
                <span className="submenu-arrow">{activeSubMenu === 'share' ? '▼' : '▶'}</span>
              </button>
              {activeSubMenu === 'share' && (
                <div className="submenu">
                  <button className="menu-item" onClick={handleShareUpscaled}>
                    Upscaled
                  </button>
                  <button className="menu-item" onClick={handleShareNative}>
                    Native size
                  </button>
                </div>
              )}
            </div>

            {/* Download submenu */}
            <div
              onMouseEnter={() => openSubMenu('download')}
              onMouseLeave={() => closeSubMenuDelayed()}
            >
              <button
                className="menu-item submenu-trigger"
                onClick={() => (activeSubMenu === 'download' ? setActiveSubMenu(null) : openSubMenu('download'))}
              >
                <span>Download</span>
                <span className="submenu-arrow">{activeSubMenu === 'download' ? '▼' : '▶'}</span>
              </button>
              {activeSubMenu === 'download' && (
                <div className="submenu">
                  <button className="menu-item" onClick={handleDownloadUpscaled}>
                    Upscaled
                  </button>
                  <button className="menu-item" onClick={handleDownloadNative}>
                    Native format
                  </button>
                  <div
                    onMouseEnter={openFormatSub}
                    onMouseLeave={() => closeFormatSubPanelDelayed()}
                  >
                    <button
                      className="menu-item submenu-trigger"
                      onClick={() => (showFormatSubPanel ? setShowFormatSubPanel(false) : openFormatSub())}
                    >
                      <span>Alternative format</span>
                      <span className="submenu-arrow">{showFormatSubPanel ? '▼' : '▶'}</span>
                    </button>
                    {showFormatSubPanel && (() => {
                      const alternativeFormats = (post.files || [])
                        .filter(f => !f.is_native)
                        .map(f => f.format);
                      return (
                        <div className="submenu">
                          {alternativeFormats.length > 0 ? (
                            alternativeFormats.map(format => (
                              <button
                                key={format}
                                className="menu-item"
                                onClick={() => handleDownloadFormat(format)}
                              >
                                {format.toUpperCase()}
                              </button>
                            ))
                          ) : (
                            <div className="menu-item disabled-text">No alternatives</div>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                </div>
              )}
            </div>

            {/* Owner-only actions */}
            {isOwner && (
              <>
                <div className="menu-divider" />
                <button
                  className="menu-item"
                  onClick={() => { closeMoreMenu(); handleEditClick(); }}
                >
                  ✏️ Edit details
                </button>
                <button
                  className="menu-item"
                  onClick={() => { closeMoreMenu(); setShowStats(true); }}
                >
                  📈 Statistics
                </button>
                <button
                  className="menu-item"
                  onClick={() => { closeMoreMenu(); void handleHide(); }}
                >
                  {post.hidden_by_user ? '👁️ Unhide' : '🙈 Hide'}
                </button>
                <button
                  className="menu-item danger"
                  onClick={() => { closeMoreMenu(); void handleDelete(); }}
                >
                  🗑️ Delete
                </button>
              </>
            )}

            {/* Moderator-only actions */}
            {isModerator && (
              <>
                <div className="menu-divider" />
                {!isOwner && (
                  <button
                    className="menu-item"
                    onClick={() => { closeMoreMenu(); setShowStats(true); }}
                  >
                    📈 Statistics
                  </button>
                )}
                <button
                  className="menu-item"
                  onClick={() => { closeMoreMenu(); void handleModHide(); }}
                >
                  {post.hidden_by_mod ? '👁️ Unhide (Mod)' : '🙈 Hide (Mod)'}
                </button>
                <button
                  className="menu-item"
                  onClick={() => { closeMoreMenu(); void handlePromote(); }}
                >
                  {post.promoted ? '⬇️ Demote' : '⭐ Promote'}
                </button>
                {!post.public_visibility && (
                  <button
                    className="menu-item"
                    onClick={() => { closeMoreMenu(); void handleApprovePublicVisibility(); }}
                  >
                    ✅ Approve public visibility
                  </button>
                )}
                {(post.hidden_by_mod || post.hidden_by_user) && (
                  <button
                    className="menu-item danger"
                    onClick={() => { closeMoreMenu(); void handlePermanentDelete(); }}
                  >
                    🗑️ Delete permanently
                  </button>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* Reaction users overlay (opened by ⚡ stat) */}
      <SPOReactionUsersOverlay
        postId={post.id}
        isOpen={showReactionUsersOverlay}
        onClose={() => setShowReactionUsersOverlay(false)}
      />

      {/* Stats Panel Modal */}
      <StatsPanel
        postId={post.id}
        isOpen={showStats}
        onClose={() => setShowStats(false)}
      />



      <style jsx>{`
        .post-page {
          padding: 24px;
        }

        /* Clamp both the artwork and the content below it to 512 CSS pixels max */
        .post-container {
          width: 100%;
          max-width: 512px;
          margin: 0 auto;
          box-sizing: border-box;
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

        .post-info-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 16px;
        }

        .post-info-author {
          display: flex;
          align-items: center;
          gap: 8px;
          color: var(--text-primary);
          min-width: 0;
          flex-shrink: 1;
        }

        .post-info-author:hover .post-info-handle {
          color: var(--accent-pink);
        }

        .post-info-avatar {
          width: 32px;
          height: 32px;
          border-radius: 0;
          object-fit: cover;
          image-rendering: pixelated;
          flex-shrink: 0;
        }

        .post-info-avatar-placeholder {
          background: var(--bg-tertiary);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--text-muted);
        }

        .post-info-handle {
          font-size: 0.95rem;
          font-weight: 500;
          color: var(--accent-cyan);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          transition: color var(--transition-fast);
        }

        .post-info-stats {
          display: flex;
          align-items: center;
          gap: 12px;
          flex-shrink: 0;
          color: var(--text-secondary);
        }

        .stat-item {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          font-size: 0.9rem;
          background: transparent;
          border: none;
          color: inherit;
          padding: 4px 2px;
          font-family: inherit;
        }

        .stat-reactions {
          cursor: pointer;
          border-radius: 4px;
          transition: background var(--transition-fast);
        }

        .stat-reactions:hover {
          background: rgba(255, 255, 255, 0.08);
        }

        .stat-icon {
          font-size: 1rem;
          line-height: 1;
        }

        .stat-count {
          font-variant-numeric: tabular-nums;
        }

        .more-button {
          background: transparent;
          border: none;
          color: var(--text-primary);
          font-size: 1.25rem;
          line-height: 1;
          cursor: pointer;
          padding: 4px 6px;
          border-radius: 4px;
          transition: background var(--transition-fast);
        }

        .more-button:hover {
          background: rgba(255, 255, 255, 0.08);
        }

        .post-tech-info {
          font-size: 0.8rem;
          color: var(--text-muted);
          margin-bottom: 16px;
          font-variant-numeric: tabular-nums;
          text-align: center;
        }

        .tech-separator {
          margin: 0 8px;
          opacity: 0.5;
        }

        .frame-count-warn {
          color: #ff8080;
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
          margin: -4px;
        }

        .hashtags > :global(*) {
          margin: 4px;
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

        .license-section {
          margin-top: 16px;
          padding-top: 16px;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        .license-link {
          display: inline-block;
        }

        .license-badge {
          max-width: 180px;
          height: auto;
          opacity: 0.85;
          transition: opacity var(--transition-fast);
        }

        .license-badge:hover {
          opacity: 1;
        }

        .license-text {
          font-size: 0.85rem;
          color: var(--text-muted);
          font-style: italic;
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
          margin-top: 16px;
        }

        .edit-actions > :global(* + *) {
          margin-left: 12px;
        }

        .mod-status-badges {
          display: flex;
          flex-wrap: wrap;
          margin: 16px -4px -4px;
        }

        .mod-status-badges > :global(*) {
          margin: 4px;
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

        @media (max-width: 640px) {
          .post-page {
            padding: 16px;
          }
        }

        /* Below the .post-container max-width, pull the PBS out to the
           viewport edges and square its corners. Artwork above and the
           comments widget below intentionally keep their side padding. */
        @media (max-width: 512px) {
          .post-info {
            margin-left: -16px;
            margin-right: -16px;
            border-radius: 0;
          }
        }
      `}</style>
      <style jsx global>{`
        .more-menu-backdrop {
          position: fixed;
          inset: 0;
          z-index: 20000;
        }

        .more-menu {
          position: fixed;
          background: #1a1a24;
          border: 1px solid rgba(255, 255, 255, 0.15);
          border-radius: 8px;
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
          min-width: 200px;
          padding: 4px 0;
          z-index: 20001;
        }

        .more-menu .menu-item {
          display: flex;
          width: 100%;
          padding: 10px 16px;
          font-size: 14px;
          color: #e8e8f0;
          background: transparent;
          border: none;
          text-align: left;
          cursor: pointer;
          font-family: inherit;
          align-items: center;
          justify-content: flex-start;
          gap: 8px;
        }

        .more-menu .menu-item.submenu-trigger {
          justify-content: space-between;
        }

        .more-menu .menu-item:hover:not(:disabled):not(.disabled-text) {
          background: rgba(255, 255, 255, 0.08);
        }

        .more-menu .menu-item.disabled,
        .more-menu .menu-item.disabled-text {
          color: #6a6a80;
          cursor: not-allowed;
        }

        .more-menu .menu-item.disabled-text {
          cursor: default;
        }

        .more-menu .menu-item.danger {
          color: #ef4444;
        }

        .more-menu .menu-item.danger:hover {
          background: rgba(239, 68, 68, 0.15);
        }

        .more-menu .menu-divider {
          height: 1px;
          background: rgba(255, 255, 255, 0.1);
          margin: 4px 0;
        }

        .more-menu .submenu {
          padding-left: 12px;
        }

        .more-menu .submenu-arrow {
          margin-left: 8px;
          font-size: 0.7rem;
          opacity: 0.7;
        }
      `}</style>
      <PlayerBar />
    </Layout>
  );
}


