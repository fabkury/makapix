import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Link from 'next/link';
import Layout from '../../../components/Layout';
import { authenticatedFetch } from '../../../lib/api';

interface ArtistStats {
  user_id: number;
  user_key: string;
  total_posts: number;
  total_views: number;
  unique_viewers: number;
  views_by_country: Record<string, number>;
  views_by_device: Record<string, number>;
  total_reactions: number;
  reactions_by_emoji: Record<string, number>;
  total_comments: number;
  total_views_authenticated: number;
  unique_viewers_authenticated: number;
  views_by_country_authenticated: Record<string, number>;
  views_by_device_authenticated: Record<string, number>;
  total_reactions_authenticated: number;
  reactions_by_emoji_authenticated: Record<string, number>;
  total_comments_authenticated: number;
  first_post_at: string | null;
  latest_post_at: string | null;
  computed_at: string;
}

interface PostStatsListItem {
  post_id: number;
  public_sqid: string;
  title: string;
  created_at: string;
  total_views: number;
  unique_viewers: number;
  total_reactions: number;
  total_comments: number;
  total_views_authenticated: number;
  unique_viewers_authenticated: number;
  total_reactions_authenticated: number;
  total_comments_authenticated: number;
}

interface ArtistDashboardResponse {
  artist_stats: ArtistStats;
  posts: PostStatsListItem[];
  total_posts: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export default function ArtistDashboard() {
  const router = useRouter();
  const { sqid } = router.query;

  const [dashboard, setDashboard] = useState<ArtistDashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [showAuthenticatedOnly, setShowAuthenticatedOnly] = useState(false);

  const API_BASE_URL = typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  useEffect(() => {
    if (!sqid || typeof sqid !== 'string') return;

    const fetchDashboard = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await authenticatedFetch(
          `${API_BASE_URL}/api/user/${sqid}/artist-dashboard?page=${page}&page_size=20`
        );

        if (!response.ok) {
          if (response.status === 401) {
            router.push('/auth');
            return;
          } else if (response.status === 403) {
            setError('You do not have permission to view this dashboard');
          } else if (response.status === 404) {
            setError('Artist not found');
          } else {
            setError('Failed to load dashboard');
          }
          setLoading(false);
          return;
        }

        const data = await response.json();
        setDashboard(data);
      } catch (err) {
        console.error('Error fetching dashboard:', err);
        setError('Failed to load dashboard');
      } finally {
        setLoading(false);
      }
    };

    fetchDashboard();
  }, [sqid, page, API_BASE_URL]);

  if (loading) {
    return (
      <Layout title="Artist Dashboard">
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
          @keyframes spin { to { transform: rotate(360deg); } }
        `}</style>
      </Layout>
    );
  }

  if (error || !dashboard) {
    return (
      <Layout title="Artist Dashboard">
        <div className="error-container">
          <span className="error-icon">😢</span>
          <h1>{error || 'Dashboard not found'}</h1>
          <Link href={`/u/${sqid}`} className="back-link">← Back to Profile</Link>
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

  const stats = showAuthenticatedOnly
    ? {
        total_views: dashboard.artist_stats.total_views_authenticated,
        unique_viewers: dashboard.artist_stats.unique_viewers_authenticated,
        views_by_country: dashboard.artist_stats.views_by_country_authenticated,
        views_by_device: dashboard.artist_stats.views_by_device_authenticated,
        total_reactions: dashboard.artist_stats.total_reactions_authenticated,
        reactions_by_emoji: dashboard.artist_stats.reactions_by_emoji_authenticated,
        total_comments: dashboard.artist_stats.total_comments_authenticated,
      }
    : {
        total_views: dashboard.artist_stats.total_views,
        unique_viewers: dashboard.artist_stats.unique_viewers,
        views_by_country: dashboard.artist_stats.views_by_country,
        views_by_device: dashboard.artist_stats.views_by_device,
        total_reactions: dashboard.artist_stats.total_reactions,
        reactions_by_emoji: dashboard.artist_stats.reactions_by_emoji,
        total_comments: dashboard.artist_stats.total_comments,
      };

  return (
    <Layout title="Artist Dashboard">
      <div className="dashboard-container">
        <div className="dashboard-header">
          <Link href={`/u/${sqid}`} className="back-link">
            ← Back to Profile
          </Link>
          <h1>Artist Dashboard</h1>
          <div className="filter-toggle">
            <label>
              <input
                type="checkbox"
                checked={showAuthenticatedOnly}
                onChange={(e) => setShowAuthenticatedOnly(e.target.checked)}
              />
              <span>Authenticated users only</span>
            </label>
          </div>
        </div>

        {/* Summary Statistics */}
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-value">{dashboard.artist_stats.total_posts}</div>
            <div className="stat-label">Total Posts</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.total_views.toLocaleString()}</div>
            <div className="stat-label">Total Views</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.unique_viewers.toLocaleString()}</div>
            <div className="stat-label">Unique Viewers</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.total_reactions.toLocaleString()}</div>
            <div className="stat-label">Total Reactions</div>
          </div>
          <div className="stat-card">
            <div className="stat-value">{stats.total_comments.toLocaleString()}</div>
            <div className="stat-label">Total Comments</div>
          </div>
        </div>

        {/* Views by Country */}
        {Object.keys(stats.views_by_country).length > 0 && (
          <div className="breakdown-section">
            <h2>Views by Country</h2>
            <div className="breakdown-list">
              {Object.entries(stats.views_by_country)
                .sort(([, a], [, b]) => b - a)
                .map(([country, count]) => (
                  <div key={country} className="breakdown-item">
                    <span className="breakdown-label">{country}</span>
                    <span className="breakdown-value">{count.toLocaleString()}</span>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Views by Device */}
        {Object.keys(stats.views_by_device).length > 0 && (
          <div className="breakdown-section">
            <h2>Views by Device</h2>
            <div className="breakdown-list">
              {Object.entries(stats.views_by_device)
                .sort(([, a], [, b]) => b - a)
                .map(([device, count]) => (
                  <div key={device} className="breakdown-item">
                    <span className="breakdown-label">{device}</span>
                    <span className="breakdown-value">{count.toLocaleString()}</span>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Reactions by Emoji */}
        {Object.keys(stats.reactions_by_emoji).length > 0 && (
          <div className="breakdown-section">
            <h2>Reactions by Emoji</h2>
            <div className="breakdown-list">
              {Object.entries(stats.reactions_by_emoji)
                .sort(([, a], [, b]) => b - a)
                .slice(0, 10)
                .map(([emoji, count]) => (
                  <div key={emoji} className="breakdown-item">
                    <span className="breakdown-label">{emoji}</span>
                    <span className="breakdown-value">{count.toLocaleString()}</span>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Post Statistics List */}
        <div className="posts-section">
          <h2>Post Statistics</h2>
          <div className="posts-table">
            <div className="table-header">
              <div className="col-title">Post</div>
              <div className="col-stat">Views</div>
              <div className="col-stat">Unique</div>
              <div className="col-stat">Reactions</div>
              <div className="col-stat">Comments</div>
            </div>
            {dashboard.posts.map((post) => {
              const postStats = showAuthenticatedOnly
                ? {
                    views: post.total_views_authenticated,
                    unique: post.unique_viewers_authenticated,
                    reactions: post.total_reactions_authenticated,
                    comments: post.total_comments_authenticated,
                  }
                : {
                    views: post.total_views,
                    unique: post.unique_viewers,
                    reactions: post.total_reactions,
                    comments: post.total_comments,
                  };

              return (
                <div key={post.post_id} className="table-row">
                  <div className="col-title">
                    <Link href={`/p/${post.public_sqid}`} className="post-link">
                      {post.title}
                    </Link>
                    <div className="post-date">
                      {new Date(post.created_at).toLocaleDateString()}
                    </div>
                  </div>
                  <div className="col-stat" data-label="Views:">{postStats.views.toLocaleString()}</div>
                  <div className="col-stat" data-label="Unique:">{postStats.unique.toLocaleString()}</div>
                  <div className="col-stat" data-label="Reactions:">{postStats.reactions.toLocaleString()}</div>
                  <div className="col-stat" data-label="Comments:">{postStats.comments.toLocaleString()}</div>
                </div>
              );
            })}
          </div>

          {/* Pagination */}
          {(page > 1 || dashboard.has_more) && (
            <div className="pagination">
              {page > 1 && (
                <button
                  className="pagination-btn"
                  onClick={() => setPage(page - 1)}
                >
                  ← Previous
                </button>
              )}
              <span className="page-info">
                Page {page} of {Math.ceil(dashboard.total_posts / dashboard.page_size)}
              </span>
              {dashboard.has_more && (
                <button
                  className="pagination-btn"
                  onClick={() => setPage(page + 1)}
                >
                  Next →
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      <style jsx>{`
        .dashboard-container {
          max-width: 1200px;
          margin: 0 auto;
          padding: 24px;
        }

        .dashboard-header {
          margin-bottom: 32px;
        }

        .back-link {
          display: inline-block;
          color: var(--accent-cyan);
          margin-bottom: 16px;
          font-size: 0.9rem;
        }

        h1 {
          font-size: 2rem;
          color: var(--text-primary);
          margin-bottom: 16px;
        }

        h2 {
          font-size: 1.3rem;
          color: var(--text-primary);
          margin-bottom: 16px;
        }

        .filter-toggle {
          margin-top: 16px;
        }

        .filter-toggle label {
          display: flex;
          align-items: center;
          gap: 8px;
          cursor: pointer;
          font-size: 0.9rem;
          color: var(--text-secondary);
        }

        .filter-toggle input[type="checkbox"] {
          cursor: pointer;
        }

        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 16px;
          margin-bottom: 32px;
        }

        .stat-card {
          background: var(--bg-secondary);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          padding: 24px;
          text-align: center;
        }

        .stat-value {
          font-size: 2rem;
          font-weight: bold;
          color: var(--accent-cyan);
          margin-bottom: 8px;
        }

        .stat-label {
          font-size: 0.9rem;
          color: var(--text-secondary);
        }

        .breakdown-section {
          background: var(--bg-secondary);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          padding: 24px;
          margin-bottom: 24px;
        }

        .breakdown-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .breakdown-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 8px 12px;
          background: var(--bg-tertiary);
          border-radius: 4px;
        }

        .breakdown-label {
          font-size: 0.95rem;
          color: var(--text-primary);
          text-transform: capitalize;
        }

        .breakdown-value {
          font-size: 0.95rem;
          font-weight: 600;
          color: var(--accent-cyan);
        }

        .posts-section {
          background: var(--bg-secondary);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 8px;
          padding: 24px;
        }

        .posts-table {
          width: 100%;
          overflow-x: auto;
        }

        .table-header,
        .table-row {
          display: grid;
          grid-template-columns: 2fr 1fr 1fr 1fr 1fr;
          gap: 16px;
          padding: 12px 0;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .table-header {
          font-weight: 600;
          color: var(--text-secondary);
          font-size: 0.85rem;
          text-transform: uppercase;
        }

        .table-row:hover {
          background: var(--bg-tertiary);
        }

        .col-title {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .post-link {
          color: var(--text-primary);
          text-decoration: none;
          font-weight: 500;
        }

        .post-link:hover {
          color: var(--accent-cyan);
        }

        .post-date {
          font-size: 0.8rem;
          color: var(--text-secondary);
        }

        .col-stat {
          text-align: right;
          color: var(--text-primary);
        }

        .pagination {
          display: flex;
          justify-content: center;
          align-items: center;
          gap: 16px;
          margin-top: 24px;
        }

        .pagination-btn {
          padding: 8px 16px;
          background: var(--bg-tertiary);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 4px;
          color: var(--text-primary);
          cursor: pointer;
          font-size: 0.9rem;
        }

        .pagination-btn:hover {
          background: var(--bg-primary);
          border-color: var(--accent-cyan);
        }

        .page-info {
          color: var(--text-secondary);
          font-size: 0.9rem;
        }

        @media (max-width: 768px) {
          .stats-grid {
            grid-template-columns: repeat(2, 1fr);
          }

          .table-header,
          .table-row {
            grid-template-columns: 2fr 1fr 1fr 1fr 1fr;
            font-size: 0.85rem;
            gap: 8px;
          }

          .col-stat {
            font-size: 0.85rem;
          }
        }

        @media (max-width: 480px) {
          .stats-grid {
            grid-template-columns: 1fr;
          }

          .table-header,
          .table-row {
            grid-template-columns: 1fr;
            gap: 4px;
          }

          .table-header {
            display: none;
          }

          .col-stat::before {
            content: attr(data-label);
            font-weight: 600;
            margin-right: 8px;
          }
        }
      `}</style>
    </Layout>
  );
}
