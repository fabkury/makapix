import Link from 'next/link';
import Layout from '../components/Layout';

export default function BetaPage() {
  return (
    <Layout
      title="Android App — Coming Soon"
      description="The Makapix Club Android app is coming soon to Google Play — beta testing goal reached, thank you!"
    >
      <div className="beta-container">
        <article className="beta-article">
          <h1>The Makapix Club app is almost here 📱</h1>

          <p className="lead">
            Thanks to our amazing beta testers, we&apos;ve reached the enrollment goal
            for the <strong>Makapix Club Android app</strong> — the full animated
            pixel-art editor plus the whole Club (feeds, reactions, comments,
            publishing, remixing), in one app. The beta is now full, and the public
            Play Store release is on its way.
          </p>

          <div className="screenshots">
            <figure>
              <img src="/beta/feed.png" alt="Club feed in the app" width={480} height={960} />
              <figcaption>The Club feeds, in your pocket</figcaption>
            </figure>
            <figure>
              <img
                src="/beta/artwork.png"
                alt="Artwork view with reactions in the app"
                width={480}
                height={960}
              />
              <figcaption>React, comment &amp; send to players</figcaption>
            </figure>
            <figure>
              <img
                src="/beta/editor.png"
                alt="Pixel art editor in the app"
                width={480}
                height={960}
              />
              <figcaption>The full animated editor</figcaption>
            </figure>
          </div>

          <h2>Already a tester? Thank you — one more favor</h2>

          <p>
            Google requires the test to run for <strong>14 more days</strong> before it
            unlocks the public release, so please <strong>stay enrolled and keep the
            app installed</strong> until then — leaving the test early resets
            Google&apos;s clock. Beyond that, just use the app (or don&apos;t!).
          </p>

          <h2>Not a tester?</h2>

          <p>
            Sit tight — the app is coming to Google Play for everyone soon. Meanwhile,
            everything works right here in your browser, and we&apos;ll announce the
            release on the site and on{' '}
            <a
              href="https://discord.gg/xk9umcujXV"
              target="_blank"
              rel="noopener noreferrer"
            >
              Discord
            </a>
            .
          </p>

          <h2>Found a bug? Have opinions?</h2>

          <p>
            We want them! Email{' '}
            <a href="mailto:acme@makapix.club">acme@makapix.club</a> or post in our{' '}
            <a
              href="https://discord.gg/xk9umcujXV"
              target="_blank"
              rel="noopener noreferrer"
            >
              Discord
            </a>
            . Feedback about the editor, the Club, or anything in between is welcome.
          </p>

          <p className="thanks">
            Thank you for helping bring Makapix Club to everyone&apos;s pocket.
          </p>

          <p className="see-also">
            See also: <Link href="/about">about Makapix Club</Link> ·{' '}
            <Link href="/privacy">privacy policy</Link>
          </p>
        </article>
      </div>

      <style jsx>{`
        .beta-container {
          max-width: 720px;
          margin: 0 auto;
          padding: 32px 24px 64px;
        }

        .beta-article {
          color: var(--text-secondary);
          line-height: 1.7;
        }

        .beta-article h1 {
          font-size: 1.75rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0 0 16px 0;
          text-align: center;
        }

        .beta-article h2 {
          font-size: 1.15rem;
          font-weight: 600;
          color: var(--text-primary);
          margin: 32px 0 12px 0;
        }

        .beta-article p {
          margin: 0 0 16px 0;
          font-size: 0.95rem;
        }

        .beta-article .lead {
          font-size: 1.05rem;
          color: var(--text-primary);
          margin-bottom: 24px;
        }

        .beta-article strong {
          color: var(--text-primary);
        }

        .screenshots {
          display: flex;
          gap: 16px;
          justify-content: center;
          margin: 0 0 24px 0;
        }

        .screenshots figure {
          margin: 0;
          flex: 1 1 0;
          min-width: 0;
          max-width: 200px;
          text-align: center;
        }

        .screenshots img {
          width: 100%;
          height: auto;
          border: 1px solid rgba(255, 255, 255, 0.25);
          border-radius: 12px;
          display: block;
        }

        .screenshots figcaption {
          margin-top: 8px;
          font-size: 0.8rem;
          color: var(--text-secondary);
        }

        .thanks {
          margin-top: 24px;
        }

        .see-also {
          margin-top: 32px;
          font-size: 0.85rem;
          text-align: center;
        }

        .beta-article a,
        .beta-article :global(a) {
          color: var(--accent-cyan);
          text-decoration: none;
          overflow-wrap: anywhere;
        }

        .beta-article a:hover,
        .beta-article :global(a:hover) {
          text-decoration: underline;
        }

        @media (max-width: 480px) {
          .beta-container {
            padding: 24px 16px 48px;
          }

          .beta-article h1 {
            font-size: 1.5rem;
          }

          .beta-article h2 {
            font-size: 1.1rem;
          }

          .screenshots {
            gap: 8px;
          }

          .screenshots figcaption {
            font-size: 0.7rem;
          }
        }
      `}</style>
    </Layout>
  );
}
