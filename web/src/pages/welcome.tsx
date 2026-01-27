import { useEffect, useState } from 'react';
import Link from 'next/link';
import Layout from '../components/Layout';
import AuthPanel from '../components/AuthPanel';

const LOGO_INTRO_MS = 1188;
const AFTER_LOGO_PAUSE_MS = 900;
const BETWEEN_STAGES_PAUSE_MS = 1400;

export default function WelcomePage() {
  const [stage, setStage] = useState<0 | 1 | 2 | 3>(0);
  const [wantFreezeLogo, setWantFreezeLogo] = useState(false);
  const [lastFrameReady, setLastFrameReady] = useState(false);
  const [unmountAnimated, setUnmountAnimated] = useState(false);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const [instantMode, setInstantMode] = useState(false);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const mq = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    if (!mq) return;
    const update = () => setPrefersReducedMotion(!!mq.matches);
    update();
    mq.addEventListener?.('change', update);
    return () => mq.removeEventListener?.('change', update);
  }, []);

  // If user arrived from within the app (e.g. clicked "Recent" while logged out),
  // skip all staged animations and show the page instantly.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const v = sessionStorage.getItem('makapix_welcome_instant');
      if (v === '1') {
        sessionStorage.removeItem('makapix_welcome_instant');
        setInstantMode(true);
        setUnmountAnimated(true); // never show animated logo
        setWantFreezeLogo(true); // show still frame immediately
        setStage(3); // no delayed reveals
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    if (prefersReducedMotion || instantMode) {
      setWantFreezeLogo(true);
      setStage(3);
      return;
    }

    const timers: number[] = [];

    timers.push(
      window.setTimeout(() => {
        setWantFreezeLogo(true);
      }, LOGO_INTRO_MS)
    );

    timers.push(
      window.setTimeout(() => {
        setStage(1);
      }, LOGO_INTRO_MS + AFTER_LOGO_PAUSE_MS)
    );

    timers.push(
      window.setTimeout(() => {
        setStage(2);
      }, LOGO_INTRO_MS + AFTER_LOGO_PAUSE_MS + BETWEEN_STAGES_PAUSE_MS)
    );

    timers.push(
      window.setTimeout(() => {
        setStage(3);
      }, LOGO_INTRO_MS + AFTER_LOGO_PAUSE_MS + BETWEEN_STAGES_PAUSE_MS * 2)
    );

    return () => {
      timers.forEach((t) => window.clearTimeout(t));
    };
  }, [prefersReducedMotion]);

  // Preload the last-frame still so the swap is seamless (no flash).
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const img = new Image();
    img.decoding = 'async';
    img.src = '/brand/logo-intro-last-frame.webp';
    if (img.complete) {
      setLastFrameReady(true);
      return;
    }
    const onLoad = () => setLastFrameReady(true);
    const onError = () => {
      // If preload fails, we'll still attempt to show it; but don't block the sequence.
      setLastFrameReady(true);
    };
    img.addEventListener('load', onLoad);
    img.addEventListener('error', onError);
    return () => {
      img.removeEventListener('load', onLoad);
      img.removeEventListener('error', onError);
    };
  }, []);

  const showStill = wantFreezeLogo && (lastFrameReady || instantMode);

  // Once we've faded to the still, unmount the animated image to avoid any ongoing decode work.
  useEffect(() => {
    if (!showStill) return;
    const t = window.setTimeout(() => setUnmountAnimated(true), 2200);
    return () => window.clearTimeout(t);
  }, [showStill]);

  return (
    <Layout title="Makapix Club" description="Let's meet at the pixel.">
      <div className={`welcome-root stage-${stage} ${instantMode ? 'instant' : ''}`}>
        <section className="welcome-left" aria-label="Makapix Club introduction">
          <div className="logo-wrap" aria-hidden="true">
            {!unmountAnimated && (
              <img
                src="/brand/logo-intro-lossy.webp"
                alt=""
                className={`logo-intro logo-animated ${showStill ? 'is-hidden' : ''}`}
                decoding="async"
                fetchPriority="high"
              />
            )}
            <img
              src="/brand/logo-intro-last-frame.webp"
              alt=""
              className={`logo-intro logo-still ${showStill ? 'is-visible' : ''}`}
              decoding="async"
              fetchPriority="high"
              onLoad={() => setLastFrameReady(true)}
            />
          </div>

          <h1 className="headline">Let&apos;s meet at the pixel.</h1>

          <div className="copy">
            <p>From 1-bpp to 24-bpp, Makapix Club convenes:</p>
            <ul>
              <li>DIY makers</li>
              <li>Pixel artists</li>
              <li>Art lovers</li>
            </ul>
            <p className="closing">Come in, we are open!</p>
            <p className="recommended-link">
              <Link href="/recommended">See our Recommended artworks without logging in →</Link>
            </p>
            <p className="recommended-link">
              <Link href="/about">About Makapix Club →</Link>
            </p>
          </div>
        </section>

        <aside className="welcome-right" aria-label="Login or register">
          <AuthPanel variant="embedded" showLogoSection={false} />
        </aside>
      </div>

      <style jsx global>{`
        /* Landing page: pure black backdrop (and header) unlike the rest of the site */
        body {
          background-color: #000 !important;
        }
        .header {
          background: #000 !important;
          border-bottom-color: rgba(255, 255, 255, 0.06) !important;
          backdrop-filter: none !important;
        }
      `}</style>

      <style jsx>{`
        .welcome-root {
          width: 100%;
          max-width: 1100px;
          margin: 0 auto;
          padding: 36px 32px 64px;
          display: grid;
          grid-template-columns: 1.2fr 1fr;
          gap: 28px;
          align-items: start;
        }

        .welcome-left {
          padding-top: 10px;
        }

        .logo-wrap {
          /* ~75% larger than previous 128px */
          width: 224px;
          /* Only occupy 2/3 height in layout; image will visually "spill" below for overlap */
          height: 220px;
          border-radius: 26px;
          overflow: visible;
          background: transparent;
          margin: 0 auto;
          position: relative;
          z-index: 1;
        }

        .logo-intro {
          width: 224px;
          height: 224px;
          object-fit: contain;
          image-rendering: auto;
          display: block;
          position: absolute;
          top: 0;
          left: 0;
          border-radius: 26px;
          background: #000;
          z-index: 1;
          will-change: opacity;
          transition: opacity 700ms ease;
          opacity: 1;
        }

        .logo-still {
          opacity: 0;
          z-index: 2;
        }

        .logo-still.is-visible {
          opacity: 1;
        }

        .logo-animated.is-hidden {
          opacity: 0;
        }

        .headline {
          margin-top: 0;
          font-size: 30px;
          line-height: 1.12;
          letter-spacing: -0.02em;
          font-weight: 700;
          color: var(--text-primary);
          font-family: ui-serif, Georgia, 'Times New Roman', Times, serif;
          position: relative;
          z-index: 2;
          text-align: center;
          margin-top: 18px;
        }

        .copy {
          margin-top: 18px;
          color: var(--text-secondary);
          font-size: 16px;
          line-height: 1.65;
          max-width: 46ch;
          margin-left: auto;
          margin-right: auto;
          padding-left: 56px;
          padding-right: 56px;
          position: relative;
          z-index: 2;
        }

        .copy ul {
          margin: 10px 0 14px;
          padding-left: 56px;
        }

        .copy li {
          margin: 6px 0;
        }

        .closing {
          margin-top: 12px;
          color: var(--text-primary);
        }

        .recommended-link {
          margin-top: 10px;
        }

        .recommended-link :global(a) {
          color: var(--text-secondary);
          text-decoration: none;
        }

        .recommended-link :global(a:hover) {
          color: var(--text-primary);
        }

        .welcome-right {
          padding-top: 8px;
          /* On desktop, the grid column already sits on the right.
             Don't right-align the card inside the column (it creates empty space on the left). */
          display: block;
        }

        /* Make the embedded auth panel a bit wider on the landing page */
        .welcome-right :global(.auth-card),
        .welcome-right :global(.success-card) {
          max-width: 460px;
        }

        /* Staged reveal */
        .headline,
        .copy {
          opacity: 0;
          transform: translateY(6px);
          transition: opacity 1400ms ease, transform 1400ms ease;
        }

        .stage-1 .headline,
        .stage-2 .headline,
        .stage-3 .headline {
          opacity: 1;
          transform: translateY(0);
        }

        .stage-2 .copy,
        .stage-3 .copy {
          opacity: 1;
          transform: translateY(0);
        }

        /* Internal navigation: show instantly (no delays/fades). */
        .instant .headline,
        .instant .copy {
          transition: none !important;
          opacity: 1 !important;
          transform: none !important;
        }

        @media (max-width: 900px) {
          .welcome-root {
            grid-template-columns: 1fr;
            gap: 18px;
            padding: 28px 18px 48px;
          }

          .welcome-right {
            padding-top: 0;
            display: flex;
            justify-content: center;
          }

          .logo-wrap {
            width: 168px;
            /* Reserve a bit more vertical space on mobile so the logo doesn't crowd the headline */
            height: 140px;
          }

          .logo-intro {
            width: 168px;
            height: 168px;
          }

          .headline {
            margin-top: 22px;
          }
        }
      `}</style>
    </Layout>
  );
}


