import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';
import { authenticatedFetch, clearTokens } from '../lib/api';
import { ensureCompatibleArtUrl } from '../utils/imageCompat';

// Contract: docs/pulse/messages/0002-server-pulse-contract-accepted.md

interface PulsePost {
  id: number;
  public_sqid: string;
  title: string;
  art_url: string;
  frame_count?: number;
  owner?: { handle: string; public_sqid?: string | null } | null;
}

interface PulseComment {
  id: string;
  preview: string;
  is_reply: boolean;
  created_at: string;
  post: PulsePost;
}

interface PulseCard {
  id: string;
  kind: string;
  actor: { public_sqid: string; handle: string; avatar_url: string | null };
  started_at: string;
  updated_at: string;
  count: number;
  posts?: PulsePost[] | null;
  comments?: PulseComment[] | null;
  player?: { device_model: string | null } | null;
  badges?: { badge: string; label: string; icon_url_64: string | null }[] | null;
  reputation?: { delta: number; total: number } | null;
}

interface PageResponse<T> {
  items: T[];
  next_cursor: string | null;
}

const plural = (n: number, one: string, many: string) => (n === 1 ? one : many);

// What the card says after the member's name. A kind this build does not know
// returns null and the card is skipped, so the server can add kinds freely.
const cardVerb = (card: PulseCard): string | null => {
  const n = card.count;
  switch (card.kind) {
    case 'likes':
      return `liked ${n} ${plural(n, 'artwork', 'artworks')}`;
    case 'posts':
      return `posted ${n} ${plural(n, 'artwork', 'artworks')}`;
    case 'remixes':
      return `posted ${n} ${plural(n, 'remix', 'remixes')}`;
    case 'comments':
      return `wrote ${n} ${plural(n, 'comment', 'comments')}`;
    case 'promoted':
      return `had ${n} ${plural(n, 'artwork', 'artworks')} added to Recommended`;
    case 'player':
      return card.player?.device_model
        ? `registered a ${card.player.device_model} player`
        : 'registered a player';
    case 'badge':
      return `earned ${n} ${plural(n, 'badge', 'badges')}`;
    case 'reputation':
      return card.reputation
        ? `gained ${card.reputation.delta} reputation`
        : null;
    default:
      return null;
  }
};

const KIND_ICON: Record<string, string> = {
  likes: '👍',
  posts: '🖼️',
  remixes: '🔀',
  comments: '💬',
  promoted: '⭐',
  player: '📺',
  badge: '🏅',
  reputation: '📈',
};

const formatRelativeTime = (dateStr: string): string => {
  const date = new Date(dateStr);
  const diffMs = Date.now() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
};

export default function PulsePage() {
  const router = useRouter();
  const [cards, setCards] = useState<PulseCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const observerTarget = useRef<HTMLDivElement>(null);
  const loadingRef = useRef(false);
  const nextCursorRef = useRef<string | null>(null);

  const API_BASE_URL = typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  // Members only: visitors go to the Welcome page
  useEffect(() => {
    if (!localStorage.getItem('access_token')) {
      router.replace('/welcome');
    } else {
      setIsAuthenticated(true);
    }
  }, [router]);

  const loadCards = useCallback(async (cursor: string | null = null) => {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setLoading(true);
    setError(null);

    try {
      const url = `${API_BASE_URL}/api/v1/pulse?limit=20${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ''}`;
      const response = await authenticatedFetch(url);

      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      if (!response.ok) {
        throw new Error(`Failed to load Pulse (${response.status})`);
      }

      const data: PageResponse<PulseCard> = await response.json();
      if (!data || !Array.isArray(data.items)) {
        throw new Error('Invalid response format from server');
      }

      setCards(prev => {
        if (!cursor) return data.items;
        // A card that grew between two page fetches can come back: keep one
        const seen = new Set(prev.map(c => c.id));
        return [...prev, ...data.items.filter(c => !seen.has(c.id))];
      });
      nextCursorRef.current = data.next_cursor;
      setHasMore(data.next_cursor !== null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load Pulse');
      console.error('Error loading Pulse:', err);
    } finally {
      loadingRef.current = false;
      setLoading(false);
      setLoaded(true);
    }
  }, [API_BASE_URL, router]);

  useEffect(() => {
    if (isAuthenticated) loadCards();
  }, [isAuthenticated, loadCards]);

  // Infinite scroll
  useEffect(() => {
    if (!loaded || !hasMore) return;
    const target = observerTarget.current;
    if (!target) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting && !loadingRef.current && nextCursorRef.current) {
          loadCards(nextCursorRef.current);
        }
      },
      { threshold: 0.1, root: null }
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [loaded, hasMore, cards.length, loadCards]);

  const visibleCards = cards.filter(card => cardVerb(card) !== null);

  return (
    <Layout title="Pulse" description="What the Makapix Club community is up to">
      <div className="pulse-container">
        <h1 className="pulse-title">
          <span aria-hidden="true">🔥</span> Pulse
        </h1>
        <p className="pulse-subtitle">What the Club has been up to in the last 30 days.</p>

        {error && (
          <div className="pulse-state">
            <p>{error}</p>
            <button onClick={() => loadCards(cards.length ? nextCursorRef.current : null)} className="retry-button">
              Retry
            </button>
          </div>
        )}

        {visibleCards.length === 0 && (loading || !isAuthenticated) && !error && (
          <div className="pulse-state">
            <div className="loading-spinner"></div>
          </div>
        )}

        {visibleCards.length === 0 && loaded && !loading && !error && (
          <div className="pulse-state">
            <span className="empty-icon">🐣</span>
            <p>It&apos;s quiet right now. Like an artwork or post one to get things going!</p>
          </div>
        )}

        <ul className="pulse-list">
          {visibleCards.map(card => {
            const posts = card.posts ?? [];
            const comments = card.comments ?? [];
            const shown = posts.length || comments.length;
            const more = shown ? card.count - shown : 0;
            const profileHref = `/u/${card.actor.public_sqid}`;
            return (
              <li key={card.id} className="pulse-card">
                <div className="pulse-card-head">
                  <Link href={profileHref} className="pulse-avatar" aria-label={card.actor.handle}>
                    {card.actor.avatar_url ? (
                      <img src={card.actor.avatar_url} alt="" className="pixel-art" loading="lazy" />
                    ) : (
                      <span aria-hidden="true">👤</span>
                    )}
                  </Link>
                  <p className="pulse-summary">
                    <span className="pulse-kind-icon" aria-hidden="true">{KIND_ICON[card.kind]}</span>{' '}
                    <Link href={profileHref} className="pulse-handle">{card.actor.handle}</Link>{' '}
                    {cardVerb(card)}
                    {card.kind === 'reputation' && card.reputation && (
                      <span className="pulse-muted"> (now {card.reputation.total})</span>
                    )}
                  </p>
                  <time className="pulse-time" dateTime={card.updated_at} title={new Date(card.updated_at).toLocaleString()}>
                    {formatRelativeTime(card.updated_at)}
                  </time>
                </div>

                {posts.length > 0 && (
                  <div className="pulse-posts">
                    {posts.map(post => (
                      <Link
                        key={post.id}
                        href={`/p/${post.public_sqid}`}
                        className="pulse-post"
                        title={post.owner ? `${post.title} by ${post.owner.handle}` : post.title}
                      >
                        <img
                          src={ensureCompatibleArtUrl(post.art_url, post.frame_count)}
                          alt={post.title}
                          className="pixel-art"
                          loading="lazy"
                        />
                      </Link>
                    ))}
                    {more > 0 && <span className="pulse-more">+{more} more</span>}
                  </div>
                )}

                {comments.length > 0 && (
                  <ul className="pulse-comments">
                    {comments.map(comment => (
                      <li key={comment.id}>
                        <Link href={`/p/${comment.post.public_sqid}`} className="pulse-comment">
                          <img
                            src={ensureCompatibleArtUrl(comment.post.art_url, comment.post.frame_count)}
                            alt={comment.post.title}
                            className="pixel-art"
                            loading="lazy"
                          />
                          <span className="pulse-comment-text">
                            {comment.is_reply && <span className="pulse-muted">↳ </span>}
                            {comment.preview}
                          </span>
                        </Link>
                      </li>
                    ))}
                    {more > 0 && <li className="pulse-more">+{more} more</li>}
                  </ul>
                )}

                {card.badges && card.badges.length > 0 && (
                  <div className="pulse-badges">
                    {card.badges.map(badge => (
                      <span key={badge.badge} className="pulse-badge">
                        {badge.icon_url_64 && (
                          <img src={badge.icon_url_64} alt="" className="pixel-art" loading="lazy" />
                        )}
                        {badge.label}
                      </span>
                    ))}
                  </div>
                )}
              </li>
            );
          })}
        </ul>

        {visibleCards.length > 0 && (
          <div ref={observerTarget} className="load-more-trigger">
            {loading && <div className="loading-spinner"></div>}
            {!hasMore && <span className="end-message">✨</span>}
          </div>
        )}
      </div>

      <style jsx>{`
        .pulse-container {
          width: 100%;
          max-width: 720px;
          margin: 0 auto;
          padding: 16px 12px 120px;
          min-height: calc(100vh - var(--header-offset));
        }

        .pulse-title {
          font-size: 1.5rem;
          color: var(--text-primary);
          margin: 8px 0 4px;
        }

        .pulse-subtitle {
          color: var(--text-muted);
          font-size: 0.9rem;
          margin: 0 0 16px;
        }

        .pulse-list {
          list-style: none;
          margin: 0;
          padding: 0;
          display: flex;
          flex-direction: column;
          gap: 10px;
        }

        .pulse-card {
          background: var(--bg-card);
          border: 1px solid var(--bg-tertiary);
          border-radius: 10px;
          padding: 12px;
        }

        .pulse-card-head {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .pulse-card :global(a.pulse-avatar) {
          flex: 0 0 36px;
          width: 36px;
          height: 36px;
          border-radius: 6px;
          overflow: hidden;
          background: var(--bg-tertiary);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 18px;
        }

        .pulse-card :global(a.pulse-avatar img) {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }

        .pulse-summary {
          flex: 1;
          min-width: 0;
          margin: 0;
          color: var(--text-secondary);
          font-size: 0.95rem;
          line-height: 1.35;
          overflow-wrap: anywhere;
        }

        .pulse-card :global(a.pulse-handle) {
          color: var(--text-primary);
          font-weight: 600;
        }

        .pulse-card :global(a.pulse-handle:hover) {
          color: var(--accent-cyan);
        }

        .pulse-muted {
          color: var(--text-muted);
        }

        .pulse-time {
          flex: 0 0 auto;
          color: var(--text-muted);
          font-size: 0.8rem;
          white-space: nowrap;
        }

        .pulse-posts {
          display: flex;
          flex-wrap: wrap;
          align-items: center;
          gap: 6px;
          margin-top: 10px;
        }

        .pulse-posts :global(a.pulse-post) {
          width: 96px;
          height: 96px;
          background: var(--bg-primary);
          border-radius: 4px;
          overflow: hidden;
          display: flex;
          align-items: center;
          justify-content: center;
          outline: 2px solid transparent;
          transition: outline-color var(--transition-fast);
        }

        .pulse-posts :global(a.pulse-post:hover),
        .pulse-posts :global(a.pulse-post:focus-visible) {
          outline-color: var(--accent-cyan);
        }

        .pulse-posts :global(a.pulse-post img) {
          width: 100%;
          height: 100%;
          object-fit: contain;
        }

        .pulse-more {
          color: var(--text-muted);
          font-size: 0.85rem;
          padding: 0 6px;
          list-style: none;
        }

        .pulse-comments {
          list-style: none;
          margin: 10px 0 0;
          padding: 0;
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .pulse-comments :global(a.pulse-comment) {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 6px;
          border-radius: 6px;
          background: var(--bg-secondary);
          color: var(--text-primary);
          font-size: 0.9rem;
        }

        .pulse-comments :global(a.pulse-comment:hover) {
          background: var(--bg-tertiary);
        }

        .pulse-comments :global(a.pulse-comment img) {
          flex: 0 0 40px;
          width: 40px;
          height: 40px;
          object-fit: contain;
          background: var(--bg-primary);
          border-radius: 3px;
        }

        .pulse-comment-text {
          min-width: 0;
          overflow-wrap: anywhere;
        }

        .pulse-badges {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-top: 10px;
        }

        .pulse-badge {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 4px 8px;
          border-radius: 6px;
          background: var(--bg-secondary);
          color: var(--text-primary);
          font-size: 0.85rem;
        }

        .pulse-badge :global(img) {
          width: 24px;
          height: 24px;
        }

        .pulse-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 12px;
          padding: 4rem 2rem;
          text-align: center;
          color: var(--text-muted);
        }

        .empty-icon {
          font-size: 4rem;
        }

        .retry-button {
          padding: 0.75rem 1.5rem;
          background: var(--accent-cyan);
          color: var(--bg-primary);
          border-radius: 8px;
          font-weight: 600;
        }

        .load-more-trigger {
          min-height: 100px;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .loading-spinner {
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
        }

        @media (max-width: 480px) {
          .pulse-posts :global(a.pulse-post) {
            width: 72px;
            height: 72px;
          }
        }
      `}</style>
    </Layout>
  );
}
