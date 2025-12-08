import type { AppProps } from 'next/app';
import { useEffect, useRef } from 'react';
import { useRouter } from 'next/router';
import '../styles/globals.css';
import { getAccessToken, getRefreshToken, isTokenExpired, refreshAccessToken } from '../lib/api';
import { usePageViewTracking } from '../hooks/usePageViewTracking';

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter();
  // Use ref to prevent duplicate refresh attempts
  const isCheckingRef = useRef(false);

  // Track page views for analytics
  usePageViewTracking();

  // Check token and refresh if needed
  // This function handles all token refresh scenarios including:
  // - App first load / browser reopen after being closed
  // - Tab becoming visible after being in background
  // - Periodic checks while app is active
  const checkAndRefreshToken = async (reason: string = 'scheduled') => {
    // Prevent concurrent checks
    if (isCheckingRef.current) {
      console.log(`[Auth] Skipping check (${reason}) - already in progress`);
      return;
    }
    
    isCheckingRef.current = true;
    
    try {
      const token = getAccessToken();
      const refreshToken = getRefreshToken();
      
      // No tokens at all - user is logged out, nothing to do
      if (!token && !refreshToken) {
        console.log(`[Auth] No tokens found (${reason}) - user not logged in`);
        return;
      }
      
      // If we have a refresh token but no access token, try to refresh
      // This can happen if access token was cleared but refresh token remains
      if (!token && refreshToken) {
        console.log(`[Auth] No access token but have refresh token, attempting refresh (${reason})`);
        const success = await refreshAccessToken();
        if (success) {
          console.log('[Auth] Refresh successful - session restored');
        } else {
          console.log('[Auth] Refresh failed - user will need to log in again');
        }
        return;
      }
      
      // If token exists, check if it's expired or about to expire
      // Use a 5 minute buffer to refresh before actual expiry
      if (token) {
        const expired = isTokenExpired(token, 0); // Actually expired
        const expiringSoon = isTokenExpired(token, 300); // Within 5 minutes
        
        if (expired) {
          console.log(`[Auth] Access token EXPIRED, attempting refresh (${reason})`);
          const success = await refreshAccessToken();
          if (success) {
            console.log('[Auth] Refresh successful - session restored from expired token');
          } else {
            console.log('[Auth] Refresh failed - user will need to log in again');
          }
        } else if (expiringSoon) {
          console.log(`[Auth] Access token expiring soon, refreshing proactively (${reason})`);
          const success = await refreshAccessToken();
          if (success) {
            console.log('[Auth] Proactive refresh successful');
          } else {
            console.log('[Auth] Proactive refresh failed - will retry later');
          }
        }
        // else: token is valid and not expiring soon, nothing to do
      }
    } finally {
      isCheckingRef.current = false;
    }
  };

  // Proactive token refresh - runs on mount and sets up event listeners
  useEffect(() => {
    // CRITICAL: Initial check on mount
    // This handles the case where user reopens browser after closing it
    // The access token may be expired but refresh token should still be valid
    console.log('[Auth] App mounted, checking token status');
    checkAndRefreshToken('mount');

    // Set up interval to check every 2 minutes (will be throttled in background)
    const refreshInterval = setInterval(() => {
      checkAndRefreshToken('interval');
    }, 120000); // 2 minutes

    // CRITICAL: Handle visibility change - when user returns to tab
    // This is essential because setInterval is heavily throttled when tab is in background
    // When user reopens browser or switches back to tab, we immediately check
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        console.log('[Auth] Tab became visible, checking token');
        checkAndRefreshToken('visibility');
      }
    };

    // Handle window focus - backup for visibility change
    const handleFocus = () => {
      checkAndRefreshToken('focus');
    };

    // Handle online event - refresh when connection is restored after being offline
    const handleOnline = () => {
      console.log('[Auth] Network connection restored, checking token');
      checkAndRefreshToken('online');
    };

    // Handle storage events from other tabs
    // This synchronizes auth state when another tab logs out or refreshes
    const handleStorageChange = (event: StorageEvent) => {
      if (event.key === 'access_token' || event.key === 'refresh_token') {
        console.log(`[Auth] Storage changed from another tab: ${event.key}`);
        // Another tab modified tokens, re-check our state
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

  return <Component {...pageProps} />;
}

