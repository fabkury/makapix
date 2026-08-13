import { formatDayFull, formatHourFull } from './format';

interface TooltipRow {
  name?: string | number;
  value?: number | string;
  color?: string;
  fill?: string;
}

interface ChartTooltipProps {
  granularity: 'day' | 'hour';
  active?: boolean;
  label?: string | number;
  payload?: TooltipRow[];
}

export default function ChartTooltip({ granularity, active, label, payload }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;

  const heading =
    granularity === 'day' ? formatDayFull(String(label ?? '')) : formatHourFull(String(label ?? ''));

  return (
    <div className="chart-tooltip">
      <div className="tooltip-label">{heading}</div>
      {payload.map((entry, i) => (
        <div key={i} className="tooltip-row">
          <span className="tooltip-key" style={{ background: entry.color || entry.fill }} />
          <span className="tooltip-value">
            {typeof entry.value === 'number' ? entry.value.toLocaleString() : entry.value}
          </span>
          <span className="tooltip-name">{entry.name}</span>
        </div>
      ))}
      <style jsx>{`
        .chart-tooltip {
          background: var(--bg-tertiary, #1a1a24);
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 8px;
          box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
          padding: 8px 12px;
          font-size: 0.8rem;
          pointer-events: none;
        }

        .tooltip-label {
          color: var(--text-secondary, #a0a0b8);
          margin-bottom: 4px;
          font-weight: 600;
        }

        .tooltip-row {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 1px 0;
        }

        .tooltip-key {
          width: 12px;
          height: 3px;
          border-radius: 1.5px;
          flex-shrink: 0;
        }

        .tooltip-value {
          color: var(--text-primary, #e8e8f0);
          font-weight: 700;
          font-variant-numeric: tabular-nums;
        }

        .tooltip-name {
          color: var(--text-secondary, #a0a0b8);
        }
      `}</style>
    </div>
  );
}
