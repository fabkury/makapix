import type { AppProps } from 'next/app';
import React, { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/router';
import Head from 'next/head';
import '../styles/globals.css';
import { getAccessToken, isTokenExpired, refreshAccessToken, wasRecentlyLoggedOut } from '../lib/api';
import { usePageViewTracking } from '../hooks/usePageViewTracking';
import { PlayerBarProvider } from '../contexts/PlayerBarContext';
import { SocialNotificationsProvider } from '../contexts/SocialNotificationsContext';

// Site-wide default SEO / social-share (Open Graph + Twitter) metadata.
// Rendered via next/head so individual pages can override any tag by emitting
// their own <Head> with a matching `key` (e.g. a per-artwork og:image on
// /p/[sqid] — see docs/outreach/05-onsite-conversion-and-seo.md §2b).
// NEXT_PUBLIC_API_BASE_URL is the public site origin (https://makapix.club in
// prod, https://development.makapix.club in dev), so OG_IMAGE is absolute.
const SITE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://makapix.club';
const OG_IMAGE = `${SITE_URL}/og-default.png`;
const DEFAULT_TITLE = 'Makapix Club — pixel art on real displays';
const DEFAULT_DESCRIPTION =
  'The open community where pixel art comes alive on physical displays. Free, no ads, no algorithm.';

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#aaa' }}>
          <p>Something went wrong.</p>
          <button
            onClick={() => window.location.reload()}
            style={{
              marginTop: '1rem',
              padding: '0.5rem 1rem',
              background: '#333',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
            }}
          >
            Reload page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter();
  // Use ref to prevent duplicate refresh attempts
  const isCheckingRef = useRef(false);
  // Track userId for social notifications
  const [userId, setUserId] = useState<string | null>(null);

  // Track page views for analytics
  usePageViewTracking();

  // Track userId from localStorage
  useEffect(() => {
    const checkUserId = () => {
      const storedUserId = localStorage.getItem('user_id');
      const token = getAccessToken();
      // Only set userId if we have both token and userId
      setUserId(token && storedUserId ? storedUserId : null);
    };

    checkUserId();

    // Listen for storage changes (login/logout in other tabs)
    const handleStorageChange = (event: StorageEvent) => {
      if (event.key === 'user_id' || event.key === 'access_token') {
        checkUserId();
      }
    };

    // Custom event for same-tab localStorage changes
    const handleLocalStorageUpdate = () => {
      checkUserId();
    };

    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('localStorageUpdated', handleLocalStorageUpdate);
    
    // Also check on route changes in case login happens
    router.events.on('routeChangeComplete', checkUserId);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('localStorageUpdated', handleLocalStorageUpdate);
      router.events.off('routeChangeComplete', checkUserId);
    };
  }, [router.events]);

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
    <ErrorBoundary>
      <Head>
        <title key="title">{DEFAULT_TITLE}</title>
        <meta name="description" content={DEFAULT_DESCRIPTION} key="description" />
        <meta property="og:site_name" content="Makapix Club" key="og:site_name" />
        <meta property="og:type" content="website" key="og:type" />
        <meta property="og:title" content={DEFAULT_TITLE} key="og:title" />
        <meta property="og:description" content={DEFAULT_DESCRIPTION} key="og:description" />
        <meta property="og:image" content={OG_IMAGE} key="og:image" />
        <meta property="og:image:type" content="image/png" key="og:image:type" />
        <meta property="og:image:width" content="1200" key="og:image:width" />
        <meta property="og:image:height" content="630" key="og:image:height" />
        <meta property="og:image:alt" content="Makapix Club — pixel art on real displays" key="og:image:alt" />
        <meta name="twitter:card" content="summary_large_image" key="twitter:card" />
        <meta name="twitter:title" content={DEFAULT_TITLE} key="twitter:title" />
        <meta name="twitter:description" content={DEFAULT_DESCRIPTION} key="twitter:description" />
        <meta name="twitter:image" content={OG_IMAGE} key="twitter:image" />
      </Head>
      <SocialNotificationsProvider userId={userId}>
        <PlayerBarProvider>
          <Component {...pageProps} />
        </PlayerBarProvider>
      </SocialNotificationsProvider>
    </ErrorBoundary>
  );
}

