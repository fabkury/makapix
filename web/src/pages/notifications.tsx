import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/router";
import Link from "next/link";
import Layout from "../components/Layout";
import {
  useSocialNotificationsContext,
  SocialNotificationFull,
} from "../contexts/SocialNotificationsContext";

/**
 * Notifications Page.
 *
 * Displays a list of social notifications (reactions and comments on user's artwork).
 * Automatically marks all notifications as read when opened.
 */
export default function NotificationsPage() {
  const router = useRouter();
  const [userId, setUserId] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const hasMarkedAsReadRef = useRef(false);

  // Check authentication on mount
  useEffect(() => {
    const token = localStorage.getItem("access_token");
    const storedUserId = localStorage.getItem("user_id");

    if (!token || !storedUserId) {
      router.push("/auth?redirect=/notifications");
      return;
    }

    setUserId(storedUserId);
  }, [router]);

  const {
    notifications,
    loading,
    fetchNotifications,
    markAllAsRead,
  } = useSocialNotificationsContext();

  // Fetch initial notifications and mark all as read
  useEffect(() => {
    if (userId && !hasMarkedAsReadRef.current) {
      hasMarkedAsReadRef.current = true;
      
      // Fetch notifications first, then mark all as read
      fetchNotifications().then(({ nextCursor }) => {
        setNextCursor(nextCursor);
        // Mark all as read after fetching
        markAllAsRead();
      });
    }
  }, [userId, fetchNotifications, markAllAsRead]);

  // Load more notifications
  const loadMore = useCallback(async () => {
    if (!nextCursor || isLoadingMore) return;

    setIsLoadingMore(true);
    const result = await fetchNotifications(nextCursor);
    setNextCursor(result.nextCursor);
    setIsLoadingMore(false);
  }, [nextCursor, isLoadingMore, fetchNotifications]);

  // Format relative time
  const formatRelativeTime = (dateStr: string): string => {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return "just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
  };

  // Handle notification click - no need to mark individual as read since all are marked on page load
  const handleNotificationClick = (_notification: SocialNotificationFull) => {
    // All notifications are already marked as read when the page loads
  };

  // Check if notification is a system notification (no artwork)
  const isSystemNotification = (notification: SocialNotificationFull): boolean => {
    return notification.notification_type === "moderator_granted" ||
           notification.notification_type === "moderator_revoked" ||
           notification.notification_type === "follow" ||
           notification.notification_type === "reputation_change";
  };

  // Render notification message
  const renderNotificationMessage = (notification: SocialNotificationFull): string => {
    const actor = notification.actor_handle || "Someone";
    const title = notification.content_title || "your artwork";

    if (notification.notification_type === "reaction") {
      return `${actor} reacted ${notification.emoji || ""} to "${title}"`;
    } else if (notification.notification_type === "comment") {
      return `${actor} commented on "${title}"`;
    } else if (notification.notification_type === "comment_reply") {
      return `${actor} replied to your comment on "${title}"`;
    } else if (notification.notification_type === "moderator_granted") {
      return `${actor} granted you moderator status`;
    } else if (notification.notification_type === "moderator_revoked") {
      return `${actor} revoked your moderator status`;
    } else if (notification.notification_type === "follow") {
      return `${actor} started following you`;
    } else if (notification.notification_type === "reputation_change") {
      return `${actor} adjusted your reputation (${notification.content_title || ""})`;
    }
    return `${actor} interacted with "${title}"`;
  };

  if (!userId) {
    return (
      <Layout title="Notifications">
        <div className="page-container">
          <div className="loading">Loading...</div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout title="Notifications">
      <div className="page-container">
        <header className="page-header">
          <h1>Notifications</h1>
        </header>

        {loading && notifications.length === 0 ? (
          <div className="loading">Loading notifications...</div>
        ) : notifications.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z" />
              </svg>
            </div>
            <p>No notifications yet</p>
            <span className="empty-hint">
              When someone reacts to or comments on your artwork, follows you,
              or when you receive system notifications, you&apos;ll see them here.
            </span>
          </div>
        ) : (
          <>
            <ul className="notification-list">
              {notifications.map((notification) => {
                const isSystem = isSystemNotification(notification);
                const notificationContent = (
                  <>
                    <div className="notification-icon">
                      {isSystem && notification.actor_avatar_url ? (
                        <img
                          src={notification.actor_avatar_url}
                          alt=""
                          width={32}
                          height={32}
                          className="actor-avatar"
                        />
                      ) : isSystem ? (
                        <svg
                          width="20"
                          height="20"
                          viewBox="0 0 24 24"
                          fill="currentColor"
                        >
                          <path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4z" />
                        </svg>
                      ) : notification.notification_type === "reaction" ? (
                        <span className="emoji">{notification.emoji || "..."}</span>
                      ) : (
                        <svg
                          width="20"
                          height="20"
                          viewBox="0 0 24 24"
                          fill="currentColor"
                        >
                          <path d="M21.99 4c0-1.1-.89-2-1.99-2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14l4 4-.01-18z" />
                        </svg>
                      )}
                    </div>
                    <div className="notification-content">
                      <p className="notification-message">
                        {renderNotificationMessage(notification)}
                      </p>
                      {notification.notification_type === "comment" &&
                        notification.comment_preview && (
                          <p className="comment-preview">
                            &ldquo;{notification.comment_preview}&rdquo;
                          </p>
                        )}
                      <span className="notification-time">
                        {formatRelativeTime(notification.created_at)}
                      </span>
                    </div>
                    {!notification.is_read && (
                      <div className="unread-indicator" aria-hidden="true" />
                    )}
                    {notification.content_art_url && (
                      <img
                        src={notification.content_art_url}
                        alt=""
                        width={64}
                        height={64}
                        className="notification-artwork pixel-art"
                        aria-hidden="true"
                      />
                    )}
                    {isSystem && notification.actor_avatar_url && (
                      <img
                        src={notification.actor_avatar_url}
                        alt=""
                        width={64}
                        height={64}
                        className="notification-artwork pixel-art"
                        aria-hidden="true"
                      />
                    )}
                  </>
                );

                return (
                  <li
                    key={notification.id}
                    className={`notification-item ${!notification.is_read ? "unread" : ""}`}
                  >
                    {isSystem ? (
                      <div className="notification-link system-notification">
                        {notificationContent}
                      </div>
                    ) : (
                      <Link
                        href={`/p/${notification.content_sqid}`}
                        onClick={() => handleNotificationClick(notification)}
                        className="notification-link"
                      >
                        {notificationContent}
                      </Link>
                    )}
                  </li>
                );
              })}
            </ul>

            {nextCursor && (
              <div className="load-more-container">
                <button
                  className="load-more-btn"
                  onClick={loadMore}
                  disabled={isLoadingMore}
                >
                  {isLoadingMore ? "Loading..." : "Load More"}
                </button>
              </div>
            )}
          </>
        )}
      </div>

      <style jsx>{`
        .page-container {
          max-width: 600px;
          margin: 0 auto;
          padding: 24px 16px;
        }

        .page-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 24px;
        }

        h1 {
          font-size: 24px;
          font-weight: 700;
          margin: 0;
        }

        .loading {
          text-align: center;
          color: var(--text-secondary, #888);
          padding: 48px 0;
        }

        .empty-state {
          text-align: center;
          color: var(--text-secondary, #888);
          padding: 64px 0;
        }

        .empty-icon {
          margin-bottom: 16px;
          opacity: 0.5;
        }

        .empty-state p {
          font-size: 18px;
          margin: 0 0 8px;
        }

        .empty-hint {
          font-size: 14px;
          opacity: 0.7;
        }

        .notification-list {
          list-style: none;
          padding: 0;
          margin: 0;
        }

        .notification-item {
          height: 64px;
        }

        .notification-item.unread {
          background: rgba(0, 212, 255, 0.05);
        }

        .notification-item :global(.notification-link) {
          display: flex;
          align-items: center;
          gap: 8px;
          height: 64px;
          padding: 0 8px 0 12px;
          text-decoration: none;
          color: inherit;
          transition: background var(--transition-fast);
        }

        .notification-item :global(.notification-link:hover:not(.system-notification)) {
          background: var(--bg-tertiary, #222);
        }

        .notification-icon {
          flex-shrink: 0;
          width: 32px;
          height: 32px;
          border-radius: 50%;
          background: var(--bg-tertiary, #222);
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--text-secondary, #888);
        }

        .notification-icon .emoji {
          font-size: 16px;
        }

        .notification-icon .actor-avatar {
          width: 32px;
          height: 32px;
          border-radius: 50%;
          object-fit: cover;
          image-rendering: pixelated;
        }

        .system-notification {
          cursor: default;
        }

        .notification-content {
          flex: 1;
          min-width: 0;
          overflow: hidden;
        }

        .notification-message {
          margin: 0;
          font-size: 13px;
          line-height: 1.3;
          color: var(--text-primary, #fff);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .comment-preview {
          margin: 2px 0 0;
          font-size: 12px;
          color: var(--text-secondary, #888);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
          max-width: 100%;
        }

        .notification-time {
          font-size: 11px;
          color: var(--text-tertiary, #666);
        }

        .unread-indicator {
          flex-shrink: 0;
          width: 6px;
          height: 6px;
          border-radius: 50%;
          background: var(--accent-cyan);
          box-shadow: 0 0 6px rgba(0, 212, 255, 0.5);
        }

        .notification-item :global(.notification-artwork) {
          flex-shrink: 0;
          width: 64px;
          height: 64px;
          display: block;
        }

        .load-more-container {
          padding: 24px 0;
          text-align: center;
        }

        .load-more-btn {
          padding: 12px 32px;
          background: var(--bg-tertiary, #222);
          border: 1px solid var(--border-color, #333);
          border-radius: 8px;
          color: var(--text-primary, #fff);
          font-size: 14px;
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .load-more-btn:hover:not(:disabled) {
          background: var(--accent-cyan);
          color: var(--bg-primary, #000);
          border-color: var(--accent-cyan);
        }

        .load-more-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
      `}</style>
    </Layout>
  );
}
