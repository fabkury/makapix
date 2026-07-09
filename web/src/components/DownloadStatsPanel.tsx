import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { authenticatedFetch } from '../lib/api';
import { ensureCompatibleArtUrl } from '../utils/imageCompat';

interface DailyCount {
  date: string;
  count: number;
}

interface DownloadStatsSummary {
  total_downloads: number;
  unique_artworks: number;
  avg_per_artwork: number;
}

interface TopArtworkRow {
  post_id: number;
  public_sqid: string | null;
  title: string;
  art_url: string | null;
  owner_handle: string;
  downloads: number;
}

interface DownloadStats {
  window_days: number;
  include_bots: boolean;
  summary: DownloadStatsSummary;
  daily_downloads: DailyCount[];
  top_artworks: TopArtworkRow[];
  computed_at: string;
}

export default function DownloadStatsPanel() {
  const [stats, setStats] = useState<DownloadStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [includeBots, setIncludeBots] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const API_BASE_URL = typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  const fetchStats = useCallback(async (opts: { refresh?: boolean } = {}) => {
    const params = new URLSearchParams({
      days: '14',
      top_n: '50',
      include_bots: includeBots ? 'true' : 'false',
    });
    if (opts.refresh) params.set('refresh', 'true');

    try {
      const response = await authenticatedFetch(
        `${API_BASE_URL}/api/admin/download-stats?${params.toString()}`,
      );

      if (response.status === 401) {
        setError('Authentication required');
        return;
      }
      if (!response.ok) {
        setError(
          response.status === 403
            ? "You don't have permission to view download stats"
            : 'Failed to load download stats',
        );
        return;
      }
      const data = (await response.json()) as DownloadStats;
      setStats(data);
      setError(null);
    } catch (err) {
      console.error('Error fetching download stats:', err);
      setError('Failed to load download stats');
    }
  }, [API_BASE_URL, includeBots]);

  useEffect(() => {
    setLoading(true);
    fetchStats().finally(() => setLoading(false));
  }, [fetchStats]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await fetchStats({ refresh: true });
    } finally {
      setIsRefreshing(false);
    }
  };

  if (loading) {
    return (
      <div className="metrics-loading">
        <div className="loading-spinner" />
        <div>Loading download stats…</div>
      </div>
    );
  }

  if (error || !stats) {
    return (
      <div className="metrics-error">
        <div className="error-icon">⚠️</div>
        <div>{error || 'No data'}</div>
      </div>
    );
  }

  const maxDaily = Math.max(...stats.daily_downloads.map(d => d.count), 1);

  return (
    <div className="download-stats">
      {/* Toggle */}
      <div className="metrics-toggle">
        <label className="toggle-label">
          <input
            type="checkbox"
            checked={includeBots}
            onChange={(e) => setIncludeBots(e.target.checked)}
          />
          <span>
            {includeBots
              ? 'Including bot/crawler downloads in totals'
              : 'Showing human downloads only (bots filtered)'}
          </span>
        </label>
      </div>

      {/* Caveat banner */}
      <div className="caveat">
        ℹ️ Vault responses set <code>Cache-Control: immutable</code>, so each
        browser cache fills exactly once per artwork. &ldquo;Downloads&rdquo;
        here counts cache-fills, not page views.
      </div>

      {/* Summary KPIs */}
      <div className="metrics-summary">
        <div className="metric-card">
          <div className="metric-value">{stats.summary.total_downloads.toLocaleString()}</div>
          <div className="metric-label">Total Downloads ({stats.window_days}d)</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{stats.summary.unique_artworks.toLocaleString()}</div>
          <div className="metric-label">Unique Artworks Downloaded</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">
            {stats.summary.unique_artworks > 0
              ? stats.summary.avg_per_artwork.toFixed(1)
              : '—'}
          </div>
          <div className="metric-label">Avg / Artwork</div>
        </div>
      </div>

      {/* Daily trend chart */}
      <div className="metrics-section">
        <h3>📈 Downloads (Last {stats.window_days} Days)</h3>
        <div className="trend-chart">
          {stats.daily_downloads.map((day, index) => {
            const height = (day.count / maxDaily) * 100;
            const date = new Date(day.date);
            const isWeekend = date.getDay() === 0 || date.getDay() === 6;
            const showLabel =
              index % 3 === 0 ||
              index === stats.daily_downloads.length - 1 ||
              day.count === maxDaily;
            return (
              <div key={day.date} className="trend-bar-wrap">
                {showLabel && (
                  <span className="trend-bar-label" aria-hidden="true">
                    {day.count.toLocaleString()}
                  </span>
                )}
                <div
                  className={`trend-bar ${isWeekend ? 'weekend' : ''}`}
                  style={{ height: `${Math.max(height, 2)}%` }}
                  title={`${day.date}: ${day.count} downloads`}
                  aria-label={`${day.date}: ${day.count} downloads`}
                  role="img"
                />
              </div>
            );
          })}
        </div>
        <div className="trend-labels">
          <span>{stats.window_days} days ago</span>
          <span>Today</span>
        </div>
      </div>

      {/* Top artworks table */}
      <div className="metrics-section">
        <h3>🏆 Top Downloaded Artworks</h3>
        {stats.top_artworks.length === 0 ? (
          <div className="empty">
            No downloads recorded yet in this window. The rollup runs daily —
            check back tomorrow.
          </div>
        ) : (
          <div className="table-scroll">
          <table className="top-table">
            <thead>
              <tr>
                <th className="rank-col">#</th>
                <th className="thumb-col"></th>
                <th>Title</th>
                <th>Artist</th>
                <th className="downloads-col">Downloads</th>
              </tr>
            </thead>
            <tbody>
              {stats.top_artworks.map((row, idx) => (
                <tr key={row.post_id}>
                  <td className="rank-col">{idx + 1}</td>
                  <td className="thumb-col">
                    {row.art_url ? (
                      <img
                        src={ensureCompatibleArtUrl(row.art_url)}
                        alt=""
                        width={40}
                        height={40}
                        loading="lazy"
                      />
                    ) : null}
                  </td>
                  <td>
                    {row.public_sqid ? (
                      <Link href={`/p/${row.public_sqid}`}>{row.title}</Link>
                    ) : (
                      <span>{row.title}</span>
                    )}
                  </td>
                  <td>
                    <Link href={`/u/${row.owner_handle}`}>@{row.owner_handle}</Link>
                  </td>
                  <td className="downloads-col">{row.downloads.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        )}
      </div>

      <div className="metrics-footer">
        <span>Last updated: {new Date(stats.computed_at).toLocaleString()}</span>
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="refresh-link"
          title="Cache is refreshed every 5 minutes; click here to refresh it now"
        >
          {isRefreshing ? 'Refreshing…' : 'Refresh cache'}
        </button>
      </div>

      <style jsx>{`
        .download-stats { padding: 24px; }

        .metrics-toggle {
          margin-bottom: 16px;
          padding: 12px;
          background: var(--bg-secondary, #1a1a2e);
          border-radius: 8px;
        }
        .toggle-label {
          display: flex;
          align-items: center;
          cursor: pointer;
          font-size: 0.9rem;
          color: var(--text-secondary, #ccc);
        }
        .toggle-label > :global(* + *) { margin-left: 8px; }
        .toggle-label input[type="checkbox"] {
          cursor: pointer;
          width: 18px;
          height: 18px;
        }

        .caveat {
          margin-bottom: 24px;
          padding: 10px 14px;
          background: var(--bg-tertiary, #2a2a3e);
          border-left: 3px solid var(--accent-purple, #b44eff);
          border-radius: 6px;
          color: var(--text-secondary, #ccc);
          font-size: 0.85rem;
          line-height: 1.5;
        }
        .caveat code {
          background: rgba(255, 255, 255, 0.08);
          padding: 1px 6px;
          border-radius: 4px;
          font-size: 0.8rem;
        }

        .metrics-loading,
        .metrics-error {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 60px 24px;
          color: var(--text-muted, #888);
        }
        .loading-spinner {
          width: 40px;
          height: 40px;
          border: 3px solid var(--bg-tertiary, #2a2a3e);
          border-top-color: var(--accent-cyan, #4ecdc4);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
          margin-bottom: 16px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .error-icon { font-size: 2rem; margin-bottom: 12px; }

        .metrics-summary {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 12px;
          margin-bottom: 24px;
        }
        @media (max-width: 640px) {
          .metrics-summary { grid-template-columns: 1fr; }
        }
        .metric-card {
          background: var(--bg-secondary, #1a1a2e);
          border-radius: 12px;
          padding: 16px;
          text-align: center;
        }
        .metric-value {
          font-size: 1.5rem;
          font-weight: 700;
          color: var(--accent-cyan, #4ecdc4);
          margin-bottom: 4px;
        }
        .metric-label {
          font-size: 0.75rem;
          color: var(--text-muted, #888);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .metrics-section { margin-bottom: 32px; }
        .metrics-section h3 {
          font-size: 1rem;
          font-weight: 600;
          color: var(--text-primary, #fff);
          margin-bottom: 12px;
        }

        .trend-chart {
          display: flex;
          align-items: flex-end;
          height: 110px;
          background: var(--bg-tertiary, #2a2a3e);
          border-radius: 8px;
          padding: 16px 8px 12px;
          gap: 4px;
        }
        .trend-bar-wrap {
          flex: 1;
          height: 100%;
          display: flex;
          flex-direction: column;
          justify-content: flex-end;
          align-items: center;
          position: relative;
        }
        .trend-bar-label {
          position: absolute;
          top: -2px;
          font-size: 0.65rem;
          color: var(--text-muted, #888);
        }
        .trend-bar {
          width: 100%;
          background: linear-gradient(to top, var(--accent-purple, #b44eff), var(--accent-cyan, #4ecdc4));
          border-radius: 3px 3px 0 0;
          transition: height 0.3s ease;
        }
        .trend-bar.weekend { opacity: 0.75; }
        .trend-labels {
          display: flex;
          justify-content: space-between;
          margin-top: 6px;
          font-size: 0.7rem;
          color: var(--text-muted, #888);
        }

        .empty {
          padding: 32px;
          text-align: center;
          color: var(--text-muted, #888);
          background: var(--bg-tertiary, #2a2a3e);
          border-radius: 8px;
        }

        .table-scroll {
          overflow-x: auto;
          -webkit-overflow-scrolling: touch;
          border-radius: 8px;
        }
        .top-table {
          width: 100%;
          border-collapse: collapse;
          background: var(--bg-secondary, #1a1a2e);
        }
        .top-table th,
        .top-table td {
          padding: 8px 12px;
          text-align: left;
          border-bottom: 1px solid var(--bg-tertiary, #2a2a3e);
        }
        .top-table thead th {
          background: var(--bg-tertiary, #2a2a3e);
          font-size: 0.75rem;
          color: var(--text-muted, #888);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .top-table .rank-col { width: 36px; color: var(--text-muted, #888); }
        .top-table .thumb-col { width: 48px; }
        .top-table .thumb-col img {
          display: block;
          width: 40px;
          height: 40px;
          object-fit: cover;
          background: var(--bg-tertiary, #2a2a3e);
          image-rendering: pixelated;
          border-radius: 4px;
        }
        .top-table .downloads-col {
          text-align: right;
          font-variant-numeric: tabular-nums;
          color: var(--accent-cyan, #4ecdc4);
          font-weight: 600;
        }
        .top-table tr:last-child td { border-bottom: 0; }
        .top-table a {
          color: var(--text-primary, #fff);
          text-decoration: none;
        }
        .top-table a:hover { color: var(--accent-cyan, #4ecdc4); }

        .metrics-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-top: 24px;
          padding-top: 16px;
          border-top: 1px solid var(--bg-tertiary, #2a2a3e);
          font-size: 0.8rem;
          color: var(--text-muted, #888);
        }
        .refresh-link {
          background: none;
          border: 0;
          color: var(--accent-cyan, #4ecdc4);
          cursor: pointer;
          font-size: 0.85rem;
          padding: 0;
        }
        .refresh-link:hover:not(:disabled) { text-decoration: underline; }
        .refresh-link:disabled { opacity: 0.5; cursor: not-allowed; }
      `}</style>
    </div>
  );
}
