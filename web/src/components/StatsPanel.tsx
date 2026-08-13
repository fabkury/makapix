import { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/router";
import { ApiRequestError, clearTokens, getPostStats } from "../lib/api";
import { DailyViewCount, PostStatsResponse } from "../types/stats";
import { TrendPoint } from "./metrics/types";
import { CHART } from "./metrics/theme";
import { countryName, getCountryFlag } from "./metrics/format";
import BarList, { BarListItem } from "./metrics/BarList";
import ChartCard from "./metrics/ChartCard";
import DeviceGrid from "./metrics/DeviceGrid";
import KpiCard from "./metrics/KpiCard";
import KpiGrid from "./metrics/KpiGrid";
import TrendChart from "./metrics/TrendChart";

interface StatsPanelProps {
  postId: string | number;
  isOpen: boolean;
  onClose: () => void;
}

const toViewTrend = (daily: DailyViewCount[]): TrendPoint[] =>
  (daily || []).map((d) => ({
    x: d.date,
    primary: d.views,
    secondary: d.unique_viewers,
  }));

const toImpressionTrend = (daily: DailyViewCount[]): TrendPoint[] =>
  (daily || []).map((d) => ({ x: d.date, primary: d.impressions ?? 0 }));

/**
 * Per-artwork statistics modal for owners/moderators, on the metrics kit.
 * Views and Impressions are separate metrics, never summed
 * (docs/artwork-views/ D2/D3); cross-day unique-viewer sums are labeled
 * approximate (D13).
 */
export default function StatsPanel({
  postId,
  isOpen,
  onClose,
}: StatsPanelProps) {
  const router = useRouter();
  const [stats, setStats] = useState<PostStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [includeUnauthenticated, setIncludeUnauthenticated] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const loadStats = async (refresh: boolean) => {
    try {
      const data = await getPostStats(postId, refresh);
      setStats(data);
      setError(null);
    } catch (err) {
      if (err instanceof ApiRequestError) {
        if (err.status === 401) {
          clearTokens();
          router.push("/auth");
          return;
        }
        if (err.status === 403) {
          setError("You don't have permission to view these statistics");
          return;
        }
        if (err.status === 404) {
          setError("Post not found");
          return;
        }
      }
      console.error("Error fetching stats:", err);
      setError("Failed to load statistics");
    }
  };

  useEffect(() => {
    if (!isOpen || !postId) return;
    setLoading(true);
    loadStats(false).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, postId]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await loadStats(true);
    setIsRefreshing(false);
  };

  // Swap between "all" and authenticated-only field sets
  const displayed = useMemo(() => {
    if (!stats) return null;
    if (includeUnauthenticated) {
      return {
        total_views: stats.total_views,
        unique_viewers: stats.unique_viewers,
        total_impressions: stats.total_impressions ?? 0,
        views_by_country: stats.views_by_country,
        views_by_device: stats.views_by_device,
        daily_views: stats.daily_views,
        total_reactions: stats.total_reactions,
        reactions_by_emoji: stats.reactions_by_emoji,
        total_comments: stats.total_comments,
      };
    }
    return {
      total_views: stats.total_views_authenticated,
      unique_viewers: stats.unique_viewers_authenticated,
      total_impressions: stats.total_impressions_authenticated ?? 0,
      views_by_country: stats.views_by_country_authenticated,
      views_by_device: stats.views_by_device_authenticated,
      daily_views: stats.daily_views_authenticated,
      total_reactions: stats.total_reactions_authenticated,
      reactions_by_emoji: stats.reactions_by_emoji_authenticated,
      total_comments: stats.total_comments_authenticated,
    };
  }, [stats, includeUnauthenticated]);

  if (!isOpen) return null;

  const countryItems: BarListItem[] = displayed
    ? Object.entries(displayed.views_by_country).map(([code, count]) => ({
        key: code,
        label: `${getCountryFlag(code)} ${countryName(code)}`,
        title: countryName(code),
        count,
      }))
    : [];

  const reactionItems: BarListItem[] = displayed
    ? Object.entries(displayed.reactions_by_emoji).map(([emoji, count]) => ({
        key: emoji,
        label: emoji,
        count,
      }))
    : [];

  return (
    <div className="stats-overlay" onClick={onClose}>
      <div className="stats-panel" onClick={(e) => e.stopPropagation()}>
        <div className="stats-header">
          <h2>📊 Artwork Statistics</h2>
          <button className="close-button" onClick={onClose}>
            ×
          </button>
        </div>

        {stats && !loading && !error && (
          <div className="stats-toggle">
            <label className="toggle-label">
              <input
                type="checkbox"
                checked={includeUnauthenticated}
                onChange={(e) => setIncludeUnauthenticated(e.target.checked)}
              />
              <span>Include unauthenticated traffic</span>
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

        {displayed && !loading && !error && (
          <div className="stats-content">
            <KpiGrid minWidth={120}>
              <KpiCard
                label="Views (30d)"
                value={displayed.total_views.toLocaleString()}
                hint="Deliberate looks — counted at most once per visitor per day."
              />
              <KpiCard
                label="Impressions (30d)"
                value={displayed.total_impressions.toLocaleString()}
                hint="Passive exposure during player / web-player rotation. Never added to Views."
              />
              <KpiCard
                label="Unique viewers (30d)"
                value={displayed.unique_viewers.toLocaleString()}
                hint="Approximate — sum of each day's unique viewers; a viewer returning on N days counts N times."
              />
              <KpiCard
                label="Reactions"
                value={displayed.total_reactions.toLocaleString()}
              />
              <KpiCard
                label="Comments"
                value={displayed.total_comments.toLocaleString()}
              />
            </KpiGrid>

            <ChartCard title="Daily views" subtitle="Last 30 days">
              <TrendChart
                data={toViewTrend(displayed.daily_views)}
                granularity="day"
                primaryName="Views"
                primaryColor={CHART.cyan}
                secondaryName="Unique viewers"
                secondaryColor={CHART.pink}
                height={220}
              />
            </ChartCard>

            {displayed.total_impressions > 0 && (
              <ChartCard
                title="Daily impressions"
                subtitle="Last 30 days · playback exposure"
              >
                <TrendChart
                  data={toImpressionTrend(displayed.daily_views)}
                  granularity="day"
                  primaryName="Impressions"
                  primaryColor={CHART.purple}
                  height={180}
                />
              </ChartCard>
            )}

            {countryItems.length > 0 && (
              <ChartCard title="Top countries" subtitle="Views, last 30 days">
                <BarList items={countryItems} />
              </ChartCard>
            )}

            {Object.keys(displayed.views_by_device).length > 0 && (
              <ChartCard title="Devices" subtitle="Share of views, last 30 days">
                <DeviceGrid viewsByDevice={displayed.views_by_device} />
              </ChartCard>
            )}

            <ChartCard title="Reactions">
              {reactionItems.length > 0 ? (
                <BarList items={reactionItems} maxItems={10} />
              ) : (
                <p className="no-data">No reactions yet.</p>
              )}
            </ChartCard>

            <div className="stats-footer">
              <span>
                Updated: {new Date(stats!.computed_at).toLocaleString()}
                {" · "}
                <button
                  className="refresh-link"
                  onClick={handleRefresh}
                  disabled={isRefreshing}
                >
                  {isRefreshing ? "Refreshing..." : "Refresh cache"}
                </button>
              </span>
              {stats!.first_view_at && (
                <span>
                  First view: {new Date(stats!.first_view_at).toLocaleString()}
                </span>
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
          z-index: 20000;
          padding: 20px;
          -webkit-backdrop-filter: blur(4px);
          backdrop-filter: blur(4px);
        }

        .stats-panel {
          background: var(--bg-secondary, #1a1a2e);
          border-radius: 16px;
          width: 100%;
          max-width: 720px;
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
          background: linear-gradient(
            135deg,
            rgba(180, 78, 255, 0.1),
            rgba(78, 159, 255, 0.1)
          );
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
          padding: 14px 24px;
          border-bottom: 1px solid var(--bg-tertiary, #2a2a3e);
        }

        .toggle-label {
          display: flex;
          align-items: center;
          gap: 10px;
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

        .stats-content {
          padding: 20px 24px 24px;
          overflow-y: auto;
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .stats-loading {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 12px;
          padding: 60px 24px;
          color: var(--text-secondary, #ccc);
        }

        .loading-spinner {
          width: 32px;
          height: 32px;
          border: 3px solid rgba(255, 255, 255, 0.15);
          border-top-color: var(--accent-cyan, #4ecdc4);
          border-radius: 50%;
          animation: spin 0.9s linear infinite;
        }

        @keyframes spin {
          to {
            transform: rotate(360deg);
          }
        }

        .stats-error {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 40px 24px;
          color: var(--text-secondary, #ccc);
          justify-content: center;
        }

        .no-data {
          color: var(--text-muted, #6a6a80);
          font-style: italic;
          margin: 0;
        }

        .stats-footer {
          display: flex;
          justify-content: space-between;
          flex-wrap: wrap;
          gap: 8px;
          font-size: 0.75rem;
          color: var(--text-muted, #6a6a80);
        }

        .refresh-link {
          background: none;
          border: none;
          color: var(--accent-cyan, #4ecdc4);
          cursor: pointer;
          padding: 0;
          font-size: inherit;
          text-decoration: underline;
        }

        .refresh-link:disabled {
          color: var(--text-muted, #6a6a80);
          cursor: default;
        }
      `}</style>
    </div>
  );
}
