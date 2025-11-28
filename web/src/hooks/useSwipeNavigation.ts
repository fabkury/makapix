import { useEffect, useRef } from 'react';

export type SwipeDirection = 'left' | 'right';

export interface SwipeHandlers {
  onSwipeLeft: () => void;
  onSwipeRight: () => void;
}

/**
 * Hook to detect horizontal swipe gestures on mobile devices
 * 
 * @param handlers - Callbacks for left and right swipes
 * @param enabled - Whether swipe detection is enabled (default: true)
 */
export function useSwipeNavigation(
  handlers: SwipeHandlers,
  enabled: boolean = true
): void {
  const touchStartRef = useRef<{ x: number; y: number; time: number } | null>(null);
  const touchEndRef = useRef<{ x: number; y: number; time: number } | null>(null);
  
  // Store handlers in ref to avoid re-running effect on every render
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  // Minimum swipe distance (in pixels)
  const MIN_SWIPE_DISTANCE = 50;
  // Maximum vertical deviation (to distinguish from scroll)
  const MAX_VERTICAL_DEVIATION = 75;
  // Maximum swipe duration (in milliseconds)
  const MAX_SWIPE_DURATION = 500;

  useEffect(() => {
    if (!enabled) return;

    // Check if device is mobile (touch capable and small screen)
    const isMobile = () => {
      if (typeof window === 'undefined') return false;
      const hasTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
      const isSmallScreen = window.innerWidth <= 768;
      return hasTouch && isSmallScreen;
    };

    if (!isMobile()) return;

    const handleTouchStart = (e: TouchEvent) => {
      const touch = e.touches[0];
      touchStartRef.current = {
        x: touch.clientX,
        y: touch.clientY,
        time: Date.now(),
      };
      touchEndRef.current = null;
    };

    const handleTouchMove = (e: TouchEvent) => {
      // Prevent default scrolling only if we're clearly doing a horizontal swipe
      const touch = e.touches[0];
      if (touchStartRef.current) {
        const deltaX = Math.abs(touch.clientX - touchStartRef.current.x);
        const deltaY = Math.abs(touch.clientY - touchStartRef.current.y);
        
        // Only prevent scroll if:
        // 1. Horizontal movement is significantly greater than vertical (2:1 ratio)
        // 2. We've moved enough horizontally to indicate intent (25px)
        // This allows normal scrolling to work while still catching intentional swipes
        if (deltaX > deltaY * 2 && deltaX > 25) {
          e.preventDefault();
        }
      }
    };

    const handleTouchEnd = (e: TouchEvent) => {
      const touch = e.changedTouches[0];
      touchEndRef.current = {
        x: touch.clientX,
        y: touch.clientY,
        time: Date.now(),
      };

      if (!touchStartRef.current || !touchEndRef.current) return;

      const deltaX = touchEndRef.current.x - touchStartRef.current.x;
      const deltaY = Math.abs(touchEndRef.current.y - touchStartRef.current.y);
      const deltaTime = touchEndRef.current.time - touchStartRef.current.time;

      // Check if swipe is valid
      const isValidSwipe =
        Math.abs(deltaX) >= MIN_SWIPE_DISTANCE &&
        deltaY <= MAX_VERTICAL_DEVIATION &&
        deltaTime <= MAX_SWIPE_DURATION;

      if (isValidSwipe) {
        if (deltaX > 0) {
          // Swipe right (previous post)
          handlersRef.current.onSwipeRight();
        } else {
          // Swipe left (next post)
          handlersRef.current.onSwipeLeft();
        }
      }

      // Reset
      touchStartRef.current = null;
      touchEndRef.current = null;
    };

    // Add event listeners
    window.addEventListener('touchstart', handleTouchStart, { passive: false });
    window.addEventListener('touchmove', handleTouchMove, { passive: false });
    window.addEventListener('touchend', handleTouchEnd, { passive: true });

    return () => {
      window.removeEventListener('touchstart', handleTouchStart);
      window.removeEventListener('touchmove', handleTouchMove);
      window.removeEventListener('touchend', handleTouchEnd);
    };
  }, [enabled]);
}

