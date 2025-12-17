import { useState, useEffect } from 'react';
import { useRouter } from 'next/router';
import Layout from '../components/Layout';
import { useNotifications } from '../hooks/useNotifications';

interface Notification {
  id: string;
  notification_type: 'reaction' | 'comment';
  content_type: 'post' | 'blog_post';
  content_id: number;
  actor_handle: string;
  emoji?: string;
  comment_preview?: string;
  content_title?: string;
  content_url?: string;
  is_read: boolean;
  created_at: string;
}

export default function NotificationsPage() {
  const router = useRouter();
  const [userId, setUserId] = useState<string | null>(null);
  
  const {
    notifications,
    loading,
    fetchNotifications,
    markAllAsRead,
  } = useNotifications(userId);

  useEffect(() => {
    const storedUserId = localStorage.getItem('user_id');
    if (!storedUserId) {
      router.push('/auth');
      return;
    }
    setUserId(storedUserId);
  }, [router]);

  useEffect(() => {
    if (userId) {
      fetchNotifications();
      // Mark all as read when page loads
      const unreadIds = notifications.filter(n => !n.is_read).map(n => n.id);
      if (unreadIds.length > 0) {
        setTimeout(() => markAllAsRead(), 1000);
      }
    }
  }, [userId]);

  const getNotificationText = (notification: Notification): string => {
    const contentType = notification.content_type === 'post' ? 'artwork' : 'blog post';
    
    if (notification.notification_type === 'reaction') {
      return `${notification.actor_handle} reacted ${notification.emoji} to your ${contentType}`;
    } else {
      return `${notification.actor_handle} commented on your ${contentType}`;
    }
  };

  const getNotificationUrl = (notification: Notification): string => {
    if (notification.content_url) {
      return notification.content_url;
    }
    if (notification.content_type === 'post') {
      return `/post/${notification.content_id}`;
    } else {
      return `/blog/${notification.content_id}`;
    }
  };

  const formatTime = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    
    return date.toLocaleDateString();
  };

  if (!userId) {
    return null;
  }

  return (
    <Layout title="Notifications">
      <div className="notifications-page">
        <div className="notifications-header">
          <h1>Notifications</h1>
          {notifications.filter(n => !n.is_read).length > 0 && (
            <button onClick={markAllAsRead} className="mark-all-read-btn">
              Mark all as read
            </button>
          )}
        </div>

        {loading && notifications.length === 0 ? (
          <div className="loading">Loading notifications...</div>
        ) : notifications.length === 0 ? (
          <div className="empty-state">
            <p>No notifications yet</p>
            <p>When someone reacts or comments on your content, you&apos;ll see it here!</p>
          </div>
        ) : (
          <div className="notifications-list">
            {notifications.map((notification) => (
              <div
                key={notification.id}
                className={`notification-item ${!notification.is_read ? 'unread' : ''}`}
                onClick={() => router.push(getNotificationUrl(notification))}
              >
                <div className="notification-content">
                  <div className="notification-text">
                    {getNotificationText(notification)}
                  </div>
                  {notification.content_title && (
                    <div className="notification-title">
                      &ldquo;{notification.content_title}&rdquo;
                    </div>
                  )}
                  {notification.comment_preview && (
                    <div className="notification-preview">
                      {notification.comment_preview}
                    </div>
                  )}
                  <div className="notification-time">
                    {formatTime(notification.created_at)}
                  </div>
                </div>
                {!notification.is_read && (
                  <div className="unread-indicator" />
                )}
              </div>
            ))}
          </div>
        )}

        <style jsx>{`
          .notifications-page {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
          }

          .notifications-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
          }

          .notifications-header h1 {
            font-size: 28px;
            font-weight: 600;
            margin: 0;
            color: var(--text-primary);
          }

          .mark-all-read-btn {
            background: var(--accent);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: opacity 0.2s;
          }

          .mark-all-read-btn:hover {
            opacity: 0.8;
          }

          .loading {
            text-align: center;
            padding: 40px;
            color: var(--text-secondary);
          }

          .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-secondary);
          }

          .empty-state p:first-child {
            font-size: 18px;
            font-weight: 500;
            margin-bottom: 8px;
          }

          .empty-state p:last-child {
            font-size: 14px;
          }

          .notifications-list {
            display: flex;
            flex-direction: column;
            gap: 1px;
            background: var(--border);
            border-radius: 8px;
            overflow: hidden;
          }

          .notification-item {
            background: var(--bg-secondary);
            padding: 16px;
            cursor: pointer;
            transition: background-color 0.2s;
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 12px;
          }

          .notification-item:hover {
            background: var(--bg-tertiary);
          }

          .notification-item.unread {
            background: var(--bg-primary);
          }

          .notification-item.unread:hover {
            background: var(--bg-secondary);
          }

          .notification-content {
            flex: 1;
          }

          .notification-text {
            font-size: 15px;
            color: var(--text-primary);
            margin-bottom: 6px;
            font-weight: 500;
          }

          .notification-title {
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: 4px;
            font-style: italic;
          }

          .notification-preview {
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: 6px;
            padding: 8px;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 4px;
          }

          .notification-time {
            font-size: 12px;
            color: var(--text-tertiary);
          }

          .unread-indicator {
            width: 8px;
            height: 8px;
            background: #007aff;
            border-radius: 50%;
            flex-shrink: 0;
            margin-top: 4px;
          }

          @media (max-width: 768px) {
            .notifications-page {
              padding: 12px;
            }

            .notifications-header h1 {
              font-size: 20px;
            }
          }
        `}</style>
      </div>
    </Layout>
  );
}
