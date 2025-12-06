import type { AppProps } from 'next/app';
import { useEffect } from 'react';
import '../styles/globals.css';
import { getAccessToken, isTokenExpired, refreshAccessToken } from '../lib/api';

export default function App({ Component, pageProps }: AppProps) {
  // Priority 3: Proactive token refresh
  // Periodically check and refresh tokens before they expire
  useEffect(() => {
    // Check token and refresh if needed on mount
    const checkAndRefreshToken = async () => {
      const token = getAccessToken();
      if (token && isTokenExpired(token, 300)) { // 5 minutes before expiry
        await refreshAccessToken();
      }
    };

    // Initial check
    checkAndRefreshToken();

    // Set up interval to check every minute
    const refreshInterval = setInterval(async () => {
      const token = getAccessToken();
      if (token && isTokenExpired(token, 300)) { // 5 minutes before expiry
        await refreshAccessToken();
      }
    }, 60000); // Check every minute

    return () => clearInterval(refreshInterval);
  }, []);

  return <Component {...pageProps} />;
}

