import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import Layout from '../components/Layout';
import AuthPanel from '../components/AuthPanel';
import { authenticatedFetch } from '../lib/api';
import { ensureCompatibleArtUrl } from '../utils/imageCompat';

const LOGO_INTRO_MS = 1188;
// Reveal the value prop quickly — it must NOT wait for the logo animation.
const STAGE1_MS = 450; // headline + subhead + benefit chips
const STAGE2_MS = 1100; // audience copy + links

interface SamplePost {
  id: number;
  public_sqid: string;
  title: string;
  art_url: string;
  width: number;
  height: number;
  frame_count?: number;
}

export default function WelcomePage() {
  const [stage, setStage] = useState<0 | 1 | 2 | 3>(0);
  const [wantFreezeLogo, setWantFreezeLogo] = useState(false);
  const [lastFrameReady, setLastFrameReady] = useState(false);
  const [unmountAnimated, setUnmountAnimated] = useState(false);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const [instantMode, setInstantMode] = useState(false);
  const [samples, setSamples] = useState<SamplePost[]>([]);

  const API_BASE_URL = typeof window !== 'undefined'
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : '';

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

  // Load a few real promoted artworks so the value prop is instantly visible
  // and alive. Independent of the logo animation; the endpoint is public.
  const loadSamples = useCallback(async () => {
    if (!API_BASE_URL) return;
    try {
      const url =
        `${API_BASE_URL}/api/feed/promoted?limit=12` +
        `&fields=id,public_sqid,title,art_url,width,height,frame_count`;
      const response = await authenticatedFetch(url);
      if (!response.ok) return;
      const data = await response.json();
      if (data && Array.isArray(data.items)) {
        setSamples(data.items);
      }
    } catch {
      // A missing sample grid is non-fatal — the hero still stands on its own.
    }
  }, [API_BASE_URL]);

  useEffect(() => {
    loadSamples();
  }, [loadSamples]);

  useEffect(() => {
    if (prefersReducedMotion || instantMode) {
      setWantFreezeLogo(true);
      setStage(3);
      return;
    }

    const timers: number[] = [];

    timers.push(
      window.setTimeout(() => {
        setStage((s) => (s < 1 ? 1 : s));
      }, STAGE1_MS)
    );

    timers.push(
      window.setTimeout(() => {
        setStage((s) => (s < 2 ? 2 : s));
      }, STAGE2_MS)
    );

    timers.push(
      window.setTimeout(() => {
        setWantFreezeLogo(true);
      }, LOGO_INTRO_MS)
    );

    return () => {
      timers.forEach((t) => window.clearTimeout(t));
    };
  }, [prefersReducedMotion, instantMode]);

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
    <Layout
      title="Makapix Club — pixel art on real displays"
      description="The open community where pixel art comes off the screen and onto real displays. Free, no ads, no algorithm."
    >
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

          <h1 className="headline">Pixel art, alive on real displays.</h1>

          <p className="subhead">
            The open community where pixel art comes off the screen &mdash;
            free, no ads, no algorithm.
          </p>

          <ul className="chips" aria-label="What makes Makapix different">
            <li className="chip chip-cyan">On real displays</li>
            <li className="chip chip-pink">Creator analytics</li>
            <li className="chip chip-green">Open &amp; ad-free</li>
          </ul>

          <div className="copy">
            <p>From 1-bpp to 24-bpp, Makapix Club convenes makers, pixel artists, and art lovers.</p>
            <p className="closing">Come in, we are open!</p>
            <p className="recommended-link">
              <Link href="/recommended">See our Recommended artworks without logging in →</Link>
            </p>
            <p className="recommended-link">
              <Link href="/about">About Makapix Club →</Link>
            </p>
            <p className="recommended-link">
              <Link href="/players">Building a connected display? See player projects →</Link>
            </p>
          </div>
        </section>

        <aside className="welcome-right" aria-label="Login or register">
          <AuthPanel variant="embedded" showLogoSection={false} />
        </aside>
      </div>

      {samples.length > 0 && (
        <section className="samples" aria-label="Recent community artwork">
          <div className="samples-head">
            <h2>Fresh from the community</h2>
            <Link href="/recommended" className="samples-more">Browse the gallery →</Link>
          </div>
          <div className="samples-grid">
            {samples.map((post) => (
              <Link
                key={post.id}
                href={`/p/${post.public_sqid}`}
                className="sample-cell"
                aria-label={post.title}
                title={post.title}
              >
                <img
                  src={ensureCompatibleArtUrl(post.art_url, post.frame_count)}
                  alt={post.title}
                  className="pixel-art"
                  loading="lazy"
                  decoding="async"
                />
              </Link>
            ))}
          </div>
        </section>
      )}

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
          padding: 36px 32px 32px;
          display: grid;
          /* minmax(0, 1fr) on the right track sizes it purely by free space, not
             by its content's min-content. Without this, the wider register-mode
             content (vs. login) expands the column and the auth panel jumps width
             when switching tabs. */
          grid-template-columns: 1.2fr minmax(0, 1fr);
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
          margin-top: 18px;
          font-size: 32px;
          line-height: 1.1;
          letter-spacing: -0.02em;
          font-weight: 700;
          color: var(--text-primary);
          font-family: ui-serif, Georgia, 'Times New Roman', Times, serif;
          position: relative;
          z-index: 2;
          text-align: center;
        }

        .subhead {
          margin: 12px auto 0;
          max-width: 42ch;
          text-align: center;
          color: var(--text-secondary);
          font-size: 17px;
          line-height: 1.5;
          position: relative;
          z-index: 2;
        }

        .chips {
          list-style: none;
          margin: 16px auto 0;
          padding: 0;
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          justify-content: center;
          position: relative;
          z-index: 2;
        }

        .chip {
          font-size: 13px;
          font-weight: 600;
          letter-spacing: 0.01em;
          padding: 5px 12px;
          border-radius: 999px;
          border: 1px solid transparent;
          white-space: nowrap;
          color: var(--text-primary);
        }

        .chip-cyan {
          border-color: rgba(0, 212, 255, 0.45);
          color: var(--accent-cyan, #00d4ff);
          background: rgba(0, 212, 255, 0.08);
        }

        .chip-pink {
          border-color: rgba(255, 110, 180, 0.45);
          color: var(--accent-pink, #ff6eb4);
          background: rgba(255, 110, 180, 0.08);
        }

        .chip-green {
          border-color: rgba(120, 230, 150, 0.45);
          color: #78e696;
          background: rgba(120, 230, 150, 0.08);
        }

        .copy {
          margin-top: 20px;
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
          text-align: center;
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

        /* Live sample grid */
        .samples {
          width: 100%;
          max-width: 1100px;
          margin: 8px auto 0;
          padding: 24px 32px 56px;
          opacity: 0;
          animation: samples-in 700ms ease forwards;
        }

        @keyframes samples-in {
          to {
            opacity: 1;
          }
        }

        .samples-head {
          display: flex;
          align-items: baseline;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 16px;
          border-top: 1px solid rgba(255, 255, 255, 0.06);
          padding-top: 24px;
        }

        .samples-head h2 {
          margin: 0;
          font-size: 18px;
          font-weight: 700;
          color: var(--text-primary);
          letter-spacing: -0.01em;
        }

        /* Link renders an <a>; styled-jsx only scopes native tags, so target it
           via :global() under the scoped grid (same pattern as .recommended-link). */
        .samples-head :global(.samples-more) {
          font-size: 14px;
          color: var(--text-secondary);
          text-decoration: none;
          white-space: nowrap;
        }

        .samples-head :global(.samples-more:hover) {
          color: var(--text-primary);
        }

        /* Fixed cells of canonical 128x128 artwork, centered in the row. */
        .samples-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, 146px);
          justify-content: center;
          gap: 12px;
        }

        /* 146px border-box = 128px artwork + 8px frame each side + 1px border. */
        .samples-grid :global(.sample-cell) {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 146px;
          height: 146px;
          border-radius: 10px;
          background: #0a0a0a;
          border: 1px solid rgba(255, 255, 255, 0.06);
          overflow: hidden;
          transition: border-color 160ms ease, transform 160ms ease, box-shadow 160ms ease;
        }

        .samples-grid :global(.sample-cell:hover) {
          border-color: rgba(0, 212, 255, 0.5);
          transform: translateY(-2px);
          box-shadow: var(--glow-cyan, 0 0 16px rgba(0, 212, 255, 0.25));
        }

        /* Canonical 128x128 thumbnail: small art scales UP, large scales down.
           The .pixel-art class forces nearest-neighbor, so upscales stay crisp. */
        .samples-grid :global(.sample-cell img) {
          width: 128px;
          height: 128px;
          object-fit: contain;
        }

        /* Staged reveal — value prop is revealed early (stage 1), copy at stage 2 */
        .headline,
        .subhead,
        .chips,
        .copy {
          opacity: 0;
          transform: translateY(6px);
          transition: opacity 900ms ease, transform 900ms ease;
        }

        .stage-1 .headline,
        .stage-2 .headline,
        .stage-3 .headline,
        .stage-1 .subhead,
        .stage-2 .subhead,
        .stage-3 .subhead,
        .stage-1 .chips,
        .stage-2 .chips,
        .stage-3 .chips {
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
        .instant .subhead,
        .instant .chips,
        .instant .copy {
          transition: none !important;
          opacity: 1 !important;
          transform: none !important;
        }

        @media (max-width: 900px) {
          .welcome-root {
            grid-template-columns: 1fr;
            gap: 18px;
            padding: 28px 18px 24px;
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
            font-size: 27px;
          }

          .copy {
            padding-left: 16px;
            padding-right: 16px;
          }

          .samples {
            padding: 16px 18px 40px;
          }
        }
      `}</style>
    </Layout>
  );
}
