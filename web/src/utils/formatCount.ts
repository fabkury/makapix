/**
 * Format a number for display in profile stats.
 * - Numbers < 1000: show as-is
 * - Numbers >= 1000 and < 1M: show as X.XK
 * - Numbers >= 1M: show as X.XM
 */
export function formatCount(num: number): string {
  if (num < 1000) {
    return String(num);
  }
  if (num < 1000000) {
    const k = num / 1000;
    return k >= 100 ? `${Math.floor(k)}K` : `${k.toFixed(1).replace(/\.0$/, '')}K`;
  }
  const m = num / 1000000;
  return m >= 100 ? `${Math.floor(m)}M` : `${m.toFixed(1).replace(/\.0$/, '')}M`;
}
