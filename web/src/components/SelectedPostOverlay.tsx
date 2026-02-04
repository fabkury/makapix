import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion, useAnimationControls, useReducedMotion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/router';
import { authenticatedFetch, getAccessToken } from '../lib/api';
import { PLAYER_BAR_HEIGHT } from './PlayerBarDynamic';
import SPOCommentsOverlay from './SPOCommentsOverlay';

type Rect = { left: number; top: number; width: number; height: number };

const EMOJI_OPTIONS = ['👍', '❤️', '🔥', '😊', '⭐'];

export interface SelectedPostOverlayPost {
  id: number;
  public_sqid: string;
  title: string;
  description?: string;
  art_url: string;
  owner?: {
    handle: string;
    avatar_url?: string | null;
    public_sqid?: string;
  };
  created_at: string;
  frame_count: number;
  width: number;
  height: number;
  files: Array<{ format: string; file_bytes: number; is_native: boolean }>;
}

export interface SelectedPostOverlayProps {
  posts: SelectedPostOverlayPost[];
  selectedIndex: number;
  setSelectedIndex: (idx: number) => void;
  onClose: () => void; // parent should set selectedIndex = null
  onNavigateToPost: (idx: number) => void; // parent should set nav context + router.push
  getOriginRectForIndex: (idx: number) => Rect | null;
  currentUserId?: string | null;
  isModerator?: boolean;
}

interface ReactionTotals {
  totals: Record<string, number>;
  authenticated_totals: Record<string, number>;
  anonymous_totals: Record<string, number>;
  mine: string[];
}

interface Comment {
  id: string;
  author_id: string | null;
  author_ip: string | null;
  parent_id: string | null;
  depth: number;
  body: string;
  hidden_by_mod: boolean;
  deleted_by_owner: boolean;
  created_at: string;
  updated_at: string | null;
  author_handle?: string;
  author_display_name?: string;
}

interface WidgetData {
  reactions: ReactionTotals;
  comments: Comment[];
  views_count: number;
}

function getVisualViewportBox(): { x: number; y: number; width: number; height: number } {
  if (typeof window === 'undefined') return { x: 0, y: 0, width: 0, height: 0 };
  const vv = window.visualViewport;
  if (!vv) return { x: 0, y: 0, width: window.innerWidth, height: window.innerHeight };
  return {
    x: vv.offsetLeft ?? 0,
    y: vv.offsetTop ?? 0,
    width: vv.width ?? window.innerWidth,
    height: vv.height ?? window.innerHeight,
  };
}

const POST_HEADER_HEIGHT = 32;
const META_AREA_WIDTH = 384;

function computeSelectedTargetRect(): { x: number; y: number; width: number; height: number } {
  const vv = getVisualViewportBox();
  const size = 384;
  return {
    x: vv.x + (vv.width - size) / 2,
    // Stable position pinned to the top of the viewport (not affected by page scroll)
    // and must leave room for the post-header.
    y: POST_HEADER_HEIGHT,
    width: size,
    height: size,
  };
}

function computeMetaAreaPosition(): { x: number; y: number } {
  const vv = getVisualViewportBox();
  const targetRect = computeSelectedTargetRect();
  return {
    x: vv.x + (vv.width - META_AREA_WIDTH) / 2,
    // Position below the artwork
    y: targetRect.y + targetRect.height,
  };
}

async function fetchWidgetData(postId: number): Promise<WidgetData | null> {
  const url = `/api/post/${postId}/widget-data`;
  const hasToken = !!getAccessToken();
  try {
    const resp = hasToken
      ? await authenticatedFetch(url.startsWith('http') ? url : `${window.location.origin}${url}`)
      : await fetch(url, { credentials: 'include' });
    if (!resp.ok) return null;
    const data = await resp.json();
    return data;
  } catch {
    return null;
  }
}

async function toggleReaction(postId: number, emoji: string, shouldAdd: boolean): Promise<void> {
  const encoded = encodeURIComponent(emoji);
  const url = `/api/post/${postId}/reactions/${encoded}`;
  const method = shouldAdd ? 'PUT' : 'DELETE';
  const hasToken = !!getAccessToken();
  const resp = hasToken
    ? await authenticatedFetch(url.startsWith('http') ? url : `${window.location.origin}${url}`, { method })
    : await fetch(url, { method, credentials: 'include' });
  if (!resp.ok) {
    const txt = await resp.text().catch(() => '');
    throw new Error(`Failed to ${shouldAdd ? 'add' : 'remove'} reaction: ${resp.status} ${txt}`.trim());
  }
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

// Inline styles to ensure they work inside the portal
// NOTE: overlayStyles is used as a base; bottom is dynamically adjusted to exclude PlayerBar
const overlayStyles: React.CSSProperties = {
  position: 'fixed',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0, // Dynamically adjusted in JSX when PlayerBar is present
  // Must sit above the site top-header and any other fixed UI.
  zIndex: 20000,
  pointerEvents: 'auto',
  // Prevent touch gestures from causing page scroll when dragging inside the overlay
  touchAction: 'none',
};

const backdropStyles: React.CSSProperties = {
  position: 'fixed',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  background: 'rgba(0, 0, 0, 0.85)',
  backdropFilter: 'blur(16px)',
  WebkitBackdropFilter: 'blur(16px)',
};

const artworkShellStyles: React.CSSProperties = {
  position: 'fixed',
  // CRITICAL: Must set left/top to 0 so Framer Motion's x/y transforms 
  // become actual viewport coordinates. Without this, x/y offset from
  // an unpredictable "static" position in the document flow.
  left: 0,
  top: 0,
  overflow: 'visible',
  touchAction: 'none',
  willChange: 'transform, width, height',
  background: 'rgba(0, 0, 0, 0.18)',
  cursor: 'pointer',
};

const artworkClipStyles: React.CSSProperties = {
  width: '100%',
  height: '100%',
  position: 'relative',
  overflow: 'hidden',
};

const artworkImageStyles: React.CSSProperties = {
  display: 'block',
  width: '100%',
  height: '100%',
  objectFit: 'cover',
  objectPosition: 'center',
  userSelect: 'none',
  WebkitUserSelect: 'none',
  pointerEvents: 'none',
  imageRendering: 'pixelated',
};

const likeBurstStyles: React.CSSProperties = {
  position: 'absolute',
  left: '50%',
  top: '50%',
  marginLeft: '-28px',
  marginTop: '-28px',
  fontSize: '56px',
  textShadow: '0 10px 24px rgba(0, 0, 0, 0.45)',
  pointerEvents: 'none',
};

function computePostHeaderPosition(): { x: number; y: number } {
  const vv = getVisualViewportBox();
  const headerWidth = 384;
  return {
    x: vv.x + (vv.width - headerWidth) / 2,
    // Stable position pinned to the top of the viewport (independent of scroll)
    y: 0,
  };
}

const postHeaderLeftStyles: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '8px',
};

const postHeaderRightStyles: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
};

const postAuthorAvatarStyles: React.CSSProperties = {
  width: 32,
  height: 32,
  borderRadius: 0,
  objectFit: 'cover',
  imageRendering: 'pixelated',
};

const postAuthorHandleStyles: React.CSSProperties = {
  fontFamily: "'Noto Sans', 'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  fontSize: '14px',
  fontWeight: 500,
  color: '#e8e8f0',
};

const postReactionCountStyles: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '2px',
  fontFamily: "'Noto Sans', 'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  fontSize: '14px',
  fontWeight: 500,
  color: '#e8e8f0',
};

const postCommentCountStyles: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '2px',
  fontFamily: "'Noto Sans', 'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  fontSize: '14px',
  fontWeight: 500,
  color: '#e8e8f0',
};

const postViewCountStyles: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '2px',
  fontFamily: "'Noto Sans', 'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  fontSize: '14px',
  fontWeight: 500,
  color: '#e8e8f0',
};

const metaAreaStyles: React.CSSProperties = {
  position: 'fixed',
  left: 0,
  top: 0,
  width: META_AREA_WIDTH,
  background: '#000',
  fontFamily: "'Noto Sans', 'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  pointerEvents: 'auto',
  zIndex: 20001,
};

const titleRowStyles: React.CSSProperties = {
  height: 32,
  display: 'flex',
  alignItems: 'center',
  paddingLeft: 16,
  paddingRight: 16,
  fontSize: '14px',
  fontWeight: 600,
  color: '#e8e8f0',
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
};

const reactionsRowStyles: React.CSSProperties = {
  height: 32,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 12,
  padding: '0 8px',
};

const reactionButtonStyles: React.CSSProperties = {
  position: 'relative',
  padding: '4px 8px',
  fontSize: '18px',
  background: 'transparent',
  border: '2px solid transparent',
  borderRadius: '8px',
  cursor: 'pointer',
  transition: 'all 0.15s ease',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
};

const reactionBadgeStyles: React.CSSProperties = {
  position: 'absolute',
  bottom: -2,
  right: -2,
  background: '#00d4ff',
  color: '#1a1a24',
  fontSize: '10px',
  fontWeight: 700,
  padding: '1px 4px',
  borderRadius: '8px',
  minWidth: 16,
  textAlign: 'center',
  lineHeight: '1.2',
  boxShadow: '0 2px 4px rgba(0, 0, 0, 0.3)',
};

const commentButtonStyles: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 4,
  padding: '4px 8px',
  fontSize: '18px',
  background: 'transparent',
  border: '2px solid transparent',
  borderRadius: '8px',
  cursor: 'pointer',
  transition: 'all 0.15s ease',
  color: '#e8e8f0',
};

const descriptionAreaStyles: React.CSSProperties = {
  maxHeight: 200,
  overflowY: 'auto',
  padding: 12,
  fontSize: '13px',
  lineHeight: 1.5,
  color: '#a0a0b8',
  // Allow vertical scrolling within description only, without propagating to page
  touchAction: 'pan-y',
  overscrollBehavior: 'contain',
};

const technicalInfoRowStyles: React.CSSProperties = {
  height: 24,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: '12px',
  color: '#a0a0b8',
};

const moreButtonStyles: React.CSSProperties = {
  background: 'transparent',
  border: 'none',
  color: '#e8e8f0',
  fontSize: '18px',
  cursor: 'pointer',
  padding: '4px 8px',
  marginLeft: '8px',
  borderRadius: '4px',
  lineHeight: 1,
};

const moreMenuOverlayStyles: React.CSSProperties = {
  position: 'fixed',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  zIndex: 20002,
};

const moreMenuStyles: React.CSSProperties = {
  position: 'absolute',
  background: '#1a1a24',
  border: '1px solid rgba(255, 255, 255, 0.15)',
  borderRadius: '8px',
  boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
  minWidth: '200px',
  overflow: 'visible',
};

const menuItemStyles: React.CSSProperties = {
  display: 'block',
  width: '100%',
  padding: '10px 16px',
  fontSize: '14px',
  color: '#e8e8f0',
  background: 'transparent',
  border: 'none',
  textAlign: 'left',
  cursor: 'pointer',
  fontFamily: "'Noto Sans', 'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
};

const menuItemDisabledStyles: React.CSSProperties = {
  ...menuItemStyles,
  color: '#6a6a80',
  cursor: 'not-allowed',
};

const subPanelStyles: React.CSSProperties = {
  position: 'absolute',
  // Position to the LEFT of the parent menu since menu is at right edge of screen
  right: '100%',
  top: 0,
  background: '#1a1a24',
  border: '1px solid rgba(255, 255, 255, 0.15)',
  borderRadius: '8px',
  boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
  minWidth: '140px',
  overflow: 'hidden',
  marginRight: '4px',
};

type AnimationPhase = 'mounting' | 'flying-in' | 'selected' | 'flying-out' | 'swiping';

export default function SelectedPostOverlay({
  posts,
  selectedIndex,
  setSelectedIndex,
  onClose,
  onNavigateToPost,
  getOriginRectForIndex,
  currentUserId,
  isModerator = false,
}: SelectedPostOverlayProps) {
  const reduceMotion = useReducedMotion();
  const router = useRouter();
  const controls = useAnimationControls();
  const outgoingControls = useAnimationControls();
  const incomingControls = useAnimationControls();
  const backdropControls = useAnimationControls();
  const headerControls = useAnimationControls();
  const metaAreaControls = useAnimationControls();
  const [portalEl, setPortalEl] = useState<HTMLElement | null>(null);
  const [phase, setPhase] = useState<AnimationPhase>('mounting');
  const [hasPlayerBar, setHasPlayerBar] = useState(false);
  const [pressing, setPressing] = useState(false);
  const [likeBurstKey, setLikeBurstKey] = useState(0);

  // Reset like burst after 3 seconds
  useEffect(() => {
    if (likeBurstKey === 0) return;
    const timer = setTimeout(() => {
      setLikeBurstKey(0);
    }, 3000);
    return () => clearTimeout(timer);
  }, [likeBurstKey]);

  const [targetRect, setTargetRect] = useState(() => computeSelectedTargetRect());
  const [headerPosition, setHeaderPosition] = useState(() => computePostHeaderPosition());
  const [metaAreaPosition, setMetaAreaPosition] = useState(() => computeMetaAreaPosition());
  const [headerContentKey, setHeaderContentKey] = useState(0);
  const [metaContentKey, setMetaContentKey] = useState(0);
  const [showCommentsOverlay, setShowCommentsOverlay] = useState(false);
  const [showMoreMenu, setShowMoreMenu] = useState(false);
  const [showFormatSubPanel, setShowFormatSubPanel] = useState(false);
  const [menuPosition, setMenuPosition] = useState<{ top: number; right: number } | null>(null);
  const moreMenuRef = useRef<HTMLDivElement>(null);
  const moreButtonRef = useRef<HTMLButtonElement>(null);
  const subPanelCloseTimeoutRef = useRef<number | null>(null);

  // Helper to close submenu with optional delay
  const closeSubPanelDelayed = useCallback((delay: number = 300) => {
    if (subPanelCloseTimeoutRef.current) {
      window.clearTimeout(subPanelCloseTimeoutRef.current);
    }
    subPanelCloseTimeoutRef.current = window.setTimeout(() => {
      setShowFormatSubPanel(false);
      subPanelCloseTimeoutRef.current = null;
    }, delay);
  }, []);

  // Helper to cancel pending close and optionally show submenu
  const cancelSubPanelClose = useCallback((show?: boolean) => {
    if (subPanelCloseTimeoutRef.current) {
      window.clearTimeout(subPanelCloseTimeoutRef.current);
      subPanelCloseTimeoutRef.current = null;
    }
    if (show !== undefined) {
      setShowFormatSubPanel(show);
    }
  }, []);

  // Helper to immediately close submenu (for when parent closes)
  const closeSubPanelImmediate = useCallback(() => {
    if (subPanelCloseTimeoutRef.current) {
      window.clearTimeout(subPanelCloseTimeoutRef.current);
      subPanelCloseTimeoutRef.current = null;
    }
    setShowFormatSubPanel(false);
  }, []);

  // Widget data (reactions + comments)
  const [widgetData, setWidgetData] = useState<WidgetData | null>(null);
  const [loadingWidget, setLoadingWidget] = useState(false);
  const widgetCacheRef = useRef<Map<number, WidgetData>>(new Map());

  // Track which posts have been viewed in this SPO session (to avoid duplicate view calls)
  const viewedPostsRef = useRef<Set<number>>(new Set());
  
  // Store the initial origin rect SYNCHRONOUSLY on first render to avoid timing issues
  // Using a ref to capture it immediately, then a state for re-renders
  const initialOriginRectRef = useRef<Rect | null>(null);
  if (initialOriginRectRef.current === null) {
    initialOriginRectRef.current = getOriginRectForIndex(selectedIndex);
  }
  const [initialOriginRect] = useState<Rect | null>(() => initialOriginRectRef.current);
  
  // Track outgoing artwork during swipe transitions
  const [outgoingPost, setOutgoingPost] = useState<{ 
    post: SelectedPostOverlayPost; 
    rect: Rect;
    startX: number;
    startY: number;
    startWidth: number;
    startHeight: number;
  } | null>(null);
  
  // Track incoming artwork during swipe transitions (separate from main to avoid React re-render issues)
  const [incomingPost, setIncomingPost] = useState<{ 
    post: SelectedPostOverlayPost; 
    rect: Rect;
    startX: number;
    startY: number;
    startWidth: number;
    startHeight: number;
  } | null>(null);

  const pressTimerRef = useRef<number | null>(null);
  const pressStartRef = useRef<{ x: number; y: number; time: number } | null>(null);
  const reactionInFlightRef = useRef(false);

  const dismissToOriginAndCloseRef = useRef<() => Promise<void>>(() => Promise.resolve());

  const post = posts[selectedIndex];

  // Get current origin rect fresh from DOM (can change when scrolling/resizing)
  const getCurrentOriginRect = useCallback(() => getOriginRectForIndex(selectedIndex), [getOriginRectForIndex, selectedIndex]);

  const clearPressTimer = useCallback(() => {
    if (pressTimerRef.current) window.clearTimeout(pressTimerRef.current);
    pressTimerRef.current = null;
    pressStartRef.current = null;
    setPressing(false);
  }, []);

  // Cleanup subpanel close timeout on unmount
  useEffect(() => {
    return () => {
      if (subPanelCloseTimeoutRef.current) {
        window.clearTimeout(subPanelCloseTimeoutRef.current);
      }
    };
  }, []);

  // Create portal root
  useEffect(() => {
    if (typeof document === 'undefined') return;
    const el = document.createElement('div');
    el.setAttribute('data-selected-post-overlay', 'true');
    document.body.appendChild(el);
    setPortalEl(el);

    return () => {
      el.remove();
    };
  }, []);

  // The selection overlay should NOT darken the PlayerBar. We enforce this by
  // cutting the backdrop short by PLAYER_BAR_HEIGHT when the PlayerBar exists.
  useEffect(() => {
    if (typeof document === 'undefined') return;
    const check = () => setHasPlayerBar(!!document.querySelector('.player-bar'));
    check();
    const obs = new MutationObserver(check);
    obs.observe(document.body, { childList: true, subtree: true });
    return () => obs.disconnect();
  }, []);

  // Keep target position aligned to the visual viewport (browser bar show/hide)
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const vv = window.visualViewport;
    const handler = () => {
      const next = computeSelectedTargetRect();
      const nextHeaderPos = computePostHeaderPosition();
      const nextMetaPos = computeMetaAreaPosition();
      setTargetRect(next);
      setHeaderPosition(nextHeaderPos);
      setMetaAreaPosition(nextMetaPos);
      if (phase !== 'selected') return;
      controls.start({
        x: next.x,
        y: next.y,
        transition: reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 520, damping: 44 },
      });
      metaAreaControls.start({
        x: nextMetaPos.x,
        y: nextMetaPos.y,
        transition: reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 520, damping: 44 },
      });
    };

    handler();

    if (vv) {
      vv.addEventListener('resize', handler);
      vv.addEventListener('scroll', handler);
      return () => {
        vv.removeEventListener('resize', handler);
        vv.removeEventListener('scroll', handler);
      };
    }

    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, [controls, metaAreaControls, phase, reduceMotion]);

  // Fetch widget data (reactions + comments)
  useEffect(() => {
    const postId = post?.id;
    if (!postId) return;
    let cancelled = false;
    (async () => {
      try {
        const cached = widgetCacheRef.current.get(postId);
        if (cached) {
          setWidgetData(cached);
          return;
        }

        setLoadingWidget(true);
        const data = await fetchWidgetData(postId);
        if (cancelled) return;
        if (data) {
          widgetCacheRef.current.set(postId, data);
          setWidgetData(data);
        }
      } catch {
        // ignore
      } finally {
        if (!cancelled) setLoadingWidget(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [post?.id]);

  // Register intentional view with debounce
  useEffect(() => {
    const postId = post?.id;
    if (!postId) return;

    // Skip if already viewed in this SPO session
    if (viewedPostsRef.current.has(postId)) return;

    // Skip self-views
    const ownerSqid = post?.owner?.public_sqid;
    if (currentUserId && ownerSqid && currentUserId === ownerSqid) return;

    // Debounce: only register if displayed for 2 seconds
    const timer = setTimeout(async () => {
      viewedPostsRef.current.add(postId);
      const url = `/api/post/${postId}/view`;
      const hasToken = !!getAccessToken();
      try {
        const res = hasToken
          ? await authenticatedFetch(url, { method: 'POST' })
          : await fetch(url, { method: 'POST', credentials: 'include' });
        // Optimistically increment view count on success (204)
        if (res.ok) {
          setWidgetData((prev) =>
            prev ? { ...prev, views_count: prev.views_count + 1 } : prev
          );
          // Also update the cache so swiping away and back shows the updated count
          const cached = widgetCacheRef.current.get(postId);
          if (cached) {
            widgetCacheRef.current.set(postId, {
              ...cached,
              views_count: cached.views_count + 1,
            });
          }
        }
      } catch {
        // Ignore fetch errors - view registration is best-effort
      }
    }, 2000);

    return () => clearTimeout(timer);
  }, [post?.id, post?.owner?.public_sqid, currentUserId]);

  // Animate in: wait for portal, then animate from grid position to center
  useEffect(() => {
    if (!portalEl || !post || phase !== 'mounting') return;
    
    // Use a small delay to ensure the initial position is rendered
    const timer = requestAnimationFrame(() => {
      setPhase('flying-in');

      // Fade backdrop in concurrently with fly-in
      void backdropControls.start({
        opacity: 0.62,
        transition: reduceMotion ? { duration: 0 } : { duration: 0.38, ease: [0.22, 1, 0.36, 1] },
      });

      // Animate header sliding in from top
      const headerPos = computePostHeaderPosition();
      headerControls.set({
        x: headerPos.x,
        y: headerPos.y - POST_HEADER_HEIGHT,
        opacity: 0,
      });
      void headerControls.start({
        x: headerPos.x,
        y: headerPos.y,
        opacity: 1,
        transition: reduceMotion
          ? { duration: 0 }
          : { duration: 0.3, ease: [0.42, 0, 0.58, 1] },
      });

      // Animate meta area fading in
      const metaPos = computeMetaAreaPosition();
      metaAreaControls.set({
        x: metaPos.x,
        y: metaPos.y,
        opacity: 0,
      });
      void metaAreaControls.start({
        x: metaPos.x,
        y: metaPos.y,
        opacity: 1,
        transition: reduceMotion
          ? { duration: 0 }
          : { duration: 0.3, ease: [0.22, 1, 0.36, 1] },
      });
      
      const origin = initialOriginRect;
      if (!origin) {
        // Fallback: appear directly in selected position
        controls.set({
          x: targetRect.x,
          y: targetRect.y,
          width: targetRect.width,
          height: targetRect.height,
          scale: 1,
        });
        setPhase('selected');
        return;
      }

      // Explicitly set starting position at the origin (grid card position)
      // This ensures the animation starts from exactly where the card is
      controls.set({
        x: origin.left,
        y: origin.top,
        width: origin.width,
        height: origin.height,
        scale: 1,
      });

      // Animate from origin to target
      controls
        .start({
          x: targetRect.x,
          y: targetRect.y,
          width: targetRect.width,
          height: targetRect.height,
          transition: reduceMotion
            ? { duration: 0 }
            : { type: 'spring', stiffness: 400, damping: 35, mass: 0.8 },
        })
        .then(() => setPhase('selected'));
    });

    return () => cancelAnimationFrame(timer);
  }, [backdropControls, controls, headerControls, metaAreaControls, portalEl, post, phase, initialOriginRect, reduceMotion, targetRect]);

  const handleReactionClick = useCallback(async (emoji: string) => {
    if (!post || reactionInFlightRef.current) return;
    reactionInFlightRef.current = true;
    try {
      const isActive = widgetData?.reactions.mine.includes(emoji) || false;
      const next = !isActive;
      
      // Optimistic update
      if (widgetData) {
        const newMine = next
          ? [...widgetData.reactions.mine, emoji]
          : widgetData.reactions.mine.filter(e => e !== emoji);
        const newTotals = { ...widgetData.reactions.totals };
        newTotals[emoji] = Math.max(0, (newTotals[emoji] || 0) + (next ? 1 : -1));
        
        const updated: WidgetData = {
          ...widgetData,
          reactions: {
            ...widgetData.reactions,
            mine: newMine,
            totals: newTotals,
          },
        };
        setWidgetData(updated);
        widgetCacheRef.current.set(post.id, updated);
      }

      await toggleReaction(post.id, emoji, next);

      // Re-fetch to sync
      const data = await fetchWidgetData(post.id);
      if (data) {
        setWidgetData(data);
        widgetCacheRef.current.set(post.id, data);
      }
    } catch (err) {
      console.error('Failed to toggle reaction:', err);
      // Revert on error
      const data = await fetchWidgetData(post.id);
      if (data) {
        setWidgetData(data);
        widgetCacheRef.current.set(post.id, data);
      }
    } finally {
      reactionInFlightRef.current = false;
    }
  }, [post, widgetData]);

  const handleEditInPiskel = useCallback(() => {
    if (!post) return;
    setShowMoreMenu(false);
    router.push(`/editor?edit=${post.public_sqid}`);
  }, [post, router]);

  const handleEditInPixelc = useCallback(() => {
    if (!post) return;
    setShowMoreMenu(false);
    router.push(`/pixelc?edit=${post.public_sqid}`);
  }, [post, router]);

  const handleDownloadNative = useCallback(async () => {
    if (!post) return;
    setShowMoreMenu(false);
    try {
      const resp = await fetch(`/api/d/${post.public_sqid}`);
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
  }, [post]);

  const handleDownloadUpscaled = useCallback(async () => {
    if (!post) return;
    setShowMoreMenu(false);
    try {
      const resp = await fetch(`/api/d/${post.public_sqid}/upscaled`);
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
  }, [post]);

  const handleDownloadFormat = useCallback(async (format: string) => {
    if (!post) return;
    setShowMoreMenu(false);
    setShowFormatSubPanel(false);
    try {
      const resp = await fetch(`/api/d/${post.public_sqid}.${format}`);
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
  }, [post]);

  const handleShareUpscaled = useCallback(async () => {
    if (!post) return;
    setShowMoreMenu(false);
    try {
      const resp = await fetch(`/api/d/${post.public_sqid}/upscaled`);
      if (!resp.ok) throw new Error('Fetch failed');
      const blob = await resp.blob();
      const file = new File([blob], `${post.title || post.public_sqid}_upscaled.webp`, { type: 'image/webp' });

      if (navigator.share && navigator.canShare?.({ files: [file] })) {
        await navigator.share({
          files: [file],
          title: post.title,
        });
      } else {
        // Fallback: copy post URL to clipboard
        const postUrl = `${window.location.origin}/p/${post.public_sqid}`;
        await navigator.clipboard.writeText(postUrl);
        alert('Link copied to clipboard');
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        console.error('Share failed:', err);
      }
    }
  }, [post]);

  const handleShareNative = useCallback(async () => {
    if (!post) return;
    setShowMoreMenu(false);
    try {
      const resp = await fetch(`/api/d/${post.public_sqid}`);
      if (!resp.ok) throw new Error('Fetch failed');
      const blob = await resp.blob();
      const nativeFile2 = post.files?.find(f => f.is_native) || post.files?.[0];
      const ext = nativeFile2?.format || 'png';
      const mimeType = ext === 'webp' ? 'image/webp' : ext === 'gif' ? 'image/gif' : 'image/png';
      const file = new File([blob], `${post.title || post.public_sqid}.${ext}`, { type: mimeType });

      if (navigator.share && navigator.canShare?.({ files: [file] })) {
        await navigator.share({
          files: [file],
          title: post.title,
        });
      } else {
        // Fallback: copy post URL to clipboard
        const postUrl = `${window.location.origin}/p/${post.public_sqid}`;
        await navigator.clipboard.writeText(postUrl);
        alert('Link copied to clipboard');
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        console.error('Share failed:', err);
      }
    }
  }, [post]);

  const dismissToOriginAndClose = useCallback(async () => {
    // Get fresh origin rect from DOM to ensure precision after any scroll/resize
    const origin = getCurrentOriginRect() ?? initialOriginRect;
    if (!origin) {
      // Still fade the backdrop out to avoid a hard cut
      const headerPos = computePostHeaderPosition();
      await Promise.all([
        backdropControls.start({
          opacity: 0,
          transition: reduceMotion ? { duration: 0 } : { duration: 0.32, ease: [0.4, 0, 1, 1] },
        }),
        headerControls.start({
          y: headerPos.y - POST_HEADER_HEIGHT,
          opacity: 0,
          transition: reduceMotion ? { duration: 0 } : { duration: 0.3, ease: [0.42, 0, 0.58, 1] },
        }),
        metaAreaControls.start({
          opacity: 0,
          transition: reduceMotion ? { duration: 0 } : { duration: 0.32, ease: [0.4, 0, 1, 1] },
        }),
      ]);
      onClose();
      return;
    }
    setPhase('flying-out');
    clearPressTimer();
    const headerPos = computePostHeaderPosition();
    const flyBack = controls.start({
      x: origin.left,
      y: origin.top,
      width: origin.width,
      height: origin.height,
      transition: reduceMotion
        ? { duration: 0 }
        : { type: 'spring', stiffness: 500, damping: 40, mass: 0.8 },
    });
    const fadeOut = backdropControls.start({
      opacity: 0,
      transition: reduceMotion ? { duration: 0 } : { duration: 0.32, ease: [0.4, 0, 1, 1] },
    });
    const headerFadeOut = headerControls.start({
      y: headerPos.y - POST_HEADER_HEIGHT,
      opacity: 0,
      transition: reduceMotion ? { duration: 0 } : { duration: 0.3, ease: [0.42, 0, 0.58, 1] },
    });
    const metaFadeOut = metaAreaControls.start({
      opacity: 0,
      transition: reduceMotion ? { duration: 0 } : { duration: 0.32, ease: [0.4, 0, 1, 1] },
    });
    await Promise.all([flyBack, fadeOut, headerFadeOut, metaFadeOut]);
    onClose();
  }, [backdropControls, clearPressTimer, controls, headerControls, metaAreaControls, getCurrentOriginRect, initialOriginRect, onClose, reduceMotion]);

  // Keep ref updated with latest dismissToOriginAndClose
  useEffect(() => {
    dismissToOriginAndCloseRef.current = dismissToOriginAndClose;
  }, [dismissToOriginAndClose]);

  const snapBackToTarget = useCallback(async () => {
    setPhase('flying-in');
    clearPressTimer();
    await controls.start({
      x: targetRect.x,
      y: targetRect.y,
      width: targetRect.width,
      height: targetRect.height,
      scale: 1,
      transition: reduceMotion
        ? { duration: 0 }
        : { type: 'spring', stiffness: 650, damping: 48, mass: 0.7 },
    });
    setPhase('selected');
  }, [clearPressTimer, controls, reduceMotion, targetRect]);

  const bounceX = useCallback(
    async (dir: 'left' | 'right') => {
      setPhase('swiping');
      clearPressTimer();
      const dx = dir === 'left' ? -24 : 24;
      await controls.start({
        x: targetRect.x + dx,
        transition: reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 700, damping: 24, mass: 0.35 },
      });
      await controls.start({
        x: targetRect.x,
        transition: reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 650, damping: 36, mass: 0.45 },
      });
      setPhase('selected');
    },
    [clearPressTimer, controls, reduceMotion, targetRect.x]
  );

  const swipeToIndex = useCallback(
    async (nextIndex: number) => {
      if (nextIndex < 0 || nextIndex >= posts.length) return;
      // Get fresh origin rects from DOM
      const outRect = getCurrentOriginRect() ?? initialOriginRect;
      const inRect = getOriginRectForIndex(nextIndex);
      if (!outRect || !inRect) {
        // Fallback: just swap and snap
        setSelectedIndex(nextIndex);
        await snapBackToTarget();
        return;
      }

      setPhase('swiping');
      clearPressTimer();

      // Capture both posts for the transition
      const currentPost = posts[selectedIndex];
      const nextPost = posts[nextIndex];

      // Set up the OUTGOING element at center (where it currently is)
      setOutgoingPost({ 
        post: currentPost, 
        rect: outRect,
        startX: targetRect.x,
        startY: targetRect.y,
        startWidth: targetRect.width,
        startHeight: targetRect.height,
      });
      outgoingControls.set({
        x: targetRect.x,
        y: targetRect.y,
        width: targetRect.width,
        height: targetRect.height,
        scale: 1,
        opacity: 1,
      });

      // Set up the INCOMING element at its grid card position
      setIncomingPost({
        post: nextPost,
        rect: inRect,
        startX: inRect.left,
        startY: inRect.top,
        startWidth: inRect.width,
        startHeight: inRect.height,
      });
      incomingControls.set({
        x: inRect.left,
        y: inRect.top,
        width: inRect.width,
        height: inRect.height,
        scale: 1,
        opacity: 1,
      });

      // Run BOTH animations simultaneously:
      // - Outgoing flies from center back to its grid position
      // - Incoming flies from its grid position to center
      await Promise.all([
        outgoingControls.start({
          x: outRect.left,
          y: outRect.top,
          width: outRect.width,
          height: outRect.height,
          transition: reduceMotion
            ? { duration: 0 }
            : { type: 'spring', stiffness: 450, damping: 38, mass: 0.7 },
        }),
        incomingControls.start({
          x: targetRect.x,
          y: targetRect.y,
          width: targetRect.width,
          height: targetRect.height,
          transition: reduceMotion
            ? { duration: 0 }
            : { type: 'spring', stiffness: 450, damping: 38, mass: 0.7 },
        }),
      ]);

      // Animation complete - now update state and position main element at center
      setSelectedIndex(nextIndex);
      controls.set({
        x: targetRect.x,
        y: targetRect.y,
        width: targetRect.width,
        height: targetRect.height,
        scale: 1,
      });
      
      // Trigger content crossfade by updating keys
      setHeaderContentKey((k) => k + 1);
      setMetaContentKey((k) => k + 1);
      
      // Clear transition elements
      setOutgoingPost(null);
      setIncomingPost(null);
      setPhase('selected');
    },
    [
      clearPressTimer,
      controls,
      outgoingControls,
      incomingControls,
      getCurrentOriginRect,
      getOriginRectForIndex,
      initialOriginRect,
      posts,
      selectedIndex,
      reduceMotion,
      setSelectedIndex,
      snapBackToTarget,
      targetRect,
    ]
  );

  // ESC to close, arrow keys to navigate
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showMoreMenu) {
          setShowMoreMenu(false);
          closeSubPanelImmediate();
        } else if (!showCommentsOverlay) {
          void dismissToOriginAndClose();
        }
      }

      // Arrow key navigation (only when interactive and no overlays open)
      if (phase === 'selected' && !showMoreMenu && !showCommentsOverlay) {
        if (e.key === 'ArrowRight') {
          e.preventDefault();
          if (selectedIndex < posts.length - 1) {
            void swipeToIndex(selectedIndex + 1);
          } else {
            void bounceX('left');
          }
        } else if (e.key === 'ArrowLeft') {
          e.preventDefault();
          if (selectedIndex > 0) {
            void swipeToIndex(selectedIndex - 1);
          } else {
            void bounceX('right');
          }
        }
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [
    closeSubPanelImmediate,
    dismissToOriginAndClose,
    showCommentsOverlay,
    showMoreMenu,
    phase,
    selectedIndex,
    posts.length,
    swipeToIndex,
    bounceX,
  ]);

  // Close menu when clicking outside
  useEffect(() => {
    if (!showMoreMenu) return;
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      if (moreMenuRef.current && !moreMenuRef.current.contains(target) &&
          moreButtonRef.current && !moreButtonRef.current.contains(target)) {
        setShowMoreMenu(false);
        closeSubPanelImmediate();
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [closeSubPanelImmediate, showMoreMenu]);

  if (!portalEl || !post) return null;
  
  // Compute initial position for the motion.div
  const origin = initialOriginRect;
  const initialX = origin?.left ?? targetRect.x;
  const initialY = origin?.top ?? targetRect.y;
  const initialW = origin?.width ?? targetRect.width;
  const initialH = origin?.height ?? targetRect.height;

  const isInteractive = phase === 'selected';
  const totalReactions = widgetData ? Object.values(widgetData.reactions.totals).reduce((sum, count) => sum + count, 0) : 0;
  const totalComments = widgetData?.comments.length || 0;

  return createPortal(
    <div style={{ ...overlayStyles, bottom: hasPlayerBar ? PLAYER_BAR_HEIGHT : 0 }} role="dialog" aria-modal="true">
      <motion.div
        style={{
          ...backdropStyles,
          bottom: hasPlayerBar ? PLAYER_BAR_HEIGHT : 0,
        }}
        initial={{ opacity: 0 }}
        animate={backdropControls}
        onMouseDown={(e) => {
          if (!isInteractive) return;
          e.preventDefault();
          void dismissToOriginAndClose();
        }}
        onTouchStart={(e) => {
          if (!isInteractive) return;
          e.preventDefault();
          void dismissToOriginAndClose();
        }}
      />

      {/* Post Header */}
      <motion.div
        aria-label="post-header"
        role="banner"
        style={{
          position: 'fixed',
          left: 0,
          top: 0,
          width: 384,
          height: POST_HEADER_HEIGHT,
          background: '#000',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 16px',
          zIndex: 20001,
          pointerEvents: 'auto',
        }}
        initial={{ x: headerPosition.x, y: headerPosition.y - POST_HEADER_HEIGHT, opacity: 0 }}
        animate={headerControls}
      >
        <AnimatePresence mode="wait">
          <motion.div
            key={headerContentKey}
            style={{ ...postHeaderLeftStyles, pointerEvents: 'auto' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: reduceMotion ? 0 : 0.2 }}
          >
            {post.owner?.public_sqid ? (
              <div
                role="button"
                tabIndex={0}
                style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', pointerEvents: 'auto' }}
                onClick={(e) => {
                  e.stopPropagation();
                  e.preventDefault();
                  if (post.owner?.public_sqid) {
                    router.push(`/u/${post.owner.public_sqid}`);
                  }
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.stopPropagation();
                    e.preventDefault();
                    if (post.owner?.public_sqid) {
                      router.push(`/u/${post.owner.public_sqid}`);
                    }
                  }
                }}
              >
                {post.owner?.avatar_url ? (
                  <img
                    src={post.owner.avatar_url.startsWith('http') ? post.owner.avatar_url : `${typeof window !== 'undefined' ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin) : ''}${post.owner.avatar_url}`}
                    alt={post.owner.handle || 'Author'}
                    style={postAuthorAvatarStyles}
                  />
                ) : (
                  <div style={{ ...postAuthorAvatarStyles, background: '#1a1a24', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" style={{ color: '#6a6a80' }}>
                      <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                    </svg>
                  </div>
                )}
                {post.owner?.handle && (
                  <span style={postAuthorHandleStyles}>{post.owner.handle}</span>
                )}
              </div>
            ) : (
              <>
                {post.owner?.avatar_url ? (
                  <img
                    src={post.owner.avatar_url.startsWith('http') ? post.owner.avatar_url : `${typeof window !== 'undefined' ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin) : ''}${post.owner.avatar_url}`}
                    alt={post.owner.handle || 'Author'}
                    style={postAuthorAvatarStyles}
                  />
                ) : (
                  <div style={{ ...postAuthorAvatarStyles, background: '#1a1a24', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" style={{ color: '#6a6a80' }}>
                      <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                    </svg>
                  </div>
                )}
                {post.owner?.handle && (
                  <span style={postAuthorHandleStyles}>{post.owner.handle}</span>
                )}
              </>
            )}
          </motion.div>
        </AnimatePresence>
        <AnimatePresence mode="wait">
          <motion.div
            key={headerContentKey}
            style={postHeaderRightStyles}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: reduceMotion ? 0 : 0.2 }}
          >
            {!loadingWidget && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: reduceMotion ? 0 : 0.2 }}
                style={{ display: 'flex', alignItems: 'center', gap: '12px' }}
              >
                <div style={postReactionCountStyles}>
                  <span style={{ fontSize: '16px', marginRight: '-2px' }}>⚡</span>
                  <span>{totalReactions}</span>
                </div>
                <div style={postCommentCountStyles}>
                  <span style={{ fontSize: '16px', marginRight: '-2px' }}>💬</span>
                  <span>{totalComments}</span>
                </div>
                <div style={postViewCountStyles}>
                  <span style={{ fontSize: '16px', marginRight: '-2px' }}>👁</span>
                  <span>{widgetData?.views_count ?? 0}</span>
                </div>
                <button
                  ref={moreButtonRef}
                  style={moreButtonStyles}
                  onClick={(e) => {
                    e.stopPropagation();
                    if (!showMoreMenu && moreButtonRef.current) {
                      const rect = moreButtonRef.current.getBoundingClientRect();
                      const viewportWidth = window.innerWidth;
                      const menuWidth = 200; // minWidth from moreMenuStyles
                      const margin = 8;

                      // Position menu below the button, aligned to the right edge of the button
                      // but ensure it stays within viewport
                      let rightPos = viewportWidth - rect.right;
                      if (rect.right - menuWidth < margin) {
                        // Menu would overflow left, align to left edge instead
                        rightPos = viewportWidth - menuWidth - margin;
                      }

                      setMenuPosition({
                        top: rect.bottom + 4,
                        right: Math.max(margin, rightPos),
                      });
                    }
                    setShowMoreMenu(!showMoreMenu);
                  }}
                  aria-label="More options"
                >
                  &#8942;
                </button>
              </motion.div>
            )}
          </motion.div>
        </AnimatePresence>
      </motion.div>

      {/* More Menu Overlay */}
      {showMoreMenu && (
        <div
          style={moreMenuOverlayStyles}
          onClick={(e) => {
            e.stopPropagation();
            setShowMoreMenu(false);
            closeSubPanelImmediate();
          }}
        >
          <div
            ref={moreMenuRef}
            style={{
              ...moreMenuStyles,
              right: menuPosition?.right ?? 16,
              top: menuPosition?.top ?? (POST_HEADER_HEIGHT + 4),
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Disabled items */}
            <button style={menuItemDisabledStyles} disabled>
              Use as profile photo
            </button>
            <button style={menuItemDisabledStyles} disabled>
              Add to my favorites
            </button>

            {/* Enabled items */}
            <button
              style={menuItemStyles}
              onClick={handleEditInPiskel}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              Edit in Piskel
            </button>
            {/* Edit in Pixelc: enabled for all supported formats */}
            {['png', 'webp', 'gif', 'bmp'].includes((post.files?.find(f => f.is_native)?.format || '').toLowerCase()) ? (
              <button
                style={menuItemStyles}
                onClick={handleEditInPixelc}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                Edit in Pixelc
              </button>
            ) : (
              <button style={menuItemDisabledStyles} disabled>
                Edit in Pixelc
              </button>
            )}

            <div style={{ height: 1, background: 'rgba(255,255,255,0.1)', margin: '4px 0' }} />

            <button
              style={menuItemStyles}
              onClick={handleShareUpscaled}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              Share upscaled
            </button>
            <button
              style={menuItemStyles}
              onClick={handleShareNative}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              Share native size
            </button>

            <div style={{ height: 1, background: 'rgba(255,255,255,0.1)', margin: '4px 0' }} />

            <button
              style={menuItemStyles}
              onClick={handleDownloadUpscaled}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              Download upscaled
            </button>
            <div
              style={{ position: 'relative' }}
              onMouseEnter={() => cancelSubPanelClose(true)}
              onMouseLeave={() => closeSubPanelDelayed()}
            >
              <button
                style={{
                  ...menuItemStyles,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  if (showFormatSubPanel) {
                    closeSubPanelImmediate();
                  } else {
                    cancelSubPanelClose(true);
                  }
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
              >
                <span>Download alternative format</span>
                <span style={{ marginLeft: '8px' }}>{showFormatSubPanel ? '▼' : '◀'}</span>
              </button>
              {showFormatSubPanel && (() => {
                const alternativeFormats = (post.files || [])
                  .filter(f => !f.is_native)
                  .map(f => f.format);
                return (
                  <div style={subPanelStyles}>
                    {alternativeFormats.length > 0 ? (
                      alternativeFormats.map(format => (
                        <button
                          key={format}
                          style={menuItemStyles}
                          onClick={() => handleDownloadFormat(format)}
                          onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
                          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                        >
                          {format.toUpperCase()}
                        </button>
                      ))
                    ) : (
                      <div style={{ ...menuItemStyles, color: '#6a6a80', cursor: 'default' }}>
                        No alternative formats
                      </div>
                    )}
                  </div>
                );
              })()}
            </div>
            <button
              style={menuItemStyles}
              onClick={handleDownloadNative}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255,255,255,0.08)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
            >
              Download native format
            </button>
          </div>
        </div>
      )}

      {/* Outgoing artwork during swipe transition (flies back to grid) */}
      {outgoingPost && (
        <motion.div
          style={{
            ...artworkShellStyles,
            boxShadow: '0 18px 48px rgba(0,0,0,0.35)',
            pointerEvents: 'none',
          }}
          initial={{
            x: outgoingPost.startX,
            y: outgoingPost.startY,
            width: outgoingPost.startWidth,
            height: outgoingPost.startHeight,
            scale: 1,
            opacity: 1,
          }}
          animate={outgoingControls}
        >
          <div style={artworkClipStyles}>
            <img
              src={outgoingPost.post.art_url}
              alt={outgoingPost.post.title}
              draggable={false}
              style={artworkImageStyles}
            />
          </div>
        </motion.div>
      )}

      {/* Incoming artwork during swipe transition (flies from grid to center) */}
      {incomingPost && (
        <motion.div
          style={{
            ...artworkShellStyles,
            boxShadow: '0 18px 48px rgba(0,0,0,0.35)',
            pointerEvents: 'none',
          }}
          initial={{
            x: incomingPost.startX,
            y: incomingPost.startY,
            width: incomingPost.startWidth,
            height: incomingPost.startHeight,
            scale: 1,
            opacity: 1,
          }}
          animate={incomingControls}
        >
          <div style={artworkClipStyles}>
            <img
              src={incomingPost.post.art_url}
              alt={incomingPost.post.title}
              draggable={false}
              style={artworkImageStyles}
            />
          </div>
        </motion.div>
      )}

      {/* Main artwork (current selection) - hidden during swipe transitions */}
      <motion.div
        style={{
          ...artworkShellStyles,
          scale: pressing ? 0.985 : 1,
          boxShadow: '0 18px 48px rgba(0,0,0,0.35)',
          // Hide during swipe transitions when outgoing/incoming are visible
          opacity: (outgoingPost || incomingPost) ? 0 : 1,
          pointerEvents: (outgoingPost || incomingPost) ? 'none' : 'auto',
        }}
        initial={{
          x: initialX,
          y: initialY,
          width: initialW,
          height: initialH,
          scale: 1,
        }}
        animate={controls}
        drag={isInteractive}
        dragMomentum={false}
        dragElastic={0.12}
        onPointerDown={(e) => {
          if (!isInteractive) return;
          pressStartRef.current = { x: e.clientX, y: e.clientY, time: Date.now() };
          setPressing(true);
          pressTimerRef.current = window.setTimeout(() => {
            pressTimerRef.current = null;
            setLikeBurstKey((k) => k + 1);
            if (navigator?.vibrate) navigator.vibrate(18);
            // Long press on artwork shows like animation
            void handleReactionClick('👍');
          }, 420);
        }}
        onPointerMove={(e) => {
          const start = pressStartRef.current;
          if (!start) return;
          const dx = e.clientX - start.x;
          const dy = e.clientY - start.y;
          if (Math.hypot(dx, dy) > 10) clearPressTimer();
        }}
        onPointerUp={() => {
          clearPressTimer();
        }}
        onPointerCancel={() => {
          clearPressTimer();
        }}
        onDragStart={() => {
          clearPressTimer();
        }}
        onDragEnd={async (_e, info) => {
          if (!isInteractive) return;
          // Capture press start time before clearing (clearPressTimer nulls it)
          const pressStart = pressStartRef.current;
          clearPressTimer();
          const dx = info.offset.x;
          const dy = info.offset.y;
          const vx = info.velocity.x;
          const vy = info.velocity.y;

          const absX = Math.abs(dx);
          const absY = Math.abs(dy);

          // Detect tap: minimal movement and short duration
          const duration = pressStart ? Date.now() - pressStart.time : Infinity;
          const isTap = absX < 10 && absY < 10 && duration < 300;
          if (isTap) {
            onNavigateToPost(selectedIndex);
            return;
          }

          const isHorizontal = absX > absY * 1.25 && absX > 70;
          const isUp = dy < -90 || (vy < -650 && dy < -35);
          const isDown = dy > 90 || (vy > 650 && dy > 35);

          if (isHorizontal) {
            if (dx < 0) {
              if (selectedIndex >= posts.length - 1) {
                await bounceX('left');
              } else {
                await swipeToIndex(selectedIndex + 1);
              }
              return;
            }
            if (selectedIndex <= 0) {
              await bounceX('right');
            } else {
              await swipeToIndex(selectedIndex - 1);
            }
            return;
          }

          if (isUp || isDown) {
            await dismissToOriginAndClose();
            return;
          }

          await snapBackToTarget();
        }}
        onClick={(e) => {
          e.stopPropagation();
          if (!isInteractive) return;
          onNavigateToPost(selectedIndex);
        }}
      >
        <div style={artworkClipStyles}>
          <img
            src={post.art_url}
            alt={post.title}
            draggable={false}
            style={artworkImageStyles}
          />

          {likeBurstKey > 0 && (
            <motion.div
              key={likeBurstKey}
              style={likeBurstStyles}
              initial={{ opacity: 0, scale: 0.6, y: 16 }}
              animate={{
                opacity: 1,
                scale: 1,
                y: 0,
                transition: reduceMotion
                  ? { duration: 0 }
                  : { type: 'spring', stiffness: 640, damping: 32, mass: 0.35 },
              }}
              exit={{ opacity: 0 }}
            >
              👍
            </motion.div>
          )}
        </div>
      </motion.div>

      {/* Artwork Meta Area */}
      <motion.div
        style={metaAreaStyles}
        initial={{ x: metaAreaPosition.x, y: metaAreaPosition.y, opacity: 0 }}
        animate={metaAreaControls}
      >
        <AnimatePresence mode="wait">
          <motion.div
            key={metaContentKey}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: reduceMotion ? 0 : 0.2 }}
          >
            {/* Title Row */}
            <div style={titleRowStyles}>{post.title}</div>

            {/* Technical Info Row */}
            <div style={technicalInfoRowStyles}>
              {formatDateTime(post.created_at)}
              <span style={{ margin: '0 8px', opacity: 0.5 }}>&bull;</span>
              <span style={post.frame_count > 256 ? { color: '#ff8080' } : undefined}>
                {post.frame_count}
              </span>
              &times;({post.width}&times;{post.height})
              <span style={{ margin: '0 8px', opacity: 0.5 }}>&bull;</span>
              {formatFileSizeCompact(post.files?.find(f => f.is_native)?.file_bytes || 0)} {(post.files?.find(f => f.is_native)?.format || 'png').toUpperCase()}
            </div>

            {/* Reactions Row */}
            <div style={reactionsRowStyles}>
              {EMOJI_OPTIONS.map(emoji => {
                const count = widgetData?.reactions.totals[emoji] || 0;
                const isActive = widgetData?.reactions.mine.includes(emoji) || false;
                return (
                  <button
                    key={emoji}
                    style={{
                      ...reactionButtonStyles,
                      borderColor: isActive ? '#00d4ff' : 'transparent',
                      background: isActive ? 'rgba(0, 212, 255, 0.15)' : 'transparent',
                    }}
                    onClick={(e) => {
                      e.stopPropagation();
                      void handleReactionClick(emoji);
                    }}
                    disabled={loadingWidget}
                  >
                    {emoji}
                    {count > 0 && <span style={reactionBadgeStyles}>{count}</span>}
                  </button>
                );
              })}
              <button
                style={commentButtonStyles}
                onClick={(e) => {
                  e.stopPropagation();
                  setShowCommentsOverlay(true);
                }}
              >
                <span>💬</span>
                {totalComments > 0 && <span style={{ fontSize: '12px', color: '#00d4ff' }}>{totalComments}</span>}
              </button>
            </div>

            {/* Description Area */}
            {post.description && (
              <div style={descriptionAreaStyles}>{post.description}</div>
            )}
          </motion.div>
        </AnimatePresence>
      </motion.div>

      {/* Comments Overlay */}
      <SPOCommentsOverlay
        postId={post.id}
        isOpen={showCommentsOverlay}
        onClose={() => setShowCommentsOverlay(false)}
        currentUserId={currentUserId}
        isModerator={isModerator}
        initialComments={widgetData?.comments || []}
      />
    </div>,
    portalEl
  );
}
