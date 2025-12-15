import type { AppProps } from 'next/app';
import { useEffect, useRef } from 'react';
import { useRouter } from 'next/router';
import '../styles/globals.css';
import { getAccessToken, isTokenExpired, refreshAccessToken, wasRecentlyLoggedOut } from '../lib/api';
import { usePageViewTracking } from '../hooks/usePageViewTracking';
import { PlayerBarProvider } from '../contexts/PlayerBarContext';

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter();
  // Use ref to prevent duplicate refresh attempts
  const isCheckingRef = useRef(false);

  // Track page views for analytics
  usePageViewTracking();

  // In dev tooling (including automated browsers), extra DOM attributes may be injected
  // before hydration (e.g. `data-cursor-ref`), which can cause noisy hydration warnings.
  // Filter only that specific warning so real issues still surface.
  useEffect(() => {
    if (process.env.NODE_ENV === 'production') return;

    const origError = console.error;
    const origWarn = console.warn;

    const shouldFilter = (args: unknown[]) =>
      args.some((a) => typeof a === 'string' && a.includes('data-cursor-ref'));

    console.error = (...args: unknown[]) => {
      if (shouldFilter(args)) return;
      origError(...args);
    };
    console.warn = (...args: unknown[]) => {
      if (shouldFilter(args)) return;
      origWarn(...args);
    };

    return () => {
      console.error = origError;
      console.warn = origWarn;
    };
  }, []);

  // Check token and refresh if needed
  const checkAndRefreshToken = async (_reason: string = 'scheduled') => {
    // Prevent concurrent checks
    if (isCheckingRef.current) return;
    
    isCheckingRef.current = true;
    
    try {
      const token = getAccessToken();
      
      // If no access token, try to refresh using the HttpOnly cookie
      if (!token) {
        if (wasRecentlyLoggedOut()) return;
        await refreshAccessToken();
        return;
      }
      
      // If token exists, check if expired or about to expire
      const expired = isTokenExpired(token, 0);
      const expiringSoon = isTokenExpired(token, 300); // 5 minute buffer
      
      if (expired || expiringSoon) {
        await refreshAccessToken();
      }
    } finally {
      isCheckingRef.current = false;
    }
  };

  // Proactive token refresh - runs on mount and sets up event listeners
  useEffect(() => {
    // Initial check on mount - handles case where user reopens browser
    checkAndRefreshToken('mount');

    // Set up interval to check every 2 minutes (will be throttled in background)
    const refreshInterval = setInterval(() => {
      checkAndRefreshToken('interval');
    }, 120000); // 2 minutes

    // Handle visibility change - when user returns to tab
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        checkAndRefreshToken('visibility');
      }
    };

    // Handle window focus - backup for visibility change
    const handleFocus = () => {
      checkAndRefreshToken('focus');
    };

    // Handle online event - refresh when connection is restored
    const handleOnline = () => {
      checkAndRefreshToken('online');
    };

    // Handle storage events from other tabs
    const handleStorageChange = (event: StorageEvent) => {
      if (event.key === 'access_token') {
        checkAndRefreshToken('storage-sync');
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('focus', handleFocus);
    window.addEventListener('online', handleOnline);
    window.addEventListener('storage', handleStorageChange);

    return () => {
      clearInterval(refreshInterval);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('focus', handleFocus);
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []); // Empty deps - only run once on mount

  // Check token on route change
  useEffect(() => {
    const handleRouteChange = () => {
      checkAndRefreshToken('navigation');
    };

    router.events.on('routeChangeStart', handleRouteChange);

    return () => {
      router.events.off('routeChangeStart', handleRouteChange);
    };
  }, [router.events]);

  return (
    <PlayerBarProvider>
      <Component {...pageProps} />
    </PlayerBarProvider>
  );
}

