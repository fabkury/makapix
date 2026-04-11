import dynamic from 'next/dynamic';

// The WebPlayer chunk pulls in SPOCommentsOverlay and its transitive deps.
// Most pageviews never open the player, so we code-split it behind a dynamic
// import with SSR disabled to keep the initial bundle lean — critical for the
// old/low-end browsers the Web Player targets.
export const WebPlayer = dynamic(
  () => import('./WebPlayer').then((m) => m.WebPlayer),
  { ssr: false, loading: () => null },
);
