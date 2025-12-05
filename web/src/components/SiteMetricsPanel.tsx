import { useState, useEffect, useMemo } from 'react';

interface DailyCount {
  date: string;
  count: number;
}

interface HourlyCount {
  hour: string;
  count: number;
}

interface SitewideStats {
  total_page_views_30d: number;
  unique_visitors_30d: number;
  new_signups_30d: number;
  new_posts_30d: number;
  total_api_calls_30d: number;
  total_errors_30d: number;
  total_page_views_30d_authenticated: number;
  unique_visitors_30d_authenticated: number;
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
};

export default function SiteMetricsPanel() {
  const [stats, setStats] = useState<SitewideStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [includeUnauthenticated, setIncludeUnauthenticated] = useState(true);

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

    fetchStats();
  }, [API_BASE_URL]);

  // Compute displayed stats based on toggle
  const displayedStats = useMemo(() => {
    if (!stats) return null;
    
    if (includeUnauthenticated) {
      // Show all statistics (including unauthenticated)
      return {
        total_page_views_30d: stats.total_page_views_30d,
        unique_visitors_30d: stats.unique_visitors_30d,
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
        total_page_views_30d: stats.total_page_views_30d_authenticated,
        unique_visitors_30d: stats.unique_visitors_30d_authenticated,
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
          <div className="metric-value">{displayedStats.total_page_views_30d.toLocaleString()}</div>
          <div className="metric-label">Page Views (30d)</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{displayedStats.unique_visitors_30d.toLocaleString()}</div>
          <div className="metric-label">Unique Visitors (30d)</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{stats.new_signups_30d.toLocaleString()}</div>
          <div className="metric-label">New Signups (30d)</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{stats.new_posts_30d.toLocaleString()}</div>
          <div className="metric-label">New Posts (30d)</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{stats.total_api_calls_30d.toLocaleString()}</div>
          <div className="metric-label">API Calls (30d)</div>
        </div>
        <div className="metric-card">
          <div className="metric-value">{stats.total_errors_30d.toLocaleString()}</div>
          <div className="metric-label">Errors (30d)</div>
        </div>
      </div>

      {/* 30-Day Trends */}
      <div className="metrics-section">
        <h3>📈 Page Views (Last 30 Days)</h3>
        <div className="trend-chart">
          {displayedStats.daily_views.map((day) => {
            const height = maxDailyViews > 0 ? (day.count / maxDailyViews) * 100 : 0;
            const date = new Date(day.date);
            const isWeekend = date.getDay() === 0 || date.getDay() === 6;
            return (
              <div
                key={day.date}
                className={`trend-bar ${isWeekend ? 'weekend' : ''}`}
                style={{ height: `${Math.max(height, 2)}%` }}
                title={`${day.date}: ${day.count} views`}
              />
            );
          })}
        </div>
        <div className="trend-labels">
          <span>30 days ago</span>
          <span>Today</span>
        </div>
      </div>

      {/* 24-Hour Granular Chart */}
      <div className="metrics-section">
        <h3>⏰ Page Views (Last 24 Hours - Hourly)</h3>
        <div className="trend-chart hourly">
          {displayedStats.hourly_views.map((hour) => {
            const height = maxHourlyViews > 0 ? (hour.count / maxHourlyViews) * 100 : 0;
            const hourDate = new Date(hour.hour);
            const hourLabel = hourDate.getHours();
            return (
              <div
                key={hour.hour}
                className="trend-bar"
                style={{ height: `${Math.max(height, 2)}%` }}
                title={`${hourLabel}:00 - ${hour.count} views`}
              />
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
                      style={{ width: `${(count / maxDailyViews) * 100}%` }}
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
                const percentage = displayedStats.total_page_views_30d > 0
                  ? Math.round((count / displayedStats.total_page_views_30d) * 100)
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
                      style={{ width: `${(count / maxDailyViews) * 100}%` }}
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
                      style={{ width: `${(count / stats.total_errors_30d) * 100}%` }}
                    />
                  </div>
                  <div className="breakdown-value">{count.toLocaleString()}</div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="metrics-footer">
        <span>Last updated: {new Date(stats.computed_at).toLocaleString()}</span>
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
          height: 100px;
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
          font-size: 0.75rem;
          color: var(--text-muted, #888);
          padding-top: 16px;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
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

