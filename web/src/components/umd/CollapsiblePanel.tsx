/**
 * CollapsiblePanel - A collapsible section container for the UMD.
 * Features a title header that toggles open/closed state.
 */

import { useState, ReactNode } from 'react';

interface CollapsiblePanelProps {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
}

export default function CollapsiblePanel({ title, children, defaultOpen = false }: CollapsiblePanelProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className="collapsible-panel">
      <button
        className="panel-header"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
      >
        <span className="panel-title">{title}</span>
        <span className={`chevron ${isOpen ? 'open' : ''}`}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="m6 9 6 6 6-6" />
          </svg>
        </span>
      </button>
      {isOpen && (
        <div className="panel-content">
          {children}
        </div>
      )}

      <style jsx>{`
        .collapsible-panel {
          background: var(--bg-secondary);
          border: 1px solid var(--border-color);
          border-radius: 8px;
          overflow: hidden;
        }
        .panel-header {
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 16px;
          background: transparent;
          border: none;
          color: var(--text-primary);
          cursor: pointer;
          font-size: 1rem;
          font-weight: 600;
          transition: background 0.15s ease;
        }
        .panel-header:hover {
          background: rgba(255, 255, 255, 0.05);
        }
        .panel-title {
          text-align: left;
        }
        .chevron {
          display: flex;
          align-items: center;
          color: var(--text-secondary);
          transition: transform 0.2s ease;
        }
        .chevron.open {
          transform: rotate(180deg);
        }
        .panel-content {
          padding: 0 16px 16px;
        }
      `}</style>
    </div>
  );
}
