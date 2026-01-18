/**
 * FollowButton component - displays follow/unfollow button.
 * Uses pixel art icon with glow effect.
 */

import { useState } from 'react';
import { authenticatedFetch } from '../../lib/api';

interface FollowButtonProps {
  userSqid: string;
  initialFollowing: boolean;
  onFollowChange?: (following: boolean, newFollowerCount: number) => void;
  disabled?: boolean;
}

export default function FollowButton({
  userSqid,
  initialFollowing,
  onFollowChange,
  disabled = false,
}: FollowButtonProps) {
  const [isFollowing, setIsFollowing] = useState(initialFollowing);
  const [isLoading, setIsLoading] = useState(false);

  const handleClick = async () => {
    if (isLoading || disabled) return;

    setIsLoading(true);
    const API_BASE_URL = typeof window !== 'undefined'
      ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
      : '';

    try {
      const method = isFollowing ? 'DELETE' : 'POST';
      const response = await authenticatedFetch(
        `${API_BASE_URL}/api/user/u/${userSqid}/follow`,
        { method }
      );

      if (response.ok) {
        const data = await response.json();
        setIsFollowing(data.following);
        onFollowChange?.(data.following, data.follower_count);
      }
    } catch (error) {
      console.error('Follow action failed:', error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <button
      className={`follow-button ${isFollowing ? 'following' : ''}`}
      onClick={handleClick}
      disabled={isLoading || disabled}
      aria-label={isFollowing ? 'Unfollow' : 'Follow'}
      title={isFollowing ? 'Unfollow' : 'Follow'}
    >
      <img
        src="/button/follow-user/btn007-follow-user-32px-1x.png"
        srcSet="/button/follow-user/btn007-follow-user-32px-1x.png 1x, /button/follow-user/btn007-follow-user-40px-1_25x.png 1.25x, /button/follow-user/btn007-follow-user-48px-1_5x.png 1.5x, /button/follow-user/btn007-follow-user-56px-1_75x.png 1.75x, /button/follow-user/btn007-follow-user-64px-2x.png 2x, /button/follow-user/btn007-follow-user-72px-2_25x.png 2.25x, /button/follow-user/btn007-follow-user-80px-2_5x.png 2.5x, /button/follow-user/btn007-follow-user-88px-2_75x.png 2.75x, /button/follow-user/btn007-follow-user-96px-3x.png 3x, /button/follow-user/btn007-follow-user-104px-3_25x.png 3.25x, /button/follow-user/btn007-follow-user-112px-3_5x.png 3.5x, /button/follow-user/btn007-follow-user-128px-4x.png 4x"
        alt=""
        width={32}
        height={32}
        className="follow-icon"
        aria-hidden="true"
      />

      <style jsx>{`
        .follow-button {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 10px 24px;
          border: 1px solid rgba(255, 255, 255, 0.2);
          border-radius: 8px;
          background: transparent;
          cursor: pointer;
          transition: all 0.2s ease;
        }
        .follow-button:hover:not(:disabled) {
          background: rgba(255, 255, 255, 0.1);
        }
        .follow-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .follow-button :global(.follow-icon) {
          display: block;
          width: 32px;
          height: 32px;
          filter: ${isFollowing
            ? 'drop-shadow(0 0 8px rgba(0, 245, 255, 0.8))'
            : 'none'};
          transition: filter 0.2s ease;
        }
        .follow-button.following {
          border-color: var(--accent-cyan);
        }
      `}</style>
    </button>
  );
}
