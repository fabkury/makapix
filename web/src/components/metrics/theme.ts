// Chart colors for the mod-dashboard metrics panel.
//
// Hex values mirror web/src/styles/globals.css :root — keep in sync if the
// site tokens ever change. They are hardcoded because recharts sets SVG
// presentation attributes, which cannot resolve CSS custom properties.
//
// Color follows the entity, never the chart: views are always cyan, unique
// visitors always pink, signups always blue, posts always purple. Red is
// reserved for errors and never used as a series color.
//
// CVD note (validated): purple (#b44eff) and blue (#4e9fff) sit at the
// deutan-separation floor — never plot them in the same chart.
export const CHART = {
  cyan: '#00d4ff', // --accent-cyan   → page views, player views
  pink: '#ff6eb4', // --accent-pink   → unique visitors
  blue: '#4e9fff', // --accent-blue   → signups
  purple: '#b44eff', // --accent-purple → posts, breakdown bars
  red: '#ef4444', // errors only — never a series color
  grid: 'rgba(255, 255, 255, 0.06)',
  axisLine: 'rgba(255, 255, 255, 0.12)',
  tick: '#6a6a80', // --text-muted
  tickWeekend: '#a0a0b8', // --text-secondary (weekend ticks read slightly brighter)
  surface: '#16161f', // --bg-card; ring color for line dots, tooltip cursor base
} as const;
