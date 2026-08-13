import { useId } from 'react';
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { CHART } from './theme';
import { TrendPoint } from './types';
import {
  formatCompact,
  formatDayFull,
  formatDayTick,
  formatHourFull,
  formatHourTick,
  isWeekend,
} from './format';
import ChartTooltip from './ChartTooltip';

interface TrendChartProps {
  data: TrendPoint[];
  granularity: 'day' | 'hour';
  primaryName: string;
  primaryColor: string;
  secondaryName?: string;
  secondaryColor?: string;
  height?: number;
}

// Weekend ticks render one step brighter than weekday ticks.
function DayTick({ x, y, payload }: { x?: number; y?: number; payload?: { value?: string } }) {
  const value = String(payload?.value ?? '');
  return (
    <text
      x={x}
      y={y}
      dy={12}
      textAnchor="middle"
      fontSize={11}
      fill={isWeekend(value) ? CHART.tickWeekend : CHART.tick}
    >
      {formatDayTick(value)}
    </text>
  );
}

/**
 * Trend chart. With a single series: one bar chart. With a secondary series:
 * stacked small multiples — bars on top, line below — sharing the x-axis,
 * each panel with its own y-scale, hover synced across panels. (Never a
 * dual-axis chart: two y-scales on one plot make series crossings and gaps
 * an artifact of axis choice rather than data.)
 */
export default function TrendChart({
  data,
  granularity,
  primaryName,
  primaryColor,
  secondaryName,
  secondaryColor,
  height = 240,
}: TrendChartProps) {
  const hasSecondary = Boolean(secondaryName && secondaryColor);
  const formatX = granularity === 'day' ? formatDayFull : formatHourFull;
  const syncId = useId();

  // Panel heights: the bottom panel also carries the shared x-axis labels.
  const X_AXIS_SPACE = 26;
  const PANEL_GAP = 6;
  const usable = Math.max(140, height) - X_AXIS_SPACE - PANEL_GAP;
  const primaryHeight = hasSecondary ? Math.round(usable * 0.56) : height;
  const secondaryHeight = usable - Math.round(usable * 0.56) + X_AXIS_SPACE;

  const xAxisTicks = (
    <XAxis
      dataKey="x"
      tickLine={false}
      axisLine={{ stroke: CHART.axisLine }}
      interval="preserveStartEnd"
      minTickGap={16}
      tick={granularity === 'day' ? <DayTick /> : { fill: CHART.tick, fontSize: 11 }}
      tickFormatter={granularity === 'day' ? formatDayTick : formatHourTick}
    />
  );

  const yAxis = (
    <YAxis
      width={44}
      allowDecimals={false}
      tickFormatter={formatCompact}
      tick={{ fill: CHART.tick, fontSize: 11 }}
      axisLine={false}
      tickLine={false}
    />
  );

  const tooltip = (
    <Tooltip
      content={<ChartTooltip granularity={granularity} />}
      cursor={{ fill: 'rgba(255, 255, 255, 0.05)' }}
    />
  );

  const primaryBar = (
    <Bar
      dataKey="primary"
      name={primaryName}
      fill={primaryColor}
      fillOpacity={0.85}
      maxBarSize={24}
      radius={[4, 4, 0, 0]}
      animationDuration={300}
    />
  );

  return (
    <div className="trend-chart">
      {hasSecondary ? (
        <>
          {/* Top panel: primary series (bars), x-axis hidden but aligned */}
          <div className="panel-label">
            <span className="legend-key" style={{ background: primaryColor }} />
            {primaryName}
          </div>
          <div className="chart-box" style={{ height: primaryHeight }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={data}
                syncId={syncId}
                margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
              >
                <CartesianGrid vertical={false} stroke={CHART.grid} />
                <XAxis dataKey="x" hide />
                {yAxis}
                {tooltip}
                {primaryBar}
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* Bottom panel: secondary series (line), carries the x-axis */}
          <div className="panel-label panel-label-secondary">
            <span
              className="legend-key legend-key-line"
              style={{ background: secondaryColor }}
            />
            {secondaryName}
          </div>
          <div className="chart-box" style={{ height: secondaryHeight }}>
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={data}
                syncId={syncId}
                margin={{ top: 4, right: 8, bottom: 0, left: 0 }}
              >
                <CartesianGrid vertical={false} stroke={CHART.grid} />
                {xAxisTicks}
                {yAxis}
                {tooltip}
                <Line
                  dataKey="secondary"
                  name={secondaryName}
                  type="monotone"
                  stroke={secondaryColor}
                  strokeWidth={2}
                  dot={{ r: 4, fill: secondaryColor, stroke: CHART.surface, strokeWidth: 2 }}
                  activeDot={{ r: 5 }}
                  animationDuration={300}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </>
      ) : (
        <div className="chart-box" style={{ height }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid vertical={false} stroke={CHART.grid} />
              {xAxisTicks}
              {yAxis}
              {tooltip}
              {primaryBar}
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
      <details className="data-table">
        <summary>View data</summary>
        <table>
          <thead>
            <tr>
              <th>{granularity === 'day' ? 'Date' : 'Hour'}</th>
              <th>{primaryName}</th>
              {hasSecondary && <th>{secondaryName}</th>}
            </tr>
          </thead>
          <tbody>
            {data.map((point) => (
              <tr key={point.x}>
                <td>{formatX(point.x)}</td>
                <td>{point.primary.toLocaleString()}</td>
                {hasSecondary && <td>{(point.secondary ?? 0).toLocaleString()}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </details>
      <style jsx>{`
        .trend-chart {
          min-width: 0;
        }

        .panel-label {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          margin-bottom: 4px;
          font-size: 0.8rem;
          color: var(--text-secondary, #a0a0b8);
        }

        .panel-label-secondary {
          margin-top: 6px;
        }

        .legend-key {
          width: 12px;
          height: 8px;
          border-radius: 2px;
          flex-shrink: 0;
        }

        .legend-key-line {
          height: 3px;
          border-radius: 1.5px;
        }

        .chart-box {
          min-width: 0;
        }

        .data-table {
          margin-top: 8px;
          font-size: 0.75rem;
          color: var(--text-muted, #6a6a80);
        }

        .data-table summary {
          cursor: pointer;
          user-select: none;
        }

        .data-table summary:hover {
          color: var(--text-secondary, #a0a0b8);
        }

        .data-table table {
          margin-top: 8px;
          border-collapse: collapse;
          width: 100%;
          color: var(--text-secondary, #a0a0b8);
        }

        .data-table th {
          text-align: right;
          font-weight: 600;
          padding: 2px 8px;
          border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }

        .data-table th:first-child {
          text-align: left;
        }

        .data-table td {
          text-align: right;
          padding: 2px 8px;
          font-variant-numeric: tabular-nums;
        }

        .data-table td:first-child {
          text-align: left;
        }
      `}</style>
    </div>
  );
}
