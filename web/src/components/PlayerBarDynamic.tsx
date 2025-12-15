import dynamic from 'next/dynamic';

// Export the height constant without importing `PlayerBar` on the server.
// IMPORTANT: `dynamic(..., { ssr: false })` prevents SSR rendering, but a normal re-export
// would still cause the server bundle to import `./PlayerBar` at module evaluation time.
// That can crash SSR/dev server when `PlayerBar` (or its deps) touch browser-only APIs.
export const PLAYER_BAR_HEIGHT = 64;

/**
 * Dynamic import of PlayerBar with SSR disabled.
 * This eliminates all hydration issues by ensuring the component
 * only renders on the client side.
 */
const PlayerBarDynamic = dynamic(() => import('./PlayerBar'), {
  ssr: false,
});

export default PlayerBarDynamic;

