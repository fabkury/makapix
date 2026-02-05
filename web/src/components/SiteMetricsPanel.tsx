import { useState, useEffect, useMemo } from 'react';
import { authenticatedFetch } from '../lib/api';

interface DailyCount {
  date: string;
  count: number;
}

interface HourlyCount {
  hour: string;
  count: number;
}

interface SitewideStats {
  total_page_views_14d: number;
  unique_visitors_14d: number;
  new_signups_14d: number;
  new_posts_14d: number;
  total_api_calls_14d: number;
  total_errors_14d: number;
  total_page_views_14d_authenticated: number;
  unique_visitors_14d_authenticated: number;
  daily_views: DailyCount[];
  daily_signups: DailyCount[];
  daily_posts: DailyCount[];
  daily_views_authenticated: DailyCount[];
  hourly_views: HourlyCount[];
  hourly_views_authenticated: HourlyCount[];
  views_by_page: Record<string, number>;
  views_by_country: Record<string, number>;
  views_by_device: Record<string, number>;
  top_referrers: Record<string, number>;
  views_by_page_authenticated: Record<string, number>;
  views_by_country_authenticated: Record<string, number>;
  views_by_device_authenticated: Record<string, number>;
  top_referrers_authenticated: Record<string, number>;
  errors_by_type: Record<string, number>;
  // Player Activity
  total_player_artwork_views_14d: number;
  active_players_14d: number;
  daily_player_views: DailyCount[];
  views_by_player: Record<string, number>;
  computed_at: string;
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
  player: '🎮 Player',
};

interface OnlinePlayer {
  id: string;
  name: string | null;
  device_model: string | null;
  firmware_version: string | null;
  last_seen_at: string | null;
  owner_handle: string | null;
}

export default function SiteMetricsPanel() {
  const [stats, setStats] = useState<SitewideStats | null>(null);
  const [onlinePlayers, setOnlinePlayers] = useState<OnlinePlayer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [includeUnauthenticated, setIncludeUnauthenticated] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const API_BASE_URL = typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

  useEffect(() => {
    const fetchStats = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await authenticatedFetch(`${API_BASE_URL}/api/admin/sitewide-stats`);

        if (response.status === 401) {
          setError('Authentication required');
          setLoading(false);
          return;
        }

        if (!response.ok) {
          if (response.status === 403) {
            setError('You don\'t have permission to view sitewide metrics');
          } else {
            setError('Failed to load sitewide metrics');
          }
          setLoading(false);
          return;
        }

        const data = await response.json();
        setStats(data);
      } catch (err) {
        console.error('Error fetching sitewide stats:', err);
        setError('Failed to load sitewide metrics');
      } finally {
        setLoading(false);
      }
    };

    const fetchOnlinePlayers = async () => {
      try {
        const response = await authenticatedFetch(`${API_BASE_URL}/api/admin/online-players`);
        if (response.ok) {
          const data = await response.json();
          setOnlinePlayers(data.online_players || []);
        }
      } catch (err) {
        console.error('Error fetching online players:', err);
      }
    };

    fetchStats();
    fetchOnlinePlayers();
  }, [API_BASE_URL]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      const [statsResponse, playersResponse] = await Promise.all([
        authenticatedFetch(`${API_BASE_URL}/api/admin/sitewide-stats?refresh=true`),
        authenticatedFetch(`${API_BASE_URL}/api/admin/online-players`),
      ]);
      
      if (statsResponse.ok) {
        const data = await statsResponse.json();
        setStats(data);
      }
      
      if (playersResponse.ok) {
        const data = await playersResponse.json();
        setOnlinePlayers(data.online_players || []);
      }
    } catch (err) {
      console.error('Error refreshing sitewide stats:', err);
    } finally {
      setIsRefreshing(false);
    }
  };

  // Compute displayed stats based on toggle
  const displayedStats = useMemo(() => {
    if (!stats) return null;

    if (includeUnauthenticated) {
      // Show all statistics (including unauthenticated)
      return {
        total_page_views_14d: stats.total_page_views_14d,
        unique_visitors_14d: stats.unique_visitors_14d,
        daily_views: stats.daily_views,
        hourly_views: stats.hourly_views,
        views_by_page: stats.views_by_page,
        views_by_country: stats.views_by_country,
        views_by_device: stats.views_by_device,
        top_referrers: stats.top_referrers,
      };
    } else {
      // Show authenticated-only statistics
      return {
        total_page_views_14d: stats.total_page_views_14d_authenticated,
        unique_visitors_14d: stats.unique_visitors_14d_authenticated,
        daily_views: stats.daily_views_authenticated,
        hourly_views: stats.hourly_views_authenticated,
        views_by_page: stats.views_by_page_authenticated,
        views_by_country: stats.views_by_country_authenticated,
        views_by_device: stats.views_by_device_authenticated,
        top_referrers: stats.top_referrers_authenticated,
      };
    }
  }, [stats, includeUnauthenticated]);

  if (loading) {
    return (
      <div className="metrics-loading">
        <div className="loading-spinner"></div>
        <p>Loading sitewide metrics...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="metrics-error">
        <span className="error-icon">⚠️</span>
        <p>{error}</p>
      </div>
    );
  }

  if (!stats || !displayedStats) {
    return (
      <div className="metrics-error">
        <p>No metrics data available</p>
      </div>
    );
  }

  // Calculate max values for charts
  const maxDailyViews = Math.max(...displayedStats.daily_views.map(d => d.count), 1);
  const maxHourlyViews = Math.max(...displayedStats.hourly_views.map(h => h.count), 1);
  const maxCountryViews = Math.max(...Object.values(displayedStats.views_by_country), 1);
  const maxPageViews = Math.max(...Object.values(displayedStats.views_by_page), 1);
  const maxReferrerViews = Math.max(...Object.values(displayedStats.top_referrers), 1);

  return (
    <div className="site-metrics">
      {/* Toggle */}
      <div className="metrics-toggle">
        <label className="toggle-label">
          <input
            type="checkbox"
            checked={includeUnauthenticated}
            onChange={(e) => setIncludeUnauthenticated(e.target.checked)}
          />
          <span>{includeUnauthenticated ? 'Showing all statistics (including unauthenticated)' : 'Showing authenticated-only statistics'}</span>
        </label>
      </div>

      {/* Summary Cards */}
      <div className="metrics-summary">
        <div className="metric-card">
          <div className="metric-value">{displayedStats.total_page_views_14d.toLocaleString()}</div>
          <div className="metric-label">Page Views (14d)</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{displayedStats.unique_visitors_14d.toLocaleString()}</div>
          <div className="metric-label">Unique Visitors (14d)</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{stats.new_signups_14d.toLocaleString()}</div>
          <div className="metric-label">New Signups (14d)</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{stats.new_posts_14d.toLocaleString()}</div>
          <div className="metric-label">New Posts (14d)</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{stats.total_api_calls_14d.toLocaleString()}</div>
          <div className="metric-label">API Calls (14d)</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{stats.total_errors_14d.toLocaleString()}</div>
          <div className="metric-label">Errors (14d)</div>
        </div>
      </div>

      {/* 14-Day Trends */}
      <div className="metrics-section">
        <h3>📈 Page Views (Last 14 Days)</h3>
        <div className="trend-chart">
          {displayedStats.daily_views.map((day, index) => {
            const height = maxDailyViews > 0 ? (day.count / maxDailyViews) * 100 : 0;
            const date = new Date(day.date);
            const isWeekend = date.getDay() === 0 || date.getDay() === 6;
            const showLabel =
              index % 3 === 0 ||
              index === displayedStats.daily_views.length - 1 ||
              day.count === maxDailyViews;
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
                  title={`${day.date}: ${day.count} views`}
                  aria-label={`${day.date}: ${day.count} views`}
                  role="img"
                />
              </div>
            );
          })}
        </div>
        <div className="trend-labels">
          <span>14 days ago</span>
          <span>Today</span>
        </div>
      </div>

      {/* 24-Hour Granular Chart */}
      <div className="metrics-section">
        <h3>⏰ Page Views (Last 24 Hours - Hourly)</h3>
        <div className="trend-chart hourly">
          {displayedStats.hourly_views.map((hour, index) => {
            const height = maxHourlyViews > 0 ? (hour.count / maxHourlyViews) * 100 : 0;
            const hourDate = new Date(hour.hour);
            const hourLabel = hourDate.getHours();
            const showLabel =
              // Show every 3 hours + last bar + peak hour(s)
              index % 3 === 0 ||
              index === displayedStats.hourly_views.length - 1 ||
              hour.count === maxHourlyViews;
            return (
              <div key={hour.hour} className="trend-bar-wrap">
                <span className="trend-bar-xlabel" aria-hidden="true">
                  {hourLabel}
                </span>
                {showLabel && (
                  <span className="trend-bar-label" aria-hidden="true">
                    {hour.count.toLocaleString()}
                  </span>
                )}
                <div
                  className="trend-bar"
                  style={{ height: `${Math.max(height, 2)}%` }}
                  title={`${hourLabel}:00 - ${hour.count} views`}
                  aria-label={`${hourLabel}:00 - ${hour.count} views`}
                  role="img"
                />
              </div>
            );
          })}
        </div>
        <div className="trend-labels">
          <span>24h ago</span>
          <span>Now</span>
        </div>
      </div>

      {/* Top Pages */}
      {Object.keys(displayedStats.views_by_page).length > 0 && (
        <div className="metrics-section">
          <h3>📄 Top Pages</h3>
          <div className="breakdown-list">
            {Object.entries(displayedStats.views_by_page)
              .sort(([, a], [, b]) => b - a)
              .slice(0, 10)
              .map(([page, count]) => (
                <div key={page} className="breakdown-item">
                  <div className="breakdown-label">{page}</div>
                  <div className="breakdown-bar-container">
                    <div
                      className="breakdown-bar"
                      style={{ width: `${(count / maxPageViews) * 100}%` }}
                    />
                  </div>
                  <div className="breakdown-value">{count.toLocaleString()}</div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Country Breakdown */}
      {Object.keys(displayedStats.views_by_country).length > 0 && (
        <div className="metrics-section">
          <h3>🌍 Top Countries</h3>
          <div className="breakdown-list">
            {Object.entries(displayedStats.views_by_country)
              .sort(([, a], [, b]) => b - a)
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
        <div className="metrics-section">
          <h3>📱 Devices</h3>
          <div className="device-grid">
            {Object.entries(displayedStats.views_by_device)
              .sort(([, a], [, b]) => b - a)
              .map(([device, count]) => {
                const percentage = displayedStats.total_page_views_14d > 0
                  ? Math.round((count / displayedStats.total_page_views_14d) * 100)
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

      {/* Top Referrers */}
      {Object.keys(displayedStats.top_referrers).length > 0 && (
        <div className="metrics-section">
          <h3>🔗 Top Referrers</h3>
          <div className="breakdown-list">
            {Object.entries(displayedStats.top_referrers)
              .sort(([, a], [, b]) => b - a)
              .slice(0, 10)
              .map(([referrer, count]) => (
                <div key={referrer} className="breakdown-item">
                  <div className="breakdown-label">{referrer}</div>
                  <div className="breakdown-bar-container">
                    <div
                      className="breakdown-bar"
                      style={{ width: `${(count / maxReferrerViews) * 100}%` }}
                    />
                  </div>
                  <div className="breakdown-value">{count.toLocaleString()}</div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Error Tracking */}
      {Object.keys(stats.errors_by_type).length > 0 && (
        <div className="metrics-section">
          <h3>⚠️ Errors by Type</h3>
          <div className="breakdown-list">
            {Object.entries(stats.errors_by_type)
              .sort(([, a], [, b]) => b - a)
              .map(([errorType, count]) => (
                <div key={errorType} className="breakdown-item">
                  <div className="breakdown-label">{errorType}</div>
                  <div className="breakdown-bar-container">
                    <div
                      className="breakdown-bar error-bar"
                      style={{ width: `${(count / stats.total_errors_14d) * 100}%` }}
                    />
                  </div>
                  <div className="breakdown-value">{count.toLocaleString()}</div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Player Activity Section */}
      <div className="metrics-section player-activity-section">
        <h3>🎮 Player Activity (Artwork Views)</h3>
        <p className="section-note">
          Views from physical player devices (P3A and others) - separate from website page views.
        </p>

        {/* Player Summary Cards */}
        <div className="player-summary">
          <div className="metric-card player-card">
            <div className="metric-value">{stats.total_player_artwork_views_14d?.toLocaleString() || 0}</div>
            <div className="metric-label">Player Artwork Views (14d)</div>
          </div>
          <div className="metric-card player-card">
            <div className="metric-value">{stats.active_players_14d?.toLocaleString() || 0}</div>
            <div className="metric-label">Active Players (14d)</div>
          </div>
        </div>

        {/* Daily Player Views Trend */}
        {stats.daily_player_views && stats.daily_player_views.length > 0 && (
          <>
            <h4>📈 Player Views (Last 14 Days)</h4>
            <div className="trend-chart">
              {(() => {
                const maxPlayerViews = Math.max(...stats.daily_player_views.map(d => d.count), 1);
                return stats.daily_player_views.map((day, index) => {
                  const height = maxPlayerViews > 0 ? (day.count / maxPlayerViews) * 100 : 0;
                  const showLabel =
                    index % 3 === 0 ||
                    index === stats.daily_player_views.length - 1 ||
                    day.count === maxPlayerViews;
                  return (
                    <div key={day.date} className="trend-bar-wrap">
                      {showLabel && day.count > 0 && (
                        <span className="trend-bar-label" aria-hidden="true">
                          {day.count.toLocaleString()}
                        </span>
                      )}
                      <div
                        className="trend-bar player-bar"
                        style={{ height: `${Math.max(height, 2)}%` }}
                        title={`${day.date}: ${day.count} player views`}
                        aria-label={`${day.date}: ${day.count} player views`}
                        role="img"
                      />
                    </div>
                  );
                });
              })()}
            </div>
            <div className="trend-labels">
              <span>14 days ago</span>
              <span>Today</span>
            </div>
          </>
        )}

        {/* Views by Player */}
        {stats.views_by_player && Object.keys(stats.views_by_player).length > 0 && (
          <>
            <h4>🏆 Top Players</h4>
            <div className="breakdown-list">
              {Object.entries(stats.views_by_player)
                .sort(([, a], [, b]) => b - a)
                .map(([playerName, count]) => {
                  const maxPlayerCount = Math.max(...Object.values(stats.views_by_player));
                  return (
                    <div key={playerName} className="breakdown-item">
                      <div className="breakdown-label">
                        <span className="player-icon">📺</span>
                        <span>{playerName}</span>
                      </div>
                      <div className="breakdown-bar-container">
                        <div
                          className="breakdown-bar player-bar"
                          style={{ width: `${(count / maxPlayerCount) * 100}%` }}
                        />
                      </div>
                      <div className="breakdown-value">{count.toLocaleString()}</div>
                    </div>
                  );
                })}
            </div>
          </>
        )}

        {stats.total_player_artwork_views_14d === 0 && (
          <p className="no-data">No player activity in the last 14 days.</p>
        )}
      </div>

      {/* Online Players Section */}
      <div className="metrics-section online-players-section">
        <h3>🟢 Online Players</h3>
        
        {onlinePlayers.length > 0 ? (
          <div className="online-players-list">
            {onlinePlayers.map((player) => (
              <div key={player.id} className="online-player-card">
                <div className="player-header">
                  <span className="player-status-dot">●</span>
                  <span className="player-name">{player.name || 'Unnamed Player'}</span>
                </div>
                <div className="player-details">
                  {player.device_model && (
                    <div className="player-detail">
                      <span className="detail-label">Model:</span>
                      <span className="detail-value">{player.device_model}</span>
                    </div>
                  )}
                  {player.firmware_version && (
                    <div className="player-detail">
                      <span className="detail-label">Firmware:</span>
                      <span className="detail-value">{player.firmware_version}</span>
                    </div>
                  )}
                  {player.owner_handle && (
                    <div className="player-detail">
                      <span className="detail-label">Owner:</span>
                      <span className="detail-value">{player.owner_handle}</span>
                    </div>
                  )}
                  {player.last_seen_at && (
                    <div className="player-detail">
                      <span className="detail-label">Last seen:</span>
                      <span className="detail-value">
                        {new Date(player.last_seen_at).toLocaleTimeString()}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="no-data">No players currently online.</p>
        )}
      </div>

      {/* Footer */}
      <div className="metrics-footer">
        <span>Last updated: {new Date(stats.computed_at).toLocaleString()}</span>
        <button 
          onClick={handleRefresh} 
          disabled={isRefreshing}
          className="refresh-link"
          title="Cache is refreshed every 5 minutes, but click here to refresh it now"
        >
          {isRefreshing ? 'Refreshing...' : 'Refresh cache'}
        </button>
      </div>

      <style jsx>{`
        .site-metrics {
          padding: 24px;
        }

        .metrics-toggle {
          margin-bottom: 24px;
          padding: 12px;
          background: var(--bg-secondary, #1a1a2e);
          border-radius: 8px;
        }

        .toggle-label {
          display: flex;
          align-items: center;
          gap: 8px;
          cursor: pointer;
          font-size: 0.9rem;
          color: var(--text-secondary, #ccc);
        }

        .toggle-label input[type="checkbox"] {
          cursor: pointer;
          width: 18px;
          height: 18px;
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

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .error-icon {
          font-size: 2rem;
          margin-bottom: 12px;
        }

        .metrics-summary {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
          margin-bottom: 24px;
        }

        @media (min-width: 640px) {
          .metrics-summary {
            grid-template-columns: repeat(3, 1fr);
          }
        }

        @media (min-width: 1024px) {
          .metrics-summary {
            grid-template-columns: repeat(6, 1fr);
          }
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

        .metrics-section {
          margin-bottom: 32px;
        }

        .metrics-section h3 {
          font-size: 1rem;
          font-weight: 600;
          color: var(--text-primary, #fff);
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

        .trend-chart.hourly {
          height: 120px;
          padding-bottom: 18px; /* room for hour labels */
        }

        .trend-bar-wrap {
          flex: 1;
          position: relative;
          height: 100%;
          display: flex;
          align-items: flex-end;
          justify-content: center;
          min-width: 0;
        }

        .trend-bar-xlabel {
          position: absolute;
          bottom: -16px;
          font-size: 10px;
          line-height: 1;
          color: rgba(255, 255, 255, 0.6);
          width: 100%;
          text-align: center;
          pointer-events: none;
          white-space: nowrap;
        }

        .trend-bar {
          width: 100%;
          background: linear-gradient(to top, var(--accent-purple, #b44eff), var(--accent-cyan, #4ecdc4));
          border-radius: 2px 2px 0 0;
          min-height: 2px;
          cursor: pointer;
          transition: opacity 0.2s;
        }

        .trend-bar-label {
          position: absolute;
          top: -2px;
          transform: translateY(-100%);
          font-size: 10px;
          line-height: 1;
          color: rgba(255, 255, 255, 0.72);
          white-space: nowrap;
          pointer-events: none;
          text-shadow: 0 1px 2px rgba(0, 0, 0, 0.6);
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
          background: linear-gradient(to right, var(--accent-purple, #b44eff), var(--accent-pink, #ff6b9d));
        }

        .breakdown-bar.country-bar {
          background: linear-gradient(to right, var(--accent-purple, #b44eff), var(--accent-pink, #ff6b9d));
        }

        .breakdown-bar.error-bar {
          background: linear-gradient(to right, #ef4444, #f97316);
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

        .metrics-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 0.75rem;
          color: var(--text-muted, #888);
          padding-top: 16px;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        .refresh-link {
          background: none;
          border: none;
          color: var(--accent-cyan, #4ecdc4);
          cursor: pointer;
          font-size: 0.75rem;
          padding: 4px 8px;
          border-radius: 4px;
          transition: all 0.2s ease;
        }

        .refresh-link:hover:not(:disabled) {
          background: rgba(78, 205, 196, 0.1);
          text-decoration: underline;
        }

        .refresh-link:disabled {
          color: var(--text-muted, #888);
          cursor: not-allowed;
        }

        /* Player Activity Styles */
        .player-activity-section {
          background: var(--bg-secondary, #1a1a2e);
          border-radius: 12px;
          padding: 20px;
          margin-top: 24px;
          border: 1px solid rgba(78, 205, 196, 0.2);
        }

        .player-activity-section h3 {
          color: var(--accent-cyan, #4ecdc4);
          margin-bottom: 8px;
        }

        .player-activity-section h4 {
          font-size: 0.9rem;
          font-weight: 600;
          color: var(--text-secondary, #ccc);
          margin: 20px 0 12px 0;
        }

        .section-note {
          font-size: 0.8rem;
          color: var(--text-muted, #888);
          margin-bottom: 16px;
        }

        .player-summary {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: 12px;
          margin-bottom: 20px;
        }

        .player-card {
          background: var(--bg-tertiary, #2a2a3e);
          border: 1px solid rgba(78, 205, 196, 0.15);
        }

        .player-card .metric-value {
          color: var(--accent-cyan, #4ecdc4);
        }

        .trend-bar.player-bar {
          background: linear-gradient(to top, var(--accent-cyan, #4ecdc4), #7fdbda);
        }

        .breakdown-bar.player-bar {
          background: linear-gradient(to right, var(--accent-cyan, #4ecdc4), #7fdbda);
        }

        .player-icon {
          font-size: 1rem;
          margin-right: 4px;
        }

        .no-data {
          text-align: center;
          color: var(--text-muted, #888);
          font-style: italic;
          padding: 20px;
        }

        /* Online Players Styles */
        .online-players-section {
          background: var(--bg-secondary, #1a1a2e);
          border-radius: 12px;
          padding: 20px;
          margin-top: 24px;
          border: 1px solid rgba(78, 205, 196, 0.2);
        }

        .online-players-section h3 {
          color: var(--accent-cyan, #4ecdc4);
          margin-bottom: 16px;
        }

        .online-players-list {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
          gap: 16px;
        }

        .online-player-card {
          background: var(--bg-tertiary, #2a2a3e);
          border: 1px solid rgba(78, 205, 196, 0.15);
          border-radius: 8px;
          padding: 16px;
          transition: all 0.2s ease;
        }

        .online-player-card:hover {
          border-color: rgba(78, 205, 196, 0.3);
          transform: translateY(-2px);
        }

        .player-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 12px;
          padding-bottom: 12px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }

        .player-status-dot {
          color: #00ff00;
          font-size: 1.2rem;
          animation: pulse 2s ease-in-out infinite;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }

        .player-name {
          font-weight: 600;
          color: var(--text-primary, #fff);
          font-size: 1rem;
        }

        .player-details {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .player-detail {
          display: flex;
          justify-content: space-between;
          font-size: 0.85rem;
        }

        .detail-label {
          color: var(--text-muted, #888);
        }

        .detail-value {
          color: var(--text-secondary, #ccc);
          font-family: monospace;
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

