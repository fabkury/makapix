import Link from 'next/link';
import Layout from '../components/Layout';

// Bump the effective date on material changes, together with
// api/app/constants.py:TERMS_VERSION (they must match).
export default function TermsPage() {
  return (
    <Layout
      title="Terms of Service"
      description="Terms of Service for Makapix Club - the plain-language rules for using the site, app, and player devices"
    >
      <div className="terms-container">
        <article className="policy-article">
          <h1>Terms of Service</h1>

          <p className="effective-date">Effective date: July 6, 2026</p>

          <p className="lead">
            Makapix Club is a small, community-run social network for pixel artists and DIY
            makers. These terms are the agreement between you and us when you use it. We
            have kept them short and in plain language — there is no fine print.
          </p>

          <p>
            These terms cover everything that makes up Makapix Club: the website at{' '}
            <a href="https://makapix.club">makapix.club</a>, the Makapix mobile app, and
            physical player devices that connect to our service. Questions? Email{' '}
            <a href="mailto:acme@makapix.club">acme@makapix.club</a>.
          </p>

          <h2>Who can use Makapix Club</h2>

          <p>
            You must be at least <strong>13 years old</strong> to create an account. If you
            are under the age where your country requires parental consent for online
            services, you need that consent. By creating an account you confirm this.
          </p>

          <h2>Your account</h2>

          <p>
            You are responsible for what happens under your account and for keeping your
            password safe. One person can have one account. Don&apos;t impersonate other
            people or create accounts to evade a ban. You can delete your account at any
            time from your settings (see the{' '}
            <Link href="/privacy">Privacy Policy</Link> for what happens to your data).
          </p>

          <h2>Your content stays yours</h2>

          <p>
            <strong>You keep ownership of the artwork you post.</strong> By posting, you
            give Makapix Club the permission we need to operate the service: to host,
            store, display, and distribute your content on the website, in the app, and to
            player devices, including making technical copies (thumbnails, format
            conversions, backups).
          </p>

          <p>
            <strong>How others may use your art is up to you.</strong> Every artwork
            carries the license you choose when posting (see{' '}
            <Link href="/about?tab=licenses">Licenses</Link>). Other users must respect
            that license. If you choose a permissive license, that choice applies to copies
            people lawfully made while it was in effect.
          </p>

          <p>
            Only post content you have the right to post. Don&apos;t upload other
            people&apos;s work without permission.
          </p>

          <h2>Community rules and zero tolerance</h2>

          <p>
            The <Link href="/about?tab=rules">Community Rules</Link> are part of these
            terms. In short: no harassment, no hate, no sexual or explicit content outside
            the monitored-hashtag system, no gratuitous violence, no spam, and{' '}
            <strong>
              absolutely no illegal content — we have zero tolerance for objectionable
              content and abusive users
            </strong>
            . Content that sexualizes minors leads to an immediate permanent ban and a
            report to the authorities.
          </p>

          <p>
            You can report any post, comment, or user (no account needed), and you can
            block users you don&apos;t want to interact with. Reports are reviewed within
            24 hours.
          </p>

          <h2>Moderation and enforcement</h2>

          <p>
            Our moderators may hide or remove content, add required hashtags, issue
            violations, suspend accounts, or ban users, following the ladder described on
            the <Link href="/about?tab=moderation">Moderation page</Link>. If you think a
            moderation action was unfair, you can appeal — the Moderation page explains
            how. We may also remove content or accounts when the law requires it.
          </p>

          <h2>Player devices and the API</h2>

          <p>
            Physical players and the public API are provided for personal, non-abusive
            use. Don&apos;t use them to overload the service, scrape content in bulk
            against artists&apos; licenses, or circumvent moderation controls.
          </p>

          <h2>The service is provided as-is</h2>

          <p>
            Makapix Club is a community project, not a commercial product with an SLA. We
            work hard to keep it running and to keep backups (see the{' '}
            <Link href="/privacy">Privacy Policy</Link> for our honest description of
            them), but we can&apos;t promise uninterrupted service or that data will never
            be lost. To the maximum extent the law allows, Makapix Club and its operators
            are not liable for indirect or consequential damages from using the service.
            Nothing in these terms limits liability where the law doesn&apos;t allow it to
            be limited.
          </p>

          <h2>Ending the agreement</h2>

          <p>
            You can stop using Makapix Club and delete your account at any time. We can
            suspend or terminate accounts that break these terms or the Community Rules,
            per the enforcement ladder above. Sections about content licensing, disclaimers,
            and liability survive termination.
          </p>

          <h2>Changes to these terms</h2>

          <p>
            If we change these terms, we will update the effective date above. For
            significant changes we will make a reasonable effort to notify you (for
            example, a site announcement). Continuing to use Makapix Club after a change
            means you accept the updated terms.
          </p>

          <h2>Contact</h2>

          <p>
            <a href="mailto:acme@makapix.club">acme@makapix.club</a> — for questions about
            these terms, moderation, or anything else.
          </p>

          <p>
            See also the <Link href="/privacy">Privacy Policy</Link>, the{' '}
            <Link href="/about?tab=rules">Community Rules</Link>, and the{' '}
            <Link href="/about?tab=moderation">Moderation page</Link>.
          </p>
        </article>
      </div>

      <style jsx>{`
        .terms-container {
          max-width: 720px;
          margin: 0 auto;
          padding: 32px 24px 64px;
        }

        .policy-article {
          color: var(--text-secondary);
          line-height: 1.7;
        }

        .policy-article h1 {
          font-size: 1.75rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0 0 8px 0;
          text-align: center;
        }

        .effective-date {
          text-align: center;
          font-size: 0.85rem;
          color: var(--text-secondary);
          margin: 0 0 24px 0;
        }

        .policy-article h2 {
          font-size: 1.15rem;
          font-weight: 600;
          color: var(--text-primary);
          margin: 32px 0 12px 0;
        }

        .policy-article p {
          margin: 0 0 16px 0;
          font-size: 0.95rem;
        }

        .policy-article .lead {
          font-size: 1.05rem;
          color: var(--text-primary);
          margin-bottom: 24px;
        }

        .policy-article strong {
          color: var(--text-primary);
        }

        .policy-article a,
        .policy-article :global(a) {
          color: var(--accent-cyan);
          text-decoration: none;
        }

        .policy-article a:hover,
        .policy-article :global(a:hover) {
          text-decoration: underline;
        }

        @media (max-width: 480px) {
          .terms-container {
            padding: 24px 16px 48px;
          }

          .policy-article h1 {
            font-size: 1.5rem;
          }

          .policy-article h2 {
            font-size: 1.1rem;
          }
        }
      `}</style>
    </Layout>
  );
}
