import Link from 'next/link';
import Layout from '../components/Layout';

export default function BetaPage() {
  return (
    <Layout
      title="Beta-Test the Android App"
      description="Help launch the Makapix Club Android app — join the closed beta on Google Play"
    >
      <div className="beta-container">
        <article className="beta-article">
          <h1>Help us launch the Makapix Club app 📱</h1>

          <p className="lead">
            The official <strong>Makapix Club Android app</strong> is ready for beta
            testing — the full animated pixel-art editor plus the whole Club (feeds,
            reactions, comments, publishing, remixing), in one app. Draw offline on the
            bus; post it to the Club when you&apos;re back online; watch it appear on
            Makapix players.
          </p>

          <p>
            We need <strong>at least 12 beta testers who stay enrolled for 14 days</strong>{' '}
            to unlock the public Play Store release — Google&apos;s rule, not ours. Every
            day below 12 testers pauses Google&apos;s clock, so every single tester
            genuinely matters. Joining takes about two minutes.
          </p>

          <h2>How to join</h2>

          <p className="order-note">
            ⚠️ The order of the first two steps matters — step 2 only works after step 1.
          </p>

          <ol className="steps">
            <li>
              <strong>Join the tester group</strong> (this grants access; we never see
              your email address):
              <br />
              <a
                href="https://groups.google.com/g/makapix-testers"
                target="_blank"
                rel="noopener noreferrer"
              >
                groups.google.com/g/makapix-testers
              </a>{' '}
              → &quot;Join group&quot;
              <br />
              <span className="alt">
                Or by email: send any message to{' '}
                <a href="mailto:makapix-testers+subscribe@googlegroups.com">
                  makapix-testers+subscribe@googlegroups.com
                </a>{' '}
                from the address tied to your Google account.
              </span>
            </li>
            <li>
              <strong>Become a tester</strong> (signed in to the same Google account you
              use on your phone):
              <br />
              <a
                href="https://play.google.com/apps/testing/club.makapix.app"
                target="_blank"
                rel="noopener noreferrer"
              >
                play.google.com/apps/testing/club.makapix.app
              </a>{' '}
              → &quot;Become a tester&quot;
            </li>
            <li>
              <strong>Install the app</strong> from the Play Store link shown on that
              page.
            </li>
            <li>
              <strong>Stay enrolled for at least 14 days</strong> — keep the app
              installed and don&apos;t leave the test early; leaving is what resets
              Google&apos;s clock. Beyond that, just use the app (or don&apos;t!).
            </li>
          </ol>

          <h2>What you need</h2>

          <p>
            An Android phone or tablet (Android 5.0 or newer — both arm64 and arm32 are
            supported) and a Google account.
          </p>

          <h2>Troubleshooting</h2>

          <p>
            <strong>&quot;App not available for this account&quot;</strong> on the
            opt-in page usually means step 1 was skipped — join the tester group first,
            then try again.
          </p>

          <p>
            <strong>&quot;Not available in your country&quot;</strong>: tell us your
            country at <a href="mailto:acme@makapix.club">acme@makapix.club</a> and
            we&apos;ll widen the test&apos;s availability, usually the same day.
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
            Thank you for helping bring Makapix Club to everyone&apos;s pocket. 🎨
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

        .order-note {
          padding: 10px 14px;
          border: 1px solid rgba(255, 110, 180, 0.4);
          border-radius: 8px;
          background: rgba(255, 110, 180, 0.08);
          color: var(--text-primary);
        }

        .steps {
          margin: 0 0 16px 0;
          padding-left: 24px;
        }

        .steps li {
          margin-bottom: 16px;
          font-size: 0.95rem;
        }

        .alt {
          font-size: 0.85rem;
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
        }
      `}</style>
    </Layout>
  );
}
