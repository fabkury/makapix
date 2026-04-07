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

export function WebPlayer({ isActive, onClose, buildApiQuery, baseParams }: WebPlayerProps) {
  const [currentArtwork, setCurrentArtwork] = useState<Artwork | null>(null);
  const [empty, setEmpty] = useState(false);
  const [fadeIn, setFadeIn] = useState(false);
  const [fadeOut, setFadeOut] = useState(false);

  const lastArtworkIdRef = useRef<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closingRef = useRef(false);
  const mountedRef = useRef(false);

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

  const [squareSize, setSquareSize] = useState(0);

  const apiBaseUrl = typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin)
    : "";

  // Compute the largest square that fits the viewport minus wp-bar
  const updateSquareSize = useCallback(() => {
    const availableHeight = window.innerHeight - WP_BAR_HEIGHT;
    setSquareSize(Math.min(window.innerWidth, availableHeight));
  }, []);

  // Display an artwork and manage history
  const displayArtwork = useCallback((artwork: Artwork, addToHistory: boolean) => {
    lastArtworkIdRef.current = artwork.id;
    setCurrentArtwork(artwork);
    setEmpty(false);
    if (addToHistory) {
      // Truncate any forward history beyond current position
      const history = historyRef.current;
      historyRef.current = history.slice(0, historyIndexRef.current + 1);
      historyRef.current.push(artwork);
      // Enforce max history size
      if (historyRef.current.length > MAX_HISTORY) {
        historyRef.current = historyRef.current.slice(-MAX_HISTORY);
      }
      historyIndexRef.current = historyRef.current.length - 1;
    }
  }, []);

  // Fetch a random artwork from the API
  const fetchRandomArtwork = useCallback(async (retryCount = 0) => {
    try {
      const qs = buildApiQueryRef.current(baseParamsRef.current);
      const params = new URLSearchParams(qs);
      params.set("sort", "random");
      params.set("limit", "1");
      params.delete("order");
      params.delete("cursor");
      const url = `${apiBaseUrl}/api/post?${params.toString()}`;
      const response = await authenticatedFetch(url);
      if (!response.ok) return;
      const data = await response.json();
      if (!data.items || data.items.length === 0) {
        setEmpty(true);
        return;
      }
      const artwork: Artwork = {
        id: data.items[0].id,
        art_url: data.items[0].art_url,
        width: data.items[0].width,
        height: data.items[0].height,
      };
      if (artwork.id === lastArtworkIdRef.current && retryCount < MAX_REPEAT_RETRIES) {
        return fetchRandomArtwork(retryCount + 1);
      }
      displayArtwork(artwork, true);
    } catch {
      // Silently ignore fetch errors — WP will retry on next dwell cycle
    }
  }, [apiBaseUrl, displayArtwork]);

  // Reset dwell timer (called after any navigation action)
  const resetDwellTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    timerRef.current = setTimeout(() => {
      fetchRandomArtwork();
    }, DWELL_TIME_MS);
  }, [fetchRandomArtwork]);

  // Navigate to previous artwork in history
  const goBack = useCallback(() => {
    if (historyIndexRef.current <= 0) return;
    historyIndexRef.current -= 1;
    const artwork = historyRef.current[historyIndexRef.current];
    lastArtworkIdRef.current = artwork.id;
    setCurrentArtwork(artwork);
    resetDwellTimer();
  }, [resetDwellTimer]);

  // Navigate to next artwork: forward in history, or fetch new random
  const goNext = useCallback(() => {
    if (historyIndexRef.current < historyRef.current.length - 1) {
      historyIndexRef.current += 1;
      const artwork = historyRef.current[historyIndexRef.current];
      lastArtworkIdRef.current = artwork.id;
      setCurrentArtwork(artwork);
      resetDwellTimer();
    } else {
      fetchRandomArtwork();
    }
  }, [fetchRandomArtwork, resetDwellTimer]);

  // Activation: fade in, fetch first artwork, lock scroll, push history
  useEffect(() => {
    if (!isActive) return;
    mountedRef.current = true;
    closingRef.current = false;

    setFadeIn(false);
    setFadeOut(false);
    setEmpty(false);
    setCurrentArtwork(null);
    lastArtworkIdRef.current = null;
    historyRef.current = [];
    historyIndexRef.current = -1;

    // Lock body scroll
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    // Push history entry so mobile back button closes WP
    window.history.pushState({ wpActive: true }, "");

    // Start fade in on next frame
    requestAnimationFrame(() => {
      if (mountedRef.current) setFadeIn(true);
    });

    // Fetch first artwork
    fetchRandomArtwork();
    updateSquareSize();

    return () => {
      mountedRef.current = false;
      document.body.style.overflow = prevOverflow;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [isActive, fetchRandomArtwork, updateSquareSize]);

  // Dwell timer: fetch next artwork after DWELL_TIME_MS
  useEffect(() => {
    if (!isActive || !currentArtwork) return;
    timerRef.current = setTimeout(() => {
      fetchRandomArtwork();
    }, DWELL_TIME_MS);
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [isActive, currentArtwork, fetchRandomArtwork]);

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

  // Escape key handler
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
  ].filter(Boolean).join(" ");

  return createPortal(
    <div className={overlayClass}>
      <div className="wp-artwork-area">
        {empty && (
          <div className="wp-empty">No artworks match current filters</div>
        )}
        {currentArtwork && (
          <img
            key={currentArtwork.id}
            src={currentArtwork.art_url}
            alt=""
            className="pixel-art"
            style={{
              width: squareSize,
              height: squareSize,
              objectFit: "contain",
            }}
            draggable={false}
          />
        )}
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
        }

        .wp-artwork-area img {
          display: block;
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
    document.body
  );
}
