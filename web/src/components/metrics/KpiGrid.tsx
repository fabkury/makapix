import { ReactNode } from "react";

/**
 * Responsive auto-fit grid for KpiCard rows. Extracted from
 * SiteMetricsPanel so the artist-facing stats surfaces share one layout.
 */
export default function KpiGrid({
  children,
  minWidth = 150,
}: {
  children: ReactNode;
  /** Minimum tile width in px (modal contexts want a tighter 120). */
  minWidth?: number;
}) {
  return (
    <div className="kpi-grid">
      {children}
      <style jsx>{`
        .kpi-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(${minWidth}px, 1fr));
          gap: 12px;
        }
      `}</style>
    </div>
  );
}
