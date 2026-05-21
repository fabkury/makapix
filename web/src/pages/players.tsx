import Layout from '../components/Layout';

const PLAYER_GUIDE_URL =
  'https://github.com/fabkury/makapix/blob/main/docs/player/README.md';
const FULL_DOCS_URL = 'https://github.com/fabkury/makapix/blob/main/docs/README.md';
const P3A_REPO_URL = 'https://github.com/fabkury/p3a';
const PIXELIX_REPO_URL = 'https://github.com/BlueAndi/Pixelix';
const WAVESHARE_BOARD_URL =
  'https://www.waveshare.com/product/arduino/boards-kits/esp32-p4/esp32-p4-wifi6-touch-lcd-4b.htm?sku=31416';

export default function PlayersPage() {
  return (
    <Layout
      title="Players — Makapix Club"
      description="Pixels, off-screen. Connect physical pixel displays to the Makapix community feed."
    >
      <article className="players-root">
        <header className="hero">
          <h1>Pixels, off-screen.</h1>
          <p className="lead">
            Makapix Club is built around physical pixel displays. Connect an LED matrix,
            an e-paper panel, or any device that speaks MQTT over TLS, and stream community
            artwork the moment it&apos;s posted.
          </p>
          <div className="cta-row">
            <a
              href={PLAYER_GUIDE_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="cta cta-secondary"
            >
              Read the Player Guide ↗
            </a>
          </div>
        </header>

        <figure className="hero-photo">
          <img
            src="/players/p3a-with-makapix-club-artwork.jpg"
            alt="A p3a player device on a desk, displaying pixel art from Makapix Club."
            loading="lazy"
          />
          <figcaption>
            A p3a player displaying a fresh post from the Makapix Club feed.
          </figcaption>
        </figure>

        <section className="projects">
          <h2>Reference projects</h2>
          <p className="section-lead">
            Two open-source player projects already integrate with MPX. Both are free to
            study, fork, and build on.
          </p>

          <div className="project-cards">
            <article className="project-card">
              <div className="project-logo project-logo-square">
                <img src="/players/p3a-logo.png" alt="p3a logo" />
              </div>
              <h3>p3a</h3>
              <p>
                A first-party reference firmware for the{' '}
                <a href={WAVESHARE_BOARD_URL} target="_blank" rel="noopener noreferrer">
                  Waveshare ESP32-P4-WIFI6-TOUCH-LCD-4B
                </a>{' '}
                board. Demonstrates the full registration, MQTT, and query flow against MPX.
              </p>
              <a
                href={P3A_REPO_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="project-link"
              >
                Source on GitHub ↗
              </a>
            </article>

            <article className="project-card">
              <div className="project-logo project-logo-wide">
                <img src="/players/pixelix-logo.png" alt="Pixelix logo" />
              </div>
              <h3>Pixelix</h3>
              <p>
                A mature, plugin-based firmware for ESP32 LED-matrix displays by{' '}
                <a
                  href="https://github.com/BlueAndi"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  @BlueAndi
                </a>
                , with native support for Makapix Club content alongside other sources.
              </p>
              <a
                href={PIXELIX_REPO_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="project-link"
              >
                Source on GitHub ↗
              </a>
            </article>
          </div>
        </section>

        <section className="how-it-works">
          <h2>How it works</h2>
          <ol className="steps">
            <li>
              <strong>Provision.</strong> Register a device on the MPX server. Receive a
              TLS client certificate and a private MQTT key.
            </li>
            <li>
              <strong>Connect.</strong> Open an MQTT-over-TLS connection on port 8883.
              Subscribe to your device&apos;s topics.
            </li>
            <li>
              <strong>Query.</strong> Fetch artworks from the community feed, filtered by
              canvas size, format, color count, tags, and more.
            </li>
            <li>
              <strong>Display.</strong> Decode PNG, GIF, WebP, or BMP and render onto your
              hardware. Report playback status and react with emoji on behalf of the device
              owner.
            </li>
          </ol>
        </section>

        <section className="docs">
          <h2>Build your own player</h2>
          <p>
            Any device that can do MQTT over TLS and decode standard image formats is a
            valid player — ESP32, Raspberry Pi, Arduino with a TLS-capable network shield,
            even a laptop. The wire protocol is documented and stable.
          </p>
          <ul className="doc-links">
            <li>
              <a href={PLAYER_GUIDE_URL} target="_blank" rel="noopener noreferrer">
                <strong>Player Device Guide</strong> ↗
              </a>
              <span>
                {' '}
                — Provisioning, MQTT/TLS setup, querying the feed, displaying artwork, and
                status reporting. Start with <em>Quick Start</em> if you have hardware in
                front of you.
              </span>
            </li>
            <li>
              <a href={FULL_DOCS_URL} target="_blank" rel="noopener noreferrer">
                <strong>Full documentation</strong> ↗
              </a>
              <span>
                {' '}
                — Architecture, HTTP API reference, MQTT protocol, and deployment. For
                integrators going beyond a single device.
              </span>
            </li>
          </ul>
        </section>

        <style jsx>{`
          .players-root {
            width: 100%;
            max-width: 880px;
            margin: 0 auto;
            padding: 40px 24px 72px;
            color: var(--text-secondary);
            line-height: 1.7;
          }

          .hero {
            text-align: center;
            margin-bottom: 36px;
          }

          .hero h1 {
            font-size: 2.25rem;
            line-height: 1.12;
            letter-spacing: -0.02em;
            font-weight: 700;
            color: var(--text-primary);
            font-family: ui-serif, Georgia, 'Times New Roman', Times, serif;
            margin: 0 0 18px 0;
          }

          .lead {
            font-size: 1.05rem;
            color: var(--text-primary);
            max-width: 56ch;
            margin: 0 auto 24px auto;
          }

          .cta-row {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 12px;
            margin-top: 4px;
          }

          .cta {
            display: inline-block;
            padding: 10px 18px;
            border-radius: 10px;
            font-size: 0.95rem;
            font-weight: 600;
            text-decoration: none;
            transition: background var(--transition-fast),
              border-color var(--transition-fast), color var(--transition-fast);
          }

          .cta-secondary {
            background: transparent;
            color: var(--text-primary);
            border: 1px solid rgba(255, 255, 255, 0.18);
          }

          .cta-secondary:hover {
            border-color: rgba(255, 255, 255, 0.35);
            background: rgba(255, 255, 255, 0.04);
          }

          .hero-photo {
            margin: 0 0 48px 0;
            padding: 0;
          }

          .hero-photo img {
            width: 100%;
            height: auto;
            display: block;
            border-radius: 14px;
            border: 1px solid rgba(255, 255, 255, 0.06);
          }

          .hero-photo figcaption {
            margin-top: 10px;
            text-align: center;
            font-size: 0.85rem;
            color: var(--text-secondary);
            opacity: 0.75;
          }

          h2 {
            font-size: 1.35rem;
            font-weight: 600;
            color: var(--text-primary);
            margin: 0 0 14px 0;
          }

          .section-lead {
            margin: 0 0 20px 0;
          }

          .projects,
          .how-it-works,
          .docs {
            margin-bottom: 48px;
          }

          .project-cards {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
          }

          .project-card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-left: 3px solid var(--accent-pink);
            border-radius: 12px;
            padding: 20px;
            display: flex;
            flex-direction: column;
          }

          .project-logo {
            display: flex;
            align-items: center;
            justify-content: flex-start;
            margin-bottom: 14px;
            min-height: 64px;
          }

          .project-logo img {
            display: block;
            image-rendering: pixelated;
            height: auto;
          }

          .project-logo-square img {
            width: 64px;
            height: 64px;
          }

          .project-logo-wide img {
            width: auto;
            max-width: 220px;
            height: 40px;
          }

          .project-card h3 {
            font-size: 1.15rem;
            font-weight: 700;
            color: var(--text-primary);
            margin: 0 0 10px 0;
          }

          .project-card p {
            margin: 0 0 16px 0;
            font-size: 0.95rem;
            flex-grow: 1;
          }

          .project-link {
            color: var(--accent-pink);
            text-decoration: none;
            font-weight: 600;
            font-size: 0.95rem;
          }

          .project-link:hover {
            text-decoration: underline;
          }

          .steps {
            list-style: none;
            counter-reset: step;
            padding: 0;
            margin: 0;
          }

          .steps li {
            position: relative;
            counter-increment: step;
            padding: 14px 16px 14px 56px;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            font-size: 0.95rem;
          }

          .steps li + li {
            margin-top: 10px;
          }

          .steps li::before {
            content: counter(step);
            position: absolute;
            left: 16px;
            top: 14px;
            width: 28px;
            height: 28px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            background: var(--accent-pink);
            color: #fff;
            font-weight: 700;
            font-size: 0.85rem;
            line-height: 1;
          }

          .steps strong {
            color: var(--text-primary);
          }

          .doc-links {
            list-style: none;
            padding: 0;
            margin: 0;
          }

          .doc-links li {
            padding: 14px 16px;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 10px;
            font-size: 0.95rem;
          }

          .doc-links li + li {
            margin-top: 10px;
          }

          .doc-links a {
            color: var(--accent-pink);
            text-decoration: none;
          }

          .doc-links a:hover {
            text-decoration: underline;
          }

          .doc-links strong {
            color: var(--text-primary);
          }

          a {
            color: var(--accent-cyan);
            text-decoration: none;
          }

          a:hover {
            text-decoration: underline;
          }

          strong {
            color: var(--text-primary);
          }

          @media (max-width: 720px) {
            .players-root {
              padding: 28px 18px 56px;
            }

            .hero h1 {
              font-size: 1.85rem;
            }

            .lead {
              font-size: 1rem;
            }

            .project-cards {
              grid-template-columns: 1fr;
            }

            h2 {
              font-size: 1.2rem;
            }

            .projects,
            .how-it-works,
            .docs {
              margin-bottom: 36px;
            }
          }
        `}</style>
      </article>
    </Layout>
  );
}
