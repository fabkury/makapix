import { useState, useEffect, useMemo } from 'react';
import { authenticatedFetch } from '../lib/api';
import { DailyCount, HourlyCount, OnlinePlayer, SitewideStats, TrendPoint } from './metrics/types';
import { CHART } from './metrics/theme';
import { countryName, getCountryFlag } from './metrics/format';
import BarList, { BarListItem } from './metrics/BarList';
import ChartCard from './metrics/ChartCard';
import DeviceGrid from './metrics/DeviceGrid';
import KpiCard from './metrics/KpiCard';
import KpiGrid from './metrics/KpiGrid';
import ChartGrid from './metrics/ChartGrid';
import OnlinePlayersGrid from './metrics/OnlinePlayersGrid';
import TrendChart from './metrics/TrendChart';

function zipDaily(views: DailyCount[], visitors?: DailyCount[]): TrendPoint[] {
  return (views || []).map((day, i) => ({
    x: day.date,
    primary: day.count,
    secondary: visitors?.[i]?.count ?? 0,
  }));
}

function zipHourly(views: HourlyCount[], visitors?: HourlyCount[]): TrendPoint[] {
  return (views || []).map((hour, i) => ({
    x: hour.hour,
    primary: hour.count,
    secondary: visitors?.[i]?.count ?? 0,
  }));
}

function toPoints(series?: DailyCount[]): TrendPoint[] {
  return (series || []).map((day) => ({ x: day.date, primary: day.count }));
}

function toItems(record?: Record<string, number>): BarListItem[] {
  return Object.entries(record || {}).map(([key, count]) => ({
    key,
    label: key,
    title: key,
    count,
  }));
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

  // Swap between all-traffic and authenticated-only series based on the toggle.
  const displayedStats = useMemo(() => {
    if (!stats) return null;

    if (includeUnauthenticated) {
      return {
        total_page_views_14d: stats.total_page_views_14d,
        unique_visitors_14d: stats.unique_visitors_14d,
        daily_views: stats.daily_views,
        daily_unique_visitors: stats.daily_unique_visitors,
        hourly_views: stats.hourly_views,
        hourly_unique_visitors: stats.hourly_unique_visitors,
        views_by_page: stats.views_by_page,
        views_by_country: stats.views_by_country,
        views_by_device: stats.views_by_device,
        top_referrers: stats.top_referrers,
      };
    } else {
      return {
        total_page_views_14d: stats.total_page_views_14d_authenticated,
        unique_visitors_14d: stats.unique_visitors_14d_authenticated,
        daily_views: stats.daily_views_authenticated,
        daily_unique_visitors: stats.daily_unique_visitors_authenticated,
        hourly_views: stats.hourly_views_authenticated,
        hourly_unique_visitors: stats.hourly_unique_visitors_authenticated,
        views_by_page: stats.views_by_page_authenticated,
        views_by_country: stats.views_by_country_authenticated,
        views_by_device: stats.views_by_device_authenticated,
        top_referrers: stats.top_referrers_authenticated,
      };
    }
  }, [stats, includeUnauthenticated]);

  const dailyTraffic = useMemo(
    () => (displayedStats ? zipDaily(displayedStats.daily_views, displayedStats.daily_unique_visitors) : []),
    [displayedStats]
  );
  const hourlyTraffic = useMemo(
    () => (displayedStats ? zipHourly(displayedStats.hourly_views, displayedStats.hourly_unique_visitors) : []),
    [displayedStats]
  );
  const signupTrend = useMemo(() => toPoints(stats?.daily_signups), [stats]);
  const postTrend = useMemo(() => toPoints(stats?.daily_posts), [stats]);
  const playerTrend = useMemo(() => toPoints(stats?.daily_player_views), [stats]);

  const countryItems = useMemo<BarListItem[]>(
    () =>
      Object.entries(displayedStats?.views_by_country || {}).map(([code, count]) => ({
        key: code,
        label: `${getCountryFlag(code)} ${countryName(code)}`,
        title: countryName(code),
        count,
      })),
    [displayedStats]
  );
  const playerItems = useMemo<BarListItem[]>(
    () =>
      Object.entries(stats?.views_by_player || {}).map(([name, count]) => ({
        key: name,
        label: `📺 ${name}`,
        title: name,
        count,
      })),
    [stats]
  );

  if (loading) {
    return (
      <div className="metrics-loading">
        <div className="loading-spinner"></div>
        <p>Loading sitewide metrics...</p>
        <style jsx>{`
          .metrics-loading {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 60px 24px;
            color: var(--text-muted, #6a6a80);
          }

          .loading-spinner {
            width: 40px;
            height: 40px;
            border: 3px solid var(--bg-tertiary, #1a1a24);
            border-top-color: var(--accent-cyan, #00d4ff);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin-bottom: 16px;
          }

          @keyframes spin {
            to {
              transform: rotate(360deg);
            }
          }
        `}</style>
      </div>
    );
  }

  if (error || !stats || !displayedStats) {
    return (
      <div className="metrics-error">
        <span className="error-icon">⚠️</span>
        <p>{error || 'No metrics data available'}</p>
        <style jsx>{`
          .metrics-error {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 60px 24px;
            color: var(--text-muted, #6a6a80);
          }

          .error-icon {
            font-size: 2rem;
            margin-bottom: 12px;
          }
        `}</style>
      </div>
    );
  }

  const pageItems = toItems(displayedStats.views_by_page);
  const referrerItems = toItems(displayedStats.top_referrers);
  const errorItems = toItems(stats.errors_by_type);

  return (
    <div className="site-metrics">
      {/* Filter row */}
      <div className="controls-row">
        <label className="toggle-label">
          <input
            type="checkbox"
            checked={includeUnauthenticated}
            onChange={(e) => setIncludeUnauthenticated(e.target.checked)}
          />
          <span>Include unauthenticated traffic</span>
        </label>
        <span className="controls-hint">
          Applies to traffic charts and breakdowns; signups, posts, errors, and player stats always
          count everything.
        </span>
      </div>

      {/* KPI row */}
      <KpiGrid>
        <KpiCard label="Page views (14d)" value={displayedStats.total_page_views_14d.toLocaleString()} />
        <KpiCard
          label="Visitor-days (14d)"
          value={displayedStats.unique_visitors_14d.toLocaleString()}
          hint="Sum of each day's unique visitors — a visitor active on N days counts N times."
        />
        <KpiCard label="New signups (14d)" value={stats.new_signups_14d.toLocaleString()} />
        <KpiCard label="New posts (14d)" value={stats.new_posts_14d.toLocaleString()} />
        <KpiCard label="API calls (14d)" value={stats.total_api_calls_14d.toLocaleString()} />
        <KpiCard label="Errors (14d)" value={stats.total_errors_14d.toLocaleString()} />
      </KpiGrid>

      {/* Traffic + growth charts */}
      <ChartGrid>
        <ChartCard title="Daily traffic" subtitle="Last 14 days">
          <TrendChart
            data={dailyTraffic}
            granularity="day"
            primaryName="Page views"
            primaryColor={CHART.cyan}
            secondaryName="Unique visitors"
            secondaryColor={CHART.pink}
          />
        </ChartCard>
        <ChartCard title="Hourly traffic" subtitle="Last 24 hours, local time">
          <TrendChart
            data={hourlyTraffic}
            granularity="hour"
            primaryName="Page views"
            primaryColor={CHART.cyan}
            secondaryName="Unique visitors"
            secondaryColor={CHART.pink}
            height={260}
          />
        </ChartCard>
        <ChartCard title="New signups" subtitle="Last 14 days · not affected by the visitor filter">
          <TrendChart
            data={signupTrend}
            granularity="day"
            primaryName="Signups"
            primaryColor={CHART.blue}
            height={200}
          />
        </ChartCard>
        <ChartCard title="New posts" subtitle="Last 14 days · not affected by the visitor filter">
          <TrendChart
            data={postTrend}
            granularity="day"
            primaryName="Posts"
            primaryColor={CHART.purple}
            height={200}
          />
        </ChartCard>
        {pageItems.length > 0 && (
          <ChartCard title="Top pages" subtitle="Page views, last 14 days">
            <BarList items={pageItems} />
          </ChartCard>
        )}
        {countryItems.length > 0 && (
          <ChartCard title="Top countries" subtitle="Page views, last 14 days">
            <BarList items={countryItems} />
          </ChartCard>
        )}
        {referrerItems.length > 0 && (
          <ChartCard title="Top referrers" subtitle="Page views, last 14 days">
            <BarList items={referrerItems} />
          </ChartCard>
        )}
        {Object.keys(displayedStats.views_by_device).length > 0 && (
          <ChartCard title="Devices" subtitle="Share of page views, last 14 days">
            <DeviceGrid viewsByDevice={displayedStats.views_by_device} />
          </ChartCard>
        )}
        {errorItems.length > 0 && (
          <ChartCard title="Errors by type" subtitle="Last 14 days · not affected by the visitor filter">
            <BarList items={errorItems} variant="error" />
          </ChartCard>
        )}
      </ChartGrid>

      {/* Player activity */}
      <ChartCard
        title="Player activity"
        subtitle="Artwork views from physical player devices — separate from website page views."
      >
        <div className="player-kpis">
          <KpiCard
            label="Player artwork views (14d)"
            value={(stats.total_player_artwork_views_14d ?? 0).toLocaleString()}
          />
          <KpiCard label="Active players (14d)" value={(stats.active_players_14d ?? 0).toLocaleString()} />
        </div>
        {stats.total_player_artwork_views_14d > 0 ? (
          <>
            <TrendChart
              data={playerTrend}
              granularity="day"
              primaryName="Player views"
              primaryColor={CHART.cyan}
              height={200}
            />
            {playerItems.length > 0 && (
              <>
                <h4 className="subheading">Top players</h4>
                <BarList items={playerItems} variant="player" />
              </>
            )}
          </>
        ) : (
          <p className="no-data">No player activity in the last 14 days.</p>
        )}
      </ChartCard>

      {/* Online players */}
      <ChartCard title="Online players">
        <OnlinePlayersGrid players={onlinePlayers} />
      </ChartCard>

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
          display: flex;
          flex-direction: column;
          gap: 16px;
          padding: 16px 0;
        }

        .controls-row {
          display: flex;
          align-items: baseline;
          gap: 16px;
          flex-wrap: wrap;
        }

        .toggle-label {
          display: flex;
          align-items: center;
          gap: 8px;
          cursor: pointer;
          font-size: 0.9rem;
          color: var(--text-secondary, #a0a0b8);
          white-space: nowrap;
        }

        .toggle-label input[type='checkbox'] {
          cursor: pointer;
          width: 16px;
          height: 16px;
        }

        .controls-hint {
          font-size: 0.75rem;
          color: var(--text-muted, #6a6a80);
        }

        .player-kpis {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
          gap: 12px;
          margin-bottom: 16px;
        }

        .subheading {
          font-size: 0.85rem;
          font-weight: 600;
          color: var(--text-secondary, #a0a0b8);
          margin: 20px 0 10px;
        }

        .no-data {
          color: var(--text-muted, #6a6a80);
          font-style: italic;
          margin: 0;
        }

        .metrics-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          font-size: 0.75rem;
          color: var(--text-muted, #6a6a80);
          padding-top: 12px;
          border-top: 1px solid rgba(255, 255, 255, 0.05);
        }

        .refresh-link {
          background: none;
          border: none;
          color: var(--accent-cyan, #00d4ff);
          cursor: pointer;
          font-size: 0.75rem;
          padding: 4px 8px;
          border-radius: 4px;
          transition: all 0.2s ease;
        }

        .refresh-link:hover:not(:disabled) {
          background: rgba(0, 212, 255, 0.1);
          text-decoration: underline;
        }

        .refresh-link:disabled {
          color: var(--text-muted, #6a6a80);
          cursor: not-allowed;
        }
      `}</style>
    </div>
  );
}
