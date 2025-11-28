import { useState, useEffect, useLayoutEffect, useRef } from 'react';
import Link from 'next/link';

interface PostOwner {
  id: string;
  handle: string;
  avatar_url?: string | null;
}

interface Post {
  id: number;
  public_sqid: string;
  title: string;
  description?: string;
  hashtags?: string[];
  art_url: string;
  canvas: string;
  owner_id: string;
  created_at: string;
  owner?: PostOwner;
  // Stats returned by the API (from annotate_posts_with_counts)
  reaction_count?: number;
  comment_count?: number;
  user_has_liked?: boolean;
}

interface CardGridProps {
  posts: Post[];
  API_BASE_URL: string;
}

// Local state for optimistic like updates
interface LikeState {
  liked: boolean;
  reactionCount: number;
}

export default function CardGrid({ posts, API_BASE_URL }: CardGridProps) {
  const gridRef = useRef<HTMLDivElement>(null);
  // Track local like state for optimistic updates (keyed by post id)
  const [likeOverrides, setLikeOverrides] = useState<Record<number, LikeState>>({});
  const [loadingLikes, setLoadingLikes] = useState<Record<number, boolean>>({});

  // Reset overrides when posts change (e.g., new page loaded)
  useEffect(() => {
    setLikeOverrides({});
  }, [posts]);

  // Handle like/unlike with optimistic update
  const handleLike = async (postId: number, currentlyLiked: boolean, currentReactionCount: number) => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      // Could redirect to login or show a message
      return;
    }

    setLoadingLikes(prev => ({ ...prev, [postId]: true }));

    // Optimistic update
    setLikeOverrides(prev => ({
      ...prev,
      [postId]: {
        liked: !currentlyLiked,
        reactionCount: currentReactionCount + (currentlyLiked ? -1 : 1)
      }
    }));

    try {
      const url = `${API_BASE_URL}/api/posts/${postId}/reactions/👍`;
      const method = currentlyLiked ? 'DELETE' : 'PUT';
      
      const response = await fetch(url, {
        method,
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok && response.status !== 204) {
        // Revert optimistic update on failure
        setLikeOverrides(prev => ({
          ...prev,
          [postId]: {
            liked: currentlyLiked,
            reactionCount: currentReactionCount
          }
        }));
      }
    } catch (err) {
      console.error(`Error ${currentlyLiked ? 'unliking' : 'liking'} post:`, err);
      // Revert optimistic update on error
      setLikeOverrides(prev => ({
        ...prev,
        [postId]: {
          liked: currentlyLiked,
          reactionCount: currentReactionCount
        }
      }));
    } finally {
      setLoadingLikes(prev => ({ ...prev, [postId]: false }));
    }
  };

  // Apply crisp scaling to artworks and calculate dynamic spacing
  // Using useLayoutEffect to calculate before browser paint (prevents visible reflow)
  useLayoutEffect(() => {
    const grid = gridRef.current;
    if (!grid) return;

    const calculateSpacing = () => {
      const containerWidth = grid.clientWidth;
      if (containerWidth === 0) return;
      
      const gridStyles = window.getComputedStyle(grid);
      const templateColumns = gridStyles.gridTemplateColumns;
      const columns = templateColumns.split(' ').filter(col => col.trim().length > 0 && col.includes('px'));
      const columnCount = Math.max(columns.length, 1);
      
      const cardSize = 180; // Fixed card cell size
      const maxGapSize = cardSize; // Maximum spacing between columns equals card size
      const totalCardsWidth = columnCount * cardSize;
      const remainingSpace = containerWidth - totalCardsWidth;
      
      // Calculate spacing if distributed evenly
      const gapCount = columnCount + 1; // sides + between columns
      const evenSpacing = Math.max(1, Math.floor(remainingSpace / gapCount));
      
      // Cap the gap between columns at the card size
      const gapBetweenColumns = Math.min(evenSpacing, maxGapSize);
      
      // Calculate space used by gaps between columns
      const gapsBetweenColumnsCount = columnCount - 1;
      const spaceUsedByGaps = gapsBetweenColumnsCount * gapBetweenColumns;
      
      // Remaining space goes to sides
      const spaceForSides = remainingSpace - spaceUsedByGaps;
      const sideSpacing = Math.max(1, Math.floor(spaceForSides / 2));
      
      // Set CSS variable for spacing (used by CSS as fallback)
      grid.style.setProperty('--grid-spacing', `${sideSpacing}px`);
      // Set gap directly (applies to both horizontal and vertical spacing)
      // Gap between columns is capped at card size, and same applies to rows
      // This becomes the reference spacing for the entire layout
      grid.style.gap = `${gapBetweenColumns}px`;
      // Set side padding (excess space goes here)
      grid.style.paddingLeft = `${sideSpacing}px`;
      grid.style.paddingRight = `${sideSpacing}px`;
      // Set vertical padding to match the reference spacing (capped column gap)
      grid.style.paddingTop = `${gapBetweenColumns}px`;
      grid.style.paddingBottom = `${gapBetweenColumns}px`;
      // Set margin-top based on reference spacing (capped column gap)
      // Using quarter of the reference spacing for header-to-grid gap
      grid.style.marginTop = `${gapBetweenColumns / 4}px`;
    };

    const calculateScales = () => {
      const artworkAreas = grid.querySelectorAll('.artwork-area');
      
      artworkAreas.forEach((area) => {
        const image = area.querySelector('.artwork-image') as HTMLImageElement;
        if (!image) return;

        const canvasStr = image.getAttribute('data-canvas') || '';
        if (!canvasStr) return;

        const [widthStr, heightStr] = canvasStr.split('x');
        const nativeWidth = parseInt(widthStr, 10);
        const nativeHeight = parseInt(heightStr, 10);

        if (!nativeWidth || !nativeHeight || isNaN(nativeWidth) || isNaN(nativeHeight)) return;

        // Use the larger dimension to calculate scale
        const nativeSize = Math.max(nativeWidth, nativeHeight);
        
        // Calculate maximum integer scale that fits in 128px
        const scale = Math.floor(128 / nativeSize);
        const finalScale = Math.max(1, scale);

        // Calculate display size at integer multiple
        const displayWidth = nativeWidth * finalScale;
        const displayHeight = nativeHeight * finalScale;

        // Apply size to image
        image.style.width = `${displayWidth}px`;
        image.style.height = `${displayHeight}px`;
        image.style.maxWidth = 'none';
        image.style.maxHeight = 'none';
        image.style.objectFit = 'contain';
      });
    };

    const updateLayout = () => {
      calculateSpacing();
      calculateScales();
    };

    // Run immediately - no setTimeout delay
    updateLayout();

    const resizeObserver = new ResizeObserver(() => {
      updateLayout();
    });

    resizeObserver.observe(grid);

    const handleResize = () => {
      updateLayout();
    };

    window.addEventListener('resize', handleResize);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener('resize', handleResize);
    };
  }, [posts]);

  return (
    <div className="card-grid" ref={gridRef}>
      {posts.map((post) => {
        // Use local override if available (for optimistic updates), otherwise use API data
        const override = likeOverrides[post.id];
        const reactionCount = override?.reactionCount ?? post.reaction_count ?? 0;
        const commentCount = post.comment_count ?? 0;
        const isLiked = override?.liked ?? post.user_has_liked ?? false;
        const isLoading = loadingLikes[post.id] || false;

        return (
          <div key={post.id} className="artwork-card">
            <div className="card-top">
              <div className="artwork-area">
                <Link href={`/p/${post.public_sqid}`}>
                  <img
                    src={post.art_url}
                    alt={post.title}
                    className="artwork-image pixel-art"
                    data-canvas={post.canvas}
                    loading="lazy"
                  />
                </Link>
              </div>
              <div className="stats-panel">
                <div className="stat-item">
                  <span className="stat-emoji">⚡</span>
                  <span className="stat-count">{reactionCount}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-emoji">💬</span>
                  <span className="stat-count">{commentCount}</span>
                </div>
                <button
                  className={`like-button ${isLiked ? 'liked' : ''}`}
                  onClick={(e) => {
                    e.preventDefault();
                    handleLike(post.id, isLiked, reactionCount);
                  }}
                  disabled={isLoading}
                  aria-label={isLiked ? 'Unlike' : 'Like'}
                >
                  👍
                </button>
              </div>
            </div>
            <div className="author-bar">
              <div className="author-line">
                <Link href={`/users/${post.owner_id}`} className="author-handle" style={{ fontSize: '0.7rem', color: 'white', display: 'flex', alignItems: 'center' }}>
                  {post.owner?.avatar_url && (
                    <img src={post.owner.avatar_url} alt="" className="author-avatar" />
                  )}
                  <span>{post.owner?.handle || 'Unknown'}</span>
                </Link>
              </div>
              <div className="title-line">
                <Link href={`/p/${post.public_sqid}`} className="post-title" style={{ fontSize: '0.7rem', color: 'var(--accent-cyan)', display: 'flex', alignItems: 'center' }}>
                  {post.title}
                </Link>
              </div>
            </div>
          </div>
        );
      })}

      <style jsx>{`
        .card-grid {
          display: grid;
          grid-template-columns: repeat(1, 180px);
          gap: var(--grid-spacing, 16px);
          padding-left: var(--grid-spacing, 16px);
          padding-right: var(--grid-spacing, 16px);
          padding-top: var(--grid-spacing, 16px);
          padding-bottom: var(--grid-spacing, 16px);
          max-width: 100%;
          margin: 0 auto;
          justify-content: start;
        }

        @media (min-width: 362px) {
          .card-grid {
            grid-template-columns: repeat(2, 180px);
          }
        }

        @media (min-width: 544px) {
          .card-grid {
            grid-template-columns: repeat(3, 180px);
          }
        }

        @media (min-width: 726px) {
          .card-grid {
            grid-template-columns: repeat(4, 180px);
          }
        }

        .artwork-card {
          display: flex;
          flex-direction: column;
          width: 178px;
          height: 178px;
          background: var(--bg-secondary);
          overflow: hidden;
          transition: box-shadow var(--transition-fast);
          border: 1px solid transparent;
        }

        .artwork-card:hover {
          box-shadow: 0 0 20px rgba(0, 212, 255, 0.2);
          z-index: 1;
        }

        .card-top {
          display: flex;
          flex-direction: row;
          width: 100%;
          height: 128px;
          gap: 1px;
        }

        .artwork-area {
          width: 128px;
          height: 128px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: var(--bg-tertiary);
          flex-shrink: 0;
        }

        .artwork-area a {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 100%;
          height: 100%;
          line-height: 0;
        }

        .artwork-image {
          display: block;
          image-rendering: -webkit-optimize-contrast !important;
          image-rendering: -moz-crisp-edges !important;
          image-rendering: crisp-edges !important;
          image-rendering: pixelated !important;
          -ms-interpolation-mode: nearest-neighbor !important;
        }

        .stats-panel {
          width: 49px;
          height: 128px;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 8px;
          background: var(--bg-secondary);
          flex-shrink: 0;
          padding: 8px 4px;
        }

        .stat-item {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 2px;
          font-size: 0.75rem;
          color: var(--text-secondary);
        }

        .stat-emoji {
          font-size: 1rem;
        }

        .stat-count {
          font-weight: 600;
          font-size: 0.7rem;
        }

        .like-button {
          width: 28px;
          height: 28px;
          border-radius: 50%;
          border: 2px solid var(--bg-tertiary);
          background: var(--bg-secondary);
          font-size: 0.9rem;
          cursor: pointer;
          transition: all var(--transition-fast);
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          margin-top: 4px;
        }

        .like-button:hover:not(:disabled) {
          background: var(--bg-tertiary);
          border-color: var(--accent-pink);
          transform: scale(1.1);
        }

        .like-button:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .like-button.liked {
          background: var(--accent-pink);
          border-color: var(--accent-pink);
        }

        .like-button.liked:hover:not(:disabled) {
          background: var(--accent-cyan);
          border-color: var(--accent-cyan);
        }

        .author-bar {
          width: 168px;
          height: 49px;
          display: flex;
          flex-direction: column;
          justify-content: center;
          gap: 4px;
          background: var(--bg-secondary);
          padding: 4px 6px;
          margin-top: 1px;
        }

        .author-line {
          display: block;
          width: 100%;
          height: 18px;
          line-height: 18px;
          overflow: hidden;
          white-space: nowrap;
          text-overflow: ellipsis;
        }

        .title-line {
          display: block;
          width: 100%;
          height: 18px;
          line-height: 18px;
          overflow: hidden;
          white-space: nowrap;
          text-overflow: ellipsis;
        }

        .author-handle {
          display: inline-flex;
          flex-direction: row;
          align-items: center;
          gap: 3px;
          font-size: 0.35rem;
          font-weight: 600;
          color: var(--accent-cyan);
          text-decoration: none;
          transition: color var(--transition-fast);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: 100%;
          vertical-align: middle;
        }

        .author-handle span {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .author-handle:hover {
          color: var(--accent-blue);
        }

        .author-avatar {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          object-fit: cover;
          flex-shrink: 0;
        }

        .post-title {
          display: inline-block;
          font-size: 0.35rem;
          font-weight: 600;
          color: var(--accent-pink);
          text-decoration: none;
          transition: color var(--transition-fast);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: 100%;
          vertical-align: middle;
        }

        .post-title:hover {
          color: var(--accent-purple);
        }
      `}</style>
    </div>
  );
}
