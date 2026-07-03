import Link from 'next/link';
import Layout from '../components/Layout';

export default function DeleteAccountPage() {
  return (
    <Layout
      title="Delete Your Account"
      description="How to delete your Makapix Club account and associated data"
    >
      <div className="delete-container">
        <article className="policy-article">
          <h1>Delete Your Account</h1>

          <p className="lead">
            This page explains how to permanently delete your Makapix Club account and the
            data associated with it. It applies to accounts used on the makapix.club
            website, in the Makapix mobile app, and with physical player devices — they all
            share the same account.
          </p>

          <h2>Delete it yourself (fastest)</h2>

          <p>
            You can delete your account directly, whether you signed up on the website or
            in the app:
          </p>

          <ol>
            <li>
              Log in at <a href="https://makapix.club">makapix.club</a> (or in the Makapix
              app).
            </li>
            <li>Open your own profile page.</li>
            <li>
              Choose <strong>Edit profile</strong>, then scroll down to the{' '}
              <strong>Danger Zone</strong>.
            </li>
            <li>
              Press <strong>Delete this account</strong> and follow the confirmation steps.
            </li>
          </ol>

          <p>Deletion takes effect immediately and cannot be undone.</p>

          <h2>Can&apos;t log in? Request deletion by email</h2>

          <p>
            If you no longer have access to your account (lost password, uninstalled the
            app, no longer control the sign-in method), email{' '}
            <a href="mailto:acme@makapix.club?subject=Account%20deletion%20request">
              acme@makapix.club
            </a>{' '}
            with the subject &quot;Account deletion request&quot;. Include your Makapix
            handle, and send the email from the address registered on the account if you
            can — otherwise tell us enough to verify the account is yours. We will confirm
            and delete the account, normally within 7 days.
          </p>

          <h2>What gets deleted</h2>

          <p>
            Account deletion removes your artwork and its files (including layers files),
            comments, reactions, playlists, follows, notifications, registered player
            devices, sign-in identities (including GitHub links), avatar, email address,
            and the account itself.
          </p>

          <p>
            Two things are retained, as described in our{' '}
            <Link href="/privacy">Privacy Policy</Link>: comments that have replies from
            other people are anonymized to &quot;[deleted comment]&quot; rather than
            removed, so conversations still make sense; and anonymous aggregate statistics
            (daily view counts and similar), which are not tied to your account.
          </p>

          <h2>Deleting some data without closing your account</h2>

          <p>
            You can delete individual artworks and comments at any time from the website or
            the app, and remove registered player devices from your profile. For anything
            else, email <a href="mailto:acme@makapix.club">acme@makapix.club</a> and we
            will help.
          </p>
        </article>
      </div>

      <style jsx>{`
        .delete-container {
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
          margin: 0 0 24px 0;
          text-align: center;
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

        .policy-article ol {
          margin: 0 0 16px 0;
          padding-left: 24px;
          font-size: 0.95rem;
        }

        .policy-article li {
          margin-bottom: 8px;
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
          .delete-container {
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
