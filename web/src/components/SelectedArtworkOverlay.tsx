import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion, useAnimationControls, useReducedMotion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/router';
import { authenticatedFetch, getAccessToken } from '../lib/api';
import { PLAYER_BAR_HEIGHT } from './PlayerBarDynamic';

type Rect = { left: number; top: number; width: number; height: number };

export interface SelectedArtworkOverlayPost {
  id: number;
  public_sqid: string;
  title: string;
  description?: string;
  art_url: string;
  canvas: string; // e.g. "64x64"
  owner?: {
    handle: string;
    avatar_url?: string | null;
    public_sqid?: string;
  };
}

export interface SelectedArtworkOverlayProps {
  posts: SelectedArtworkOverlayPost[];
  selectedIndex: number;
  setSelectedIndex: (idx: number) => void;
  onClose: () => void; // parent should set selectedIndex = null
  onNavigateToPost: (idx: number) => void; // parent should set nav context + router.push
  getOriginRectForIndex: (idx: number) => Rect | null;
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

async function fetchReactionMine(postId: number): Promise<Set<string>> {
  const url = `/api/post/${postId}/reactions`;
  const hasToken = !!getAccessToken();
  const resp = hasToken
    ? await authenticatedFetch(url.startsWith('http') ? url : `${window.location.origin}${url}`)
    : await fetch(url, { credentials: 'include' });
  if (!resp.ok) return new Set();
  const data = await resp.json().catch(() => null);
  const mine = Array.isArray(data?.mine) ? data.mine : [];
  return new Set(mine);
}

async function fetchReactionsCount(postId: number): Promise<number> {
  const url = `/api/post/${postId}/reactions`;
  const hasToken = !!getAccessToken();
  try {
    const resp = hasToken
      ? await authenticatedFetch(url.startsWith('http') ? url : `${window.location.origin}${url}`)
      : await fetch(url, { credentials: 'include' });
    if (!resp.ok) return 0;
    const data = await resp.json().catch(() => null);
    const totals = data?.totals || {};
    // Sum all reaction counts
    return Object.values(totals).reduce<number>((sum, count) => sum + (typeof count === 'number' ? count : 0), 0);
  } catch {
    return 0;
  }
}

async function fetchCommentsCount(postId: number): Promise<number> {
  const url = `/api/post/${postId}/comments`;
  const hasToken = !!getAccessToken();
  try {
    const resp = hasToken
      ? await authenticatedFetch(url.startsWith('http') ? url : `${window.location.origin}${url}`)
      : await fetch(url, { credentials: 'include' });
    if (!resp.ok) return 0;
    const data = await resp.json().catch(() => null);
    const items = Array.isArray(data?.items) ? data.items : [];
    return items.length;
  } catch {
    return 0;
  }
}

async function setThumbsUp(postId: number, shouldLike: boolean): Promise<void> {
  const emoji = '👍';
  const encoded = encodeURIComponent(emoji);
  const url = `/api/post/${postId}/reactions/${encoded}`;
  const method = shouldLike ? 'PUT' : 'DELETE';
  const hasToken = !!getAccessToken();
  const resp = hasToken
    ? await authenticatedFetch(url.startsWith('http') ? url : `${window.location.origin}${url}`, { method })
    : await fetch(url, { method, credentials: 'include' });
  if (!resp.ok) {
    const txt = await resp.text().catch(() => '');
    throw new Error(`Failed to ${shouldLike ? 'add' : 'remove'} reaction: ${resp.status} ${txt}`.trim());
  }
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
  overflow: 'visible', // Must be visible to show post-footer below artwork
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
  transform: 'translate(-50%, -50%)',
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

const postFooterStyles: React.CSSProperties = {
  position: 'absolute',
  bottom: -64,
  left: 0,
  right: 0,
  height: 64,
  background: '#000',
  display: 'flex',
  flexDirection: 'column',
  pointerEvents: 'none',
};

const postFooterTextStyles: React.CSSProperties = {
  fontFamily: "'Noto Sans', 'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
  fontSize: '14px',
  fontWeight: 500,
  color: '#ffffff',
  height: 32,
  display: 'flex',
  alignItems: 'center',
  paddingLeft: 16,
  paddingRight: 16,
  whiteSpace: 'nowrap',
  overflow: 'hidden',
  textOverflow: 'ellipsis',
};

type AnimationPhase = 'mounting' | 'flying-in' | 'selected' | 'flying-out' | 'swiping';

export default function SelectedArtworkOverlay({
  posts,
  selectedIndex,
  setSelectedIndex,
  onClose,
  onNavigateToPost,
  getOriginRectForIndex,
}: SelectedArtworkOverlayProps) {
  const reduceMotion = useReducedMotion();
  const router = useRouter();
  const controls = useAnimationControls();
  const outgoingControls = useAnimationControls();
  const incomingControls = useAnimationControls();
  const backdropControls = useAnimationControls();
  const [portalEl, setPortalEl] = useState<HTMLElement | null>(null);
  const [phase, setPhase] = useState<AnimationPhase>('mounting');
  const [hasPlayerBar, setHasPlayerBar] = useState(false);
  const [pressing, setPressing] = useState(false);
  const [liked, setLiked] = useState(false);
  const [likeBurstKey, setLikeBurstKey] = useState(0);
  const [targetRect, setTargetRect] = useState(() => computeSelectedTargetRect());
  const [headerPosition, setHeaderPosition] = useState(() => computePostHeaderPosition());
  const [countsState, setCountsState] = useState<{
    postId: number | null;
    reactions: number | null;
    comments: number | null;
    status: 'idle' | 'loading' | 'ready';
  }>({ postId: null, reactions: null, comments: null, status: 'idle' });
  const countsCacheRef = useRef<Map<number, { reactions: number; comments: number }>>(new Map());
  const headerControls = useAnimationControls();
  const footerControls = useAnimationControls();
  const [headerContentKey, setHeaderContentKey] = useState(0);
  
  // Store the initial origin rect SYNCHRONOUSLY on first render to avoid timing issues
  // Using a ref to capture it immediately, then a state for re-renders
  const initialOriginRectRef = useRef<Rect | null>(null);
  if (initialOriginRectRef.current === null) {
    initialOriginRectRef.current = getOriginRectForIndex(selectedIndex);
  }
  const [initialOriginRect] = useState<Rect | null>(() => initialOriginRectRef.current);
  
  // Track outgoing artwork during swipe transitions
  const [outgoingPost, setOutgoingPost] = useState<{ 
    post: SelectedArtworkOverlayPost; 
    rect: Rect;
    startX: number;
    startY: number;
    startWidth: number;
    startHeight: number;
  } | null>(null);
  
  // Track incoming artwork during swipe transitions (separate from main to avoid React re-render issues)
  const [incomingPost, setIncomingPost] = useState<{ 
    post: SelectedArtworkOverlayPost; 
    rect: Rect;
    startX: number;
    startY: number;
    startWidth: number;
    startHeight: number;
  } | null>(null);

  const pressTimerRef = useRef<number | null>(null);
  const pressStartRef = useRef<{ x: number; y: number; time: number } | null>(null);
  const likeInFlightRef = useRef(false);

  // For History API back button handling
  const closedByPopstateRef = useRef(false);
  // Track when we're navigating away (so we don't call history.back() in cleanup)
  const navigatingAwayRef = useRef(false);
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

  // Create portal root and lock scroll
  useEffect(() => {
    if (typeof document === 'undefined') return;
    const el = document.createElement('div');
    el.setAttribute('data-selected-artwork-overlay', 'true');
    document.body.appendChild(el);
    setPortalEl(el);

    const prevOverflow = document.body.style.overflow;
    const prevTouchAction = document.body.style.touchAction as string;
    document.body.style.overflow = 'hidden';
    document.body.style.touchAction = 'none';

    return () => {
      document.body.style.overflow = prevOverflow;
      document.body.style.touchAction = prevTouchAction ?? '';
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
      setTargetRect(next);
      setHeaderPosition(nextHeaderPos);
      if (phase !== 'selected') return;
      controls.start({
        x: next.x,
        y: next.y,
        transition: reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 520, damping: 44 },
      });
      headerControls.start({
        x: nextHeaderPos.x,
        y: nextHeaderPos.y,
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
  }, [controls, headerControls, phase, reduceMotion]);

  // Fetch like state (auth or anonymous)
  useEffect(() => {
    const postId = post?.id;
    if (!postId) return;
    let cancelled = false;
    (async () => {
      try {
        const mine = await fetchReactionMine(postId);
        if (cancelled) return;
        setLiked(mine.has('👍'));
      } catch {
        // ignore
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [post?.id]);

  // Fetch reactions and comments counts
  useEffect(() => {
    const postId = post?.id;
    if (!postId) return;
    let cancelled = false;
    (async () => {
      try {
        const cached = countsCacheRef.current.get(postId);
        if (cached) {
          setCountsState({ postId, reactions: cached.reactions, comments: cached.comments, status: 'ready' });
          return;
        }

        // Important UX: when the selected post changes, the counts should disappear immediately
        // and only re-appear once the UPDATED values have been fetched.
        setCountsState({ postId, reactions: null, comments: null, status: 'loading' });

        const [reactions, comments] = await Promise.all([fetchReactionsCount(postId), fetchCommentsCount(postId)]);
        if (cancelled) return;
        countsCacheRef.current.set(postId, { reactions, comments });
        setCountsState({ postId, reactions, comments, status: 'ready' });
      } catch {
        // ignore (fetch helpers already return 0 on failure)
        if (cancelled) return;
        setCountsState({ postId, reactions: 0, comments: 0, status: 'ready' });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [post?.id]);

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

      // Animate header sliding in from above viewport
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
          : { type: 'spring', stiffness: 400, damping: 35, mass: 0.8 },
      });

      // Animate footer sliding down and fading in
      footerControls.set({
        y: -64,
        opacity: 0,
      });
      void footerControls.start({
        y: 0,
        opacity: 1,
        transition: reduceMotion
          ? { duration: 0 }
          : { type: 'spring', stiffness: 400, damping: 35, mass: 0.8 },
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
  }, [backdropControls, controls, footerControls, headerControls, portalEl, post, phase, initialOriginRect, reduceMotion, targetRect]);

  const triggerLikeToggle = useCallback(async () => {
    if (!post) return;
    if (likeInFlightRef.current) return;
    likeInFlightRef.current = true;
    try {
      const next = !liked;
      setLiked(next);
      setLikeBurstKey((k) => k + 1);
      if (navigator?.vibrate) navigator.vibrate(18);
      await setThumbsUp(post.id, next);

      // Only update counts once the server has confirmed the write.
      // Do an immediate +1/-1 for responsiveness, then re-sync from server to be exact.
      setCountsState((prev) => {
        if (prev.postId !== post.id || prev.status !== 'ready') return prev;
        const nextReactions = Math.max(0, (prev.reactions ?? 0) + (next ? 1 : -1));
        const nextState = { ...prev, reactions: nextReactions };
        countsCacheRef.current.set(post.id, { reactions: nextReactions, comments: prev.comments ?? 0 });
        return nextState;
      });

      // Re-sync totals in the background (accounts for other reaction types).
      void (async () => {
        try {
          const reactions = await fetchReactionsCount(post.id);
          setCountsState((prev) => {
            if (prev.postId !== post.id || prev.status !== 'ready') return prev;
            countsCacheRef.current.set(post.id, { reactions, comments: prev.comments ?? 0 });
            return { ...prev, reactions };
          });
        } catch {
          // ignore
        }
      })();
    } finally {
      likeInFlightRef.current = false;
    }
  }, [liked, post]);

  const dismissToOriginAndClose = useCallback(async () => {
    // Get fresh origin rect from DOM to ensure precision after any scroll/resize
    const origin = getCurrentOriginRect() ?? initialOriginRect;
    if (!origin) {
      // Still fade the backdrop out to avoid a hard cut
      await Promise.all([
        backdropControls.start({
          opacity: 0,
          transition: reduceMotion ? { duration: 0 } : { duration: 0.32, ease: [0.4, 0, 1, 1] },
        }),
        headerControls.start({
          x: headerPosition.x,
          y: headerPosition.y - POST_HEADER_HEIGHT,
          opacity: 0,
          transition: reduceMotion ? { duration: 0 } : { duration: 0.32, ease: [0.4, 0, 1, 1] },
        }),
        footerControls.start({
          y: -64,
          opacity: 0,
          transition: reduceMotion ? { duration: 0 } : { duration: 0.32, ease: [0.4, 0, 1, 1] },
        }),
      ]);
      onClose();
      return;
    }
    setPhase('flying-out');
    clearPressTimer();
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
    const headerSlideOut = headerControls.start({
      x: headerPosition.x,
      y: headerPosition.y - POST_HEADER_HEIGHT,
      opacity: 0,
      transition: reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 500, damping: 40, mass: 0.8 },
    });
    const footerSlideUp = footerControls.start({
      y: -64,
      opacity: 0,
      transition: reduceMotion ? { duration: 0 } : { type: 'spring', stiffness: 500, damping: 40, mass: 0.8 },
    });
    await Promise.all([flyBack, fadeOut, headerSlideOut, footerSlideUp]);
    onClose();
  }, [backdropControls, clearPressTimer, controls, footerControls, getCurrentOriginRect, headerControls, headerPosition, initialOriginRect, onClose, reduceMotion]);

  // Keep ref updated with latest dismissToOriginAndClose
  useEffect(() => {
    dismissToOriginAndCloseRef.current = dismissToOriginAndClose;
  }, [dismissToOriginAndClose]);

  // Handle browser back button (Android back gesture, etc.)
  useEffect(() => {
    if (typeof window === 'undefined') return;

    // Push a history state when overlay opens
    history.pushState({ overlayOpen: true }, '');

    const handlePopstate = () => {
      // Back button was pressed - close the overlay
      closedByPopstateRef.current = true;
      void dismissToOriginAndCloseRef.current();
    };

    window.addEventListener('popstate', handlePopstate);

    return () => {
      window.removeEventListener('popstate', handlePopstate);
      // If we're unmounting but NOT due to popstate or navigation away,
      // we need to clean up the history entry we pushed
      if (!closedByPopstateRef.current && !navigatingAwayRef.current) {
        history.back();
      }
    };
  }, []);

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
      // Header stays in place (no slide out/in) - contents will crossfade
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
      
      // Trigger header content crossfade by updating key
      setHeaderContentKey((k) => k + 1);
      
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

  // ESC to close
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') void dismissToOriginAndClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [dismissToOriginAndClose]);

  if (!portalEl || !post) return null;
  
  // Compute initial position for the motion.div
  const origin = initialOriginRect;
  const initialX = origin?.left ?? targetRect.x;
  const initialY = origin?.top ?? targetRect.y;
  const initialW = origin?.width ?? targetRect.width;
  const initialH = origin?.height ?? targetRect.height;

  const isInteractive = phase === 'selected';
  const countsForPost =
    post && countsState.postId === post.id && countsState.status === 'ready'
      ? { reactions: countsState.reactions ?? 0, comments: countsState.comments ?? 0 }
      : null;

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
          // CRITICAL: Must set left/top to 0 so Framer Motion's x/y transforms 
          // become actual viewport coordinates
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
                    // Set flag so cleanup doesn't call history.back() and cancel navigation
                    navigatingAwayRef.current = true;
                    router.push(`/u/${post.owner.public_sqid}`);
                  }
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.stopPropagation();
                    e.preventDefault();
                    if (post.owner?.public_sqid) {
                      // Set flag so cleanup doesn't call history.back() and cancel navigation
                      navigatingAwayRef.current = true;
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
            {countsForPost && (
              <motion.div
                // When counts become ready, mount and fade in (no "old number then change" flicker).
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: reduceMotion ? 0 : 0.2 }}
                style={{ display: 'flex', alignItems: 'center', gap: '12px' }}
              >
                <div style={postReactionCountStyles}>
                  <span style={{ fontSize: '16px', marginRight: '-2px' }}>⚡</span>
                  <span>{countsForPost.reactions}</span>
                </div>
                <div style={postCommentCountStyles}>
                  <span style={{ fontSize: '16px', marginRight: '-2px' }}>💬</span>
                  <span>{countsForPost.comments}</span>
                </div>
              </motion.div>
            )}
          </motion.div>
        </AnimatePresence>
      </motion.div>

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
            void triggerLikeToggle();
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

          if (isUp) {
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
                y: -8,
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

        {/* Post Footer */}
        <motion.div
          style={postFooterStyles}
          initial={{ y: -64, opacity: 0 }}
          animate={footerControls}
        >
          <AnimatePresence mode="wait">
            <motion.div
              key={headerContentKey}
              style={{ display: 'flex', flexDirection: 'column' }}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: reduceMotion ? 0 : 0.2 }}
            >
              <div style={postFooterTextStyles}>{post.title}</div>
              <div style={postFooterTextStyles}>{post.description || ''}</div>
            </motion.div>
          </AnimatePresence>
        </motion.div>
      </motion.div>
    </div>,
    portalEl
  );
}
