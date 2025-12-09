import { useEffect, useRef } from 'react';
import { useRouter } from 'next/router';

/**
 * Hook to automatically track page views for analytics.
 * 
 * This hook sends a lightweight POST request to the backend tracking API
 * on every page navigation. It's fire-and-forget and won't block page rendering.
 * 
 * Usage:
 * ```typescript
 * export default function MyPage() {
 *   usePageViewTracking();
 *   // ... rest of component
 * }
 * ```
 */
export function usePageViewTracking() {
  const router = useRouter();
  const lastTrackedPath = useRef<string | null>(null);

  useEffect(() => {
    // Track initial page load
    trackPageView(router.asPath);
    lastTrackedPath.current = router.asPath;

    // Track route changes
    const handleRouteChange = (url: string) => {
      // Only track if the path actually changed (not just hash or query params)
      const newPath = url.split('?')[0].split('#')[0];
      const oldPath = lastTrackedPath.current?.split('?')[0].split('#')[0];
      
      if (newPath !== oldPath) {
        trackPageView(url);
        lastTrackedPath.current = url;
      }
    };

    router.events.on('routeChangeComplete', handleRouteChange);

    return () => {
      router.events.off('routeChangeComplete', handleRouteChange);
    };
  }, [router]);
}

/**
 * Send page view tracking request to the backend.
 * 
 * This is a fire-and-forget request that silently fails if there's an error.
 * We don't want tracking failures to affect the user experience.
 */
function trackPageView(path: string) {
  // Get API base URL
  const API_BASE_URL =
    typeof window !== 'undefined'
      ? process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin
      : '';

  // Extract just the path (remove query params and hash for cleaner analytics)
  const cleanPath = path.split('?')[0].split('#')[0];

  // Don't track if on server side
  if (typeof window === 'undefined') {
    return;
  }

  // Send tracking request (fire-and-forget)
  fetch(`${API_BASE_URL}/api/track/page-view`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      path: cleanPath,
      referrer: document.referrer || null,
    }),
    // Use keepalive to ensure request completes even if page unloads
    keepalive: true,
  }).catch(() => {
    // Silently fail - we don't want tracking errors to affect the user
    // Errors are already logged on the backend
  });
}
