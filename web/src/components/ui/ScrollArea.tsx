import * as ScrollAreaPrimitive from "@radix-ui/react-scroll-area";
import { ReactNode } from "react";

interface ScrollAreaProps {
  children: ReactNode;
  className?: string;
  style?: React.CSSProperties;
}

export function ScrollArea({ children, className = "", style }: ScrollAreaProps) {
  return (
    <>
      <ScrollAreaPrimitive.Root className={`scroll-area-root ${className}`} style={style}>
        <ScrollAreaPrimitive.Viewport className="scroll-area-viewport">
          {children}
        </ScrollAreaPrimitive.Viewport>
        <ScrollAreaPrimitive.Scrollbar className="scroll-area-scrollbar" orientation="vertical">
          <ScrollAreaPrimitive.Thumb className="scroll-area-thumb" />
        </ScrollAreaPrimitive.Scrollbar>
        <ScrollAreaPrimitive.Corner />
      </ScrollAreaPrimitive.Root>

      <style jsx global>{`
        .scroll-area-root {
          position: relative;
          overflow: hidden;
        }

        .scroll-area-viewport {
          width: 100%;
          height: 100%;
          border-radius: inherit;
          overscroll-behavior: contain;
        }

        .scroll-area-viewport > div {
          display: block !important;
        }

        .scroll-area-scrollbar {
          display: flex;
          padding: 2px;
          background: rgba(255, 255, 255, 0.05);
          touch-action: none;
          user-select: none;
          transition: background 0.15s ease;
        }

        .scroll-area-scrollbar:hover {
          background: rgba(255, 255, 255, 0.1);
        }

        .scroll-area-scrollbar[data-orientation="vertical"] {
          width: 10px;
        }

        .scroll-area-scrollbar[data-orientation="horizontal"] {
          height: 10px;
          flex-direction: column;
        }

        .scroll-area-thumb {
          flex: 1;
          background: var(--accent-cyan);
          border-radius: 10px;
          position: relative;
          opacity: 0.6;
          transition: opacity 0.15s ease;
        }

        .scroll-area-thumb:hover {
          opacity: 1;
        }
      `}</style>
    </>
  );
}
