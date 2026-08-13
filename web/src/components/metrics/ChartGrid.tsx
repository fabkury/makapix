import { ReactNode } from "react";

/**
 * 1-column chart layout that becomes 2 columns at >=1024px. Extracted from
 * SiteMetricsPanel so the artist-facing stats surfaces share one layout.
 * `min-width: 0` on children keeps recharts from forcing horizontal scroll.
 */
export default function ChartGrid({ children }: { children: ReactNode }) {
  return (
    <div className="chart-grid">
      {children}
      <style jsx>{`
        .chart-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 16px;
        }

        @media (min-width: 1024px) {
          .chart-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
        }

        .chart-grid > :global(*) {
          min-width: 0;
        }
      `}</style>
    </div>
  );
}
