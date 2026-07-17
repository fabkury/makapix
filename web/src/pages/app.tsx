import { useEffect, useState } from "react";
import Head from "next/head";
import Link from "next/link";
import Layout from "../components/Layout";

const APP_STORE_URL = "https://apps.apple.com/us/app/makapix-club/id6788845118";
const OG_IMAGE_URL = "https://makapix.club/app/og-app.jpg";

const screenshots = [
  {
    src: "/app/shot-feed.webp",
    alt: "The Makapix Club feed in the app",
    caption: "The Club, in your pocket",
  },
  {
    src: "/app/shot-artwork.webp",
    alt: "Artwork view with reactions and comments",
    caption: "React, comment & cast to players",
  },
  {
    src: "/app/shot-editor.webp",
    alt: "The animated pixel-art editor",
    caption: "The full animated editor",
  },
  {
    src: "/app/shot-contribute.webp",
    alt: "Sharing pixel art from the app",
    caption: "Draw or upload — post anywhere",
  },
];

const features = [
  {
    icon: "🎨",
    title: "Full animated editor",
    description:
      "Draw frame-by-frame pixel art with layers, palettes, and all the tools — right on your phone.",
  },
  {
    icon: "🖼️",
    title: "The whole Club",
    description:
      "Browse feeds, react, comment, follow artists, and publish — everything the site does, natively.",
  },
  {
    icon: "📺",
    title: "Cast to real displays",
    description:
      "Send artworks straight to your LED matrices and pixel players from the app.",
  },
  {
    icon: "🔔",
    title: "Stay in the loop",
    description: "Get notified when the artists you follow post something new.",
  },
];

export default function AppPage() {
  const [isIOS, setIsIOS] = useState(false);

  useEffect(() => {
    try {
      const ua = navigator.userAgent || "";
      // iPadOS 13+ reports as Mac; detect the touch-capable Mac case too.
      const iOS =
        /iPad|iPhone|iPod/.test(ua) ||
        (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
      setIsIOS(iOS);
    } catch {
      // ignore — fall back to the default (badge + QR) layout
    }
  }, []);

  return (
    <Layout
      title="Get the App"
      description="Makapix Club is now on iPhone & iPad — the full animated pixel-art editor and the whole Club, in one app. Download free on the App Store."
    >
      <Head>
        <meta
          property="og:title"
          content="Makapix Club — now on iPhone & iPad"
          key="og:title"
        />
        <meta
          property="og:description"
          content="The full animated pixel-art editor and the whole Club, in one app. Download free on the App Store."
          key="og:description"
        />
        <meta property="og:image" content={OG_IMAGE_URL} key="og:image" />
        <meta
          property="og:url"
          content="https://makapix.club/app"
          key="og:url"
        />
        <meta
          name="twitter:card"
          content="summary_large_image"
          key="twitter:card"
        />
        <meta name="twitter:image" content={OG_IMAGE_URL} key="twitter:image" />
      </Head>

      <div className="app-page">
        {/* Hero */}
        <section className="hero">
          <img
            src="/app/app-logo.png"
            alt="Makapix Club"
            className="hero-logo"
            width={112}
            height={112}
          />
          <h1>
            Makapix Club is now on{" "}
            <span className="grad">iPhone &amp; iPad</span>
          </h1>
          <p className="lead">
            The full animated pixel-art editor and the whole Club — feeds,
            reactions, comments, publishing, and casting to your players — in
            one free app.
          </p>

          <div className="cta">
            <a
              href={APP_STORE_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="badge-link"
              aria-label="Download Makapix Club on the App Store"
            >
              <img
                src="/app/appstore-badge.svg"
                alt="Download on the App Store"
                width={168}
                height={56}
              />
            </a>

            {isIOS ? (
              <p className="cta-hint cta-hint-ios">
                👆 Tap to install on this device
              </p>
            ) : (
              <div className="qr">
                <img
                  src="/app/appstore-qr.svg"
                  alt="QR code to the App Store listing"
                  width={112}
                  height={112}
                />
                <span className="cta-hint">Scan with your iPhone camera</span>
              </div>
            )}
          </div>
        </section>

        {/* Feature graphic */}
        <img
          src="/app/og-app.jpg"
          alt="Makapix Club — pixel art on real displays"
          className="feature-graphic"
        />

        {/* What you get */}
        <section className="features">
          {features.map((f) => (
            <div key={f.title} className="feature">
              <span className="feature-icon">{f.icon}</span>
              <div className="feature-body">
                <span className="feature-title">{f.title}</span>
                <span className="feature-desc">{f.description}</span>
              </div>
            </div>
          ))}
        </section>

        {/* Screenshots */}
        <section className="shots">
          {screenshots.map((s) => (
            <figure key={s.src}>
              <img src={s.src} alt={s.alt} loading="lazy" />
              <figcaption>{s.caption}</figcaption>
            </figure>
          ))}
        </section>

        {/* Android */}
        <section className="android">
          <h2>🤖 Android is on the way</h2>
          <p>
            The Android version is in closed testing right now and heading to
            Google Play soon. Follow along on{" "}
            <a
              href="https://discord.gg/xk9umcujXV"
              target="_blank"
              rel="noopener noreferrer"
            >
              Discord
            </a>{" "}
            — we&apos;ll announce it here and there the moment it&apos;s live.
          </p>
        </section>

        <p className="see-also">
          Prefer the browser? Everything works right here too.{" "}
          <Link href="/about">About Makapix Club</Link> ·{" "}
          <Link href="/privacy">Privacy</Link> ·{" "}
          <Link href="/terms">Terms</Link>
        </p>
      </div>

      <style jsx>{`
        .app-page {
          max-width: 760px;
          margin: 0 auto;
          padding: 32px 24px 64px;
          color: var(--text-secondary);
          line-height: 1.7;
        }

        .hero {
          text-align: center;
        }

        .hero-logo {
          width: 112px;
          height: 112px;
          image-rendering: pixelated;
          margin: 0 auto 16px;
          display: block;
        }

        .hero h1 {
          font-size: 2rem;
          font-weight: 800;
          color: var(--text-primary);
          margin: 0 0 16px;
          line-height: 1.2;
        }

        .grad {
          background: linear-gradient(
            90deg,
            var(--accent-pink),
            var(--accent-cyan)
          );
          -webkit-background-clip: text;
          background-clip: text;
          -webkit-text-fill-color: transparent;
        }

        .lead {
          font-size: 1.05rem;
          color: var(--text-primary);
          margin: 0 auto 28px;
          max-width: 560px;
        }

        .cta {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 16px;
        }

        .badge-link {
          display: inline-block;
          transition: transform var(--transition-fast);
        }

        .badge-link:hover {
          transform: translateY(-2px);
        }

        .badge-link img {
          width: 168px;
          height: auto;
          display: block;
        }

        .qr {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 8px;
        }

        .qr img {
          width: 112px;
          height: 112px;
          padding: 8px;
          background: #fff;
          border-radius: 10px;
        }

        .cta-hint {
          font-size: 0.85rem;
          color: var(--text-secondary);
        }

        .cta-hint-ios {
          font-size: 0.95rem;
          color: var(--accent-cyan);
          font-weight: 500;
          margin: 0;
        }

        .feature-graphic {
          width: 100%;
          height: auto;
          border-radius: 14px;
          border: 1px solid rgba(255, 255, 255, 0.08);
          margin: 40px 0;
          display: block;
        }

        .features {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
          margin-bottom: 40px;
        }

        .feature {
          display: flex;
          align-items: flex-start;
          gap: 12px;
          padding: 16px;
          background: rgba(255, 255, 255, 0.03);
          border: 1px solid rgba(255, 255, 255, 0.06);
          border-radius: 12px;
        }

        .feature-icon {
          font-size: 1.4rem;
          line-height: 1;
          flex-shrink: 0;
        }

        .feature-body {
          display: flex;
          flex-direction: column;
          gap: 4px;
        }

        .feature-title {
          font-weight: 600;
          color: var(--text-primary);
          font-size: 0.98rem;
        }

        .feature-desc {
          font-size: 0.88rem;
          color: var(--text-secondary);
          line-height: 1.5;
        }

        .shots {
          display: grid;
          grid-template-columns: repeat(4, 1fr);
          gap: 14px;
          margin-bottom: 44px;
        }

        .shots figure {
          margin: 0;
          text-align: center;
        }

        .shots img {
          width: 100%;
          height: auto;
          border: 1px solid rgba(255, 255, 255, 0.18);
          border-radius: 14px;
          display: block;
        }

        .shots figcaption {
          margin-top: 8px;
          font-size: 0.78rem;
          color: var(--text-secondary);
        }

        .android {
          padding: 20px 22px;
          background: rgba(0, 212, 255, 0.06);
          border-left: 3px solid var(--accent-cyan);
          border-radius: 0 12px 12px 0;
          margin-bottom: 32px;
        }

        .android h2 {
          font-size: 1.1rem;
          font-weight: 600;
          color: var(--text-primary);
          margin: 0 0 8px;
        }

        .android p {
          margin: 0;
          font-size: 0.95rem;
        }

        .see-also {
          text-align: center;
          font-size: 0.85rem;
          margin: 0;
        }

        .app-page :global(a) {
          color: var(--accent-cyan);
          text-decoration: none;
          overflow-wrap: anywhere;
        }

        .app-page :global(a:hover) {
          text-decoration: underline;
        }

        @media (max-width: 640px) {
          .shots {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        @media (max-width: 480px) {
          .app-page {
            padding: 24px 16px 48px;
          }

          .hero h1 {
            font-size: 1.6rem;
          }

          .lead {
            font-size: 0.98rem;
          }

          .features {
            grid-template-columns: 1fr;
          }

          .feature-graphic {
            margin: 32px 0;
          }
        }
      `}</style>
    </Layout>
  );
}
