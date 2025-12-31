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
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="currentColor"
            aria-hidden="true"
          >
            <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2zm-2 1H8v-6c0-2.48 1.51-4.5 4-4.5s4 2.02 4 4.5v6z" />
          </svg>
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
          border-radius: 50%;
          background: var(--bg-tertiary);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--text-secondary);
          transition: all var(--transition-fast);
        }

        .notification-link:hover .notification-icon {
          background: var(--accent-cyan);
          color: var(--bg-primary);
          box-shadow: var(--glow-cyan);
        }

        .notification-link.active .notification-icon {
          background: rgba(255, 255, 255, 0.15);
          color: var(--accent-cyan);
          box-shadow: 0 0 16px rgba(0, 212, 255, 0.4),
            inset 0 0 0 2px rgba(0, 212, 255, 0.3);
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
