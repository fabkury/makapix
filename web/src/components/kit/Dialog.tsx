/**
 * Modal confirmation dialog. The overlay click and the Escape-free simplicity
 * match the previous inline implementation in submit.tsx; actions are passed
 * in so the caller controls button variants (one primary or danger max).
 */
import type { ReactNode } from 'react';

interface DialogProps {
  title: string;
  children?: ReactNode;
  actions: ReactNode;
  onClose: () => void;
}

export default function Dialog({ title, children, actions, onClose }: DialogProps) {
  return (
    <div className="kdialog-overlay" onClick={onClose}>
      <div className="kdialog" role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}>
        <h2 className="kdialog-title">{title}</h2>
        {children && <div className="kdialog-body">{children}</div>}
        <div className="kdialog-actions">{actions}</div>
      </div>
      <style jsx>{`
        .kdialog-overlay {
          position: fixed;
          top: 0;
          right: 0;
          bottom: 0;
          left: 0;
          background: rgba(0, 0, 0, 0.7);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 100;
          padding: 24px;
        }
        .kdialog {
          background: var(--bg-primary);
          border: 1px solid var(--bg-tertiary);
          border-radius: 12px;
          padding: 24px;
          max-width: 400px;
          width: 100%;
          box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4);
        }
        .kdialog-title {
          font-size: 1.25rem;
          font-weight: 600;
          color: var(--text-primary);
          margin: 0 0 12px;
        }
        .kdialog-body {
          color: var(--text-secondary);
          font-size: 0.9rem;
          margin-bottom: 24px;
        }
        .kdialog-body :global(p) {
          margin: 0;
        }
        .kdialog-actions {
          display: flex;
          justify-content: flex-end;
          gap: 12px;
        }
      `}</style>
    </div>
  );
}
