/**
 * Notification badge component that overlays a counter on top of a button.
 */

import React from 'react';

interface NotificationBadgeProps {
  count: number;
  onClick?: () => void;
  children: React.ReactNode;
  className?: string;
}

export function NotificationBadge({ count, onClick, children, className = '' }: NotificationBadgeProps) {
  return (
    <div className={`notification-badge-container ${className}`} onClick={onClick}>
      {children}
      {count > 0 && (
        <div className="notification-badge">
          {count > 99 ? '99+' : count}
        </div>
      )}
      
      <style jsx>{`
        .notification-badge-container {
          position: relative;
          display: inline-block;
          cursor: ${onClick ? 'pointer' : 'default'};
        }
        
        .notification-badge {
          position: absolute;
          bottom: -4px;
          right: -4px;
          background: #ff4444;
          color: white;
          font-size: 10px;
          font-weight: bold;
          padding: 2px 5px;
          border-radius: 10px;
          min-width: 18px;
          height: 18px;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
          border: 2px solid var(--bg-primary, #1a1a1a);
          z-index: 10;
        }
      `}</style>
    </div>
  );
}
