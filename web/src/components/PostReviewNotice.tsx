import { useState } from 'react';

type Variant = 'pre-upload' | 'pending' | 'approved';

interface PostReviewNoticeProps {
  variant: Variant;
  /** Site-relative permalink (e.g. `/p/abc123`) — enables the Copy link button. */
  sharePath?: string;
}

/**
 * Explains the moderation-review status of a post to its author.
 *
 * - `pre-upload`: shown on upload forms to users WITHOUT Trust
 *   (capabilities.can_post_public === false), before they submit.
 * - `pending`: shown after a successful upload that awaits moderator review.
 * - `approved`: shown after a successful upload that was auto-approved
 *   (the user has Trust).
 *
 * Semantics (see api/app/utils/visibility.py): a pending post is already
 * visible on the author's profile and reachable by anyone via its direct
 * link; moderator approval only gates discovery surfaces (Recent, search,
 * hashtags).
 */
export default function PostReviewNotice({ variant, sharePath }: PostReviewNoticeProps) {
  const [copied, setCopied] = useState(false);

  const copyLink = async () => {
    if (!sharePath) return;
    try {
      await navigator.clipboard.writeText(`${window.location.origin}${sharePath}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard unavailable (e.g. insecure context) — ignore silently
    }
  };

  return (
    <div className={`review-notice ${variant === 'approved' ? 'approved' : 'pending'}`}>
      {variant === 'pre-upload' && (
        <>
          <span className="notice-icon">🛡️</span>
          <div className="notice-body">
            <p className="notice-title">Your post will be reviewed before public release</p>
            <p className="notice-text">
              A moderator will review your post before it&apos;s released to the whole
              community (Recent feed, search, and hashtags). Meanwhile, it will already
              be visible on your profile page, and you can share its link with anyone
              on the internet.
            </p>
          </div>
        </>
      )}
      {variant === 'pending' && (
        <>
          <span className="notice-icon">⏳</span>
          <div className="notice-body">
            <p className="notice-title">Awaiting moderator review</p>
            <p className="notice-text">
              Your post will be reviewed by a moderator before it&apos;s publicly released
              to the community. Meanwhile, it&apos;s already visible on your profile page,
              and you can share it with anyone on the internet using its direct link.
            </p>
            {sharePath && (
              <button type="button" className="copy-link-btn" onClick={copyLink}>
                {copied ? '✓ Link copied!' : '🔗 Copy link'}
              </button>
            )}
          </div>
        </>
      )}
      {variant === 'approved' && (
        <>
          <span className="notice-icon">✅</span>
          <div className="notice-body">
            <p className="notice-title">Auto-approved — your artwork is live</p>
            <p className="notice-text">
              You&apos;re a trusted member, so your artwork was automatically approved for
              public release. It&apos;s already out for the whole community to see.
            </p>
          </div>
        </>
      )}
      <style jsx>{`
        .review-notice {
          display: flex;
          align-items: flex-start;
          padding: 14px 16px;
          border-radius: 12px;
          text-align: left;
        }
        .review-notice.pending {
          background: rgba(255, 200, 100, 0.1);
          border: 1px solid rgba(255, 200, 100, 0.3);
        }
        .review-notice.approved {
          background: rgba(100, 255, 160, 0.08);
          border: 1px solid rgba(100, 255, 160, 0.25);
        }
        .notice-icon {
          font-size: 1.3rem;
          line-height: 1.4;
          margin-right: 12px;
        }
        .notice-body {
          flex: 1;
          min-width: 0;
        }
        .notice-title {
          font-weight: 600;
          font-size: 0.95rem;
          color: var(--text-primary);
          margin: 0 0 4px;
        }
        .notice-text {
          font-size: 0.85rem;
          color: var(--text-secondary);
          margin: 0;
          line-height: 1.5;
        }
        .copy-link-btn {
          margin-top: 10px;
          padding: 6px 14px;
          border-radius: 8px;
          border: 1px solid rgba(255, 200, 100, 0.4);
          background: transparent;
          color: var(--text-primary);
          font-size: 0.85rem;
          cursor: pointer;
          transition: all var(--transition-fast);
        }
        .copy-link-btn:hover {
          border-color: var(--accent-cyan);
          color: var(--accent-cyan);
        }
      `}</style>
    </div>
  );
}
