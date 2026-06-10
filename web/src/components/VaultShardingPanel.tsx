import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { authenticatedFetch } from '../lib/api';
import { ensureCompatibleArtUrl } from '../utils/imageCompat';

interface VaultShardingDailyRow {
  date: string;
  has_data: boolean;
  level2_human: number;
  level2_bot: number;
  level3_human: number;
  level3_bot: number;
  level2_misses: number;
  level3_misses: number;
}

interface VaultShardingClassRow {
  asset_class: string;
  shard_level: number;
  downloads_human: number;
  downloads_bot: number;
  misses: number;
}

interface LegacyStragglerRow {
  post_id: number;
  public_sqid: string | null;
  title: string | null;
  art_url: string | null;
  owner_handle: string | null;
  downloads_human: number;
  downloads_bot: number;
  last_seen: string;
}

interface VaultShardingStats {
  window_days: number;
  streak_days: number;
  streak_criterion_days: number;
  streak_as_of: string;
  daily: VaultShardingDailyRow[];
  class_totals: VaultShardingClassRow[];
  stragglers: LegacyStragglerRow[];
  straggler_window_days: number;
  computed_at: string;
}

/**
 * Vault resharding migration instrumentation (docs/vault-resharding/).
 *
 * Shows daily downloads split by sharding scheme (2-level = new, 3-level =
 * legacy), the retirement streak counter that gates Phase 5 deletion, and
 * the list of artworks still being fetched via legacy URLs.
 */
export default function VaultShardingPanel() {
  const [stats, setStats] = useState<VaultShardingStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [includeBots, setIncludeBots] = useState(false);

  const API_BASE_URL =
    typeof window !== 'undefined'
      ? process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin
      : '';

  const fetchStats = useCallback(async () => {
    try {
      const response = await authenticatedFetch(
        `${API_BASE_URL}/api/admin/vault-sharding-stats?days=30`,
      );
      if (!response.ok) {
        setError(
          response.status === 403
            ? "You don't have permission to view these stats"
            : 'Failed to load vault sharding stats',
        );
        return;
      }
      const data = (await response.json()) as VaultShardingStats;
      setStats(data);
      setError(null);
    } catch (err) {
      console.error('Error fetching vault sharding stats:', err);
      setError('Failed to load vault sharding stats');
    }
  }, [API_BASE_URL]);

  useEffect(() => {
    setLoading(true);
    fetchStats().finally(() => setLoading(false));
  }, [fetchStats]);

  if (loading) {
    return (
      <div className="sharding-loading">
        <div>Loading resharding stats…</div>
      </div>
    );
  }
  if (error || !stats) {
    return <div className="sharding-error">⚠️ {error || 'No data'}</div>;
  }

  const dayTotal = (d: VaultShardingDailyRow, level: 2 | 3) => {
    const human = level === 2 ? d.level2_human : d.level3_human;
    const bot = level === 2 ? d.level2_bot : d.level3_bot;
    return human + (includeBots ? bot : 0);
  };
  const maxDaily = Math.max(
    ...stats.daily.map((d) => Math.max(dayTotal(d, 2), dayTotal(d, 3))),
    1,
  );
  const gaps = stats.daily.filter((d) => !d.has_data).length;
  const totalMisses = stats.daily.reduce(
    (acc, d) => acc + d.level2_misses + d.level3_misses,
    0,
  );
  const criterionMet = stats.streak_days >= stats.streak_criterion_days;

  return (
    <div className="vault-sharding">
      <h2>🗄️ Vault Resharding Migration</h2>
      <div className="caveat">
        ℹ️ Tracks the 3-level → 2-level vault migration
        (docs/vault-resharding/). Legacy (3-level) copies may be deleted only
        after the streak below reaches {stats.streak_criterion_days} days —
        and only manually.
      </div>

      {/* Retirement streak */}
      <div className={`streak-card ${criterionMet ? 'met' : ''}`}>
        <div className="streak-value">
          {stats.streak_days} / {stats.streak_criterion_days}
        </div>
        <div className="streak-label">
          consecutive days with 0 non-bot legacy downloads (as of{' '}
          {stats.streak_as_of})
          {criterionMet && ' — retirement criterion MET'}
        </div>
        {gaps > 0 && (
          <div className="streak-warning">
            ⚠️ {gaps} day(s) in this window have no rollup data — data gaps
            block the streak and need investigation, they are not quiet days.
          </div>
        )}
        {totalMisses > 0 && (
          <div className="streak-warning">
            ⚠️ {totalMisses} vault 404(s) in this window — during the dual
            window this signals a copy/dual-delete bug.
          </div>
        )}
      </div>

      {/* Bots toggle */}
      <div className="metrics-toggle">
        <label className="toggle-label">
          <input
            type="checkbox"
            checked={includeBots}
            onChange={(e) => setIncludeBots(e.target.checked)}
          />
          <span>
            {includeBots
              ? 'Including bot/crawler downloads in bars'
              : 'Showing non-bot downloads only (bots excluded from criterion)'}
          </span>
        </label>
      </div>

      {/* Daily trend: paired bars per day */}
      <div className="metrics-section">
        <h3>
          📊 Downloads by sharding scheme (last {stats.window_days} days)
        </h3>
        <div className="legend">
          <span className="legend-item">
            <span className="swatch new" /> 2-level (new)
          </span>
          <span className="legend-item">
            <span className="swatch legacy" /> 3-level (legacy)
          </span>
          <span className="legend-item">
            <span className="swatch gap" /> no data
          </span>
        </div>
        <div className="trend-chart">
          {stats.daily.map((day) => {
            if (!day.has_data) {
              return (
                <div key={day.date} className="trend-day">
                  <div
                    className="gap-bar"
                    title={`${day.date}: no rollup data (blocks streak)`}
                  />
                </div>
              );
            }
            const l2 = dayTotal(day, 2);
            const l3 = dayTotal(day, 3);
            return (
              <div key={day.date} className="trend-day">
                <div
                  className="bar new"
                  style={{ height: `${Math.max((l2 / maxDaily) * 100, 2)}%` }}
                  title={`${day.date} — 2-level: ${l2}${includeBots ? ' (incl. bots)' : ''}`}
                />
                <div
                  className="bar legacy"
                  style={{ height: `${Math.max((l3 / maxDaily) * 100, 2)}%` }}
                  title={`${day.date} — 3-level legacy: ${l3}${includeBots ? ' (incl. bots)' : ''}`}
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

      {/* Class totals */}
      <div className="metrics-section">
        <h3>Σ Window totals by asset class</h3>
        <table className="totals-table">
          <thead>
            <tr>
              <th>Class</th>
              <th>Scheme</th>
              <th className="num">Human</th>
              <th className="num">Bot</th>
              <th className="num">404s</th>
            </tr>
          </thead>
          <tbody>
            {stats.class_totals.map((row) => (
              <tr key={`${row.asset_class}-${row.shard_level}`}>
                <td>{row.asset_class}</td>
                <td>
                  {row.shard_level === 3 ? '3-level (legacy)' : '2-level (new)'}
                </td>
                <td className="num">{row.downloads_human.toLocaleString()}</td>
                <td className="num">{row.downloads_bot.toLocaleString()}</td>
                <td className="num">{row.misses.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Legacy stragglers */}
      <div className="metrics-section">
        <h3>
          🐌 Legacy stragglers (last {stats.straggler_window_days} days)
        </h3>
        {stats.stragglers.length === 0 ? (
          <div className="empty">
            No artworks fetched via legacy 3-level URLs in this window. 🎉
          </div>
        ) : (
          <table className="totals-table">
            <thead>
              <tr>
                <th className="thumb-col"></th>
                <th>Title</th>
                <th>Artist</th>
                <th className="num">Human</th>
                <th className="num">Bot</th>
                <th>Last seen</th>
              </tr>
            </thead>
            <tbody>
              {stats.stragglers.map((row) => (
                <tr key={row.post_id}>
                  <td className="thumb-col">
                    {row.art_url ? (
                      <img
                        src={ensureCompatibleArtUrl(row.art_url)}
                        alt=""
                        width={32}
                        height={32}
                        loading="lazy"
                      />
                    ) : null}
                  </td>
                  <td>
                    {row.public_sqid ? (
                      <Link href={`/p/${row.public_sqid}`}>
                        {row.title || row.public_sqid}
                      </Link>
                    ) : (
                      <span>{row.title || `post ${row.post_id}`}</span>
                    )}
                  </td>
                  <td>
                    {row.owner_handle ? (
                      <Link href={`/u/${row.owner_handle}`}>
                        @{row.owner_handle}
                      </Link>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="num">{row.downloads_human.toLocaleString()}</td>
                  <td className="num">{row.downloads_bot.toLocaleString()}</td>
                  <td>{row.last_seen}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <style jsx>{`
        .vault-sharding {
          padding: 24px;
          border-top: 2px solid var(--bg-tertiary, #2a2a3e);
          margin-top: 8px;
        }
        .vault-sharding h2 {
          font-size: 1.1rem;
          color: var(--text-primary, #fff);
          margin-bottom: 12px;
        }
        .sharding-loading,
        .sharding-error {
          padding: 40px 24px;
          text-align: center;
          color: var(--text-muted, #888);
        }
        .caveat {
          margin-bottom: 16px;
          padding: 10px 14px;
          background: var(--bg-tertiary, #2a2a3e);
          border-left: 3px solid var(--accent-purple, #b44eff);
          border-radius: 6px;
          color: var(--text-secondary, #ccc);
          font-size: 0.85rem;
          line-height: 1.5;
        }

        .streak-card {
          background: var(--bg-secondary, #1a1a2e);
          border: 1px solid var(--bg-tertiary, #2a2a3e);
          border-radius: 12px;
          padding: 16px;
          text-align: center;
          margin-bottom: 16px;
        }
        .streak-card.met {
          border-color: var(--accent-cyan, #4ecdc4);
        }
        .streak-value {
          font-size: 2rem;
          font-weight: 700;
          color: var(--accent-cyan, #4ecdc4);
        }
        .streak-label {
          font-size: 0.8rem;
          color: var(--text-muted, #888);
          margin-top: 4px;
        }
        .streak-warning {
          margin-top: 10px;
          padding: 8px 12px;
          background: rgba(255, 159, 67, 0.12);
          border-radius: 6px;
          color: #ff9f43;
          font-size: 0.8rem;
          text-align: left;
        }

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
        .toggle-label > :global(* + *) {
          margin-left: 8px;
        }

        .metrics-section {
          margin-bottom: 28px;
        }
        .metrics-section h3 {
          font-size: 1rem;
          font-weight: 600;
          color: var(--text-primary, #fff);
          margin-bottom: 10px;
        }

        .legend {
          display: flex;
          gap: 16px;
          margin-bottom: 8px;
          font-size: 0.75rem;
          color: var(--text-muted, #888);
        }
        .legend-item {
          display: inline-flex;
          align-items: center;
          gap: 5px;
        }
        .swatch {
          width: 12px;
          height: 12px;
          border-radius: 3px;
          display: inline-block;
        }
        .swatch.new {
          background: var(--accent-cyan, #4ecdc4);
        }
        .swatch.legacy {
          background: #ff9f43;
        }
        .swatch.gap {
          background: repeating-linear-gradient(
            45deg,
            #555,
            #555 3px,
            #333 3px,
            #333 6px
          );
        }

        .trend-chart {
          display: flex;
          align-items: flex-end;
          height: 110px;
          background: var(--bg-tertiary, #2a2a3e);
          border-radius: 8px;
          padding: 16px 8px 12px;
          gap: 3px;
        }
        .trend-day {
          flex: 1;
          height: 100%;
          display: flex;
          align-items: flex-end;
          justify-content: center;
          gap: 1px;
        }
        .bar {
          width: 45%;
          border-radius: 2px 2px 0 0;
          transition: height 0.3s ease;
        }
        .bar.new {
          background: var(--accent-cyan, #4ecdc4);
        }
        .bar.legacy {
          background: #ff9f43;
        }
        .gap-bar {
          width: 90%;
          height: 100%;
          border-radius: 2px;
          background: repeating-linear-gradient(
            45deg,
            rgba(255, 255, 255, 0.08),
            rgba(255, 255, 255, 0.08) 3px,
            transparent 3px,
            transparent 6px
          );
        }
        .trend-labels {
          display: flex;
          justify-content: space-between;
          margin-top: 6px;
          font-size: 0.7rem;
          color: var(--text-muted, #888);
        }

        .empty {
          padding: 24px;
          text-align: center;
          color: var(--text-muted, #888);
          background: var(--bg-tertiary, #2a2a3e);
          border-radius: 8px;
        }

        .totals-table {
          width: 100%;
          border-collapse: collapse;
          background: var(--bg-secondary, #1a1a2e);
          border-radius: 8px;
          overflow: hidden;
          font-size: 0.85rem;
        }
        .totals-table th,
        .totals-table td {
          padding: 8px 12px;
          text-align: left;
          border-bottom: 1px solid var(--bg-tertiary, #2a2a3e);
        }
        .totals-table thead th {
          background: var(--bg-tertiary, #2a2a3e);
          font-size: 0.75rem;
          color: var(--text-muted, #888);
          text-transform: uppercase;
          letter-spacing: 0.5px;
        }
        .totals-table .num {
          text-align: right;
          font-variant-numeric: tabular-nums;
        }
        .totals-table .thumb-col {
          width: 40px;
        }
        .totals-table .thumb-col img {
          display: block;
          width: 32px;
          height: 32px;
          object-fit: cover;
          image-rendering: pixelated;
          border-radius: 4px;
          background: var(--bg-tertiary, #2a2a3e);
        }
        .totals-table tr:last-child td {
          border-bottom: 0;
        }
        .totals-table a {
          color: var(--text-primary, #fff);
          text-decoration: none;
        }
        .totals-table a:hover {
          color: var(--accent-cyan, #4ecdc4);
        }
      `}</style>
    </div>
  );
}
