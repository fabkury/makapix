import { useState } from 'react';
import Notice from './kit/Notice';
import { IconShield, IconClock, IconCheckCircle } from './kit/icons';

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
 *   (capabilities.can_post_public === false), before they submit. Renders as
 *   a single line with an expandable explanation (docs/newpost-ui-appraisal/
 *   F12) so a new member's first impression isn't a caution banner.
 * - `pending`: shown after a successful upload that awaits moderator review.
 * - `approved`: shown after a successful upload that was auto-approved
 *   (the user has Trust).
 *
 * Review is neutral process information, not a problem, so these render in
 * the neutral `info` tone (F12); only `approved` uses the success tint.
 *
 * Semantics (see api/app/utils/visibility.py): a pending post is already
 * visible on the author's profile and reachable by anyone via its direct
 * link; moderator approval only gates discovery surfaces (Recent, search,
 * hashtags).
 */
export default function PostReviewNotice({ variant, sharePath }: PostReviewNoticeProps) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);

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

  if (variant === 'pre-upload') {
    return (
      <Notice tone="info" icon={<IconShield size={20} />}>
        <p>
          Posts from new members are reviewed before public release.{' '}
          <button type="button" className="learn-more" onClick={() => setExpanded(!expanded)}>
            {expanded ? 'Hide details' : 'How it works'}
          </button>
        </p>
        {expanded && (
          <p className="details">
            A moderator will review your post before it&apos;s released to the whole
            community (Recent feed, search, and hashtags). Meanwhile, it will already
            be visible on your profile page, and you can share its link with anyone
            on the internet.
          </p>
        )}
        <style jsx>{`
          .learn-more {
            background: none;
            border: none;
            padding: 0;
            font-size: inherit;
            color: var(--accent-cyan);
            cursor: pointer;
          }
          .learn-more:hover {
            text-decoration: underline;
          }
          .details {
            margin-top: 8px !important;
            font-size: 0.85rem;
          }
        `}</style>
      </Notice>
    );
  }

  if (variant === 'pending') {
    return (
      <Notice tone="info" icon={<IconClock size={20} />} title="Awaiting moderator review">
        <p>
          Your post will be reviewed by a moderator before it&apos;s publicly released
          to the community. Meanwhile, it&apos;s already visible on your profile page,
          and you can share it with anyone on the internet using its direct link.
        </p>
        {sharePath && (
          <>
            <button type="button" className="copy-link-btn" onClick={copyLink}>
              {copied ? 'Link copied' : 'Copy link'}
            </button>
            <style jsx>{`
              .copy-link-btn {
                margin-top: 10px;
                padding: 6px 14px;
                border-radius: 8px;
                border: 1px solid var(--bg-tertiary);
                background: transparent;
                color: var(--text-primary);
                font-size: 0.85rem;
                cursor: pointer;
                transition: border-color var(--transition-fast);
              }
              .copy-link-btn:hover {
                border-color: var(--accent-cyan);
              }
            `}</style>
          </>
        )}
      </Notice>
    );
  }

  return (
    <Notice tone="success" icon={<IconCheckCircle size={20} />} title="Your artwork is live">
      <p>
        You&apos;re a trusted member, so your artwork was automatically approved for
        public release. It&apos;s already out for the whole community to see.
      </p>
    </Notice>
  );
}
