import { useState, useRef, useEffect } from "react";

// Delta-based scroll tracking to sync with Layout.tsx and FilterButton hide/show
const SCROLL_DELTA = 256;
const SHOW_AT_TOP = 64;

interface WPButtonProps {
  onClick: () => void;
}

export function WPButton({ onClick }: WPButtonProps) {
  const [isHidden, setIsHidden] = useState(false);

  // Delta-based scroll tracking (mirrors FilterButton exactly)
  const scrollAnchorRef = useRef(0);
  const lastScrollYRef = useRef(0);

  useEffect(() => {
    let rafId: number | null = null;

    const onScroll = () => {
      if (rafId !== null) return;
      rafId = window.requestAnimationFrame(() => {
        rafId = null;
        const y = window.scrollY || 0;
        const lastY = lastScrollYRef.current;
        const scrollingDown = y > lastY;
        const scrollingUp = y < lastY;

        setIsHidden((prev) => {
          if (y <= SHOW_AT_TOP) {
            scrollAnchorRef.current = y;
            return false;
          }

          if (scrollingDown && !prev) {
            const scrolledDown = y - scrollAnchorRef.current;
            if (scrolledDown >= SCROLL_DELTA) {
              scrollAnchorRef.current = y;
              return true;
            }
          } else if (scrollingUp && prev) {
            const scrolledUp = scrollAnchorRef.current - y;
            if (scrolledUp >= SCROLL_DELTA) {
              scrollAnchorRef.current = y;
              return false;
            }
          } else if (scrollingDown && prev) {
            scrollAnchorRef.current = y;
          } else if (scrollingUp && !prev) {
            scrollAnchorRef.current = y;
          }

          return prev;
        });

        lastScrollYRef.current = y;
      });
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (rafId !== null) window.cancelAnimationFrame(rafId);
    };
  }, []);

  return (
    <div className={`wp-button-container${isHidden ? " is-hidden" : ""}`}>
      <button
        className="wp-toggle"
        onClick={onClick}
        title="Web Player"
        aria-label="Open Web Player"
      >
        <span className="wp-icon">📺</span>
      </button>

      <style jsx>{`
        .wp-button-container {
          position: fixed;
          top: calc(var(--header-offset) + 16px + 56px + 12px);
          right: 16px;
          z-index: 199;
          transition: transform 200ms ease-out, opacity 200ms ease-out;
        }

        .wp-button-container.is-hidden {
          transform: translateY(calc(-100% - var(--header-height) - 56px - 44px));
          opacity: 0;
          pointer-events: none;
        }

        .wp-toggle {
          width: 56px;
          height: 56px;
          border-radius: 50%;
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
          border: none;
          box-shadow: var(--glow-pink);
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          transition: all var(--transition-fast);
        }

        .wp-toggle:hover {
          transform: scale(1.05);
          box-shadow: 0 0 20px rgba(255, 110, 180, 0.8);
        }

        .wp-icon {
          font-size: 24px;
          line-height: 1;
        }

        @media (max-width: 640px) {
          .wp-button-container {
            top: calc(var(--header-offset) + 8px + 48px + 8px);
            right: 8px;
          }

          .wp-toggle {
            width: 48px;
            height: 48px;
          }

          .wp-icon {
            font-size: 20px;
          }
        }
      `}</style>
    </div>
  );
}
