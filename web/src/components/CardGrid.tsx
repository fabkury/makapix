import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { setNavigationContext, NavigationSource } from '../lib/navigation-context';
import SelectedPostOverlay from './SelectedPostOverlay';
import { usePlayerBarOptional } from '../contexts/PlayerBarContext';
import { authenticatedFetch } from '../lib/api';

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
  width: number;
  height: number;
  owner_id: string;
  created_at: string;
  owner?: PostOwner;
  frame_count?: number;
  files?: Array<{ format: string; file_bytes: number; is_native: boolean }>;
}

interface CardGridProps {
  posts: Post[];
  API_BASE_URL: string;
  source: NavigationSource;
  cursor?: string | null;
  prevCursor?: string | null;
  /** When true, the grid is visually hidden (e.g. behind WebPlayer overlay).
   *  Pauses animations, disconnects observers, and clears the selected post. */
  occluded?: boolean;
}

export default function CardGrid({
  posts,
  API_BASE_URL: _API_BASE_URL,
  source,
  cursor = null,
  prevCursor,
  occluded = false,
}: CardGridProps) {
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
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [isModerator, setIsModerator] = useState(false);

  // Clear selected post when grid becomes occluded (e.g. WebPlayer opens)
  useEffect(() => {
    if (occluded) setSelectedIndex(null);
  }, [occluded]);

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

  // Close overlay on route change to ensure proper navigation
  useEffect(() => {
    const handleRouteChange = () => {
      setSelectedIndex(null);
    };

    router.events.on('routeChangeStart', handleRouteChange);
    return () => {
      router.events.off('routeChangeStart', handleRouteChange);
    };
  }, [router.events]);

  // Fetch current user and moderator status
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const userId = localStorage.getItem('user_id');
    setCurrentUserId(userId);

    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
    const token = localStorage.getItem('access_token');
    if (token) {
      authenticatedFetch(`${apiBaseUrl}/api/auth/me`)
        .then(res => {
          if (!res.ok) return null;
          return res.json();
        })
        .then(data => {
          if (data?.roles) {
            const roles = data.roles as string[];
            setIsModerator(roles.includes('moderator') || roles.includes('owner'));
          }
        })
        .catch(() => {
          // ignore
        });
    }
  }, []);

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
        owner: p.owner ? {
          handle: p.owner.handle,
          avatar_url: p.owner.avatar_url,
          public_sqid: p.owner.public_sqid,
        } : undefined,
        created_at: p.created_at,
        frame_count: p.frame_count ?? 1,
        width: p.width,
        height: p.height,
        files: p.files ?? [],
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
    // When occluded (e.g. WebPlayer overlay is active), skip all layout work
    // and disconnect the ResizeObserver to save CPU.
    if (occluded) return;

    const calculateScales = () => {
      const grid = gridRef.current;
      if (!grid) return;

      const images = grid.querySelectorAll('img.artwork-image');
      images.forEach((imageEl) => {
        const image = imageEl as HTMLImageElement;
        const card = image.closest('a.artwork-card') as HTMLAnchorElement | null;
        const tileSize = card?.classList.contains('super-post') ? TILE_SIZE * 2 : TILE_SIZE;

        const nativeWidth = parseInt(image.getAttribute('data-width') || '', 10);
        const nativeHeight = parseInt(image.getAttribute('data-height') || '', 10);

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
    };

    const updateLayout = () => {
      calculateColumns();
      calculateScales();
    };

    updateLayout();

    if (typeof ResizeObserver !== 'undefined') {
      const resizeObserver = new ResizeObserver(() => {
        updateLayout();
      });

      if (scrollContainerRef.current) resizeObserver.observe(scrollContainerRef.current);

      return () => {
        resizeObserver.disconnect();
      };
    } else {
      const handleResize = () => updateLayout();
      window.addEventListener('resize', handleResize);
      return () => window.removeEventListener('resize', handleResize);
    }
  }, [posts, columnCount, superPostId, occluded]);

  return (
    <div
      className={`card-grid-scroll-container${occluded ? ' cg-occluded' : ''}`}
      ref={scrollContainerRef}
    >
      <div className="card-grid-pack" ref={packRef}>
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
                    data-width={post.width}
                    data-height={post.height}
                    loading="lazy"
                    style={{ visibility: isSelected ? 'hidden' : 'visible' }}
                  />
                </div>
              </Link>
            );
          })}
        </div>

        {!occluded && selectedIndex !== null && selectedIndex >= 0 && selectedIndex < posts.length && (
          <SelectedPostOverlay
            posts={selectedOverlayPosts}
            selectedIndex={selectedIndex}
            setSelectedIndex={setSelectedIndex}
            getOriginRectForIndex={getOriginRectForIndex}
            onClose={() => setSelectedIndex(null)}
            onNavigateToPost={(idx) => {
              const post = posts[idx];
              if (!post) return;

              // Store navigation context for swipe navigation on post page
              handlePostClick(idx);
              router.push(`/p/${post.public_sqid}`);
            }}
            currentUserId={currentUserId}
            isModerator={isModerator}
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

        /* When occluded (e.g. WebPlayer overlay is open), hide the grid so
           the browser can skip painting, compositing, and GIF decoding. */
        .card-grid-scroll-container.cg-occluded {
          visibility: hidden;
        }

        .card-grid-pack {
          position: relative;
          width: var(--grid-width, 128px);
          margin-left: auto;
          margin-right: auto;
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
          content-visibility: auto;
          contain-intrinsic-size: 128px 128px;
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
          contain-intrinsic-size: 256px 256px;
        }

        :global(a.artwork-card.super-post) .artwork-area {
          width: 256px;
          height: 256px;
        }

        :global(a.artwork-card:focus-visible) {
          outline: none;
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
