/**
 * GiftButton component - navigates to the gift page.
 * Uses 🎁 emoji, styled similarly to FollowButton but smaller.
 */

import { useRouter } from 'next/router';

interface GiftButtonProps {
  userSqid: string;
}

export default function GiftButton({ userSqid }: GiftButtonProps) {
  const router = useRouter();

  const handleClick = () => {
    router.push(`/u/${userSqid}/gift`);
  };

  return (
    <button className="gift-button" onClick={handleClick} aria-label="Send gift" title="Send gift">
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
        }
        .gift-button:hover {
          background: rgba(255, 255, 255, 0.1);
          border-color: var(--accent-cyan);
        }
        .gift-icon {
          filter: drop-shadow(0 0 6px rgba(0, 245, 255, 0.5));
        }
      `}</style>
    </button>
  );
}
