interface KpiCardProps {
  label: string;
  value: string;
  /** Fine print explaining how the number is computed; also shown on hover. */
  hint?: string;
}

export default function KpiCard({ label, value, hint }: KpiCardProps) {
  return (
    <div className="kpi-card" title={hint}>
      <div className={hint ? 'kpi-label kpi-label-hinted' : 'kpi-label'}>{label}</div>
      <div className="kpi-value">{value}</div>
      <style jsx>{`
        .kpi-card {
          background: var(--bg-card, #16161f);
          border: 1px solid rgba(255, 255, 255, 0.06);
          border-radius: 12px;
          padding: 14px 16px;
          min-width: 0;
        }

        .kpi-label {
          font-size: 0.7rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--text-muted, #6a6a80);
          margin-bottom: 6px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .kpi-label-hinted {
          text-decoration: underline dotted rgba(255, 255, 255, 0.3);
          text-underline-offset: 3px;
          cursor: help;
        }

        .kpi-value {
          font-size: 1.5rem;
          font-weight: 700;
          color: var(--text-primary, #e8e8f0);
          line-height: 1.2;
        }
      `}</style>
    </div>
  );
}
