/**
 * Gift page placeholder - future premium feature for gifting tokens/items to users.
 */

import { useRouter } from 'next/router';
import Link from 'next/link';
import Layout from '../../../components/Layout';

export default function GiftPage() {
  const router = useRouter();
  const { sqid } = router.query;

  return (
    <Layout title="Send Gift" description="Send a gift to this user">
      <div className="gift-container">
        <div className="gift-content">
          <div className="gift-icon">🎁</div>
          <h1>Gifting Coming Soon</h1>
          <p className="description">
            The ability to send gifts to your favorite artists is coming in a future update.
            Stay tuned for this exciting premium feature!
          </p>
          <Link href={`/u/${sqid}`} className="back-link">
            ← Back to Profile
          </Link>
        </div>
      </div>

      <style jsx>{`
        .gift-container {
          min-height: calc(100vh - var(--header-offset));
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 24px;
        }

        .gift-content {
          text-align: center;
          max-width: 400px;
        }

        .gift-icon {
          font-size: 5rem;
          margin-bottom: 24px;
          filter: drop-shadow(0 4px 20px rgba(255, 110, 180, 0.4));
        }

        h1 {
          font-size: 1.75rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0 0 16px 0;
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        .description {
          color: var(--text-secondary);
          line-height: 1.6;
          margin: 0 0 32px 0;
        }

        :global(.back-link) {
          display: inline-block;
          color: var(--accent-cyan);
          text-decoration: none;
          font-weight: 500;
          padding: 12px 24px;
          border: 1px solid var(--accent-cyan);
          border-radius: 8px;
          transition: all var(--transition-fast);
        }

        :global(.back-link:hover) {
          background: var(--accent-cyan);
          color: var(--bg-primary);
        }
      `}</style>
    </Layout>
  );
}
