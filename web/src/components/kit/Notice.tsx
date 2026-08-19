/**
 * Inline notice/callout. Tone encodes state (docs/newpost-ui-appraisal/ F6,
 * F12): `info` is neutral — for process information that is not a problem;
 * amber/red are reserved for things that can actually go wrong.
 */
import type { ReactNode } from 'react';

export type NoticeTone = 'info' | 'warning' | 'danger' | 'success';

interface NoticeProps {
  tone: NoticeTone;
  icon?: ReactNode;
  title?: string;
  children?: ReactNode;
}

export default function Notice({ tone, icon, title, children }: NoticeProps) {
  return (
    <div className={`knotice ${tone}`}>
      {icon && <span className="knotice-icon">{icon}</span>}
      <div className="knotice-body">
        {title && <p className="knotice-title">{title}</p>}
        {children}
      </div>
      <style jsx>{`
        .knotice {
          display: flex;
          align-items: flex-start;
          padding: 14px 16px;
          border-radius: 8px;
          text-align: left;
          font-size: 0.9rem;
          border: 1px solid var(--bg-tertiary);
          background: var(--bg-card);
          color: var(--text-secondary);
        }
        .knotice.warning {
          border-color: rgba(240, 191, 104, 0.3);
          background: rgba(240, 191, 104, 0.08);
        }
        .knotice.danger {
          border-color: rgba(242, 85, 90, 0.3);
          background: rgba(242, 85, 90, 0.08);
        }
        .knotice.success {
          border-color: rgba(87, 198, 144, 0.25);
          background: rgba(87, 198, 144, 0.06);
        }
        .knotice-icon {
          flex-shrink: 0;
          display: inline-flex;
          margin-right: 12px;
          margin-top: 1px;
          color: var(--text-secondary);
        }
        .knotice.warning .knotice-icon {
          color: var(--warning);
        }
        .knotice.danger .knotice-icon {
          color: var(--danger);
        }
        .knotice.success .knotice-icon {
          color: var(--success);
        }
        .knotice-body {
          flex: 1;
          min-width: 0;
        }
        .knotice-body :global(p) {
          margin: 0;
          line-height: 1.5;
        }
        .knotice-title {
          font-weight: 600;
          font-size: 0.95rem;
          color: var(--text-primary);
          margin: 0 0 4px !important;
        }
      `}</style>
    </div>
  );
}
