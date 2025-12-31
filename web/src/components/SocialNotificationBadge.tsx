/**
 * Social Notification Badge Component.
 *
 * Displays a notification bell icon with an unread count badge.
 * Links to the notifications page.
 */

import Link from "next/link";
import { useRouter } from "next/router";
import { useSocialNotificationsSafe } from "../contexts/SocialNotificationsContext";

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
              ? "/button/btn001-social-notification.gif"
              : "/button/btn001-social-notification-disabled.gif"}
            alt=""
            width={32}
            height={32}
            className="pixel-art"
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
