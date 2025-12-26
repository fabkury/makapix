import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { setNavigationContext, NavigationSource } from '../lib/navigation-context';
import SelectedArtworkOverlay from './SelectedArtworkOverlay';
import { usePlayerBarOptional } from '../contexts/PlayerBarContext';

// Global timestamp for synchronized glow animations across all CardGrid instances.
// All glow animations use this as their reference point so they stay in phase.
const GLOW_ANIMATION_DURATION_MS = 16000; // 16s animation cycle
const glowAnimationStartTime = typeof performance !== 'undefined' ? performance.now() : 0;

interface PostOwner {
  id: string;
  handle: string;
  avatar_url?: string | null;
  public_sqid?: string;
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

interface CardGridProps {
  posts: Post[];
  API_BASE_URL: string;
  source: NavigationSource;
  cursor?: string | null;
  prevCursor?: string | null;
}

export default function CardGrid({ posts, API_BASE_URL: _API_BASE_URL, source, cursor = null, prevCursor }: CardGridProps) {
  const router = useRouter();
  const playerBarContext = usePlayerBarOptional();
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);
  const packRef = useRef<HTMLDivElement>(null);
  const artworkAreaRefs = useRef<Map<number, HTMLDivElement | null>>(new Map());

  const TILE_SIZE = 128;
  const MAX_COLUMNS = 8;
  const [columnCount, setColumnCount] = useState(1);
  const [superPostId, setSuperPostId] = useState<number | null>(null);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  
  // Calculate synchronized animation delay so all glows stay in phase.
  // This negative delay "jumps" the animation to the correct position in the cycle.
  const [glowAnimationDelay, setGlowAnimationDelay] = useState('0s');
  useEffect(() => {
    const elapsed = performance.now() - glowAnimationStartTime;
    const delayMs = -(elapsed % GLOW_ANIMATION_DURATION_MS);
    setGlowAnimationDelay(`${delayMs}ms`);
  }, []);

  // Sync selected artwork with PlayerBarContext
  useEffect(() => {
    if (!playerBarContext) return;
    
    if (selectedIndex !== null && selectedIndex >= 0 && selectedIndex < posts.length) {
      const post = posts[selectedIndex];
      playerBarContext.setSelectedArtwork({
        id: post.id,
        public_sqid: post.public_sqid,
        title: post.title,
        art_url: post.art_url,
      });
    } else {
      playerBarContext.setSelectedArtwork(null);
    }
    // Note: We intentionally exclude playerBarContext from dependencies.
    // setSelectedArtwork is stable (from useState), and including the entire
    // context object would cause infinite re-renders.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedIndex, posts]);

  // Choose one "super post" per component mount (surrogate for backend flag).
  useEffect(() => {
    if (superPostId !== null) return;
    if (posts.length === 0) return;
    const chosen = posts[Math.floor(Math.random() * posts.length)];
    if (chosen) setSuperPostId(chosen.id);
  }, [posts, superPostId]);

  // Handle post click - store navigation context before navigating
  const handlePostClick = (postIndex: number) => {
    // Prepare minimal post data for context
    const contextPosts = posts.map((post) => ({
      public_sqid: post.public_sqid,
      id: post.id,
      owner_id: post.owner_id,
    }));

    // Store context in sessionStorage
    setNavigationContext(contextPosts, postIndex, source, cursor, prevCursor);
  };

  const selectedOverlayPosts = useMemo(
    () =>
      posts.map((p) => ({
        id: p.id,
        public_sqid: p.public_sqid,
        title: p.title,
        description: p.description,
        art_url: p.art_url,
        canvas: p.canvas,
        owner: p.owner ? {
          handle: p.owner.handle,
          avatar_url: p.owner.avatar_url,
          public_sqid: p.owner.public_sqid,
        } : undefined,
      })),
    [posts]
  );

  const getOriginRectForIndex = (idx: number) => {
    const post = posts[idx];
    if (!post) return null;
    const el = artworkAreaRefs.current.get(post.id);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    return { left: r.left, top: r.top, width: r.width, height: r.height };
  };

  useLayoutEffect(() => {
    const calculateScales = () => {
      const grid = gridRef.current;
      if (!grid) return;

      const images = grid.querySelectorAll('img.artwork-image');
      images.forEach((imageEl) => {
        const image = imageEl as HTMLImageElement;
        const card = image.closest('a.artwork-card') as HTMLAnchorElement | null;
        const tileSize = card?.classList.contains('super-post') ? TILE_SIZE * 2 : TILE_SIZE;

        const canvasStr = image.getAttribute('data-canvas') || '';
        if (!canvasStr) return;

        const [widthStr, heightStr] = canvasStr.split('x');
        const nativeWidth = parseInt(widthStr, 10);
        const nativeHeight = parseInt(heightStr, 10);

        if (!nativeWidth || !nativeHeight || isNaN(nativeWidth) || isNaN(nativeHeight)) return;

        // Scale the artwork to "cover" the square artwork area (then crop via overflow hidden).
        // IMPORTANT: do NOT force integer upscales here; it can massively overscale near-tile images
        // (e.g. 240x240 into a 256px super tile would jump to 480px if we used ceil()).
        const scale = tileSize / Math.min(nativeWidth, nativeHeight);
        const scaledW = Math.max(1, Math.round(nativeWidth * scale));
        const scaledH = Math.max(1, Math.round(nativeHeight * scale));

        image.style.width = `${scaledW}px`;
        image.style.height = `${scaledH}px`;
        image.style.maxWidth = 'none';
        image.style.maxHeight = 'none';
      });
    };

    const calculateColumns = () => {
      const scroller = scrollContainerRef.current;
      const grid = gridRef.current;
      const pack = packRef.current;
      if (!scroller || !grid || !pack) return;

      const containerWidth = scroller.clientWidth;
      if (containerWidth === 0) return;

      const nextColumnCount = Math.min(
        MAX_COLUMNS,
        Math.max(1, Math.floor(containerWidth / TILE_SIZE))
      );

      if (nextColumnCount !== columnCount) setColumnCount(nextColumnCount);

      const gridWidth = nextColumnCount * TILE_SIZE;
      grid.style.setProperty('--grid-columns', String(nextColumnCount));
      grid.style.setProperty('--grid-width', `${gridWidth}px`);
      pack.style.setProperty('--grid-width', `${gridWidth}px`);

      // Edge glow heights must match the actual rendered border columns,
      // including super posts that span multiple rows/columns.
      const cards = Array.from(grid.querySelectorAll('a.artwork-card')) as HTMLAnchorElement[];
      let leftMaxBottom = 0;
      let rightMaxBottom = 0;
      const eps = 1;
      for (const el of cards) {
        const left = el.offsetLeft;
        const right = el.offsetLeft + el.offsetWidth;
        const bottom = el.offsetTop + el.offsetHeight;
        if (Math.abs(left - 0) <= eps) leftMaxBottom = Math.max(leftMaxBottom, bottom);
        if (Math.abs(right - gridWidth) <= eps) rightMaxBottom = Math.max(rightMaxBottom, bottom);
      }

      pack.style.setProperty('--left-glow-height', `${leftMaxBottom}px`);
      pack.style.setProperty('--right-glow-height', `${rightMaxBottom}px`);

      // Ragged-edge glow for the bottom band when the right side is shorter than the left.
      // The "bottom band" is defined as the vertical span of the tiles that touch the grid bottom.
      // If the bottom-most tile is a super post, the band height becomes 256px.
      let gridMaxBottom = 0;
      for (const el of cards) {
        gridMaxBottom = Math.max(gridMaxBottom, el.offsetTop + el.offsetHeight);
      }

      let bottomBandTop = gridMaxBottom;
      for (const el of cards) {
        const bottom = el.offsetTop + el.offsetHeight;
        if (Math.abs(bottom - gridMaxBottom) <= eps) {
          bottomBandTop = Math.min(bottomBandTop, el.offsetTop);
        }
      }
      if (!isFinite(bottomBandTop) || bottomBandTop === gridMaxBottom) {
        bottomBandTop = Math.max(0, gridMaxBottom - TILE_SIZE);
      }
      const bottomBandHeight = Math.max(TILE_SIZE, gridMaxBottom - bottomBandTop);

      let bottomBandOccupiedRight = 0;
      for (const el of cards) {
        const top = el.offsetTop;
        const bottom = el.offsetTop + el.offsetHeight;
        // intersects bottom band?
        if (bottom > bottomBandTop + eps && top < gridMaxBottom - eps) {
          bottomBandOccupiedRight = Math.max(bottomBandOccupiedRight, el.offsetLeft + el.offsetWidth);
        }
      }

      const hasRaggedRight = bottomBandOccupiedRight < gridWidth - eps;
      pack.style.setProperty('--ragged-glow-left', `${bottomBandOccupiedRight}px`);
      pack.style.setProperty('--ragged-glow-top', `${bottomBandTop}px`);
      pack.style.setProperty('--ragged-glow-height', `${bottomBandHeight}px`);
      pack.style.setProperty('--ragged-glow-opacity', hasRaggedRight ? '0.9' : '0');

      // Add bottom glow to the last C artwork-cards (C = number of columns)
      cards.forEach((el) => el.classList.remove('bottom-glow'));
      const start = Math.max(0, cards.length - nextColumnCount);
      for (let i = start; i < cards.length; i++) {
        cards[i]?.classList.add('bottom-glow');
      }
    };

    const updateLayout = () => {
      calculateColumns();
      calculateScales();
    };

    updateLayout();

    const resizeObserver = new ResizeObserver(() => {
      updateLayout();
    });

    if (scrollContainerRef.current) resizeObserver.observe(scrollContainerRef.current);

    return () => {
      resizeObserver.disconnect();
    };
  }, [posts, columnCount, superPostId]);

  return (
    <div 
      className="card-grid-scroll-container" 
      ref={scrollContainerRef}
      style={{ '--glow-sync-delay': glowAnimationDelay } as React.CSSProperties}
    >
      <div className="card-grid-pack" ref={packRef}>
        <div className="edge-glow edge-glow-left" />
        <div className="edge-glow edge-glow-right" />
        <div className="edge-glow edge-glow-ragged" />

        <div className="card-grid" ref={gridRef}>
          {posts.map((post, index) => {
            const postIndex = index;
            const isSuper = columnCount >= 2 && superPostId !== null && post.id === superPostId;
            const isSelected = selectedIndex === postIndex;
            return (
              <Link
                key={post.id}
                href={`/p/${post.public_sqid}`}
                className={`artwork-card${isSuper ? ' super-post' : ''}${isSelected ? ' artwork-selected' : ''}`}
                onClick={(e) => {
                  // First tap selects (no navigation). Second tap happens on overlay.
                  e.preventDefault();
                  e.stopPropagation();
                  setSelectedIndex(postIndex);
                }}
                aria-label={post.title}
              >
                <div
                  className="artwork-area"
                  ref={(el) => {
                    artworkAreaRefs.current.set(post.id, el);
                  }}
                >
                  <img
                    src={post.art_url}
                    alt={post.title}
                    className="artwork-image pixel-art"
                    data-canvas={post.canvas}
                    loading="lazy"
                    style={{ visibility: isSelected ? 'hidden' : 'visible' }}
                  />
                </div>
              </Link>
            );
          })}
        </div>

        {selectedIndex !== null && selectedIndex >= 0 && selectedIndex < posts.length && (
          <SelectedArtworkOverlay
            posts={selectedOverlayPosts}
            selectedIndex={selectedIndex}
            setSelectedIndex={setSelectedIndex}
            getOriginRectForIndex={getOriginRectForIndex}
            onClose={() => setSelectedIndex(null)}
            onNavigateToPost={(idx) => {
              handlePostClick(idx);
              const sqid = posts[idx]?.public_sqid;
              if (!sqid) return;
              router.push(`/p/${sqid}`);
            }}
          />
        )}

      <style jsx>{`
        .card-grid-scroll-container {
          width: 100%;
          overflow-x: auto;
          overflow-y: visible;
          -webkit-overflow-scrolling: touch;
          display: block;
          padding: 0;
        }

        .card-grid-pack {
          position: relative;
          width: var(--grid-width, 128px);
          margin-left: auto;
          margin-right: auto;
        }

        .edge-glow {
          position: absolute;
          top: 0;
          width: 56px;
          pointer-events: none;
          filter: blur(10px) hue-rotate(0deg);
          opacity: 0.9;
          animation: sinebow-hue 16s linear infinite;
          animation-delay: var(--glow-sync-delay, 0s);
        }

        .edge-glow-left {
          left: -56px;
          height: var(--left-glow-height, 0px);
          background: linear-gradient(
            to left,
            rgba(0, 212, 255, 0.22) 0%,
            rgba(0, 212, 255, 0.210546875) 12.5%,
            rgba(0, 212, 255, 0.185625) 25%,
            rgba(0, 212, 255, 0.150390625) 37.5%,
            rgba(0, 212, 255, 0.11) 50%,
            rgba(0, 212, 255, 0.069609375) 62.5%,
            rgba(0, 212, 255, 0.034375) 75%,
            rgba(0, 212, 255, 0.009453125) 87.5%,
            rgba(0, 212, 255, 0) 100%
          );
        }

        .edge-glow-right {
          right: -56px;
          height: var(--right-glow-height, 0px);
          background: linear-gradient(
            to right,
            rgba(0, 212, 255, 0.22) 0%,
            rgba(0, 212, 255, 0.210546875) 12.5%,
            rgba(0, 212, 255, 0.185625) 25%,
            rgba(0, 212, 255, 0.150390625) 37.5%,
            rgba(0, 212, 255, 0.11) 50%,
            rgba(0, 212, 255, 0.069609375) 62.5%,
            rgba(0, 212, 255, 0.034375) 75%,
            rgba(0, 212, 255, 0.009453125) 87.5%,
            rgba(0, 212, 255, 0) 100%
          );
        }

        /* Extra glow for a ragged right edge on the last row */
        .edge-glow-ragged {
          left: var(--ragged-glow-left, 0px);
          top: var(--ragged-glow-top, 0px);
          height: var(--ragged-glow-height, 0px);
          opacity: var(--ragged-glow-opacity, 0);
          background: linear-gradient(
            to right,
            rgba(0, 212, 255, 0.22) 0%,
            rgba(0, 212, 255, 0.210546875) 12.5%,
            rgba(0, 212, 255, 0.185625) 25%,
            rgba(0, 212, 255, 0.150390625) 37.5%,
            rgba(0, 212, 255, 0.11) 50%,
            rgba(0, 212, 255, 0.069609375) 62.5%,
            rgba(0, 212, 255, 0.034375) 75%,
            rgba(0, 212, 255, 0.009453125) 87.5%,
            rgba(0, 212, 255, 0) 100%
          );
        }

        .card-grid {
          display: grid;
          grid-template-columns: repeat(var(--grid-columns, 1), 128px);
          grid-auto-rows: 128px;
          grid-auto-flow: dense;
          gap: 0;
          padding: 0;
          margin: 0;
          width: var(--grid-width, 128px);
        }

        .artwork-area {
          width: 128px;
          height: 128px;
          position: relative;
          overflow: hidden;
        }

        :global(a.artwork-card) {
          display: block;
          width: 128px;
          height: 128px;
          line-height: 0;
          position: relative;
          overflow: visible;
          -webkit-tap-highlight-color: rgba(0, 0, 0, 0);
          tap-highlight-color: rgba(0, 0, 0, 0);
          background: transparent;
        }

        /* Prevent brief mobile "selected"/highlight flash on tap */
        :global(a.artwork-card:active) {
          background: transparent;
        }

        :global(a.artwork-card.super-post) {
          width: 256px;
          height: 256px;
          grid-column: span 2;
          grid-row: span 2;
        }

        :global(a.artwork-card.super-post) .artwork-area {
          width: 256px;
          height: 256px;
        }

        :global(a.artwork-card:focus-visible) {
          outline: none;
        }

        :global(a.artwork-card.bottom-glow)::after {
          content: '';
          position: absolute;
          left: 0;
          right: 0;
          top: 100%;
          height: 64px;
          pointer-events: none;
          background: linear-gradient(
            to bottom,
            rgba(0, 212, 255, 0.22) 0%,
            rgba(0, 212, 255, 0.210546875) 12.5%,
            rgba(0, 212, 255, 0.185625) 25%,
            rgba(0, 212, 255, 0.150390625) 37.5%,
            rgba(0, 212, 255, 0.11) 50%,
            rgba(0, 212, 255, 0.069609375) 62.5%,
            rgba(0, 212, 255, 0.034375) 75%,
            rgba(0, 212, 255, 0.009453125) 87.5%,
            rgba(0, 212, 255, 0) 100%
          );
          filter: blur(10px) hue-rotate(0deg);
          opacity: 0.9;
          animation: sinebow-hue 16s linear infinite;
          animation-delay: var(--glow-sync-delay, 0s);
        }

        @keyframes sinebow-hue {
          from {
            filter: blur(10px) hue-rotate(0deg);
          }
          to {
            filter: blur(10px) hue-rotate(360deg);
          }
        }

        .artwork-image {
          position: absolute;
          left: 50%;
          top: 50%;
          transform: translate(-50%, -50%);
          display: block;
        }
      `}</style>
      </div>
    </div>
  );
}
