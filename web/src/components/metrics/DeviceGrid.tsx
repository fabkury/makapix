// Device type labels — must mirror api/app/utils/view_tracking.py:DeviceType.
export const DEVICE_LABELS: Record<string, string> = {
  desktop: '💻 Desktop',
  mobile: '📱 Mobile',
  tablet: '📱 Tablet',
  player: '🎮 Player',
};

interface DeviceGridProps {
  viewsByDevice: Record<string, number>;
}

export default function DeviceGrid({ viewsByDevice }: DeviceGridProps) {
  const entries = Object.entries(viewsByDevice).sort(([, a], [, b]) => b - a);
  const total = entries.reduce((sum, [, count]) => sum + count, 0);
  if (entries.length === 0 || total === 0) return null;

  return (
    <div className="device-grid">
      {entries.map(([device, count]) => (
        <div key={device} className="device-tile">
          <div className="device-label">{DEVICE_LABELS[device] || device}</div>
          <div className="device-pct">{((count / total) * 100).toFixed(1)}%</div>
          <div className="device-count">{count.toLocaleString()} views</div>
        </div>
      ))}
      <style jsx>{`
        .device-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
          gap: 10px;
        }

        .device-tile {
          background: var(--bg-tertiary, #1a1a24);
          border-radius: 8px;
          padding: 12px;
          text-align: center;
        }

        .device-label {
          font-size: 0.75rem;
          color: var(--text-secondary, #a0a0b8);
          margin-bottom: 4px;
        }

        .device-pct {
          font-size: 1.2rem;
          font-weight: 700;
          color: var(--text-primary, #e8e8f0);
        }

        .device-count {
          font-size: 0.7rem;
          color: var(--text-muted, #6a6a80);
          margin-top: 2px;
          font-variant-numeric: tabular-nums;
        }
      `}</style>
    </div>
  );
}
