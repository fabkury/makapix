import Link from 'next/link';
import Layout from '../components/Layout';

export default function PrivacyPage() {
  return (
    <Layout title="Privacy Policy" description="Privacy Policy for Makapix Club - what we collect, why, and your choices">
      <div className="privacy-container">
        <article className="policy-article">
          <h1>Privacy Policy</h1>

          <p className="effective-date">Effective date: July 3, 2026</p>

          <p className="lead">
            Makapix Club is a small, community-run social network for pixel artists and DIY
            makers. We collect as little personal data as we can, we run our own analytics
            instead of using third-party trackers, and we never sell your data or show ads.
            This policy explains, in plain language, what we collect and why.
          </p>

          <p>
            This policy covers everything that makes up Makapix Club: the website at{' '}
            <a href="https://makapix.club">makapix.club</a>, the Makapix mobile app, and
            physical player devices (LED matrices and pixel displays) that connect to our
            service. If you have any questions, email us at{' '}
            <a href="mailto:acme@makapix.club">acme@makapix.club</a>.
          </p>

          <h2>What we collect</h2>

          <p>
            <strong>Account information.</strong> When you sign up we collect your email
            address, a handle (username), and a password. Passwords are stored only as
            secure hashes — we never store or see your actual password. You can optionally
            add profile details such as a bio, tagline, website link, and avatar image.
          </p>

          <p>
            <strong>Sign-in with GitHub.</strong> If you sign in with GitHub, we receive
            your GitHub user ID, username, avatar, and email address from GitHub. We use
            these only to create and link your Makapix account. We never post to GitHub on
            your behalf.
          </p>

          <p>
            <strong>Content you create.</strong> Artwork you post (including optional layers
            files), comments, reactions, playlists, follows, and reports you submit are
            stored on our servers so we can show them to you and, depending on your
            settings, to other users.
          </p>

          <p>
            <strong>Usage data.</strong> We run our own, first-party analytics — no Google
            Analytics, no advertising trackers. When you view pages or artwork, we record
            the page or artwork viewed, an anonymized (one-way hashed) version of your IP
            address and browser signature, your device category (desktop, mobile, tablet, or
            player), your country (derived from your IP address on our own server), and the
            referring website domain. Raw usage events are kept for about 7 days and then
            reduced to daily aggregate statistics (counts and totals) that contain no
            personal identifiers.
          </p>

          <p>
            <strong>Technical necessities.</strong> Like nearly every website, our servers
            briefly process your IP address to deliver pages and to enforce rate limits that
            protect the service from abuse. These transient records expire automatically and
            are not added to our database.
          </p>

          <p>
            <strong>Physical players.</strong> If you register a player device, we store its
            registration details (name, device model, firmware version), its connection
            status, the security certificate that identifies it, and a log of commands sent
            to it (such as which artwork to display).
          </p>

          <p>
            <strong>Mobile app.</strong> The Makapix app uses the same account and content
            systems described above. If you enable push notifications, we store a push
            notification token for your device (delivered through Google Firebase Cloud
            Messaging on Android or Apple Push Notification service on iOS) so we can send
            you notifications you have asked for. You can disable push notifications at any
            time in your device settings, which stops their use.
          </p>

          <h2>What we do with it</h2>

          <p>We use the data above to:</p>

          <p>
            run the service (show artwork, deliver notifications, drive player devices);
            secure it (verify emails, reset passwords, limit abuse); provide artists with
            private statistics about how their work performs (these statistics are shown as
            aggregate numbers — viewers are not individually identified to artists); and
            moderate the community (handle reports and enforce the rules).
          </p>

          <p>
            We do <strong>not</strong> sell or rent your personal data, use it for
            advertising, or share it with data brokers. There are no ads on Makapix Club.
          </p>

          <h2>Cookies and local storage</h2>

          <p>
            We use browser storage only to keep you signed in: a short-lived session token
            in your browser&apos;s local storage and a longer-lived refresh token in a
            secure, HTTP-only cookie. We also store small preferences (like your handle and
            avatar) locally so pages load faster. We do not use advertising or third-party
            tracking cookies.
          </p>

          <h2>Who we share data with</h2>

          <p>
            We use a small number of service providers to run Makapix Club, and they only
            receive what is needed for their job:
          </p>

          <p>
            <strong>Resend</strong> delivers our transactional emails (verification codes,
            password resets, download notifications) and therefore processes your email
            address. <strong>GitHub</strong> is involved only if you choose to sign in with
            GitHub. <strong>Google Firebase / Apple</strong> deliver push notifications only
            if you enable them in the mobile app. Our servers are hosted on infrastructure
            we rent from a hosting provider, where all data described in this policy is
            stored.
          </p>

          <p>
            Beyond these providers, we disclose personal data only if required by law or to
            protect the safety and integrity of the service.
          </p>

          <h2>How long we keep data</h2>

          <p>
            Your account information and content are kept until you delete them. Raw usage
            events are deleted after about 7 days, leaving only anonymous daily aggregates.
            Transactional email records and security tokens expire on their own schedules.
            Routine copies of data made for operational reasons (such as server maintenance)
            may persist briefly after deletion before being cycled out.
          </p>

          <h2>Deleting your data</h2>

          <p>
            You can delete individual artworks and comments at any time. You can also delete
            your entire account from your profile page. Account deletion removes your
            artwork and its files (including layers files), your reactions, playlists,
            follows, notifications, sign-in identities, and avatar, and then the account
            itself. One exception: if a comment of yours has replies from other people, the
            comment&apos;s text is replaced with &quot;[deleted comment]&quot; and unlinked
            from you, so the conversation below it still makes sense. Anonymous aggregate
            statistics (daily view counts and similar) are not tied to your account and are
            retained.
          </p>

          <h2>Your rights</h2>

          <p>
            You can view and edit your profile information at any time from your profile
            page. If you want a copy of your data, want something corrected, or want help
            with deletion, email us at{' '}
            <a href="mailto:acme@makapix.club">acme@makapix.club</a> and we will help.
            Depending on where you live, local law may give you specific rights over your
            personal data — we honor reasonable requests regardless of where you are.
          </p>

          <h2>Children</h2>

          <p>
            Makapix Club is not directed at children under 13, and we do not knowingly
            collect personal data from children under 13. If you believe a child under 13
            has created an account, contact us at{' '}
            <a href="mailto:acme@makapix.club">acme@makapix.club</a> and we will remove it.
          </p>

          <h2>Security</h2>

          <p>
            All traffic to makapix.club is encrypted with HTTPS. Passwords and security
            tokens are stored only as cryptographic hashes, and player devices authenticate
            with individual certificates. No online service can promise perfect security,
            but we keep the attack surface small and take the safety of your data seriously.
          </p>

          <h2>Changes to this policy</h2>

          <p>
            If we change this policy, we will post the new version at this address and
            update the effective date above. For significant changes we will make a
            reasonable effort to notify you, for example with a notice on the site.
          </p>

          <h2>Contact</h2>

          <p>
            Makapix Club — <a href="mailto:acme@makapix.club">acme@makapix.club</a>
          </p>

          <p>
            See also our <Link href="/about?tab=rules">community rules</Link> and{' '}
            <Link href="/about">about page</Link>.
          </p>
        </article>
      </div>

      <style jsx>{`
        .privacy-container {
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
          .privacy-container {
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
