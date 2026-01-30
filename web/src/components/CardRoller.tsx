import { useState, useEffect, useRef, useLayoutEffect, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { setNavigationContext } from '../lib/navigation-context';
import { authenticatedFetch, clearTokens } from '../lib/api';

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
  width: number;
  height: number;
  owner_id: string;
  created_at: string;
  owner?: PostOwner;
}

interface HashtagStats {
  tag: string;
  reaction_count: number;
  comment_count: number;
  artwork_count: number;
}

interface CardRollerProps {
  hashtag: string;
  stats: HashtagStats;
  API_BASE_URL: string;
  initialPosts?: Post[];
}

// Configuration constants
const POSTS_PER_LOAD = 20; // Number of posts to fetch per horizontal scroll

export default function CardRoller({ hashtag, stats, API_BASE_URL, initialPosts = [] }: CardRollerProps) {
  const router = useRouter();
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  
  const [posts, setPosts] = useState<Post[]>(initialPosts);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasMore, setHasMore] = useState(true);

  const loadingRef = useRef(false);
  const hasMoreRef = useRef(true);
  const nextCursorRef = useRef<string | null>(null);

  // Load more posts for this hashtag
  const loadMorePosts = useCallback(async () => {
    if (loadingRef.current || !hasMoreRef.current) return;
    
    loadingRef.current = true;
    setLoading(true);
    
    try {
      const url = `${API_BASE_URL}/api/hashtags/${encodeURIComponent(hashtag)}/posts?limit=${POSTS_PER_LOAD}${nextCursorRef.current ? `&cursor=${encodeURIComponent(nextCursorRef.current)}` : ''}`;
      const response = await authenticatedFetch(url);
      
      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      
      if (!response.ok) {
        throw new Error(`Failed to load posts: ${response.statusText}`);
      }
      
      const data: { items: Post[]; next_cursor: string | null } = await response.json();
      
      setPosts(prev => [...prev, ...data.items]);
      setNextCursor(data.next_cursor);
      nextCursorRef.current = data.next_cursor;
      const hasMoreValue = data.next_cursor !== null;
      hasMoreRef.current = hasMoreValue;
      setHasMore(hasMoreValue);
    } catch (err) {
      console.error('Error loading posts:', err);
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }, [hashtag, API_BASE_URL, router]);

  // Initial load if no initial posts provided
  useEffect(() => {
    if (initialPosts.length === 0) {
      loadMorePosts();
    }
  }, [initialPosts.length, loadMorePosts]);

  // Intersection Observer for horizontal infinite scroll
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && hasMoreRef.current && !loadingRef.current) {
          loadMorePosts();
        }
      },
      { threshold: 0.1, root: scrollContainerRef.current }
    );

    observer.observe(sentinel);

    return () => {
      observer.disconnect();
    };
  }, [loadMorePosts]);

  // Handle post click - store navigation context before navigating
  const handlePostClick = (postIndex: number) => {
    const contextPosts = posts.map((post) => ({
      public_sqid: post.public_sqid,
      id: post.id,
      owner_id: post.owner_id,
    }));

    setNavigationContext(contextPosts, postIndex, { type: 'hashtag', id: hashtag }, nextCursor, null);
  };

  // Apply crisp scaling to artworks
  useLayoutEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const calculateScales = () => {
      const artworkAreas = container.querySelectorAll('.artwork-area');
      
      artworkAreas.forEach((area) => {
        const image = area.querySelector('.artwork-image') as HTMLImageElement;
        if (!image) return;

        const nativeWidth = parseInt(image.getAttribute('data-width') || '', 10);
        const nativeHeight = parseInt(image.getAttribute('data-height') || '', 10);

        if (!nativeWidth || !nativeHeight || isNaN(nativeWidth) || isNaN(nativeHeight)) return;

        const TILE_SIZE = 128;
        const isLarge = nativeWidth > TILE_SIZE || nativeHeight > TILE_SIZE;

        // <= 128px: integer scale to cover (then crop)
        // > 128px in either dimension: non-integer cover scale based on the smaller side
        const scale = isLarge
          ? TILE_SIZE / Math.min(nativeWidth, nativeHeight)
          : Math.max(1, Math.ceil(Math.max(TILE_SIZE / nativeWidth, TILE_SIZE / nativeHeight)));

        const displayWidth = nativeWidth * scale;
        const displayHeight = nativeHeight * scale;

        // Apply size to image
        image.style.width = `${displayWidth}px`;
        image.style.height = `${displayHeight}px`;
        image.style.maxWidth = 'none';
        image.style.maxHeight = 'none';
      });
    };

    calculateScales();

    const resizeObserver = new ResizeObserver(() => {
      calculateScales();
    });

    resizeObserver.observe(container);

    return () => {
      resizeObserver.disconnect();
    };
  }, [posts]);

  return (
    <div className="card-roller">
      <div className="card-roller-header">
        <div className="hashtag-info">
          <Link href={`/hashtags/${encodeURIComponent(hashtag)}`} className="hashtag-link">
            <span className="hashtag-symbol">#</span>
            <span className="hashtag-name">{hashtag}</span>
          </Link>
        </div>
        <div className="hashtag-stats">
          <div className="stat-item">
            <span className="stat-emoji">⚡</span>
            <span className="stat-count">{stats.reaction_count}</span>
          </div>
          <div className="stat-item">
            <span className="stat-emoji">💬</span>
            <span className="stat-count">{stats.comment_count}</span>
          </div>
          <div className="stat-item">
            <span className="stat-emoji">🎨</span>
            <span className="stat-count">{stats.artwork_count}</span>
          </div>
        </div>
      </div>
      
      <div className="card-roller-body" ref={scrollContainerRef}>
        <div className="artwork-cards-horizontal">
          {posts.map((post, index) => (
            <Link
              key={post.id}
              href={`/p/${post.public_sqid}`}
              className="artwork-card"
              onClick={() => handlePostClick(index)}
              aria-label={post.title}
            >
              <div className="artwork-area">
                <img
                  src={post.art_url}
                  alt={post.title}
                  className="artwork-image pixel-art"
                  data-width={post.width}
                  data-height={post.height}
                  loading="lazy"
                />
              </div>
            </Link>
          ))}
          
          {/* Sentinel for infinite scroll */}
          {hasMore && (
            <div ref={sentinelRef} className="scroll-sentinel">
              {loading && (
                <div className="loading-indicator">
                  <div className="loading-spinner"></div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <style jsx>{`
        .card-roller {
          width: 100%;
          margin-bottom: 32px;
        }

        .card-roller-header {
          display: flex;
          flex-direction: row;
          flex-wrap: nowrap;
          align-items: center;
          justify-content: space-between;
          padding: 16px 24px;
          background: var(--bg-secondary);
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
          gap: 12px;
        }

        .hashtag-info {
          display: flex;
          align-items: center;
          gap: 8px;
          min-width: 0;
          flex: 1 1 auto;
          overflow: hidden;
        }

        .hashtag-link {
          display: flex;
          align-items: center;
          gap: 8px;
          text-decoration: none;
          transition: all var(--transition-fast);
          min-width: 0;
          overflow: hidden;
        }

        .hashtag-link:hover {
          transform: translateX(4px);
        }

        .hashtag-symbol {
          font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
          font-weight: 700;
          font-size: 1.5rem;
          background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
          flex-shrink: 0;
        }

        .hashtag-name {
          font-size: 1.2rem;
          font-weight: 600;
          color: var(--text-primary);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .hashtag-stats {
          display: flex;
          gap: 16px;
          align-items: center;
          flex-shrink: 0;
        }

        .hashtag-stats .stat-item {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 0.9rem;
          color: var(--text-secondary);
        }

        .hashtag-stats .stat-emoji {
          font-size: 1.1rem;
        }

        .hashtag-stats .stat-count {
          font-weight: 600;
          color: var(--text-primary);
        }

        .card-roller-body {
          overflow-x: auto;
          overflow-y: hidden;
          -webkit-overflow-scrolling: touch;
          scrollbar-width: thin;
        }

        .artwork-cards-horizontal {
          display: flex;
          gap: 0;
          padding: 0;
          min-height: 128px;
        }

        :global(a.artwork-card) {
          display: block;
          width: 128px;
          height: 128px;
          flex-shrink: 0;
          line-height: 0;
        }

        :global(a.artwork-card:focus-visible) {
          outline: none;
        }

        .artwork-area {
          width: 128px;
          height: 128px;
          position: relative;
          overflow: hidden;
        }

        .artwork-image {
          position: absolute;
          left: 50%;
          top: 50%;
          transform: translate(-50%, -50%);
          display: block;
        }

        /* artwork tiles only (stats / author / title removed) */

        .scroll-sentinel {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 100px;
          flex-shrink: 0;
        }

        .loading-indicator {
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .loading-spinner {
          width: 24px;
          height: 24px;
          border: 2px solid var(--bg-tertiary);
          border-top-color: var(--accent-purple);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }

        @media (max-width: 768px) {
          .card-roller-header {
            padding: 12px 16px;
          }

          .hashtag-stats {
            gap: 10px;
          }

          .hashtag-stats .stat-emoji {
            font-size: 1rem;
          }

          .hashtag-stats .stat-count {
            font-size: 0.8rem;
          }
        }
      `}</style>
    </div>
  );
}
