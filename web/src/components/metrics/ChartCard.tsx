import { ReactNode } from 'react';

interface ChartCardProps {
  title: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
}

export default function ChartCard({ title, subtitle, children, className }: ChartCardProps) {
  return (
    <section className={className ? `chart-card ${className}` : 'chart-card'}>
      <header className="chart-card-header">
        <h3>{title}</h3>
        {subtitle && <p>{subtitle}</p>}
      </header>
      <div className="chart-card-body">{children}</div>
      <style jsx>{`
        .chart-card {
          background: var(--bg-card, #16161f);
          border: 1px solid rgba(255, 255, 255, 0.06);
          border-radius: 12px;
          padding: 20px;
          min-width: 0;
        }

        .chart-card-header h3 {
          margin: 0;
          font-size: 0.95rem;
          font-weight: 600;
          color: var(--text-primary, #e8e8f0);
        }

        .chart-card-header p {
          margin: 4px 0 0;
          font-size: 0.75rem;
          color: var(--text-muted, #6a6a80);
        }

        .chart-card-body {
          margin-top: 14px;
          min-width: 0;
        }
      `}</style>
    </section>
  );
}
