/**
 * Social Notification Badge Component.
 *
 * Displays a notification bell icon with an unread count badge.
 * Links to the notifications page.
 */

import Link from "next/link";
import { useRouter } from "next/router";
import { useSocialNotificationsSafe } from "../contexts/SocialNotificationsContext";

const SRCSET_ENABLED = "/button/social-notification/btn001-social-notification-enabled-32px-1x.png 1x, /button/social-notification/btn001-social-notification-enabled-40px-1_25x.png 1.25x, /button/social-notification/btn001-social-notification-enabled-48px-1_5x.png 1.5x, /button/social-notification/btn001-social-notification-enabled-56px-1_75x.png 1.75x, /button/social-notification/btn001-social-notification-enabled-64px-2x.png 2x, /button/social-notification/btn001-social-notification-enabled-72px-2_25x.png 2.25x, /button/social-notification/btn001-social-notification-enabled-80px-2_5x.png 2.5x, /button/social-notification/btn001-social-notification-enabled-88px-2_75x.png 2.75x, /button/social-notification/btn001-social-notification-enabled-96px-3x.png 3x, /button/social-notification/btn001-social-notification-enabled-104px-3_25x.png 3.25x, /button/social-notification/btn001-social-notification-enabled-112px-3_5x.png 3.5x, /button/social-notification/btn001-social-notification-enabled-128px-4x.png 4x";

const SRCSET_DISABLED = "/button/social-notification/btn001-social-notification-disabled-32px-1x.png 1x, /button/social-notification/btn001-social-notification-disabled-40px-1_25x.png 1.25x, /button/social-notification/btn001-social-notification-disabled-48px-1_5x.png 1.5x, /button/social-notification/btn001-social-notification-disabled-56px-1_75x.png 1.75x, /button/social-notification/btn001-social-notification-disabled-64px-2x.png 2x, /button/social-notification/btn001-social-notification-disabled-72px-2_25x.png 2.25x, /button/social-notification/btn001-social-notification-disabled-80px-2_5x.png 2.5x, /button/social-notification/btn001-social-notification-disabled-88px-2_75x.png 2.75x, /button/social-notification/btn001-social-notification-disabled-96px-3x.png 3x, /button/social-notification/btn001-social-notification-disabled-104px-3_25x.png 3.25x, /button/social-notification/btn001-social-notification-disabled-112px-3_5x.png 3.5x, /button/social-notification/btn001-social-notification-disabled-128px-4x.png 4x";

export default function SocialNotificationBadge() {
  const router = useRouter();
  const { unreadCount } = useSocialNotificationsSafe();
  const isActive = router.pathname === "/notifications";

  // Format count for display (e.g., 99+ for large numbers)
  const displayCount = unreadCount > 99 ? "99+" : unreadCount;

  return (
    <>
      <Link
        href="/notifications"
        className={`notification-link ${isActive ? "active" : ""}`}
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ""}`}
        suppressHydrationWarning
      >
        <div className="notification-icon">
          <img
            src={unreadCount > 0
              ? "/button/social-notification/btn001-social-notification-enabled-32px-1x.png"
              : "/button/social-notification/btn001-social-notification-disabled-32px-1x.png"}
            srcSet={unreadCount > 0 ? SRCSET_ENABLED : SRCSET_DISABLED}
            alt=""
            width={32}
            height={32}
            className="notification-img"
            aria-hidden="true"
          />
          {unreadCount > 0 && (
            <span className="badge" aria-hidden="true">
              {displayCount}
            </span>
          )}
        </div>
      </Link>

      <style jsx>{`
        .notification-link {
          display: flex;
          align-items: center;
          text-decoration: none;
        }

        .notification-icon {
          position: relative;
          width: 32px;
          height: 32px;
        }

        .notification-icon img {
          display: block;
          transition: filter var(--transition-fast);
        }

        .notification-link:hover .notification-icon img {
          filter: brightness(1.2);
        }

        .notification-link.active .notification-icon img {
          filter: brightness(1.3) drop-shadow(0 0 4px rgba(0, 212, 255, 0.6));
        }

        .badge {
          position: absolute;
          top: -4px;
          right: -4px;
          min-width: 18px;
          height: 18px;
          padding: 0 5px;
          border-radius: 9px;
          background: var(--accent-pink);
          color: white;
          font-size: 11px;
          font-weight: 700;
          line-height: 18px;
          text-align: center;
          box-shadow: 0 0 8px rgba(255, 110, 180, 0.6);
          animation: badge-pulse 2s ease-in-out infinite;
        }

        @keyframes badge-pulse {
          0%,
          100% {
            transform: scale(1);
          }
          50% {
            transform: scale(1.1);
          }
        }
      `}</style>
    </>
  );
}
