import { useState, useEffect, useMemo } from 'react';

interface DailyViewCount {
  date: string;
  views: number;
  unique_viewers: number;
}

interface PostStats {
  post_id: string;
  // All statistics (including unauthenticated)
  total_views: number;
  unique_viewers: number;
  views_by_country: Record<string, number>;
  views_by_device: Record<string, number>;
  views_by_type: Record<string, number>;
  daily_views: DailyViewCount[];
  total_reactions: number;
  reactions_by_emoji: Record<string, number>;
  total_comments: number;
  // Authenticated-only statistics
  total_views_authenticated: number;
  unique_viewers_authenticated: number;
  views_by_country_authenticated: Record<string, number>;
  views_by_device_authenticated: Record<string, number>;
  views_by_type_authenticated: Record<string, number>;
  daily_views_authenticated: DailyViewCount[];
  total_reactions_authenticated: number;
  reactions_by_emoji_authenticated: Record<string, number>;
  total_comments_authenticated: number;
  // Timestamps
  first_view_at: string | null;
  last_view_at: string | null;
  computed_at: string;
}

interface StatsPanelProps {
  postId: string;
  isOpen: boolean;
  onClose: () => void;
}

// Country code to name mapping (common countries)
const COUNTRY_NAMES: Record<string, string> = {
  US: 'United States',
  BR: 'Brazil',
  GB: 'United Kingdom',
  DE: 'Germany',
  FR: 'France',
  CA: 'Canada',
  AU: 'Australia',
  JP: 'Japan',
  IN: 'India',
  MX: 'Mexico',
  ES: 'Spain',
  IT: 'Italy',
  NL: 'Netherlands',
  PL: 'Poland',
  RU: 'Russia',
  KR: 'South Korea',
  CN: 'China',
  AR: 'Argentina',
  SE: 'Sweden',
  PT: 'Portugal',
};

// Device type labels
const DEVICE_LABELS: Record<string, string> = {
  desktop: '💻 Desktop',
  mobile: '📱 Mobile',
  tablet: '📱 Tablet',
  player: '🖼️ Player',
};

// View type labels
const VIEW_TYPE_LABELS: Record<string, string> = {
  intentional: '👆 Direct Click',
  listing: '📜 Feed/List',
  search: '🔍 Search',
  widget: '🧩 Widget',
};

export default function StatsPanel({ postId, isOpen, onClose }: StatsPanelProps) {
  const [stats, setStats] = useState<PostStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [includeUnauthenticated, setIncludeUnauthenticated] = useState(true);

  const API_BASE_URL = typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost')
    : '';

  useEffect(() => {
    if (!isOpen || !postId) return;

    const fetchStats = async () => {
      setLoading(true);
      setError(null);

      try {
        const accessToken = localStorage.getItem('access_token');
        if (!accessToken) {
          setError('Authentication required');
          setLoading(false);
          return;
        }

        const response = await fetch(`${API_BASE_URL}/api/posts/${postId}/stats`, {
          headers: {
            'Authorization': `Bearer ${accessToken}`,
          },
        });

        if (!response.ok) {
          if (response.status === 403) {
            setError('You don\'t have permission to view these statistics');
          } else if (response.status === 404) {
            setError('Post not found');
          } else {
            setError('Failed to load statistics');
          }
          setLoading(false);
          return;
        }

        const data = await response.json();
        setStats(data);
      } catch (err) {
        console.error('Error fetching stats:', err);
        setError('Failed to load statistics');
      } finally {
        setLoading(false);
      }
    };

    fetchStats();
  }, [isOpen, postId, API_BASE_URL]);

  // Compute displayed stats based on toggle
  const displayedStats = useMemo(() => {
    if (!stats) return null;
    
    if (includeUnauthenticated) {
      // Show all statistics (including unauthenticated)
      return {
        total_views: stats.total_views,
        unique_viewers: stats.unique_viewers,
        views_by_country: stats.views_by_country,
        views_by_device: stats.views_by_device,
        views_by_type: stats.views_by_type,
        daily_views: stats.daily_views,
        total_reactions: stats.total_reactions,
        reactions_by_emoji: stats.reactions_by_emoji,
        total_comments: stats.total_comments,
      };
    } else {
      // Show authenticated-only statistics
      return {
        total_views: stats.total_views_authenticated,
        unique_viewers: stats.unique_viewers_authenticated,
        views_by_country: stats.views_by_country_authenticated,
        views_by_device: stats.views_by_device_authenticated,
        views_by_type: stats.views_by_type_authenticated,
        daily_views: stats.daily_views_authenticated,
        total_reactions: stats.total_reactions_authenticated,
        reactions_by_emoji: stats.reactions_by_emoji_authenticated,
        total_comments: stats.total_comments_authenticated,
      };
    }
  }, [stats, includeUnauthenticated]);

  if (!isOpen) return null;

  // Calculate max values for bar charts
  const maxDailyViews = displayedStats ? Math.max(...displayedStats.daily_views.map(d => d.views), 1) : 1;
  const maxCountryViews = displayedStats ? Math.max(...Object.values(displayedStats.views_by_country), 1) : 1;

  return (
    <div className="stats-overlay" onClick={onClose}>
      <div className="stats-panel" onClick={(e) => e.stopPropagation()}>
        <div className="stats-header">
          <h2>📊 Artwork Statistics</h2>
          <button className="close-button" onClick={onClose}>×</button>
        </div>

        {stats && !loading && !error && (
          <div className="stats-toggle">
            <label className="toggle-label">
              <input
                type="checkbox"
                checked={includeUnauthenticated}
                onChange={(e) => setIncludeUnauthenticated(e.target.checked)}
              />
              <span>{includeUnauthenticated ? 'Showing all statistics (including unauthenticated)' : 'Showing authenticated-only statistics'}</span>
            </label>
          </div>
        )}

        {loading && (
          <div className="stats-loading">
            <div className="loading-spinner"></div>
            <p>Loading statistics...</p>
          </div>
        )}

        {error && (
          <div className="stats-error">
            <span className="error-icon">⚠️</span>
            <p>{error}</p>
          </div>
        )}

        {displayedStats && !loading && !error && (
          <div className="stats-content">
            {/* Summary Cards */}
            <div className="stats-summary">
              <div className="stat-card">
                <div className="stat-value">{displayedStats.total_views.toLocaleString()}</div>
                <div className="stat-label">Total Views</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{displayedStats.unique_viewers.toLocaleString()}</div>
                <div className="stat-label">Unique Visitors</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{displayedStats.total_reactions.toLocaleString()}</div>
                <div className="stat-label">Reactions</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{displayedStats.total_comments.toLocaleString()}</div>
                <div className="stat-label">Comments</div>
              </div>
            </div>

            {/* 30-Day Trend Chart */}
            <div className="stats-section">
              <h3>📈 Views (Last 30 Days)</h3>
              <div className="trend-chart">
                {displayedStats.daily_views.map((day, index) => {
                  const height = maxDailyViews > 0 ? (day.views / maxDailyViews) * 100 : 0;
                  const date = new Date(day.date);
                  const isWeekend = date.getDay() === 0 || date.getDay() === 6;
                  return (
                    <div
                      key={day.date}
                      className={`trend-bar ${isWeekend ? 'weekend' : ''}`}
                      style={{ height: `${Math.max(height, 2)}%` }}
                      title={`${day.date}: ${day.views} views, ${day.unique_viewers} unique`}
                    />
                  );
                })}
              </div>
              <div className="trend-labels">
                <span>30 days ago</span>
                <span>Today</span>
              </div>
            </div>

            {/* Country Breakdown */}
            {Object.keys(displayedStats.views_by_country).length > 0 && (
              <div className="stats-section">
                <h3>🌍 Top Countries</h3>
                <div className="breakdown-list">
                  {Object.entries(displayedStats.views_by_country)
                    .sort(([, a], [, b]) => b - a)
                    .slice(0, 10)
                    .map(([country, count]) => (
                      <div key={country} className="breakdown-item">
                        <div className="breakdown-label">
                          <span className="country-flag">{getCountryFlag(country)}</span>
                          <span>{COUNTRY_NAMES[country] || country}</span>
                        </div>
                        <div className="breakdown-bar-container">
                          <div
                            className="breakdown-bar country-bar"
                            style={{ width: `${(count / maxCountryViews) * 100}%` }}
                          />
                        </div>
                        <div className="breakdown-value">{count.toLocaleString()}</div>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* Device Breakdown */}
            {Object.keys(displayedStats.views_by_device).length > 0 && (
              <div className="stats-section">
                <h3>📱 Devices</h3>
                <div className="device-grid">
                  {Object.entries(displayedStats.views_by_device)
                    .sort(([, a], [, b]) => b - a)
                    .map(([device, count]) => {
                      const percentage = displayedStats.total_views > 0
                        ? Math.round((count / displayedStats.total_views) * 100)
                        : 0;
                      return (
                        <div key={device} className="device-item">
                          <div className="device-label">{DEVICE_LABELS[device] || device}</div>
                          <div className="device-value">{percentage}%</div>
                          <div className="device-count">{count.toLocaleString()} views</div>
                        </div>
                      );
                    })}
                </div>
              </div>
            )}

            {/* View Type Breakdown */}
            {Object.keys(displayedStats.views_by_type).length > 0 && (
              <div className="stats-section">
                <h3>👁️ View Sources</h3>
                <div className="type-breakdown">
                  {Object.entries(displayedStats.views_by_type)
                    .sort(([, a], [, b]) => b - a)
                    .map(([type, count]) => {
                      const percentage = displayedStats.total_views > 0
                        ? Math.round((count / displayedStats.total_views) * 100)
                        : 0;
                      return (
                        <div key={type} className="type-item">
                          <div className="type-label">{VIEW_TYPE_LABELS[type] || type}</div>
                          <div className="type-bar-container">
                            <div
                              className="type-bar"
                              style={{ width: `${percentage}%` }}
                            />
                          </div>
                          <div className="type-value">{percentage}%</div>
                        </div>
                      );
                    })}
                </div>
              </div>
            )}

            {/* Reactions Breakdown */}
            {displayedStats.total_reactions > 0 && Object.keys(displayedStats.reactions_by_emoji).length > 0 && (
              <div className="stats-section">
                <h3>❤️ Reactions</h3>
                <div className="reactions-grid">
                  {Object.entries(displayedStats.reactions_by_emoji)
                    .sort(([, a], [, b]) => b - a)
                    .map(([emoji, count]) => (
                      <div key={emoji} className="reaction-item">
                        <span className="reaction-emoji">{emoji}</span>
                        <span className="reaction-count">{count}</span>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* Footer */}
            <div className="stats-footer">
              <span>Last updated: {new Date(stats.computed_at).toLocaleString()}</span>
              {stats.first_view_at && (
                <span>First view: {new Date(stats.first_view_at).toLocaleString()}</span>
              )}
            </div>
          </div>
        )}
      </div>

      <style jsx>{`
        .stats-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.8);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          padding: 20px;
          backdrop-filter: blur(4px);
        }

        .stats-panel {
          background: var(--bg-secondary, #1a1a2e);
          border-radius: 16px;
          width: 100%;
          max-width: 600px;
          max-height: 90vh;
          overflow: hidden;
          display: flex;
          flex-direction: column;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
          border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .stats-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 20px 24px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.1);
          background: linear-gradient(135deg, rgba(180, 78, 255, 0.1), rgba(78, 159, 255, 0.1));
        }

        .stats-header h2 {
          font-size: 1.25rem;
          font-weight: 600;
          color: var(--text-primary, #fff);
          margin: 0;
        }

        .close-button {
          background: transparent;
          border: none;
          color: var(--text-muted, #888);
          font-size: 1.5rem;
          cursor: pointer;
          padding: 4px 8px;
          border-radius: 4px;
          transition: all 0.2s;
        }

        .close-button:hover {
          background: rgba(255, 255, 255, 0.1);
          color: var(--text-primary, #fff);
        }

        .stats-toggle {
          padding: 16px 24px;
          border-bottom: 1px solid var(--bg-tertiary, #2a2a3e);
          background: var(--bg-secondary, #1e1e2e);
        }

        .toggle-label {
          display: flex;
          align-items: center;
          gap: 12px;
          cursor: pointer;
          color: var(--text-secondary, #ccc);
          font-size: 0.9rem;
          user-select: none;
        }

        .toggle-label input[type="checkbox"] {
          width: 18px;
          height: 18px;
          cursor: pointer;
          accent-color: var(--accent-cyan, #4ecdc4);
        }

        .toggle-label span {
          flex: 1;
        }

        .stats-content {
          padding: 24px;
          overflow-y: auto;
          flex: 1;
        }

        .stats-loading,
        .stats-error {
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

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .error-icon {
          font-size: 2rem;
          margin-bottom: 12px;
        }

        .stats-summary {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
          margin-bottom: 24px;
        }

        @media (min-width: 480px) {
          .stats-summary {
            grid-template-columns: repeat(4, 1fr);
          }
        }

        .stat-card {
          background: var(--bg-tertiary, #2a2a3e);
          border-radius: 12px;
          padding: 16px;
          text-align: center;
        }

        .stat-value {
          font-size: 1.5rem;
          font-weight: 700;
          color: var(--accent-cyan, #4ecdc4);
          margin-bottom: 4px;
        }

        .stat-label {
          font-size: 0.75rem;
          color: var(--text-muted, #888);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }

        .stats-section {
          margin-bottom: 24px;
        }

        .stats-section h3 {
          font-size: 0.9rem;
          font-weight: 600;
          color: var(--text-secondary, #ccc);
          margin-bottom: 12px;
        }

        .trend-chart {
          display: flex;
          align-items: flex-end;
          gap: 2px;
          height: 80px;
          background: var(--bg-tertiary, #2a2a3e);
          border-radius: 8px;
          padding: 12px 8px;
        }

        .trend-bar {
          flex: 1;
          background: linear-gradient(to top, var(--accent-purple, #b44eff), var(--accent-cyan, #4ecdc4));
          border-radius: 2px 2px 0 0;
          min-height: 2px;
          cursor: pointer;
          transition: opacity 0.2s;
        }

        .trend-bar.weekend {
          opacity: 0.6;
        }

        .trend-bar:hover {
          opacity: 1;
          box-shadow: 0 0 8px var(--accent-cyan, #4ecdc4);
        }

        .trend-labels {
          display: flex;
          justify-content: space-between;
          font-size: 0.7rem;
          color: var(--text-muted, #888);
          margin-top: 8px;
        }

        .breakdown-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .breakdown-item {
          display: grid;
          grid-template-columns: 140px 1fr 60px;
          align-items: center;
          gap: 12px;
        }

        .breakdown-label {
          display: flex;
          align-items: center;
          gap: 8px;
          font-size: 0.85rem;
          color: var(--text-secondary, #ccc);
        }

        .country-flag {
          font-size: 1.1rem;
        }

        .breakdown-bar-container {
          height: 8px;
          background: var(--bg-tertiary, #2a2a3e);
          border-radius: 4px;
          overflow: hidden;
        }

        .breakdown-bar {
          height: 100%;
          border-radius: 4px;
          transition: width 0.3s ease;
        }

        .country-bar {
          background: linear-gradient(to right, var(--accent-purple, #b44eff), var(--accent-pink, #ff6b9d));
        }

        .breakdown-value {
          text-align: right;
          font-size: 0.85rem;
          font-weight: 600;
          color: var(--text-primary, #fff);
        }

        .device-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
        }

        .device-item {
          background: var(--bg-tertiary, #2a2a3e);
          border-radius: 8px;
          padding: 12px;
          text-align: center;
        }

        .device-label {
          font-size: 0.85rem;
          color: var(--text-secondary, #ccc);
          margin-bottom: 4px;
        }

        .device-value {
          font-size: 1.5rem;
          font-weight: 700;
          color: var(--accent-cyan, #4ecdc4);
        }

        .device-count {
          font-size: 0.75rem;
          color: var(--text-muted, #888);
        }

        .type-breakdown {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .type-item {
          display: grid;
          grid-template-columns: 120px 1fr 50px;
          align-items: center;
          gap: 12px;
        }

        .type-label {
          font-size: 0.85rem;
          color: var(--text-secondary, #ccc);
        }

        .type-bar-container {
          height: 8px;
          background: var(--bg-tertiary, #2a2a3e);
          border-radius: 4px;
          overflow: hidden;
        }

        .type-bar {
          height: 100%;
          background: linear-gradient(to right, var(--accent-cyan, #4ecdc4), var(--accent-purple, #b44eff));
          border-radius: 4px;
          transition: width 0.3s ease;
        }

        .type-value {
          text-align: right;
          font-size: 0.85rem;
          font-weight: 600;
          color: var(--text-primary, #fff);
        }

        .reactions-grid {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }

        .reaction-item {
          display: flex;
          align-items: center;
          gap: 6px;
          background: var(--bg-tertiary, #2a2a3e);
          padding: 8px 12px;
          border-radius: 20px;
        }

        .reaction-emoji {
          font-size: 1.1rem;
        }

        .reaction-count {
          font-size: 0.85rem;
          font-weight: 600;
          color: var(--text-primary, #fff);
        }

        .stats-footer {
          display: flex;
          justify-content: space-between;
          font-size: 0.75rem;
          color: var(--text-muted, #888);
          padding-top: 16px;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
          flex-wrap: wrap;
          gap: 8px;
        }
      `}</style>
    </div>
  );
}

// Helper function to get country flag emoji from country code
function getCountryFlag(countryCode: string): string {
  if (!countryCode || countryCode.length !== 2) return '🏳️';
  
  const codePoints = countryCode
    .toUpperCase()
    .split('')
    .map(char => 127397 + char.charCodeAt(0));
  
  return String.fromCodePoint(...codePoints);
}

