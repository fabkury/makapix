/**
 * Notification Center component.
 * 
 * Displays real-time MQTT notifications in a sidebar or popup.
 */

import React from "react";
import { useMqttNotifications } from "../hooks/use-mqtt-notifications";

interface NotificationCenterProps {
  userId: string | null;
  onNotificationClick?: (notification: any) => void;
}

export function NotificationCenter({
  userId,
  onNotificationClick,
}: NotificationCenterProps) {
  const { notifications, connected, clearNotifications } = useMqttNotifications(userId);

  if (!userId) {
    return null;
  }

  return (
    <div className="notification-center">
      <div className="notification-header">
        <h3>Notifications</h3>
        <div className="notification-status">
          <span
            className={`status-indicator ${connected ? "connected" : "disconnected"}`}
          >
            {connected ? "●" : "○"}
          </span>
          <span>{connected ? "Connected" : "Disconnected"}</span>
        </div>
        {notifications.length > 0 && (
          <button onClick={clearNotifications} className="clear-button">
            Clear
          </button>
        )}
      </div>

      <div className="notification-list">
        {notifications.length === 0 ? (
          <div className="notification-empty">No new notifications</div>
        ) : (
          notifications.map((notification, index) => (
            <div
              key={`${notification.post_id}-${index}`}
              className="notification-item"
              onClick={() => onNotificationClick?.(notification)}
            >
              <div className="notification-title">{notification.title}</div>
              <div className="notification-meta">
                <span className="notification-author">
                  by {notification.owner_handle}
                </span>
                {notification.promoted_category && (
                  <span className="notification-category">
                    {notification.promoted_category}
                  </span>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      <style jsx>{`
        .notification-center {
          position: fixed;
          top: 20px;
          right: 20px;
          width: 320px;
          max-height: 500px;
          background: white;
          border: 1px solid #e0e0e0;
          border-radius: 8px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
          display: flex;
          flex-direction: column;
          z-index: 1000;
        }

        .notification-header {
          padding: 12px 16px;
          border-bottom: 1px solid #e0e0e0;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .notification-header h3 {
          margin: 0;
          font-size: 16px;
          font-weight: 600;
        }

        .notification-status {
          display: flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          color: #666;
        }

        .status-indicator {
          font-size: 10px;
        }

        .status-indicator.connected {
          color: #4caf50;
        }

        .status-indicator.disconnected {
          color: #f44336;
        }

        .clear-button {
          background: none;
          border: none;
          color: #666;
          cursor: pointer;
          font-size: 12px;
          padding: 4px 8px;
        }

        .clear-button:hover {
          color: #000;
        }

        .notification-list {
          overflow-y: auto;
          max-height: 400px;
        }

        .notification-empty {
          padding: 24px;
          text-align: center;
          color: #999;
          font-size: 14px;
        }

        .notification-item {
          padding: 12px 16px;
          border-bottom: 1px solid #f0f0f0;
          cursor: pointer;
          transition: background-color 0.2s;
        }

        .notification-item:hover {
          background-color: #f5f5f5;
        }

        .notification-item:last-child {
          border-bottom: none;
        }

        .notification-title {
          font-weight: 500;
          font-size: 14px;
          margin-bottom: 4px;
          color: #333;
        }

        .notification-meta {
          display: flex;
          gap: 8px;
          font-size: 12px;
          color: #666;
        }

        .notification-category {
          background: #e3f2fd;
          color: #1976d2;
          padding: 2px 6px;
          border-radius: 4px;
          font-size: 11px;
        }
      `}</style>
    </div>
  );
}

