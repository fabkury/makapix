/**
 * Styled-jsx UI kit (docs/newpost-ui-appraisal/ F18). One primary action per
 * screen; secondary/ghost for everything else; danger only for destructive
 * confirmations. Hover feedback is a brightness/border shift — never glow,
 * movement, or a color-identity change.
 *
 * Note: components/ui/ holds an older shadcn/Tailwind set that is unstyled in
 * this project (Tailwind is not configured) — do not build on it.
 */
import type { ButtonHTMLAttributes, ReactNode } from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  fullWidth?: boolean;
  children: ReactNode;
}

export default function Button({
  variant = 'secondary',
  fullWidth = false,
  children,
  className = '',
  ...rest
}: ButtonProps) {
  return (
    <button className={`kbtn ${variant} ${fullWidth ? 'full' : ''} ${className}`} {...rest}>
      {children}
      <style jsx>{`
        .kbtn {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          padding: 12px 24px;
          border-radius: 8px;
          font-size: 1rem;
          font-weight: 600;
          cursor: pointer;
          border: 1px solid transparent;
          transition: all var(--transition-fast);
        }
        .kbtn.full {
          width: 100%;
        }
        .kbtn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }
        .kbtn.primary {
          background: var(--accent-cyan);
          color: #0b0c10;
        }
        .kbtn.primary:hover:not(:disabled) {
          filter: brightness(1.1);
        }
        .kbtn.secondary {
          background: transparent;
          border-color: var(--bg-tertiary);
          color: var(--text-primary);
        }
        .kbtn.secondary:hover:not(:disabled) {
          border-color: var(--accent-cyan);
          color: var(--accent-cyan);
        }
        .kbtn.ghost {
          background: transparent;
          color: var(--text-secondary);
        }
        .kbtn.ghost:hover:not(:disabled) {
          color: var(--text-primary);
          background: var(--bg-secondary);
        }
        .kbtn.danger {
          background: rgba(242, 85, 90, 0.15);
          border-color: rgba(242, 85, 90, 0.4);
          color: var(--danger);
        }
        .kbtn.danger:hover:not(:disabled) {
          background: rgba(242, 85, 90, 0.25);
        }
      `}</style>
    </button>
  );
}
