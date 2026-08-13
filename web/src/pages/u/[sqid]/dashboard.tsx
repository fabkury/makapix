import { useState, useEffect } from "react";
import { useRouter } from "next/router";
import Link from "next/link";
import Layout from "../../../components/Layout";
import {
  ApiRequestError,
  clearTokens,
  getArtistDashboard,
} from "../../../lib/api";
import {
  ArtistDashboardResponse,
  DailyViewCount,
} from "../../../types/stats";
import { TrendPoint } from "../../../components/metrics/types";
import { CHART } from "../../../components/metrics/theme";
import {
  countryName,
  getCountryFlag,
} from "../../../components/metrics/format";
import BarList, {
  BarListItem,
} from "../../../components/metrics/BarList";
import ChartCard from "../../../components/metrics/ChartCard";
import ChartGrid from "../../../components/metrics/ChartGrid";
import DeviceGrid from "../../../components/metrics/DeviceGrid";
import KpiCard from "../../../components/metrics/KpiCard";
import KpiGrid from "../../../components/metrics/KpiGrid";
import TrendChart from "../../../components/metrics/TrendChart";

const toViewTrend = (daily: DailyViewCount[]): TrendPoint[] =>
  (daily || []).map((d) => ({
    x: d.date,
    primary: d.views,
    secondary: d.unique_viewers,
  }));

const toImpressionTrend = (daily: DailyViewCount[]): TrendPoint[] =>
  (daily || []).map((d) => ({ x: d.date, primary: d.impressions ?? 0 }));

/**
 * Artist Dashboard on the metrics kit (docs/artwork-views/): 30-day Views
 * vs Impressions (never summed, D2), daily trend, countries with flags,
 * device share, and the per-artwork table.
 */
export default function ArtistDashboard() {
  const router = useRouter();
  const { sqid } = router.query;

  const [dashboard, setDashboard] = useState<ArtistDashboardResponse | null>(
    null,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [includeUnauthenticated, setIncludeUnauthenticated] = useState(true);

  useEffect(() => {
    if (!sqid || typeof sqid !== "string") return;

    const fetchDashboard = async () => {
      setLoading(true);
      setError(null);
      try {
        setDashboard(await getArtistDashboard(sqid, page));
      } catch (err) {
        if (err instanceof ApiRequestError) {
          if (err.status === 401) {
            clearTokens();
            router.push("/auth");
            return;
          }
          if (err.status === 403) {
            setError("You do not have permission to view this dashboard");
          } else if (err.status === 404) {
            setError("Artist not found");
          } else {
            setError("Failed to load dashboard");
          }
        } else {
          console.error("Error fetching dashboard:", err);
          setError("Failed to load dashboard");
        }
      } finally {
        setLoading(false);
      }
    };

    fetchDashboard();
  }, [sqid, page, router]);

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
            min-height: calc(100vh - var(--header-offset));
          }
          .loading-spinner {
            width: 40px;
            height: 40px;
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
        `}</style>
      </Layout>
    );
  }

  if (error || !dashboard) {
    return (
      <Layout title="Artist Dashboard">
        <div className="error-container">
          <span className="error-icon">😢</span>
          <h1>{error || "Dashboard not found"}</h1>
          <Link href={`/u/${sqid}`} className="back-link">
            ← Back to Profile
          </Link>
        </div>
        <style jsx>{`
          .error-container {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            min-height: calc(100vh - var(--header-offset));
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

  const a = dashboard.artist_stats;
  const stats = includeUnauthenticated
    ? {
        total_views: a.total_views,
        unique_viewers: a.unique_viewers,
        total_impressions: a.total_impressions ?? 0,
        views_by_country: a.views_by_country,
        views_by_device: a.views_by_device,
        daily_views: a.daily_views ?? [],
        total_reactions: a.total_reactions,
        reactions_by_emoji: a.reactions_by_emoji,
        total_comments: a.total_comments,
      }
    : {
        total_views: a.total_views_authenticated,
        unique_viewers: a.unique_viewers_authenticated,
        total_impressions: a.total_impressions_authenticated ?? 0,
        views_by_country: a.views_by_country_authenticated,
        views_by_device: a.views_by_device_authenticated,
        daily_views: a.daily_views_authenticated ?? [],
        total_reactions: a.total_reactions_authenticated,
        reactions_by_emoji: a.reactions_by_emoji_authenticated,
        total_comments: a.total_comments_authenticated,
      };

  const countryItems: BarListItem[] = Object.entries(
    stats.views_by_country,
  ).map(([code, count]) => ({
    key: code,
    label: `${getCountryFlag(code)} ${countryName(code)}`,
    title: countryName(code),
    count,
  }));

  const reactionItems: BarListItem[] = Object.entries(
    stats.reactions_by_emoji,
  ).map(([emoji, count]) => ({ key: emoji, label: emoji, count }));

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
                checked={includeUnauthenticated}
                onChange={(e) => setIncludeUnauthenticated(e.target.checked)}
              />
              <span>Include unauthenticated traffic</span>
            </label>
          </div>
        </div>

        {/* KPI row */}
        <div className="kpi-section">
          <KpiGrid>
            <KpiCard label="Posts" value={a.total_posts.toLocaleString()} />
            <KpiCard
              label="Views (30d)"
              value={stats.total_views.toLocaleString()}
              hint="Deliberate looks — counted at most once per visitor per artwork per day."
            />
            <KpiCard
              label="Impressions (30d)"
              value={stats.total_impressions.toLocaleString()}
              hint="Passive exposure during player / web-player rotation. Never added to Views."
            />
            <KpiCard
              label="Unique viewers (30d)"
              value={stats.unique_viewers.toLocaleString()}
              hint="Approximate — summed per day and per artwork; a returning viewer counts more than once."
            />
            <KpiCard
              label="Reactions"
              value={stats.total_reactions.toLocaleString()}
            />
            <KpiCard
              label="Comments"
              value={stats.total_comments.toLocaleString()}
            />
          </KpiGrid>
        </div>

        {/* Charts */}
        <div className="charts-section">
          <ChartGrid>
            <ChartCard title="Daily views" subtitle="Last 30 days, all artworks">
              <TrendChart
                data={toViewTrend(stats.daily_views)}
                granularity="day"
                primaryName="Views"
                primaryColor={CHART.cyan}
                secondaryName="Unique viewers"
                secondaryColor={CHART.pink}
                height={220}
              />
            </ChartCard>
            {stats.total_impressions > 0 && (
              <ChartCard
                title="Daily impressions"
                subtitle="Last 30 days · playback exposure"
              >
                <TrendChart
                  data={toImpressionTrend(stats.daily_views)}
                  granularity="day"
                  primaryName="Impressions"
                  primaryColor={CHART.purple}
                  height={220}
                />
              </ChartCard>
            )}
            {countryItems.length > 0 && (
              <ChartCard title="Top countries" subtitle="Views, last 30 days">
                <BarList items={countryItems} />
              </ChartCard>
            )}
            {Object.keys(stats.views_by_device).length > 0 && (
              <ChartCard title="Devices" subtitle="Share of views, last 30 days">
                <DeviceGrid viewsByDevice={stats.views_by_device} />
              </ChartCard>
            )}
            {reactionItems.length > 0 && (
              <ChartCard title="Reactions">
                <BarList items={reactionItems} maxItems={10} />
              </ChartCard>
            )}
          </ChartGrid>
        </div>

        {/* Post Statistics List */}
        <div className="posts-section">
          <h2>Per-artwork stats</h2>
          <div className="posts-table">
            <div className="table-header">
              <div className="col-title">Post</div>
              <div className="col-stat">Views</div>
              <div className="col-stat">Impressions</div>
              <div className="col-stat">Reactions</div>
              <div className="col-stat">Comments</div>
            </div>
            {dashboard.posts.map((post) => {
              const row = includeUnauthenticated
                ? {
                    views: post.total_views,
                    impressions: post.total_impressions ?? 0,
                    reactions: post.total_reactions,
                    comments: post.total_comments,
                  }
                : {
                    views: post.total_views_authenticated,
                    impressions: post.total_impressions_authenticated ?? 0,
                    reactions: post.total_reactions_authenticated,
                    comments: post.total_comments_authenticated,
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
                  <div className="col-stat" data-label="Views:">
                    {row.views.toLocaleString()}
                  </div>
                  <div className="col-stat" data-label="Impressions:">
                    {row.impressions.toLocaleString()}
                  </div>
                  <div className="col-stat" data-label="Reactions:">
                    {row.reactions.toLocaleString()}
                  </div>
                  <div className="col-stat" data-label="Comments:">
                    {row.comments.toLocaleString()}
                  </div>
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
                Page {page} of{" "}
                {Math.ceil(dashboard.total_posts / dashboard.page_size)}
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
          margin-bottom: 24px;
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
          width: 16px;
          height: 16px;
        }

        .kpi-section {
          margin-bottom: 16px;
        }

        .charts-section {
          margin-bottom: 24px;
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
        }
        .col-title > :global(* + *) {
          margin-top: 4px;
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
          margin-top: 24px;
        }
        .pagination > :global(* + *) {
          margin-left: 16px;
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
          .table-header,
          .table-row {
            font-size: 0.85rem;
            gap: 8px;
          }
        }

        @media (max-width: 480px) {
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
