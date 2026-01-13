/**
 * FollowButton component - displays follow/unfollow button.
 * Uses 👣 emoji with glow effect.
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
      <span className="follow-icon">👣</span>

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
          font-size: 1.25rem;
        }
        .follow-button:hover:not(:disabled) {
          background: rgba(255, 255, 255, 0.1);
        }
        .follow-button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .follow-icon {
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
