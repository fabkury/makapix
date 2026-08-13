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

  return (
    <div className="trend-chart">
      {hasSecondary && (
        <div className="legend">
          <span className="legend-item">
            <span className="legend-key" style={{ background: primaryColor }} />
            {primaryName}
          </span>
          <span className="legend-item">
            <span className="legend-key legend-key-line" style={{ background: secondaryColor }} />
            {secondaryName}
          </span>
        </div>
      )}
      <div className="chart-box" style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke={CHART.grid} />
            <XAxis
              dataKey="x"
              tickLine={false}
              axisLine={{ stroke: CHART.axisLine }}
              interval="preserveStartEnd"
              minTickGap={16}
              tick={
                granularity === 'day' ? <DayTick /> : { fill: CHART.tick, fontSize: 11 }
              }
              tickFormatter={granularity === 'day' ? formatDayTick : formatHourTick}
            />
            <YAxis
              width={44}
              allowDecimals={false}
              tickFormatter={formatCompact}
              tick={{ fill: CHART.tick, fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              content={<ChartTooltip granularity={granularity} />}
              cursor={{ fill: 'rgba(255, 255, 255, 0.05)' }}
            />
            <Bar
              dataKey="primary"
              name={primaryName}
              fill={primaryColor}
              fillOpacity={0.85}
              maxBarSize={24}
              radius={[4, 4, 0, 0]}
              animationDuration={300}
            />
            {hasSecondary && (
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
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
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

        .legend {
          display: flex;
          gap: 16px;
          margin-bottom: 8px;
          font-size: 0.8rem;
          color: var(--text-secondary, #a0a0b8);
        }

        .legend-item {
          display: inline-flex;
          align-items: center;
          gap: 6px;
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
