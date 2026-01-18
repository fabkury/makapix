/**
 * GiftButton component - links to the gift page.
 * Uses 🎁 emoji, styled similarly to FollowButton but smaller.
 */

import Link from 'next/link';

interface GiftButtonProps {
  userSqid: string;
}

export default function GiftButton({ userSqid }: GiftButtonProps) {
  return (
    <Link href={`/u/${userSqid}/gift`} className="gift-button" aria-label="Send gift" title="Send gift">
      <span className="gift-icon">🎁</span>

      <style jsx>{`
        .gift-button {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 6px 24px;
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: 8px;
          background: transparent;
          cursor: pointer;
          transition: all 0.2s ease;
          font-size: 1.25rem;
          text-decoration: none;
        }
        .gift-button:hover {
          background: rgba(255, 255, 255, 0.1);
          border-color: var(--accent-cyan);
        }
        .gift-icon {
          filter: drop-shadow(0 0 6px rgba(0, 245, 255, 0.5));
        }
      `}</style>
    </Link>
  );
}
