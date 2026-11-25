import {
  CSSProperties,
  RefObject,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

/** Gap kept between the menu and the viewport edges. */
const VIEWPORT_MARGIN = 8;
/** Gap between the anchor button and the menu. */
const ANCHOR_GAP = 4;

interface MenuBox {
  top: number;
  left: number;
  maxHeight: number;
  maxWidth: number;
}

const useIsomorphicLayoutEffect =
  typeof window !== "undefined" ? useLayoutEffect : useEffect;

const clamp = (value: number, min: number, max: number) =>
  Math.max(min, Math.min(value, max));

/**
 * Positions a popup menu next to its anchor button so that it is always fully
 * inside the viewport.
 *
 * - Opens below the anchor, right edges aligned; flips above when it does not
 *   fit below; slides to wherever it is fully visible when it fits in neither.
 * - Re-fits when the menu changes size (inline submenus expanding). A re-fit
 *   only slides the menu by the overflow — it never flips — so the item under
 *   the cursor stays inside the submenu that was just opened.
 * - When the viewport is smaller than the menu, the menu is capped to the
 *   viewport and scrolls internally.
 *
 * The returned style uses viewport coordinates (`top` / `left`), so the menu
 * must be `position: fixed`, or absolutely positioned inside a fixed,
 * full-viewport container. Spread it last so it overrides static styles.
 */
export function useAnchoredMenu(
  open: boolean,
  anchorRef: RefObject<HTMLElement>,
  menuRef: RefObject<HTMLElement>,
): CSSProperties {
  const [box, setBox] = useState<MenuBox | null>(null);
  const boxRef = useRef<MenuBox | null>(null);

  const place = useCallback(
    (mode: "anchor" | "refit") => {
      const anchor = anchorRef.current;
      const menu = menuRef.current;
      if (!anchor || !menu) return;

      const viewportWidth = document.documentElement.clientWidth;
      const viewportHeight = window.innerHeight;
      const maxWidth = Math.max(0, viewportWidth - 2 * VIEWPORT_MARGIN);
      const maxHeight = Math.max(0, viewportHeight - 2 * VIEWPORT_MARGIN);

      // Natural (uncapped) height: content height plus borders, regardless of
      // any max-height currently applied.
      const naturalHeight =
        menu.scrollHeight + (menu.offsetHeight - menu.clientHeight);
      const height = Math.min(naturalHeight, maxHeight);
      const width = Math.min(menu.offsetWidth, maxWidth);

      const rect = anchor.getBoundingClientRect();
      const lowestTop = Math.max(
        VIEWPORT_MARGIN,
        viewportHeight - VIEWPORT_MARGIN - height,
      );

      let top: number;
      const current = boxRef.current;
      if (mode === "refit" && current) {
        top = clamp(current.top, VIEWPORT_MARGIN, lowestTop);
      } else {
        const below = rect.bottom + ANCHOR_GAP;
        const above = rect.top - ANCHOR_GAP - height;
        if (below <= lowestTop) top = below;
        else if (above >= VIEWPORT_MARGIN) top = above;
        else top = clamp(below, VIEWPORT_MARGIN, lowestTop);
      }

      const left = clamp(
        rect.right - width,
        VIEWPORT_MARGIN,
        Math.max(VIEWPORT_MARGIN, viewportWidth - VIEWPORT_MARGIN - width),
      );

      const next: MenuBox = { top, left, maxHeight, maxWidth };
      if (
        current &&
        current.top === next.top &&
        current.left === next.left &&
        current.maxHeight === next.maxHeight &&
        current.maxWidth === next.maxWidth
      ) {
        return;
      }
      boxRef.current = next;
      setBox(next);
    },
    [anchorRef, menuRef],
  );

  useIsomorphicLayoutEffect(() => {
    if (!open) {
      boxRef.current = null;
      setBox(null);
      return;
    }

    place("anchor");

    const onViewportChange = () => place("anchor");
    window.addEventListener("resize", onViewportChange);
    // Capture phase: also catches scrolling of nested scroll containers.
    window.addEventListener("scroll", onViewportChange, true);

    let observer: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined" && menuRef.current) {
      observer = new ResizeObserver(() => place("refit"));
      observer.observe(menuRef.current);
    }

    return () => {
      window.removeEventListener("resize", onViewportChange);
      window.removeEventListener("scroll", onViewportChange, true);
      observer?.disconnect();
    };
  }, [open, place, menuRef]);

  if (!box) {
    // First paint after opening: rendered but not yet measured.
    return { top: 0, left: 0, visibility: "hidden" };
  }
  return {
    top: box.top,
    left: box.left,
    right: "auto",
    maxHeight: box.maxHeight,
    maxWidth: box.maxWidth,
    overflowY: "auto",
    overscrollBehavior: "contain",
  };
}
