/**
 * Form field wrapper: label (+ optional tag), the control, helper text, and a
 * character counter that only appears while the field is focused or near its
 * limit (docs/newpost-ui-appraisal/ F14). The control itself is passed as
 * children and should carry the matching `id`.
 */
import type { ReactNode } from 'react';

interface FieldProps {
  id: string;
  label: string;
  optional?: boolean;
  helper?: ReactNode;
  count?: { value: number; max: number };
  children: ReactNode;
}

export default function Field({ id, label, optional = false, helper, count, children }: FieldProps) {
  const nearLimit = count ? count.value >= count.max * 0.8 : false;
  return (
    <div className="kfield">
      <label htmlFor={id} className="kfield-label">
        {label}
        {optional && <span className="kfield-optional"> (optional)</span>}
      </label>
      {children}
      {helper && <p className="kfield-helper">{helper}</p>}
      {count && (
        <span className={`kfield-count ${nearLimit ? 'near-limit' : ''}`}>
          {count.value}/{count.max}
        </span>
      )}
      <style jsx>{`
        .kfield {
          display: flex;
          flex-direction: column;
        }
        .kfield > :global(* + *) {
          margin-top: 6px;
        }
        .kfield-label {
          font-size: 0.9rem;
          color: var(--text-secondary);
        }
        .kfield-optional {
          font-size: 0.8rem;
          color: var(--text-muted);
        }
        .kfield-helper {
          font-size: 0.8rem;
          color: var(--text-muted);
          margin: 0;
        }
        .kfield-count {
          font-size: 0.75rem;
          color: var(--text-muted);
          text-align: right;
          visibility: hidden;
        }
        .kfield:focus-within .kfield-count {
          visibility: visible;
        }
        .kfield-count.near-limit {
          visibility: visible;
          color: var(--warning);
        }
      `}</style>
    </div>
  );
}
