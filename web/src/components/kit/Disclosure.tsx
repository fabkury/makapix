/**
 * Controlled accordion section (docs/newpost-ui-appraisal/ F15): neutral title,
 * an SVG chevron that rotates, and a `summary` shown while collapsed so the
 * section's state stays visible (e.g. the pending output size of the scaler).
 */
import type { ReactNode } from 'react';
import { IconChevronDown } from './icons';

interface DisclosureProps {
  title: string;
  /** Shown next to the title while collapsed (current selection/state). */
  summary?: ReactNode;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
}

export default function Disclosure({ title, summary, open, onToggle, children }: DisclosureProps) {
  return (
    <div className="kdisclosure">
      <button type="button" className="kdisclosure-trigger" onClick={onToggle} aria-expanded={open}>
        <span className="kdisclosure-heading">
          <span className="kdisclosure-title">{title}</span>
          {!open && summary && <span className="kdisclosure-summary">{summary}</span>}
        </span>
        <span className={`kdisclosure-chevron ${open ? 'open' : ''}`}>
          <IconChevronDown size={16} />
        </span>
      </button>
      {open && <div className="kdisclosure-content">{children}</div>}
      <style jsx>{`
        .kdisclosure {
          border: 1px solid var(--bg-tertiary);
          border-radius: 12px;
          overflow: hidden;
          background: var(--bg-secondary);
        }
        .kdisclosure-trigger {
          width: 100%;
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 16px 20px;
          background: transparent;
          color: var(--text-primary);
          font-weight: 600;
          font-size: 1rem;
          cursor: pointer;
          transition: background var(--transition-fast);
        }
        .kdisclosure-trigger:hover {
          background: rgba(255, 255, 255, 0.03);
        }
        .kdisclosure-heading {
          display: flex;
          align-items: center;
          gap: 12px;
          min-width: 0;
        }
        .kdisclosure-summary {
          font-size: 0.8rem;
          font-weight: 400;
          color: var(--text-secondary);
          padding: 4px 8px;
          background: rgba(255, 255, 255, 0.05);
          border-radius: 4px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }
        .kdisclosure-chevron {
          display: inline-flex;
          color: var(--text-secondary);
          transition: transform var(--transition-fast);
        }
        .kdisclosure-chevron.open {
          transform: rotate(180deg);
        }
        .kdisclosure-content {
          padding: 0 20px 20px;
          display: flex;
          flex-direction: column;
        }
        .kdisclosure-content > :global(* + *) {
          margin-top: 20px;
        }
      `}</style>
    </div>
  );
}
