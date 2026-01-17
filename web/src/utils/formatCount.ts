/**
 * Format a number for display in profile stats with 3 significant digits.
 * - Numbers < 1000: show as-is (e.g., 7, 999)
 * - Numbers >= 1000: show with K/M/B suffix (e.g., 1.11 K, 12.9 M)
 */
export function formatCount(num: number): string {
  if (num < 1000) {
    return String(num);
  }
  const units = [
    { value: 1e9, symbol: 'B' },
    { value: 1e6, symbol: 'M' },
    { value: 1e3, symbol: 'K' },
  ];
  for (const unit of units) {
    if (num >= unit.value) {
      const scaled = num / unit.value;
      return parseFloat(scaled.toPrecision(3)) + ' ' + unit.symbol;
    }
  }
  return String(num);
}
