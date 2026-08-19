/**
 * Thin wrapper around Radix Checkbox (keyboard/ARIA behavior for free).
 * Unstyled by design: consumers style the rendered button via their own
 * selectors (e.g. pages/divoom-import.tsx styles .col-checkbox button).
 */
import * as React from 'react';
import * as CheckboxPrimitive from '@radix-ui/react-checkbox';

const Checkbox = React.forwardRef<
  React.ElementRef<typeof CheckboxPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof CheckboxPrimitive.Root>
>((props, ref) => (
  <CheckboxPrimitive.Root ref={ref} {...props}>
    <CheckboxPrimitive.Indicator style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="12"
        height="12"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <polyline points="20 6 9 17 4 12" />
      </svg>
    </CheckboxPrimitive.Indicator>
  </CheckboxPrimitive.Root>
));
Checkbox.displayName = CheckboxPrimitive.Root.displayName;

export { Checkbox };
