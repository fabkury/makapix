import { ReactNode, useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';
import Head from 'next/head';
import { authenticatedFetch, clearTokens } from '../lib/api';

interface LayoutProps {
  children: ReactNode;
  title?: string;
  description?: string;
}

interface NavItem {
  href: string;
  icon: string;
  label: string;
  matchPaths?: string[];
}

const navItems: NavItem[] = [
  { 
    href: '/submit', 
    icon: '➕', 
    label: 'Submit',
    matchPaths: ['/submit']
  },
  { 
    href: '/recommended', 
    icon: '⭐', 
    label: 'Recommended',
    matchPaths: ['/recommended']
  },
  { 
    href: '/', 
    icon: '🐣', 
    label: 'Recent',
    matchPaths: ['/', '/recent', '/posts']
  },
  { 
    href: '/search', 
    icon: '🔍', 
    label: 'Search',
    matchPaths: ['/search', '/hashtags', '/users']
  },
];

export default function Layout({ children, title, description }: LayoutProps) {
  const router = useRouter();
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [userId, setUserId] = useState<string | null>(null);
  const [publicSqid, setPublicSqid] = useState<string | null>(null);
  const [isModerator, setIsModerator] = useState(false);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);

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
            return null;
          }
          return res.ok ? res.json() : null;
        })
        .then(data => {
          if (data?.roles) {
            const roles = data.roles as string[];
            setIsModerator(roles.includes('moderator') || roles.includes('owner'));
          }
          if (data?.user?.avatar_url) {
            setAvatarUrl(data.user.avatar_url);
          }
        })
        .catch(() => {
          // Silently ignore errors - user just won't see mod icon
        });
    }
  }, []);

  // Listen for OAuth success message from popup
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      // Verify message origin for security (in production, check against your domain)
      if (event.data && event.data.type === 'OAUTH_SUCCESS') {
        const { tokens } = event.data;
        if (tokens) {
          localStorage.setItem('access_token', tokens.access_token || tokens.token);
          localStorage.setItem('refresh_token', tokens.refresh_token || '');
          localStorage.setItem('user_id', String(tokens.user_id));
          localStorage.setItem('user_key', tokens.user_key || '');
          localStorage.setItem('public_sqid', tokens.public_sqid || '');
          localStorage.setItem('user_handle', tokens.user_handle || '');
          
          // Reload the page to update authentication state
          window.location.reload();
        }
      }
    };

    window.addEventListener('message', handleMessage);
    return () => {
      window.removeEventListener('message', handleMessage);
    };
  }, []);

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

  return (
    <>
      <Head>
        <title>{pageTitle}</title>
        {description && <meta name="description" content={description} />}
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/logo.png" />
      </Head>

      <div className="app-container">
        <header className="header">
          <div className="header-left">
            <Link href={isLoggedIn ? "/" : "/recommended"} className="logo-link" aria-label="Makapix Club Home">
              <div className="logo-container">
                <img 
                  src="/logo.png" 
                  alt="Makapix Club" 
                  className="logo"
                />
              </div>
            </Link>
            
            {isLoggedIn && publicSqid && (
              <Link href={`/u/${publicSqid}`} className={`user-profile-link ${router.pathname === '/u/[sqid]' && router.query.sqid === publicSqid ? 'active' : ''}`} aria-label="My Profile">
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

            {isLoggedIn && isModerator && (
              <Link href="/mod-dashboard" className={`mod-dashboard-link ${router.pathname === '/mod-dashboard' ? 'active' : ''}`} aria-label="Moderator Dashboard">
                <div className="mod-icon">🎛️</div>
              </Link>
            )}

            <Link href="/blog" className={`blog-feed-link ${router.pathname.startsWith('/blog') ? 'active' : ''}`} aria-label="Blog Feed">
              <div className="blog-icon">📰</div>
            </Link>
          </div>

          <nav className="nav" aria-label="Main navigation">
            {navItems.map((item) => {
              const active = isActive(item);
              // For Recent artworks (/), redirect unauthenticated users to /auth
              const handleClick = (e: React.MouseEvent) => {
                if (item.href === '/' && !isLoggedIn) {
                  e.preventDefault();
                  router.push('/auth');
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
                >
                  <span className={`nav-icon ${item.icon === '#' ? 'nav-icon-hash' : ''}`}>
                    {item.icon}
                  </span>
                </Link>
              );
            })}
          </nav>
        </header>

        <main className="main-content">
          {children}
        </main>
      </div>

      <style jsx>{`
        .app-container {
          min-height: 100vh;
          display: flex;
          flex-direction: column;
        }

        .header {
          position: sticky;
          top: 0;
          z-index: 100;
          height: var(--header-height);
          background: linear-gradient(180deg, var(--bg-secondary) 0%, rgba(18, 18, 26, 0.95) 100%);
          backdrop-filter: blur(12px);
          border-bottom: 1px solid rgba(255, 255, 255, 0.05);
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 0 16px;
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
          width: 40px;
          height: 40px;
          border-radius: 50%;
          overflow: hidden;
          background: var(--bg-tertiary);
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
          width: 32px;
          height: 32px;
          border-radius: 50%;
          background: var(--bg-tertiary);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--text-secondary);
          transition: all var(--transition-fast);
          overflow: hidden;
        }

        .user-avatar {
          width: 100%;
          height: 100%;
          object-fit: cover;
          border-radius: 50%;
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

        .header-left :global(a.blog-feed-link) {
          display: flex;
          align-items: center;
        }

        .blog-icon {
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

        .header-left :global(a.blog-feed-link:hover) .blog-icon {
          background: var(--accent-cyan);
          box-shadow: var(--glow-cyan);
        }

        .header-left :global(a.blog-feed-link.active) .blog-icon {
          background: rgba(255, 255, 255, 0.15);
          box-shadow: 0 0 16px rgba(0, 212, 255, 0.4), inset 0 0 0 2px rgba(0, 212, 255, 0.3);
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
          flex: 1;
          width: 100%;
        }

        @media (max-width: 480px) {
          .header {
            padding: 0 8px;
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
            width: 36px;
            height: 36px;
          }
        }
      `}</style>
    </>
  );
}

