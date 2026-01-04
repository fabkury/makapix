import * as SelectPrimitive from "@radix-ui/react-select";
import { ReactNode } from "react";

interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps {
  value: string;
  onValueChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  disabled?: boolean;
}

export function Select({ value, onValueChange, options, placeholder = "Select...", disabled }: SelectProps) {
  return (
    <>
      <SelectPrimitive.Root value={value} onValueChange={onValueChange} disabled={disabled}>
        <SelectPrimitive.Trigger className="select-trigger">
          <SelectPrimitive.Value placeholder={placeholder} />
          <SelectPrimitive.Icon className="select-icon">
            <ChevronDownIcon />
          </SelectPrimitive.Icon>
        </SelectPrimitive.Trigger>

        <SelectPrimitive.Portal>
          <SelectPrimitive.Content className="select-content" position="popper" sideOffset={4}>
            <SelectPrimitive.Viewport className="select-viewport">
              {options.map((option) => (
                <SelectPrimitive.Item key={option.value} value={option.value} className="select-item">
                  <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
                  <SelectPrimitive.ItemIndicator className="select-item-indicator">
                    <CheckIcon />
                  </SelectPrimitive.ItemIndicator>
                </SelectPrimitive.Item>
              ))}
            </SelectPrimitive.Viewport>
          </SelectPrimitive.Content>
        </SelectPrimitive.Portal>
      </SelectPrimitive.Root>

      <style jsx global>{`
        .select-trigger {
          display: inline-flex;
          align-items: center;
          justify-content: space-between;
          width: 100%;
          padding: 10px 12px;
          font-size: 0.9rem;
          color: var(--text-primary);
          background: var(--bg-tertiary);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 6px;
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .select-trigger:hover {
          border-color: var(--accent-cyan);
        }

        .select-trigger:focus {
          outline: none;
          border-color: var(--accent-cyan);
          box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.15);
        }

        .select-trigger[data-disabled] {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .select-trigger[data-placeholder] {
          color: var(--text-muted);
        }

        .select-icon {
          margin-left: 8px;
          color: var(--text-secondary);
        }

        .select-content {
          background: var(--bg-secondary);
          border: 1px solid rgba(255, 255, 255, 0.1);
          border-radius: 6px;
          box-shadow: 0 10px 38px -10px rgba(0, 0, 0, 0.5),
                      0 10px 20px -15px rgba(0, 0, 0, 0.4);
          overflow: hidden;
          z-index: 100;
          min-width: var(--radix-select-trigger-width);
          max-height: var(--radix-select-content-available-height);
        }

        .select-viewport {
          padding: 4px;
        }

        .select-item {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 12px;
          font-size: 0.9rem;
          color: var(--text-primary);
          border-radius: 4px;
          cursor: pointer;
          outline: none;
          transition: background 0.15s ease;
        }

        .select-item:focus,
        .select-item:hover {
          background: var(--bg-tertiary);
        }

        .select-item[data-highlighted] {
          background: var(--bg-tertiary);
        }

        .select-item[data-state="checked"] {
          color: var(--accent-cyan);
        }

        .select-item-indicator {
          margin-left: 8px;
          color: var(--accent-cyan);
        }
      `}</style>
    </>
  );
}

function ChevronDownIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M2.5 4.5L6 8L9.5 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M2.5 6L5 8.5L9.5 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}
