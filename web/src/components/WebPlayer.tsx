import { useState, useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import { authenticatedFetch } from "../lib/api";

const DWELL_TIME_MS = 30_000;
const MAX_REPEAT_RETRIES = 3;
const MAX_HISTORY = 64;
const WP_BAR_HEIGHT = 56;

interface Artwork {
  id: number;
  art_url: string;
  width: number;
  height: number;
}

interface WebPlayerProps {
  isActive: boolean;
  onClose: () => void;
  buildApiQuery: (baseParams: Record<string, string>) => string;
  baseParams: Record<string, string>;
}

/** Load an image into the browser cache and decode it, ready to paint. */
function prefetchImage(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      if (typeof img.decode === "function") {
        img.decode().then(resolve, resolve);
      } else {
        resolve();
      }
    };
    img.onerror = reject;
    img.src = url;
  });
}

export function WebPlayer({ isActive, onClose, buildApiQuery, baseParams }: WebPlayerProps) {
  // --- Double-buffer display ---
  // Two persistent <img> slots (A and B) always in the DOM, stacked via z-index.
  // Only the BACK slot's src is ever changed; the visible (front) slot is never
  // touched. When the back slot's onLoad fires, we flip z-indices. This
  // guarantees zero-frame-gap transitions — the old image stays on screen until
  // the new one is fully loaded and ready to paint.
  const [slotASrc, _setSlotASrc] = useState("");
  const [slotBSrc, _setSlotBSrc] = useState("");
  const [frontSlot, setFrontSlot] = useState<"a" | "b">("a");
  const frontSlotRef = useRef<"a" | "b">("a");
  const slotSrcRefs = useRef({ a: "", b: "" });

  // Keep refs in sync with state for synchronous access.
  const setSlotASrc = useCallback((url: string) => {
    slotSrcRefs.current.a = url;
    _setSlotASrc(url);
  }, []);
  const setSlotBSrc = useCallback((url: string) => {
    slotSrcRefs.current.b = url;
    _setSlotBSrc(url);
  }, []);

  // Artwork metadata for the currently displayed piece (for history, dwell, etc.)
  const [displayedArtwork, setDisplayedArtwork] = useState<Artwork | null>(null);

  const [empty, setEmpty] = useState(false);
  const [fadeIn, setFadeIn] = useState(false);
  const [fadeOut, setFadeOut] = useState(false);
  const [squareSize, setSquareSize] = useState(0);

  const lastArtworkIdRef = useRef<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closingRef = useRef(false);
  const mountedRef = useRef(false);

  // Prefetch-ahead: load the next artwork in the background so it's ready the
  // instant the user advances or the dwell timer fires.
  const prefetchedRef = useRef<Artwork | null>(null);
  const prefetchingRef = useRef(false);
  const prefetchCancelledRef = useRef(false);

  // History for prev/next navigation
  const historyRef = useRef<Artwork[]>([]);
  const historyIndexRef = useRef(-1);

  // Stabilize props via refs to prevent effect re-triggers from parent re-renders
  const buildApiQueryRef = useRef(buildApiQuery);
  buildApiQueryRef.current = buildApiQuery;
  const baseParamsRef = useRef(baseParams);
  baseParamsRef.current = baseParams;
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  const apiBaseUrl =
    typeof window !== "undefined"
      ? process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin
      : "";

  // Compute the largest square that fits the viewport minus wp-bar
  const updateSquareSize = useCallback(() => {
    const availableHeight = window.innerHeight - WP_BAR_HEIGHT;
    setSquareSize(Math.min(window.innerWidth, availableHeight));
  }, []);

  // --- Double-buffer helpers ---

  /** When a slot's <img> fires onLoad, flip it to front if it's the back slot. */
  const handleSlotLoad = useCallback((slot: "a" | "b") => {
    if (slot !== frontSlotRef.current) {
      frontSlotRef.current = slot;
      setFrontSlot(slot);
    }
  }, []);

  /** Put an artwork on the back buffer and let onLoad flip it to front.
   *  If the back slot already has the same URL, flip immediately. */
  const showOnBackBuffer = useCallback(
    (artwork: Artwork) => {
      const back: "a" | "b" = frontSlotRef.current === "a" ? "b" : "a";
      const backSrc = slotSrcRefs.current[back];
      const setBack = back === "a" ? setSlotASrc : setSlotBSrc;

      if (backSrc === artwork.art_url) {
        // Already on back buffer (e.g. cache hit from history) — flip now.
        frontSlotRef.current = back;
        setFrontSlot(back);
      } else {
        setBack(artwork.art_url);
        // onLoad on the back slot's <img> will trigger handleSlotLoad → flip.
      }
    },
    [setSlotASrc, setSlotBSrc],
  );

  /** Display an artwork: update metadata, push to history, and show on back buffer. */
  const showArtwork = useCallback(
    (artwork: Artwork, addToHistory: boolean) => {
      lastArtworkIdRef.current = artwork.id;
      setDisplayedArtwork(artwork);
      setEmpty(false);
      showOnBackBuffer(artwork);

      if (addToHistory) {
        historyRef.current = historyRef.current.slice(
          0,
          historyIndexRef.current + 1,
        );
        historyRef.current.push(artwork);
        if (historyRef.current.length > MAX_HISTORY) {
          historyRef.current = historyRef.current.slice(-MAX_HISTORY);
        }
        historyIndexRef.current = historyRef.current.length - 1;
      }
    },
    [showOnBackBuffer],
  );

  // --- Fetching ---

  /** Fetch a random artwork's metadata from the API (no image prefetch). */
  const fetchArtworkMetadata = useCallback(
    async (retryCount = 0): Promise<Artwork | null> => {
      try {
        const qs = buildApiQueryRef.current(baseParamsRef.current);
        const params = new URLSearchParams(qs);
        params.set("sort", "random");
        params.set("limit", "1");
        params.delete("order");
        params.delete("cursor");
        const url = `${apiBaseUrl}/api/post?${params.toString()}`;
        const response = await authenticatedFetch(url);
        if (!response.ok) return null;
        const data = await response.json();
        if (!data.items || data.items.length === 0) return null;
        const artwork: Artwork = {
          id: data.items[0].id,
          art_url: data.items[0].art_url,
          width: data.items[0].width,
          height: data.items[0].height,
        };
        if (
          artwork.id === lastArtworkIdRef.current &&
          retryCount < MAX_REPEAT_RETRIES
        ) {
          return fetchArtworkMetadata(retryCount + 1);
        }
        return artwork;
      } catch {
        return null;
      }
    },
    [apiBaseUrl],
  );

  // --- Prefetch-ahead ---

  /** Start prefetching the next random artwork in the background. */
  const startPrefetch = useCallback(() => {
    if (prefetchingRef.current) return;
    prefetchingRef.current = true;
    prefetchedRef.current = null;
    prefetchCancelledRef.current = false;

    (async () => {
      const artwork = await fetchArtworkMetadata();
      if (prefetchCancelledRef.current || !artwork) {
        prefetchingRef.current = false;
        return;
      }
      try {
        await prefetchImage(artwork.art_url);
      } catch {
        // Image failed — store anyway; the back buffer will attempt to load it.
      }
      if (prefetchCancelledRef.current) {
        prefetchingRef.current = false;
        return;
      }
      prefetchedRef.current = artwork;
      prefetchingRef.current = false;
    })();
  }, [fetchArtworkMetadata]);

  const cancelPrefetch = useCallback(() => {
    prefetchCancelledRef.current = true;
    prefetchingRef.current = false;
    prefetchedRef.current = null;
  }, []);

  // --- Navigation ---

  /** Advance to the next random artwork (dwell timer or next-button). */
  const advanceToNext = useCallback(async () => {
    if (!mountedRef.current) return;

    if (prefetchedRef.current) {
      // Prefetched and ready — instant swap.
      const artwork = prefetchedRef.current;
      prefetchedRef.current = null;
      prefetchingRef.current = false;
      showArtwork(artwork, true);
      startPrefetch();
      return;
    }

    // Nothing prefetched yet — fetch + prefetch now, then display.
    cancelPrefetch();
    const artwork = await fetchArtworkMetadata();
    if (!artwork || !mountedRef.current) {
      if (mountedRef.current) setEmpty(true);
      return;
    }
    try {
      await prefetchImage(artwork.art_url);
    } catch {
      // Show it anyway; the back buffer will try to load from src.
    }
    if (!mountedRef.current) return;
    showArtwork(artwork, true);
    startPrefetch();
  }, [showArtwork, fetchArtworkMetadata, startPrefetch, cancelPrefetch]);

  /** Navigate to previous artwork in history. */
  const goBack = useCallback(async () => {
    if (historyIndexRef.current <= 0) return;
    historyIndexRef.current -= 1;
    const artwork = historyRef.current[historyIndexRef.current];

    // Prefetch (usually a cache hit — resolves almost instantly).
    try {
      await prefetchImage(artwork.art_url);
    } catch {}
    if (!mountedRef.current) return;

    lastArtworkIdRef.current = artwork.id;
    setDisplayedArtwork(artwork);
    showOnBackBuffer(artwork);

    cancelPrefetch();
    startPrefetch();
  }, [showOnBackBuffer, cancelPrefetch, startPrefetch]);

  /** Navigate to next artwork: forward in history, or fetch new random. */
  const goNext = useCallback(async () => {
    if (historyIndexRef.current < historyRef.current.length - 1) {
      historyIndexRef.current += 1;
      const artwork = historyRef.current[historyIndexRef.current];

      try {
        await prefetchImage(artwork.art_url);
      } catch {}
      if (!mountedRef.current) return;

      lastArtworkIdRef.current = artwork.id;
      setDisplayedArtwork(artwork);
      showOnBackBuffer(artwork);

      cancelPrefetch();
      startPrefetch();
    } else {
      await advanceToNext();
    }
  }, [showOnBackBuffer, advanceToNext, cancelPrefetch, startPrefetch]);

  // --- Effects ---

  // Activation: fade in, fetch first artwork, lock scroll, push history state
  useEffect(() => {
    if (!isActive) return;
    mountedRef.current = true;
    closingRef.current = false;

    setFadeIn(false);
    setFadeOut(false);
    setEmpty(false);
    setDisplayedArtwork(null);
    setSlotASrc("");
    setSlotBSrc("");
    frontSlotRef.current = "a";
    setFrontSlot("a");
    lastArtworkIdRef.current = null;
    historyRef.current = [];
    historyIndexRef.current = -1;
    prefetchedRef.current = null;
    prefetchingRef.current = false;
    prefetchCancelledRef.current = false;

    // Lock body scroll
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    // Push history entry so mobile back button closes WP
    window.history.pushState({ wpActive: true }, "");

    // Start fade in on next frame
    requestAnimationFrame(() => {
      if (mountedRef.current) setFadeIn(true);
    });

    // Fetch and display first artwork, then start prefetching next
    (async () => {
      const artwork = await fetchArtworkMetadata();
      if (!artwork || !mountedRef.current) {
        if (mountedRef.current) setEmpty(true);
        return;
      }
      try {
        await prefetchImage(artwork.art_url);
      } catch {}
      if (!mountedRef.current) return;
      showArtwork(artwork, true);
      startPrefetch();
    })();

    updateSquareSize();

    return () => {
      mountedRef.current = false;
      document.body.style.overflow = prevOverflow;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      cancelPrefetch();
    };
  }, [isActive, fetchArtworkMetadata, showArtwork, startPrefetch, cancelPrefetch, updateSquareSize, setSlotASrc, setSlotBSrc]);

  // Dwell timer: auto-advance after DWELL_TIME_MS
  useEffect(() => {
    if (!isActive || !displayedArtwork) return;
    timerRef.current = setTimeout(() => {
      advanceToNext();
    }, DWELL_TIME_MS);
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [isActive, displayedArtwork, advanceToNext]);

  const handleClose = useCallback((fromPopstate = false) => {
    if (closingRef.current) return;
    closingRef.current = true;

    // If not triggered by popstate, pop the history entry we pushed
    if (!fromPopstate) {
      window.history.back();
    }

    setFadeOut(true);
    setTimeout(() => {
      onCloseRef.current();
    }, 300);
  }, []);

  // Escape / arrow key handler
  useEffect(() => {
    if (!isActive) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
      else if (e.key === "ArrowLeft") goBack();
      else if (e.key === "ArrowRight") goNext();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isActive, handleClose, goBack, goNext]);

  // Browser back button / mobile back gesture handler
  useEffect(() => {
    if (!isActive) return;
    const handler = () => {
      if (!closingRef.current) {
        handleClose(true);
      }
    };
    window.addEventListener("popstate", handler);
    return () => window.removeEventListener("popstate", handler);
  }, [isActive, handleClose]);

  // Viewport resize handler
  useEffect(() => {
    if (!isActive) return;
    window.addEventListener("resize", updateSquareSize);
    return () => window.removeEventListener("resize", updateSquareSize);
  }, [isActive, updateSquareSize]);

  if (!isActive) return null;
  if (typeof window === "undefined") return null;

  const overlayClass = [
    "wp-overlay",
    fadeIn && !fadeOut ? "wp-visible" : "",
    fadeOut ? "wp-fade-out" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return createPortal(
    <div className={overlayClass}>
      <div className="wp-artwork-area">
        {empty && (
          <div className="wp-empty">No artworks match current filters</div>
        )}
        {/* Double-buffer: two persistent <img> elements. Only the back slot's
            src is changed; onLoad flips it to front. The visible (front) slot
            is never touched, guaranteeing zero-frame-gap transitions. */}
        <img
          key="slot-a"
          src={slotASrc || undefined}
          alt=""
          className="pixel-art wp-buf"
          onLoad={() => handleSlotLoad("a")}
          style={{
            width: squareSize,
            height: squareSize,
            objectFit: "contain",
            zIndex: frontSlot === "a" ? 1 : 0,
          }}
          draggable={false}
        />
        <img
          key="slot-b"
          src={slotBSrc || undefined}
          alt=""
          className="pixel-art wp-buf"
          onLoad={() => handleSlotLoad("b")}
          style={{
            width: squareSize,
            height: squareSize,
            objectFit: "contain",
            zIndex: frontSlot === "b" ? 1 : 0,
          }}
          draggable={false}
        />
      </div>

      <div className="wp-bar">
        <button
          className="wp-bar-btn wp-bar-close"
          onClick={() => handleClose()}
          aria-label="Close Web Player"
        >
          &#x2715;
        </button>
        <div className="wp-bar-nav">
          <button
            className="wp-bar-btn"
            onClick={goBack}
            aria-label="Previous artwork"
          >
            &#x25C0;
          </button>
          <button
            className="wp-bar-btn"
            onClick={goNext}
            aria-label="Next artwork"
          >
            &#x25B6;
          </button>
        </div>
      </div>

      <style jsx>{`
        .wp-overlay {
          position: fixed;
          inset: 0;
          background: #000;
          z-index: 50000;
          display: flex;
          flex-direction: column;
          align-items: center;
          opacity: 0;
          transition: opacity 300ms ease-out;
        }

        .wp-overlay.wp-visible {
          opacity: 1;
        }

        .wp-overlay.wp-fade-out {
          opacity: 0;
        }

        .wp-artwork-area {
          flex: 1;
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 0;
          position: relative;
          width: 100%;
        }

        .wp-artwork-area :global(.wp-buf) {
          position: absolute;
          left: 50%;
          top: 50%;
          transform: translate(-50%, -50%);
          user-select: none;
          -webkit-user-select: none;
          pointer-events: none;
        }

        .wp-bar {
          height: ${WP_BAR_HEIGHT}px;
          width: 100%;
          display: flex;
          align-items: center;
          position: relative;
          flex-shrink: 0;
        }

        .wp-bar-close {
          position: absolute;
          left: 16px;
        }

        .wp-bar-nav {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 32px;
          width: 100%;
        }

        .wp-bar-btn {
          width: 44px;
          height: 44px;
          border-radius: 50%;
          border: none;
          background: rgba(255, 255, 255, 0.1);
          color: rgba(255, 255, 255, 0.6);
          font-size: 18px;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          transition: background 150ms ease, color 150ms ease;
        }

        .wp-bar-btn:hover {
          background: rgba(255, 255, 255, 0.2);
          color: rgba(255, 255, 255, 0.9);
        }

        .wp-empty {
          color: rgba(255, 255, 255, 0.4);
          font-size: 16px;
          text-align: center;
        }
      `}</style>
    </div>,
    document.body,
  );
}
