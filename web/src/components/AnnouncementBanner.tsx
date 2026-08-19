import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/router';

// Site-wide announcement banner. To retire the current announcement, set
// BANNER_ID to null. To publish a new one, change BANNER_ID (a new id makes
// the banner reappear for users who dismissed the previous one) and update
// the message/link below.
const BANNER_ID: string | null = 'remix-lineage-2026-08';
const BANNER_HREF = '/terms#remixes';

export default function AnnouncementBanner() {
  const router = useRouter();
  const [visible, setVisible] = useState(false);
  const bannerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!BANNER_ID) return;
    try {
      if (localStorage.getItem(`banner_dismissed_${BANNER_ID}`) === '1') return;
    } catch {
      // ignore — show the banner if localStorage is unavailable
    }
    setVisible(true);
  }, []);

  // Don't show the banner on the page it links to (hash-insensitive).
  const shown =
    Boolean(BANNER_ID) && visible && router.pathname !== BANNER_HREF.split('#')[0];

  // The banner renders inside the fixed header, so the space it occupies must
  // be pushed onto everything positioned off the header: --banner-height feeds
  // --header-offset and the main-content padding (see Layout.tsx). Track the
  // rendered height (the text can wrap on narrow screens) and zero it whenever
  // the banner is hidden.
  useEffect(() => {
    const root = document.documentElement;
    const el = bannerRef.current;
    if (!shown || !el) {
      root.style.setProperty('--banner-height', '0px');
      return;
    }
    const update = () =>
      root.style.setProperty('--banner-height', `${el.offsetHeight}px`);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(el);
    return () => {
      observer.disconnect();
      root.style.setProperty('--banner-height', '0px');
    };
  }, [shown]);

  const dismiss = () => {
    setVisible(false);
    try {
      localStorage.setItem(`banner_dismissed_${BANNER_ID}`, '1');
    } catch {
      // ignore
    }
  };

  if (!shown) return null;

  return (
    <div
      ref={bannerRef}
      className="announcement-banner"
      role="region"
      aria-label="Announcement"
    >
      <Link href={BANNER_HREF} className="announcement-link">
        Remixing is here! Your artworks are Remixable by default — you can
        turn it off per artwork. Learn more&nbsp;→
      </Link>
      <button
        type="button"
        className="announcement-dismiss"
        aria-label="Dismiss announcement"
        onClick={dismiss}
      >
        ✕
      </button>

      <style jsx>{`
        .announcement-banner {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          padding: 10px 44px 10px 16px;
          background: linear-gradient(
            90deg,
            rgba(255, 110, 180, 0.15),
            rgba(0, 212, 255, 0.15)
          );
          /* Last row inside the fixed header: the header's own bottom border
             closes the strip below, so only separate from the row above. */
          border-top: 1px solid rgba(0, 212, 255, 0.35);
          position: relative;
          text-align: center;
        }

        .announcement-banner :global(a.announcement-link) {
          color: var(--text-primary);
          font-size: 14px;
          text-decoration: none;
          line-height: 1.4;
        }

        .announcement-banner :global(a.announcement-link:hover) {
          color: var(--accent-cyan);
          text-decoration: underline;
        }

        .announcement-dismiss {
          position: absolute;
          right: 8px;
          top: 50%;
          transform: translateY(-50%);
          width: 28px;
          height: 28px;
          border: 0;
          border-radius: 6px;
          background: transparent;
          color: var(--text-secondary);
          font-size: 14px;
          line-height: 1;
          cursor: pointer;
          transition: background var(--transition-fast), color var(--transition-fast);
        }

        .announcement-dismiss:hover {
          background: rgba(255, 255, 255, 0.1);
          color: var(--text-primary);
        }

        @media (max-width: 480px) {
          .announcement-banner {
            padding: 8px 40px 8px 12px;
          }

          .announcement-banner :global(a.announcement-link) {
            font-size: 13px;
          }
        }
      `}</style>
    </div>
  );
}
