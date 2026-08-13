import { ReactNode } from 'react';

export interface BarListItem {
  key: string;
  label: ReactNode;
  /** Full-text hover title (e.g. an unabbreviated page path). */
  title?: string;
  count: number;
}

interface BarListProps {
  items: BarListItem[];
  maxItems?: number;
  variant?: 'default' | 'player' | 'error';
}

const FILLS: Record<NonNullable<BarListProps['variant']>, string> = {
  default: 'linear-gradient(90deg, #b44eff, #ff6eb4)',
  player: 'linear-gradient(90deg, #00d4ff, #7fdbda)',
  error: 'linear-gradient(90deg, #ef4444, #f97316)',
};

export default function BarList({ items, maxItems = 10, variant = 'default' }: BarListProps) {
  const shown = [...items].sort((a, b) => b.count - a.count).slice(0, maxItems);
  if (shown.length === 0) return null;
  const max = Math.max(...shown.map((item) => item.count), 1);

  return (
    <div className="bar-list">
      {shown.map((item) => (
        <div key={item.key} className="bar-row">
          <div className="bar-label" title={item.title}>
            {item.label}
          </div>
          <div className="bar-track">
            <div
              className="bar-fill"
              style={{ width: `${(item.count / max) * 100}%`, background: FILLS[variant] }}
            />
          </div>
          <div className="bar-value">{item.count.toLocaleString()}</div>
        </div>
      ))}
      <style jsx>{`
        .bar-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          min-width: 0;
        }

        .bar-row {
          display: grid;
          grid-template-columns: minmax(0, 220px) 1fr 64px;
          align-items: center;
          gap: 12px;
        }

        .bar-label {
          font-size: 0.8rem;
          color: var(--text-secondary, #a0a0b8);
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .bar-track {
          height: 8px;
          background: var(--bg-tertiary, #1a1a24);
          border-radius: 4px;
          overflow: hidden;
        }

        .bar-fill {
          height: 100%;
          border-radius: 4px;
          transition: width 0.3s ease;
        }

        .bar-value {
          font-size: 0.8rem;
          color: var(--text-secondary, #a0a0b8);
          text-align: right;
          font-variant-numeric: tabular-nums;
        }
      `}</style>
    </div>
  );
}
