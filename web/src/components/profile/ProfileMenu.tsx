/**
 * ProfileMenu component - overflow (vertical three-dot) menu shown at the right
 * of the profile stats row. Consolidates the actions that previously lived in the
 * owner-panel and moderation-row (Artist Dashboard, Post Management, User
 * Management, Manage Players, User Settings, Edit, Log Out).
 *
 * It is a presentational dropdown: callers build the `items` list with the right
 * conditional logic and pass it in. Renders nothing when `items` is empty.
 */

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';

export interface ProfileMenuItem {
  key: string;
  icon: string;
  label: string;
  href?: string; // renders a Link
  onClick?: () => void; // renders a button
  danger?: boolean; // emphasised (e.g. Log Out)
}

interface ProfileMenuProps {
  items: ProfileMenuItem[];
}

export default function ProfileMenu({ items }: ProfileMenuProps) {
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close on outside click or Escape while open.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  if (items.length === 0) return null;

  return (
    <div className="profile-menu" ref={menuRef}>
      <button
        type="button"
        className="menu-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Profile actions"
        onClick={() => setOpen((v) => !v)}
      >
        ⋮
      </button>

      {open && (
        <div className="menu-dropdown" role="menu">
          {items.map((item) =>
            item.href ? (
              <Link
                key={item.key}
                href={item.href}
                role="menuitem"
                className={`menu-item${item.danger ? ' danger' : ''}`}
                onClick={() => setOpen(false)}
              >
                <span className="menu-item-icon">{item.icon}</span>
                <span className="menu-item-label">{item.label}</span>
              </Link>
            ) : (
              <button
                key={item.key}
                type="button"
                role="menuitem"
                className={`menu-item${item.danger ? ' danger' : ''}`}
                onClick={() => {
                  setOpen(false);
                  item.onClick?.();
                }}
              >
                <span className="menu-item-icon">{item.icon}</span>
                <span className="menu-item-label">{item.label}</span>
              </button>
            )
          )}
        </div>
      )}

      <style jsx>{`
        .profile-menu {
          position: relative;
          display: inline-flex;
          align-items: center;
        }
        .menu-trigger {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 32px;
          height: 32px;
          padding: 0;
          border: 1px solid transparent;
          border-radius: 8px;
          background: transparent;
          color: var(--text-primary);
          font-size: 1.25rem;
          line-height: 1;
          cursor: pointer;
          transition: all var(--transition-fast);
        }
        .menu-trigger:hover,
        .menu-trigger[aria-expanded='true'] {
          background: rgba(255, 255, 255, 0.1);
          border-color: var(--accent-cyan);
        }

        .menu-dropdown {
          position: absolute;
          top: calc(100% + 8px);
          right: 0;
          z-index: 50;
          min-width: 210px;
          display: flex;
          flex-direction: column;
          padding: 6px;
          background: var(--bg-secondary);
          border: 1px solid rgba(255, 255, 255, 0.15);
          border-radius: 10px;
          box-shadow: 0 8px 30px rgba(0, 0, 0, 0.45);
        }

        .menu-dropdown :global(.menu-item) {
          display: flex;
          align-items: center;
          width: 100%;
          padding: 10px 12px;
          border: none;
          border-radius: 8px;
          background: transparent;
          color: var(--text-primary);
          font-size: 0.9rem;
          font-weight: 500;
          text-align: left;
          text-decoration: none;
          cursor: pointer;
          transition: background var(--transition-fast);
        }
        .menu-dropdown :global(.menu-item:hover) {
          background: rgba(255, 255, 255, 0.08);
        }
        .menu-dropdown :global(.menu-item.danger) {
          color: var(--accent-pink, #ff6b6b);
        }
        .menu-dropdown :global(.menu-item-icon) {
          font-size: 1.05rem;
          width: 1.5rem;
          flex-shrink: 0;
        }
        .menu-dropdown :global(.menu-item-label) {
          flex: 1;
        }
      `}</style>
    </div>
  );
}
