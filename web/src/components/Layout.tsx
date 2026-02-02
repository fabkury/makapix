import { ReactNode, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Head from 'next/head';
import { authenticatedFetch, clearLoggedOutMarker, clearTokens } from '../lib/api';
import SocialNotificationBadge from './SocialNotificationBadge';

interface LayoutProps {
  children: ReactNode;
  title?: string;
  description?: string;
}

interface NavItem {
  href: string;
  icon?: string;
  iconSrc?: string;
  iconSrcSet?: string;
  label: string;
  matchPaths?: string[];
}

// Feature flag and configuration for header bottom-row with trending hashtags
const SHOW_BOTTOM_ROW = true;  // Set to false to disable bottom-row entirely
const BOTTOM_ROW_PAGES = ['/', '/recommended', '/hashtags', '/hashtags/[tag]'];  // Pages where bottom-row appears

const navItems: NavItem[] = [
  {
    href: '/contribute',
    iconSrc: '/button/contribute/btn004-contribute-32px-1x.png',
    iconSrcSet: '/button/contribute/btn004-contribute-32px-1x.png 1x, /button/contribute/btn004-contribute-40px-1_25x.png 1.25x, /button/contribute/btn004-contribute-48px-1_5x.png 1.5x, /button/contribute/btn004-contribute-56px-1_75x.png 1.75x, /button/contribute/btn004-contribute-64px-2x.png 2x, /button/contribute/btn004-contribute-72px-2_25x.png 2.25x, /button/contribute/btn004-contribute-80px-2_5x.png 2.5x, /button/contribute/btn004-contribute-88px-2_75x.png 2.75x, /button/contribute/btn004-contribute-96px-3x.png 3x, /button/contribute/btn004-contribute-104px-3_25x.png 3.25x, /button/contribute/btn004-contribute-112px-3_5x.png 3.5x, /button/contribute/btn004-contribute-128px-4x.png 4x',
    label: 'Contribute',
    matchPaths: ['/contribute', '/editor', '/submit', '/divoom-import']
  },
  {
    href: '/recommended',
    iconSrc: '/button/promoted/btn002-promoted-32px-1x.png',
    iconSrcSet: '/button/promoted/btn002-promoted-32px-1x.png 1x, /button/promoted/btn002-promoted-40px-1_25x.png 1.25x, /button/promoted/btn002-promoted-48px-1_5x.png 1.5x, /button/promoted/btn002-promoted-56px-1_75x.png 1.75x, /button/promoted/btn002-promoted-64px-2x.png 2x, /button/promoted/btn002-promoted-72px-2_25x.png 2.25x, /button/promoted/btn002-promoted-80px-2_5x.png 2.5x, /button/promoted/btn002-promoted-88px-2_75x.png 2.75x, /button/promoted/btn002-promoted-96px-3x.png 3x, /button/promoted/btn002-promoted-104px-3_25x.png 3.25x, /button/promoted/btn002-promoted-112px-3_5x.png 3.5x, /button/promoted/btn002-promoted-128px-4x.png 4x',
    label: 'Recommended',
    matchPaths: ['/recommended']
  },
  {
    href: '/',
    iconSrc: '/button/new-artworks/btn006-new-artworks-v2-32px-1x.png',
    iconSrcSet: '/button/new-artworks/btn006-new-artworks-v2-32px-1x.png 1x, /button/new-artworks/btn006-new-artworks-v2-40px-1_25x.png 1.25x, /button/new-artworks/btn006-new-artworks-v2-48px-1_5x.png 1.5x, /button/new-artworks/btn006-new-artworks-v2-56px-1_75x.png 1.75x, /button/new-artworks/btn006-new-artworks-v2-64px-2x.png 2x, /button/new-artworks/btn006-new-artworks-v2-72px-2_25x.png 2.25x, /button/new-artworks/btn006-new-artworks-v2-80px-2_5x.png 2.5x, /button/new-artworks/btn006-new-artworks-v2-88px-2_75x.png 2.75x, /button/new-artworks/btn006-new-artworks-v2-96px-3x.png 3x, /button/new-artworks/btn006-new-artworks-v2-104px-3_25x.png 3.25x, /button/new-artworks/btn006-new-artworks-v2-112px-3_5x.png 3.5x, /button/new-artworks/btn006-new-artworks-v2-128px-4x.png 4x',
    label: 'Recent',
    matchPaths: ['/', '/recent', '/posts']
  },
  {
    href: '/search',
    iconSrc: '/button/search/btn003-search-32px-1x.png',
    iconSrcSet: '/button/search/btn003-search-32px-1x.png 1x, /button/search/btn003-search-40px-1_25x.png 1.25x, /button/search/btn003-search-48px-1_5x.png 1.5x, /button/search/btn003-search-56px-1_75x.png 1.75x, /button/search/btn003-search-64px-2x.png 2x, /button/search/btn003-search-72px-2_25x.png 2.25x, /button/search/btn003-search-80px-2_5x.png 2.5x, /button/search/btn003-search-88px-2_75x.png 2.75x, /button/search/btn003-search-96px-3x.png 3x, /button/search/btn003-search-104px-3_25x.png 3.25x, /button/search/btn003-search-112px-3_5x.png 3.5x, /button/search/btn003-search-128px-4x.png 4x',
    label: 'Search',
    matchPaths: ['/search', '/hashtags', '/users']
  },
];

export default function Layout({ children, title, description }: LayoutProps) {
  const router = useRouter();
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);
  const [publicSqid, setPublicSqid] = useState<string | null>(null);
  // Cache moderator status in localStorage to avoid flash on page navigation
  const [isModerator, setIsModerator] = useState(() => {
    if (typeof window === 'undefined') return false;
    return localStorage.getItem('is_moderator') === 'true';
  });
  // Prevent header avatar "flashing" on navigation: Layout is mounted per-page in this app,
  // so without a synchronous initial value, the avatar briefly renders as the placeholder
  // until `/api/auth/me` completes. Cache it in localStorage and hydrate immediately.
  const [avatarUrl, setAvatarUrl] = useState<string | null>(() => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem('avatar_url');
  });
  const [isHeaderHidden, setIsHeaderHidden] = useState(false);
  const [topHashtags, setTopHashtags] = useState<string[]>([]);
  // Note: We intentionally do NOT change --header-offset when the header hides.
  // The header uses transform to slide out, but the page layout stays fixed.
  // This prevents scroll jumps when the header shows/hides.

  // Check if current page should show bottom-row
  const isBottomRowPage = BOTTOM_ROW_PAGES.includes(router.pathname);
  // bottom-row shows only when: feature enabled, user logged in, correct page, and hashtags loaded
  const showBottomRow = SHOW_BOTTOM_ROW && isLoggedIn && isBottomRowPage && topHashtags.length > 0;

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    const storedUserId = localStorage.getItem('user_id');
    const storedPublicSqid = localStorage.getItem('public_sqid');
    setIsLoggedIn(!!token);
    setUserId(storedUserId);
    setPublicSqid(storedPublicSqid);

    // Fetch user roles and avatar if logged in
    if (token) {
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      authenticatedFetch(`${apiBaseUrl}/api/auth/me`)
        .then(res => {
          if (res.status === 401) {
            // Token refresh failed - clear tokens and redirect to login
            clearTokens();
            setIsLoggedIn(false);
            setIsModerator(false);
            try { localStorage.removeItem('is_moderator'); } catch { /* ignore */ }
            return null;
          }
          return res.ok ? res.json() : null;
        })
        .then(data => {
          if (data?.roles) {
            const roles = data.roles as string[];
            const isMod = roles.includes('moderator') || roles.includes('owner');
            setIsModerator(isMod);
            try {
              if (isMod) localStorage.setItem('is_moderator', 'true');
              else localStorage.removeItem('is_moderator');
            } catch {
              // ignore
            }
          }
          if (data?.user) {
            // Sync localStorage with actual user data from API
            if (data.user.id) {
              const newUserId = String(data.user.id);
              const oldUserId = localStorage.getItem('user_id');
              localStorage.setItem('user_id', newUserId);
              setUserId(newUserId);
              // Dispatch custom event if userId changed (for MQTT reconnection)
              if (oldUserId !== newUserId) {
                window.dispatchEvent(new Event('localStorageUpdated'));
              }
            }
            if (data.user.public_sqid) {
              localStorage.setItem('public_sqid', data.user.public_sqid);
              setPublicSqid(data.user.public_sqid);
            }
            if (data.user.avatar_url) {
              setAvatarUrl(data.user.avatar_url);
              try {
                localStorage.setItem('avatar_url', data.user.avatar_url);
              } catch {
                // ignore
              }
            } else {
              setAvatarUrl(null);
              try {
                localStorage.removeItem('avatar_url');
              } catch {
                // ignore
              }
            }
          }
        })
        .catch(() => {
          // Silently ignore errors - user just won't see mod icon
        });
    }
  }, []);

  // Sync header avatar immediately when profile updates within the same tab.
  useEffect(() => {
    const handler = (event: Event) => {
      const detail = (event as CustomEvent).detail as { avatar_url?: string | null } | undefined;
      if (detail && 'avatar_url' in detail) {
        setAvatarUrl(detail.avatar_url ?? null);
        try {
          if (detail.avatar_url) localStorage.setItem('avatar_url', detail.avatar_url);
          else localStorage.removeItem('avatar_url');
        } catch {
          // ignore
        }
      }
    };
    window.addEventListener('makapix:user-updated', handler as EventListener);
    return () => window.removeEventListener('makapix:user-updated', handler as EventListener);
  }, []);

  // Delta-based header show/hide: scrolling down 256px hides, scrolling up 256px shows.
  // This allows repeated hide/show cycles anywhere on the page.
  const scrollAnchorRef = useRef(0);
  const lastScrollYRef = useRef(0);

  useEffect(() => {
    let rafId: number | null = null;

    const SCROLL_DELTA = 256; // Trigger hide/show after scrolling this much
    const SHOW_AT_TOP = 64;   // Always show when near the top

    const onScroll = () => {
      if (rafId !== null) return;
      rafId = window.requestAnimationFrame(() => {
        rafId = null;
        const y = window.scrollY || 0;
        const lastY = lastScrollYRef.current;
        const scrollingDown = y > lastY;
        const scrollingUp = y < lastY;

        setIsHeaderHidden((prev) => {
          // Always show when near the top
          if (y <= SHOW_AT_TOP) {
            scrollAnchorRef.current = y;
            return false;
          }

          if (scrollingDown && !prev) {
            // Header is visible, scrolling down - check if we've scrolled enough to hide
            const scrolledDown = y - scrollAnchorRef.current;
            if (scrolledDown >= SCROLL_DELTA) {
              scrollAnchorRef.current = y;
              return true; // Hide
            }
          } else if (scrollingUp && prev) {
            // Header is hidden, scrolling up - check if we've scrolled enough to show
            const scrolledUp = scrollAnchorRef.current - y;
            if (scrolledUp >= SCROLL_DELTA) {
              scrollAnchorRef.current = y;
              return false; // Show
            }
          } else if (scrollingDown && prev) {
            // Already hidden, scrolling down - update anchor to track position
            scrollAnchorRef.current = y;
          } else if (scrollingUp && !prev) {
            // Already visible, scrolling up - update anchor to track position
            scrollAnchorRef.current = y;
          }

          return prev;
        });

        lastScrollYRef.current = y;
      });
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    return () => {
      if (rafId !== null) window.cancelAnimationFrame(rafId);
      window.removeEventListener('scroll', onScroll);
    };
  }, []);

  // Fetch top hashtags for header bottom-row
  useEffect(() => {
    // Fetch hashtags once when user logs in (regardless of current page)
    // This avoids re-fetching when navigating between pages
    if (!SHOW_BOTTOM_ROW || !isLoggedIn) return;

    const fetchTopHashtags = async () => {
      try {
        const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
        const res = await authenticatedFetch(`${apiBaseUrl}/api/hashtags/top`);
        if (res.ok) {
          const data = await res.json();
          setTopHashtags(data.hashtags || []);
        }
      } catch {
        // Silently fail - bottom row will be empty
      }
    };
    fetchTopHashtags();
  }, [isLoggedIn]);

  // Listen for OAuth success message from popup
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      // Verify message origin for security (in production, check against your domain)
      if (event.data && event.data.type === 'OAUTH_SUCCESS') {
        const { tokens, redirectUrl } = event.data;
        if (tokens) {
          localStorage.setItem('access_token', tokens.access_token || tokens.token);
          clearLoggedOutMarker();
          // refresh_token is now stored in HttpOnly cookie, not in localStorage
          // Do not store refresh_token even if provided
          localStorage.setItem('user_id', String(tokens.user_id));
          localStorage.setItem('user_key', tokens.user_key || '');
          localStorage.setItem('public_sqid', tokens.public_sqid || '');
          localStorage.setItem('user_handle', tokens.user_handle || '');
          // Dispatch custom event to trigger MQTT reconnection with new userId
          window.dispatchEvent(new Event('localStorageUpdated'));

          // Use redirectUrl from message if provided, otherwise check needs_welcome
          if (redirectUrl) {
            // Extract path from full URL if needed
            const url = new URL(redirectUrl, window.location.origin);
            router.push(url.pathname + url.search);
          } else if (tokens.needs_welcome) {
            // Fallback: redirect to welcome page if needs_welcome is true
            router.push('/new-account-welcome');
          } else {
            // Default: redirect to Recent Artworks
            router.push('/');
          }
        }
      }
    };

    window.addEventListener('message', handleMessage);
    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, [router]);

  const isActive = (item: NavItem): boolean => {
    const currentPath = router.pathname;
    if (item.matchPaths) {
      return item.matchPaths.some(path => {
        if (path === '/') return currentPath === '/';
        // For /user, match exactly (not /user/[id])
        if (path === '/user') return currentPath === '/user';
        // For /hashtags, match exactly (not /hashtags/[tag])
        if (path === '/hashtags') return currentPath === '/hashtags';
        // For search, also match /hashtags and /users when redirected
        if (path === '/search') {
          return currentPath === '/search' || currentPath === '/hashtags' || currentPath === '/users';
        }
        return currentPath.startsWith(path);
      });
    }
    return currentPath === item.href;
  };

  const pageTitle = title ? `${title} - Makapix Club` : 'Makapix Club';

  const markWelcomeAsInternalNav = () => {
    try {
      // Used by /welcome to skip intro animations when user was redirected from within the app.
      sessionStorage.setItem('makapix_welcome_instant', '1');
    } catch {
      // ignore
    }
  };

  return (
    <>
      <Head>
        <title>{pageTitle}</title>
        {description && <meta name="description" content={description} />}
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/logo.png" />
      </Head>

      <div className="app-container" style={{ '--header-offset': showBottomRow ? 'calc(var(--header-height) + var(--header-bottom-row-height))' : 'var(--header-height)' } as React.CSSProperties}>
        <header className={`header ${isHeaderHidden ? 'header-hidden' : ''} ${showBottomRow ? 'header-with-bottom-row' : ''}`}>
          <div className="header-top-row">
            <div className="header-left">
              <Link
                href="/about"
                className="logo-link"
                aria-label="About Makapix Club"
                // In dev, some tooling can inject extra attributes into SSR output, triggering
                // noisy hydration warnings (e.g. "Extra attributes from the server: data-cursor-ref").
                // Suppress that specific warning for these nav anchors.
                suppressHydrationWarning
              >
                <div className="logo-container">
                  <img
                    src="/button/makapix-club/mpx-logo-32px-1x.png"
                    srcSet="/button/makapix-club/mpx-logo-32px-1x.png 1x, /button/makapix-club/mpx-logo-40px-1_25x.png 1.25x, /button/makapix-club/mpx-logo-48px-1_5x.png 1.5x, /button/makapix-club/mpx-logo-56px-1_75x.png 1.75x, /button/makapix-club/mpx-logo-64px-2x.png 2x, /button/makapix-club/mpx-logo-72px-2_25x.png 2.25x, /button/makapix-club/mpx-logo-80px-2_5x.png 2.5x, /button/makapix-club/mpx-logo-88px-2_75x.png 2.75x, /button/makapix-club/mpx-logo-96px-3x.png 3x, /button/makapix-club/mpx-logo-104px-3_25x.png 3.25x, /button/makapix-club/mpx-logo-112px-3_5x.png 3.5x, /button/makapix-club/mpx-logo-128px-4x.png 4x"
                    alt="Makapix Club"
                    className="logo"
                  />
                </div>
              </Link>

              {isLoggedIn && publicSqid && (
                <Link
                  href={`/u/${publicSqid}`}
                  className={`user-profile-link ${router.pathname === '/u/[sqid]' && router.query.sqid === publicSqid ? 'active' : ''}`}
                  aria-label="My Profile"
                  suppressHydrationWarning
                >
                  <div className="user-icon">
                    {avatarUrl ? (
                      <img
                        src={avatarUrl.startsWith('http') ? avatarUrl : `${typeof window !== 'undefined' ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin) : ''}${avatarUrl}`}
                        alt="Profile"
                        className="user-avatar"
                      />
                    ) : (
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                      </svg>
                    )}
                  </div>
                </Link>
              )}

              {isLoggedIn && (
                <SocialNotificationBadge />
              )}

              {isLoggedIn && isModerator && (
                <Link
                  href="/mod-dashboard"
                  className={`mod-dashboard-link ${router.pathname === '/mod-dashboard' ? 'active' : ''}`}
                  aria-label="Moderator Dashboard"
                  suppressHydrationWarning
                >
                  <div className="mod-icon">🎛️</div>
                </Link>
              )}
            </div>

            <nav className="nav" aria-label="Main navigation">
              {navItems.map((item) => {
                const active = isActive(item);
                // Auth checks and redirects
                const handleClick = (e: React.MouseEvent) => {
                  // For Recent artworks (/), redirect unauthenticated users to /welcome
                  if (item.href === '/' && !isLoggedIn) {
                    e.preventDefault();
                    markWelcomeAsInternalNav();
                    router.push('/welcome');
                  }
                  // Contribute requires authentication
                  if (item.href === '/contribute' && !isLoggedIn) {
                    e.preventDefault();
                    router.push('/auth?redirect=/contribute');
                  }
                };
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={handleClick}
                    className={`nav-item ${active ? 'nav-item-active' : ''}`}
                    aria-label={item.label}
                    aria-current={active ? 'page' : undefined}
                    suppressHydrationWarning
                  >
                    {item.iconSrc ? (
                      <img
                        src={item.iconSrc}
                        srcSet={item.iconSrcSet}
                        alt=""
                        width={32}
                        height={32}
                        className="nav-icon-img"
                        aria-hidden="true"
                      />
                    ) : (
                      <span className={`nav-icon ${item.icon === '#' ? 'nav-icon-hash' : ''}`}>
                        {item.icon}
                      </span>
                    )}
                  </Link>
                );
              })}
            </nav>
          </div>

          {showBottomRow && (
            <div className="header-bottom-row">
              <div className="hashtag-scroll">
                {topHashtags.map((tag) => (
                  <Link key={tag} href={`/hashtags/${encodeURIComponent(tag)}`} className="hashtag-link">
                    #{tag}
                  </Link>
                ))}
              </div>
            </div>
          )}
        </header>

        <main className="main-content" style={{ paddingTop: showBottomRow ? 'calc(var(--header-height) + var(--header-bottom-row-height))' : 'var(--header-height)' }}>
          {children}
        </main>
      </div>

      <style jsx>{`
        .app-container {
          display: flex;
          flex-direction: column;
        }

        .header {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          z-index: 100;
          height: auto;
          background: #000;
          backdrop-filter: none;
          border-bottom: 1px solid #fff;
          display: flex;
          flex-direction: column;
          /* Only animate transform for show/hide - no height/padding changes that cause reflow */
          transition: transform 200ms ease-out, opacity 200ms ease-out;
        }

        .header.header-hidden {
          transform: translateY(-100%);
          opacity: 0;
          pointer-events: none;
        }

        .header.header-with-bottom-row {
          border-bottom-color: #666;
        }

        .header-top-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          height: var(--header-height);
          padding: 0 16px;
          flex-shrink: 0;
        }

        .header.header-with-bottom-row .header-top-row {
          border-bottom: 1px solid #fff;
        }

        .header-bottom-row {
          height: var(--header-bottom-row-height);
          background: #000;
          overflow: hidden;
          flex-shrink: 0;
        }

        .hashtag-scroll {
          display: flex;
          gap: 24px;
          padding: 0 16px;
          height: 100%;
          align-items: center;
          overflow-x: auto;
          -webkit-overflow-scrolling: touch;
          scrollbar-width: none;
          -ms-overflow-style: none;
        }

        .hashtag-scroll::-webkit-scrollbar {
          display: none;
        }

        .hashtag-scroll :global(a.hashtag-link) {
          color: var(--text-secondary);
          font-size: 13px;
          text-decoration: none;
          flex-shrink: 0;
          white-space: nowrap;
          transition: color var(--transition-fast);
        }

        .hashtag-scroll :global(a.hashtag-link:hover) {
          color: var(--accent-cyan);
          text-decoration: underline;
        }

        .header-left {
          display: flex;
          align-items: center;
          gap: 16px;
        }

        .logo-link {
          display: flex;
          align-items: center;
          text-decoration: none;
        }

        .logo-container {
          width: 32px;
          height: 32px;
          border-radius: 0;
          overflow: hidden;
          background: transparent;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: box-shadow var(--transition-normal);
        }

        .logo-link:hover .logo-container {
          box-shadow: var(--glow-pink);
        }

        .logo {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }

        .header-left :global(a.user-profile-link) {
          display: flex;
          align-items: center;
        }

        .user-icon {
          /* Top-header avatar MUST be exactly 32x32 CSS pixels. Keep this fixed for layout stability. */
          width: 32px;
          height: 32px;
          /* Profile picture in the top header should be a square */
          border-radius: 0;
          background: var(--bg-tertiary);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--text-secondary);
          transition: all var(--transition-fast);
          overflow: hidden;
        }

        .user-avatar {
          /* The image fills the 32x32 container above. Do not change sizing here; change .user-icon instead. */
          width: 100%;
          height: 100%;
          object-fit: cover;
          /* Profile picture in the top header should be a square */
          border-radius: 0;
          /* User avatars are pixel art and should be rendered with sharp edges */
          image-rendering: pixelated;
        }

        .header-left :global(a.user-profile-link:hover) .user-icon {
          background: var(--accent-cyan);
          color: var(--bg-primary);
          box-shadow: var(--glow-cyan);
        }

        .header-left :global(a.user-profile-link:hover) .user-icon .user-avatar {
          opacity: 0.9;
        }

        .header-left :global(a.user-profile-link.active) .user-icon {
          background: rgba(255, 255, 255, 0.15);
          color: var(--accent-cyan);
          box-shadow: 0 0 16px rgba(0, 212, 255, 0.4), inset 0 0 0 2px rgba(0, 212, 255, 0.3);
        }

        .header-left :global(a.user-profile-link.active) .user-icon .user-avatar {
          opacity: 0.9;
        }

        .header-left :global(a.mod-dashboard-link) {
          display: flex;
          align-items: center;
        }

        .mod-icon {
          width: 32px;
          height: 32px;
          border-radius: 50%;
          background: var(--bg-tertiary);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 18px;
          transition: all var(--transition-fast);
        }

        .header-left :global(a.mod-dashboard-link:hover) .mod-icon {
          background: var(--accent-purple);
          box-shadow: var(--glow-purple);
        }

        .header-left :global(a.mod-dashboard-link.active) .mod-icon {
          background: rgba(255, 255, 255, 0.15);
          box-shadow: 0 0 16px rgba(180, 78, 255, 0.4), inset 0 0 0 2px rgba(180, 78, 255, 0.3);
        }

        .nav {
          display: flex;
          align-items: center;
          gap: 16px;
        }

        .nav :global(a.nav-item) {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 44px;
          height: 44px;
          border-radius: 12px;
          text-decoration: none;
          transition: all var(--transition-fast);
          position: relative;
        }

        .nav :global(a.nav-item:hover) {
          background: var(--bg-tertiary);
        }

        .nav :global(a.nav-item-active) {
          background: rgba(255, 255, 255, 0.15);
          box-shadow: 0 0 16px rgba(0, 212, 255, 0.4), inset 0 0 0 2px rgba(0, 212, 255, 0.3);
          border-radius: 12px;
        }

        .nav :global(a.nav-item-active::after) {
          content: '';
          position: absolute;
          bottom: 4px;
          left: 50%;
          transform: translateX(-50%);
          width: 20px;
          height: 3px;
          background: linear-gradient(90deg, var(--accent-pink), var(--accent-cyan));
          border-radius: 2px;
          box-shadow: 0 0 8px rgba(255, 110, 180, 0.5);
        }

        .nav-icon {
          font-size: 22px;
          line-height: 1;
          filter: grayscale(0.3);
          transition: filter var(--transition-fast);
        }

        .nav :global(a.nav-item:hover) .nav-icon,
        .nav :global(a.nav-item-active) .nav-icon {
          filter: grayscale(0);
        }

        .nav :global(img.nav-icon-img) {
          display: block;
          filter: grayscale(0.3);
          transition: filter var(--transition-fast);
        }

        .nav :global(a.nav-item:hover) :global(img.nav-icon-img) {
          filter: grayscale(0) brightness(1.2);
        }

        .nav :global(a.nav-item-active) :global(img.nav-icon-img) {
          filter: grayscale(0) brightness(1.3) drop-shadow(0 0 4px rgba(0, 212, 255, 0.6));
        }

        .nav-icon-hash {
          font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
          font-weight: 700;
          font-size: 28px;
          color: var(--text-secondary);
          background: linear-gradient(135deg, var(--accent-purple), var(--accent-blue));
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
          display: flex;
          align-items: center;
          justify-content: center;
          height: 100%;
        }

        .nav :global(a.nav-item-active) .nav-icon-hash {
          text-shadow: var(--glow-purple);
        }

        .main-content {
          width: 100%;
          /* Document scrolling: keep main in normal flow and reserve space for header.
             padding-top is set via inline style to dynamically adjust for bottom-row.
             The header slides out via transform, not height. */
        }

        @media (max-width: 480px) {
          .header-top-row {
            padding: 0 8px;
          }

          .hashtag-scroll {
            padding: 0 8px;
            gap: 16px;
          }

          .nav {
            gap: 10px;
          }

          .nav-item {
            width: 40px;
            height: 40px;
          }

          .nav-icon {
            font-size: 20px;
          }

          .logo-container {
            width: 32px;
            height: 32px;
          }
        }
      `}</style>
    </>
  );
}

