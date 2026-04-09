import { useState, useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/router";
import { authenticatedFetch, getAccessToken } from "../lib/api";
import { EMOJI_OPTIONS } from "./CommentsAndReactions";
import SPOCommentsOverlay from "./SPOCommentsOverlay";

const DWELL_TIME_MS = 30_000;
const UI_HIDE_MS = 10_000;
const MAX_REPEAT_RETRIES = 3;
const MAX_HISTORY = 64;
const ROTATION_KEY = "wp_rotation";
const ROTATION_OPTIONS = [0, 90, 180, 270] as const;
type RotationAngle = (typeof ROTATION_OPTIONS)[number];

interface ArtworkOwner {
  handle: string;
  avatar_url: string | null;
  public_sqid: string | null;
}

interface ArtworkFile {
  format: string;
  file_bytes: number;
  is_native: boolean;
}

interface Artwork {
  id: number;
  public_sqid: string;
  art_url: string;
  title: string;
  width: number;
  height: number;
  frame_count: number;
  created_at: string;
  files: ArtworkFile[];
  owner: ArtworkOwner | null;
}

interface WebPlayerProps {
  isActive: boolean;
  onClose: () => void;
  buildApiQuery: (baseParams: Record<string, string>) => string;
  baseParams: Record<string, string>;
  channelName?: string;
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

function formatDateTime(isoString: string): string {
  const date = new Date(isoString);
  const year = date.getFullYear();
  const month = date.getMonth() + 1;
  const day = date.getDate();
  const hours = date.getHours().toString().padStart(2, "0");
  const minutes = date.getMinutes().toString().padStart(2, "0");
  return `${year}/${month}/${day} ${hours}:${minutes}`;
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const k = 1000;
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const value = bytes / Math.pow(k, i);
  if (value >= 100) return `${Math.round(value)} ${units[i]}`;
  if (value >= 10) return `${value.toFixed(1)} ${units[i]}`;
  return `${value.toFixed(2)} ${units[i]}`;
}

function resolveAvatarUrl(
  avatarUrl: string | null | undefined,
  apiBase: string,
): string | null {
  if (!avatarUrl) return null;
  if (avatarUrl.startsWith("http")) return avatarUrl;
  return `${apiBase}${avatarUrl}`;
}

interface ReactionTotals {
  totals: Record<string, number>;
  authenticated_totals: Record<string, number>;
  anonymous_totals: Record<string, number>;
  mine: string[];
}

interface WidgetComment {
  id: string;
  author_id: string | null;
  author_ip: string | null;
  parent_id: string | null;
  depth: number;
  body: string;
  hidden_by_mod: boolean;
  deleted_by_owner: boolean;
  created_at: string;
  updated_at: string | null;
  author_handle?: string;
  author_display_name?: string;
  author_avatar_url?: string | null;
  like_count?: number;
  liked_by_me?: boolean;
}

interface WidgetData {
  reactions: ReactionTotals;
  comments: WidgetComment[];
  views_count: number;
}

async function fetchWidgetData(postId: number): Promise<WidgetData | null> {
  const url = `/api/post/${postId}/widget-data`;
  const hasToken = !!getAccessToken();
  try {
    const resp = hasToken
      ? await authenticatedFetch(
          url.startsWith("http") ? url : `${window.location.origin}${url}`,
        )
      : await fetch(url, { credentials: "include" });
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

async function toggleReaction(
  postId: number,
  emoji: string,
  shouldAdd: boolean,
): Promise<void> {
  const encoded = encodeURIComponent(emoji);
  const url = `/api/post/${postId}/reactions/${encoded}`;
  const method = shouldAdd ? "PUT" : "DELETE";
  const hasToken = !!getAccessToken();
  const fullUrl = url.startsWith("http")
    ? url
    : `${window.location.origin}${url}`;
  const resp = hasToken
    ? await authenticatedFetch(fullUrl, { method })
    : await fetch(fullUrl, { method, credentials: "include" });
  if (!resp.ok) {
    const txt = await resp.text().catch(() => "");
    throw new Error(
      `Failed to ${shouldAdd ? "add" : "remove"} reaction: ${resp.status} ${txt}`.trim(),
    );
  }
}

export function WebPlayer({
  isActive,
  onClose,
  buildApiQuery,
  baseParams,
  channelName,
}: WebPlayerProps) {
  const router = useRouter();

  // --- Double-buffer display ---
  const [slotASrc, _setSlotASrc] = useState("");
  const [slotBSrc, _setSlotBSrc] = useState("");
  const [frontSlot, setFrontSlot] = useState<"a" | "b">("a");
  const frontSlotRef = useRef<"a" | "b">("a");
  const slotSrcRefs = useRef({ a: "", b: "" });

  const setSlotASrc = useCallback((url: string) => {
    slotSrcRefs.current.a = url;
    _setSlotASrc(url);
  }, []);
  const setSlotBSrc = useCallback((url: string) => {
    slotSrcRefs.current.b = url;
    _setSlotBSrc(url);
  }, []);

  // Artwork metadata for the currently displayed piece
  const [displayedArtwork, setDisplayedArtwork] = useState<Artwork | null>(
    null,
  );

  const [empty, setEmpty] = useState(false);
  const [fadeIn, setFadeIn] = useState(false);
  const [fadeOut, setFadeOut] = useState(false);

  // UI visibility (Mode A vs Mode B)
  const [uiVisible, setUiVisible] = useState(true);
  const uiTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Grace period: after manual hide, ignore mouse/touch for 5s
  const hideGraceUntilRef = useRef(0);

  // Dwell timer paused state
  const [paused, setPaused] = useState(false);
  const pausedRef = useRef(false);

  // Three-dot menu
  const [menuOpen, setMenuOpen] = useState(false);
  const [formatSubOpen, setFormatSubOpen] = useState(false);
  const subPanelTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Screen rotation
  const [rotation, setRotation] = useState<RotationAngle>(() => {
    if (typeof window === "undefined") return 0;
    const stored = localStorage.getItem(ROTATION_KEY);
    const val = stored ? Number(stored) : 0;
    return ROTATION_OPTIONS.includes(val as RotationAngle)
      ? (val as RotationAngle)
      : 0;
  });
  const rotationRef = useRef(rotation);
  rotationRef.current = rotation;

  // Reactions & comments
  const [widgetData, setWidgetData] = useState<WidgetData | null>(null);
  const widgetCacheRef = useRef<Map<number, WidgetData>>(new Map());
  const reactionInFlightRef = useRef(false);
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [isModerator, setIsModerator] = useState(false);

  const lastArtworkIdRef = useRef<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closingRef = useRef(false);
  const mountedRef = useRef(false);

  // Prefetch-ahead
  const prefetchedRef = useRef<Artwork | null>(null);
  const prefetchingRef = useRef(false);
  const prefetchCancelledRef = useRef(false);

  // History
  const historyRef = useRef<Artwork[]>([]);
  const historyIndexRef = useRef(-1);

  // Stabilize props via refs
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

  // --- UI auto-hide ---

  const clearUiTimer = useCallback(() => {
    if (uiTimerRef.current) {
      clearTimeout(uiTimerRef.current);
      uiTimerRef.current = null;
    }
  }, []);

  const startUiTimer = useCallback(() => {
    clearUiTimer();
    uiTimerRef.current = setTimeout(() => {
      if (mountedRef.current) setUiVisible(false);
    }, UI_HIDE_MS);
  }, [clearUiTimer]);

  const revealUi = useCallback(() => {
    if (Date.now() < hideGraceUntilRef.current) return;
    setUiVisible(true);
    startUiTimer();
  }, [startUiTimer]);

  const toggleUi = useCallback(() => {
    if (Date.now() < hideGraceUntilRef.current) return;
    setUiVisible((prev) => {
      if (prev) {
        clearUiTimer();
        hideGraceUntilRef.current = Date.now() + 1000;
        return false;
      } else {
        startUiTimer();
        return true;
      }
    });
  }, [clearUiTimer, startUiTimer]);

  // --- Artwork sizing (full viewport in Mode A, inset in Mode B) ---

  const computeSize = useCallback(
    (uiShown: boolean) => {
      if (!displayedArtwork) return { w: 0, h: 0 };
      const swapped = rotationRef.current === 90 || rotationRef.current === 270;
      const vw = swapped ? window.innerHeight : window.innerWidth;
      const vh = swapped ? window.innerWidth : window.innerHeight;
      const aw = displayedArtwork.width;
      const ah = displayedArtwork.height;
      const availW = vw;
      const availH = uiShown ? vh : vh;
      // Scale to fit within viewport while preserving aspect ratio.
      const scale = Math.min(availW / aw, availH / ah);
      return { w: Math.round(aw * scale), h: Math.round(ah * scale) };
    },
    [displayedArtwork],
  );

  const [artSize, setArtSize] = useState({ w: 0, h: 0 });

  const updateArtSize = useCallback(() => {
    setArtSize(computeSize(uiVisible));
  }, [computeSize, uiVisible]);

  // Recalc when artwork, viewport, UI visibility, or rotation changes
  useEffect(() => {
    if (!isActive || !displayedArtwork) return;
    updateArtSize();
  }, [isActive, displayedArtwork, uiVisible, rotation, updateArtSize]);

  // --- Double-buffer helpers ---

  const handleSlotLoad = useCallback((slot: "a" | "b") => {
    if (slot !== frontSlotRef.current) {
      frontSlotRef.current = slot;
      setFrontSlot(slot);
    }
  }, []);

  const showOnBackBuffer = useCallback(
    (artwork: Artwork) => {
      const back: "a" | "b" = frontSlotRef.current === "a" ? "b" : "a";
      const backSrc = slotSrcRefs.current[back];
      const setBack = back === "a" ? setSlotASrc : setSlotBSrc;

      if (backSrc === artwork.art_url) {
        frontSlotRef.current = back;
        setFrontSlot(back);
      } else {
        setBack(artwork.art_url);
      }
    },
    [setSlotASrc, setSlotBSrc],
  );

  const showArtwork = useCallback(
    (artwork: Artwork, addToHistory: boolean) => {
      lastArtworkIdRef.current = artwork.id;
      setDisplayedArtwork(artwork);
      setEmpty(false);
      setCommentsOpen(false);
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
        const item = data.items[0];
        const artwork: Artwork = {
          id: item.id,
          public_sqid: item.public_sqid,
          art_url: item.art_url,
          title: item.title || "",
          width: item.width,
          height: item.height,
          frame_count: item.frame_count ?? 1,
          created_at: item.created_at,
          files: item.files ?? [],
          owner: item.owner
            ? {
                handle: item.owner.handle,
                avatar_url: item.owner.avatar_url ?? null,
                public_sqid: item.owner.public_sqid ?? null,
              }
            : null,
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
      } catch {}
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

  const advanceToNext = useCallback(async () => {
    if (!mountedRef.current) return;

    if (prefetchedRef.current) {
      const artwork = prefetchedRef.current;
      prefetchedRef.current = null;
      prefetchingRef.current = false;
      showArtwork(artwork, true);
      startPrefetch();
      return;
    }

    cancelPrefetch();
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
  }, [showArtwork, fetchArtworkMetadata, startPrefetch, cancelPrefetch]);

  const goBack = useCallback(async () => {
    if (historyIndexRef.current <= 0) return;
    historyIndexRef.current -= 1;
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
  }, [showOnBackBuffer, cancelPrefetch, startPrefetch]);

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

  const togglePause = useCallback(() => {
    setPaused((prev) => {
      const next = !prev;
      pausedRef.current = next;
      return next;
    });
  }, []);

  // --- Reactions ---

  const handleReactionClick = useCallback(
    async (emoji: string) => {
      if (!displayedArtwork || reactionInFlightRef.current) return;
      reactionInFlightRef.current = true;
      try {
        const isActive = widgetData?.reactions.mine.includes(emoji) || false;
        const next = !isActive;

        // Optimistic update
        if (widgetData) {
          const newMine = next
            ? [...widgetData.reactions.mine, emoji]
            : widgetData.reactions.mine.filter((e) => e !== emoji);
          const newTotals = { ...widgetData.reactions.totals };
          newTotals[emoji] = Math.max(
            0,
            (newTotals[emoji] || 0) + (next ? 1 : -1),
          );
          const updated: WidgetData = {
            ...widgetData,
            reactions: { ...widgetData.reactions, mine: newMine, totals: newTotals },
          };
          setWidgetData(updated);
          widgetCacheRef.current.set(displayedArtwork.id, updated);
        }

        await toggleReaction(displayedArtwork.id, emoji, next);

        // Re-fetch to sync
        const data = await fetchWidgetData(displayedArtwork.id);
        if (data) {
          setWidgetData(data);
          widgetCacheRef.current.set(displayedArtwork.id, data);
        }
      } catch (err) {
        console.error("Failed to toggle reaction:", err);
        const data = await fetchWidgetData(displayedArtwork.id);
        if (data) {
          setWidgetData(data);
          widgetCacheRef.current.set(displayedArtwork.id, data);
        }
      } finally {
        reactionInFlightRef.current = false;
      }
    },
    [displayedArtwork, widgetData],
  );

  // --- Three-dot menu helpers ---

  const closeMenu = useCallback(() => {
    setMenuOpen(false);
    setFormatSubOpen(false);
    if (subPanelTimerRef.current) {
      clearTimeout(subPanelTimerRef.current);
      subPanelTimerRef.current = null;
    }
  }, []);

  const closeSubDelayed = useCallback((delay = 300) => {
    if (subPanelTimerRef.current) clearTimeout(subPanelTimerRef.current);
    subPanelTimerRef.current = setTimeout(() => setFormatSubOpen(false), delay);
  }, []);

  const openSub = useCallback(() => {
    if (subPanelTimerRef.current) clearTimeout(subPanelTimerRef.current);
    setFormatSubOpen(true);
  }, []);

  const handleRotation = useCallback(
    (angle: RotationAngle) => {
      if (angle === rotationRef.current) {
        closeMenu();
        return;
      }
      closeMenu();
      if (!window.confirm(`Rotate display to ${angle}°?`)) return;
      setRotation(angle);
      rotationRef.current = angle;
      localStorage.setItem(ROTATION_KEY, String(angle));
    },
    [closeMenu],
  );

  const handleEditInPiskel = useCallback(() => {
    if (!displayedArtwork) return;
    closeMenu();
    router.push(`/editor?edit=${displayedArtwork.public_sqid}`);
  }, [displayedArtwork, closeMenu, router]);

  const handleEditInPixelc = useCallback(() => {
    if (!displayedArtwork) return;
    closeMenu();
    router.push(`/pixelc?edit=${displayedArtwork.public_sqid}`);
  }, [displayedArtwork, closeMenu, router]);

  const handleDownloadNative = useCallback(async () => {
    if (!displayedArtwork) return;
    closeMenu();
    try {
      const resp = await fetch(`/api/d/${displayedArtwork.public_sqid}`);
      if (!resp.ok) throw new Error("Download failed");
      const blob = await resp.blob();
      const nf = displayedArtwork.files?.find((f) => f.is_native) || displayedArtwork.files?.[0];
      const ext = nf?.format || "png";
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${displayedArtwork.title || displayedArtwork.public_sqid}.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Download failed:", err);
    }
  }, [displayedArtwork, closeMenu]);

  const handleDownloadUpscaled = useCallback(async () => {
    if (!displayedArtwork) return;
    closeMenu();
    try {
      const resp = await fetch(`/api/d/${displayedArtwork.public_sqid}/upscaled`);
      if (!resp.ok) throw new Error("Download failed");
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${displayedArtwork.title || displayedArtwork.public_sqid}_upscaled.webp`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Download failed:", err);
    }
  }, [displayedArtwork, closeMenu]);

  const handleDownloadFormat = useCallback(
    async (format: string) => {
      if (!displayedArtwork) return;
      closeMenu();
      try {
        const resp = await fetch(`/api/d/${displayedArtwork.public_sqid}.${format}`);
        if (!resp.ok) throw new Error("Download failed");
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${displayedArtwork.title || displayedArtwork.public_sqid}.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } catch (err) {
        console.error("Download failed:", err);
      }
    },
    [displayedArtwork, closeMenu],
  );

  const handleShareUpscaled = useCallback(async () => {
    if (!displayedArtwork) return;
    closeMenu();
    try {
      const resp = await fetch(`/api/d/${displayedArtwork.public_sqid}/upscaled`);
      if (!resp.ok) throw new Error("Fetch failed");
      const blob = await resp.blob();
      const file = new File(
        [blob],
        `${displayedArtwork.title || displayedArtwork.public_sqid}_upscaled.webp`,
        { type: "image/webp" },
      );
      if (navigator.share && navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: displayedArtwork.title });
      } else {
        const postUrl = `${window.location.origin}/p/${displayedArtwork.public_sqid}`;
        await navigator.clipboard.writeText(postUrl);
        alert("Link copied to clipboard");
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        console.error("Share failed:", err);
      }
    }
  }, [displayedArtwork, closeMenu]);

  const handleShareNative = useCallback(async () => {
    if (!displayedArtwork) return;
    closeMenu();
    try {
      const resp = await fetch(`/api/d/${displayedArtwork.public_sqid}`);
      if (!resp.ok) throw new Error("Fetch failed");
      const blob = await resp.blob();
      const nf = displayedArtwork.files?.find((f) => f.is_native) || displayedArtwork.files?.[0];
      const ext = nf?.format || "png";
      const mimeType = ext === "webp" ? "image/webp" : ext === "gif" ? "image/gif" : "image/png";
      const file = new File(
        [blob],
        `${displayedArtwork.title || displayedArtwork.public_sqid}.${ext}`,
        { type: mimeType },
      );
      if (navigator.share && navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: displayedArtwork.title });
      } else {
        const postUrl = `${window.location.origin}/p/${displayedArtwork.public_sqid}`;
        await navigator.clipboard.writeText(postUrl);
        alert("Link copied to clipboard");
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        console.error("Share failed:", err);
      }
    }
  }, [displayedArtwork, closeMenu]);

  // --- Close & navigation helpers ---

  const handleClose = useCallback(
    (fromPopstate = false) => {
      if (closingRef.current) return;
      closingRef.current = true;
      if (!fromPopstate) window.history.back();
      setFadeOut(true);
      setTimeout(() => {
        onCloseRef.current();
      }, 300);
    },
    [],
  );

  /** Close WP and navigate to a route. */
  const navigateTo = useCallback(
    (href: string) => {
      if (closingRef.current) return;
      closingRef.current = true;
      // Pop the history entry we pushed, then navigate.
      window.history.back();
      setFadeOut(true);
      setTimeout(() => {
        onCloseRef.current();
        router.push(href);
      }, 300);
    },
    [router],
  );

  // --- Effects ---

  // Activation
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
    setUiVisible(true);
    setPaused(false);
    pausedRef.current = false;
    setMenuOpen(false);
    setFormatSubOpen(false);
    setWidgetData(null);
    widgetCacheRef.current.clear();
    setCommentsOpen(false);

    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.history.pushState({ wpActive: true }, "");

    requestAnimationFrame(() => {
      if (mountedRef.current) setFadeIn(true);
    });

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

    return () => {
      mountedRef.current = false;
      document.body.style.overflow = prevOverflow;
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      clearUiTimer();
      cancelPrefetch();
    };
  }, [isActive, fetchArtworkMetadata, showArtwork, startPrefetch, cancelPrefetch, clearUiTimer, setSlotASrc, setSlotBSrc]);

  // Start the UI auto-hide timer when UI is shown (pause when menu/comments open)
  useEffect(() => {
    if (!isActive || !uiVisible) return;
    if (menuOpen || commentsOpen) {
      clearUiTimer();
      return;
    }
    startUiTimer();
    return clearUiTimer;
  }, [isActive, uiVisible, menuOpen, commentsOpen, startUiTimer, clearUiTimer]);

  // Dwell timer (respects pause)
  useEffect(() => {
    if (!isActive || !displayedArtwork || paused) return;
    timerRef.current = setTimeout(() => {
      advanceToNext();
    }, DWELL_TIME_MS);
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [isActive, displayedArtwork, paused, advanceToNext]);

  // Keyboard
  useEffect(() => {
    if (!isActive) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
      else if (e.key === "ArrowLeft") goBack();
      else if (e.key === "ArrowRight") goNext();
      else if (e.key === " ") {
        e.preventDefault();
        togglePause();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isActive, handleClose, goBack, goNext, togglePause]);

  // Popstate (mobile back button)
  useEffect(() => {
    if (!isActive) return;
    const handler = () => {
      if (!closingRef.current) handleClose(true);
    };
    window.addEventListener("popstate", handler);
    return () => window.removeEventListener("popstate", handler);
  }, [isActive, handleClose]);

  // Viewport resize
  useEffect(() => {
    if (!isActive) return;
    const handler = () => updateArtSize();
    window.addEventListener("resize", handler);
    return () => window.removeEventListener("resize", handler);
  }, [isActive, updateArtSize]);

  // Mouse movement → reveal UI; click/tap → toggle UI
  useEffect(() => {
    if (!isActive) return;
    let touchedRecently = false;
    let touchTimer: ReturnType<typeof setTimeout> | null = null;
    const isInteractive = (e: Event) => {
      const t = e.target as HTMLElement;
      return !!t.closest("button, a, input, select, textarea");
    };
    const onMouseMove = () => {
      if (mountedRef.current && !closingRef.current) revealUi();
    };
    const onTouchEnd = (e: TouchEvent) => {
      if (!mountedRef.current || closingRef.current) return;
      if (isInteractive(e)) return;
      touchedRecently = true;
      if (touchTimer) clearTimeout(touchTimer);
      touchTimer = setTimeout(() => { touchedRecently = false; }, 500);
      toggleUi();
    };
    const onClick = (e: MouseEvent) => {
      if (touchedRecently) return; // already handled by touchend
      if (!mountedRef.current || closingRef.current) return;
      if (isInteractive(e)) return;
      toggleUi();
    };
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("touchend", onTouchEnd);
    window.addEventListener("click", onClick);
    return () => {
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("touchend", onTouchEnd);
      window.removeEventListener("click", onClick);
      if (touchTimer) clearTimeout(touchTimer);
    };
  }, [isActive, revealUi, toggleUi]);

  // Fetch widget data (reactions/comments) when artwork changes
  useEffect(() => {
    if (!isActive || !displayedArtwork) return;
    const cached = widgetCacheRef.current.get(displayedArtwork.id);
    if (cached) {
      setWidgetData(cached);
    } else {
      setWidgetData(null);
      (async () => {
        const data = await fetchWidgetData(displayedArtwork.id);
        if (data && mountedRef.current) {
          setWidgetData(data);
          widgetCacheRef.current.set(displayedArtwork.id, data);
        }
      })();
    }
  }, [isActive, displayedArtwork]);

  // Fetch current user info for comments overlay
  useEffect(() => {
    if (!isActive) return;
    const userId = localStorage.getItem("user_id");
    setCurrentUserId(userId);
    const token = getAccessToken();
    if (token) {
      authenticatedFetch(
        `${apiBaseUrl}/api/auth/me`,
      )
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data?.roles) {
            const roles = data.roles as string[];
            setIsModerator(
              roles.includes("moderator") || roles.includes("owner"),
            );
          }
        })
        .catch(() => {});
    }
  }, [isActive, apiBaseUrl]);

  if (!isActive) return null;
  if (typeof window === "undefined") return null;

  const overlayClass = [
    "wp-overlay",
    fadeIn && !fadeOut ? "wp-visible" : "",
    fadeOut ? "wp-fade-out" : "",
    uiVisible ? "wp-cursor" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const art = displayedArtwork;
  const nativeFile = art?.files?.find((f) => f.is_native);
  const totalComments = widgetData?.comments?.length ?? 0;
  const ownerHref = art?.owner?.public_sqid
    ? `/u/${art.owner.public_sqid}`
    : null;
  const avatarSrc = resolveAvatarUrl(art?.owner?.avatar_url, apiBaseUrl);

  const rotationStyle: React.CSSProperties =
    rotation === 0
      ? {}
      : rotation === 180
        ? { transform: "rotate(180deg)" }
        : {
            // 90 or 270: swap dimensions and center
            width: "100vh",
            height: "100vw",
            top: "50%",
            left: "50%",
            inset: "auto",
            transform: `translate(-50%, -50%) rotate(${rotation}deg)`,
          };

  return createPortal(
    <div className={overlayClass} style={rotationStyle}>
      <div className="wp-artwork-area">
        {empty && (
          <div className="wp-empty">No artworks match current filters</div>
        )}
        <img
          key="slot-a"
          src={slotASrc || undefined}
          alt=""
          className="pixel-art wp-buf"
          onLoad={() => handleSlotLoad("a")}
          style={{
            width: artSize.w,
            height: artSize.h,
            zIndex: frontSlot === "a" ? 1 : 0,
            visibility: frontSlot === "a" ? "visible" : "hidden",
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
            width: artSize.w,
            height: artSize.h,
            zIndex: frontSlot === "b" ? 1 : 0,
            visibility: frontSlot === "b" ? "visible" : "hidden",
          }}
          draggable={false}
        />
      </div>

      {/* --- Mode B: overlay UI --- */}
      <div className={`wp-ui${uiVisible ? " wp-ui-show" : ""}`}>
        {/* Top bar: channel + close */}
        <div className="wp-top">
          {channelName && (
            <span className="wp-channel">{channelName}</span>
          )}
          <div className="wp-top-btns">
            <button
              className="wp-btn"
              onClick={() => {
                clearUiTimer();
                setUiVisible(false);
                hideGraceUntilRef.current = Date.now() + 3000;
              }}
              aria-label="Hide controls"
            >
              &#x25A3;
            </button>
            <button
              className="wp-btn"
              onClick={() => handleClose()}
              aria-label="Close Web Player"
            >
              &#x2715;
            </button>
          </div>
        </div>

        {/* Bottom bar: artist info, artwork info, controls */}
        <div className="wp-bottom">
          {/* Artist row */}
          {art?.owner && (
            <div className="wp-artist-row">
              {ownerHref ? (
                <a
                  className="wp-avatar-link"
                  onClick={(e) => {
                    e.preventDefault();
                    navigateTo(ownerHref);
                  }}
                  href={ownerHref}
                >
                  {avatarSrc ? (
                    <img
                      src={avatarSrc}
                      alt={art.owner!.handle}
                      className="wp-avatar"
                    />
                  ) : (
                    <div className="wp-avatar wp-avatar-placeholder">
                      <svg
                        width="18"
                        height="18"
                        viewBox="0 0 24 24"
                        fill="currentColor"
                      >
                        <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
                      </svg>
                    </div>
                  )}
                </a>
              ) : (
                <div className="wp-avatar wp-avatar-placeholder">
                  <svg
                    width="18"
                    height="18"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                  >
                    <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
                  </svg>
                </div>
              )}
              <div className="wp-artist-info">
                {ownerHref ? (
                  <a
                    className="wp-artist-name"
                    href={ownerHref}
                    onClick={(e) => {
                      e.preventDefault();
                      navigateTo(ownerHref);
                    }}
                  >
                    {art.owner!.handle}
                  </a>
                ) : (
                  <span className="wp-artist-name">
                    {art.owner!.handle}
                  </span>
                )}
                {art.title && (
                  <a
                    className="wp-art-title"
                    href={`/p/${art.public_sqid}`}
                    onClick={(e) => {
                      e.preventDefault();
                      navigateTo(`/p/${art.public_sqid}`);
                    }}
                  >
                    {art.title}
                  </a>
                )}
              </div>
            </div>
          )}

          {/* Technical info */}
          {art && (
            <div className="wp-tech">
              <span>{formatDateTime(art.created_at)}</span>
              <span className="wp-tech-dot">&bull;</span>
              <span>
                <span
                  className={
                    art.frame_count > 256 ? "wp-tech-warn" : undefined
                  }
                >
                  {art.frame_count}
                </span>
                &times;({art.width}&times;{art.height})
              </span>
              {nativeFile && (
                <>
                  <span className="wp-tech-dot">&bull;</span>
                  <span>
                    {formatFileSize(nativeFile.file_bytes)}{" "}
                    {nativeFile.format.toUpperCase()}
                  </span>
                </>
              )}
            </div>
          )}

          {/* Emoji reactions */}
          {art && (
            <div className="wp-reactions">
              {EMOJI_OPTIONS.map((emoji) => {
                const count =
                  widgetData?.reactions.totals[emoji] || 0;
                const active =
                  widgetData?.reactions.mine.includes(emoji) || false;
                return (
                  <button
                    key={emoji}
                    className={`wp-reaction${active ? " wp-reaction-active" : ""}`}
                    onClick={() => handleReactionClick(emoji)}
                  >
                    <span>{emoji}</span>
                    {count > 0 && (
                      <span className="wp-reaction-count">{count}</span>
                    )}
                  </button>
                );
              })}
              <button
                className="wp-reaction wp-comment-btn"
                onClick={() => setCommentsOpen(true)}
                aria-label="Open comments"
              >
                <span>&#x1F4AC;</span>
                {totalComments > 0 && (
                  <span className="wp-reaction-count">{totalComments}</span>
                )}
              </button>
            </div>
          )}

          {/* Controls */}
          <div className="wp-controls">
            <button
              className="wp-btn"
              onClick={goBack}
              aria-label="Previous artwork"
            >
              &#x25C0;
            </button>
            <button
              className="wp-btn"
              onClick={togglePause}
              aria-label={paused ? "Resume auto-advance" : "Pause auto-advance"}
            >
              {paused ? "\u25B6" : "\u2759\u2759"}
            </button>
            <button
              className="wp-btn"
              onClick={goNext}
              aria-label="Next artwork"
            >
              &#x25B6;
            </button>
            <button
              className="wp-btn wp-more-btn"
              onClick={() => setMenuOpen(!menuOpen)}
              aria-label="More options"
            >
              &#8942;
            </button>
          </div>
        </div>
      </div>

      {/* Three-dot menu */}
      {menuOpen && art && (
        <div className="wp-menu-overlay" onClick={closeMenu}>
          <div
            className="wp-menu"
            onClick={(e) => e.stopPropagation()}
          >
            <button className="wp-menu-item wp-menu-disabled">
              Use as profile photo
            </button>
            <button className="wp-menu-item wp-menu-disabled">
              Add to my favorites
            </button>

            <div className="wp-menu-sep" />

            <button className="wp-menu-item" onClick={handleEditInPiskel}>
              Edit in Piskel
            </button>
            {["png", "webp", "gif", "bmp"].includes(
              (art.files?.find((f) => f.is_native)?.format || "").toLowerCase(),
            ) ? (
              <button className="wp-menu-item" onClick={handleEditInPixelc}>
                Edit in Pixelc
              </button>
            ) : (
              <button className="wp-menu-item wp-menu-disabled">
                Edit in Pixelc
              </button>
            )}

            <div className="wp-menu-sep" />

            <button className="wp-menu-item" onClick={handleShareUpscaled}>
              Share upscaled
            </button>
            <button className="wp-menu-item" onClick={handleShareNative}>
              Share native size
            </button>

            <div className="wp-menu-sep" />

            <button className="wp-menu-item" onClick={handleDownloadUpscaled}>
              Download upscaled
            </button>
            <div
              className="wp-menu-sub-wrap"
              onMouseEnter={openSub}
              onMouseLeave={() => closeSubDelayed()}
            >
              <button
                className="wp-menu-item wp-menu-item-sub"
                onClick={() =>
                  formatSubOpen ? setFormatSubOpen(false) : openSub()
                }
              >
                <span>Download alternative format</span>
                <span>{formatSubOpen ? "\u25BC" : "\u25C0"}</span>
              </button>
              {formatSubOpen && (
                <div
                  className="wp-submenu"
                  onMouseEnter={openSub}
                  onMouseLeave={() => closeSubDelayed()}
                >
                  {art.files
                    .filter((f) => !f.is_native)
                    .map((f) => (
                      <button
                        key={f.format}
                        className="wp-menu-item"
                        onClick={() => handleDownloadFormat(f.format)}
                      >
                        {f.format.toUpperCase()}
                      </button>
                    ))}
                  {art.files.filter((f) => !f.is_native).length === 0 && (
                    <span className="wp-menu-item wp-menu-disabled">
                      No alternative formats
                    </span>
                  )}
                </div>
              )}
            </div>
            <button className="wp-menu-item" onClick={handleDownloadNative}>
              Download native format
            </button>

            <div className="wp-menu-sep" />

            <div className="wp-rotation-group">
              <span className="wp-rotation-label">Rotate display</span>
              <div className="wp-rotation-options">
                {ROTATION_OPTIONS.map((angle) => (
                  <button
                    key={angle}
                    className={`wp-rotation-btn${rotation === angle ? " wp-rotation-active" : ""}`}
                    onClick={() => handleRotation(angle)}
                  >
                    {angle}°
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Comments overlay */}
      {art && (
        <SPOCommentsOverlay
          postId={art.id}
          isOpen={commentsOpen}
          onClose={() => setCommentsOpen(false)}
          currentUserId={currentUserId}
          isModerator={isModerator}
          initialComments={widgetData?.comments || []}
        />
      )}

      <style jsx>{`
        .wp-overlay {
          position: fixed;
          inset: 0;
          background: #000;
          z-index: 50000;
          display: flex;
          align-items: center;
          justify-content: center;
          opacity: 0;
          transition: opacity 300ms ease-out;
          cursor: none;
        }

        .wp-overlay.wp-visible {
          opacity: 1;
        }

        .wp-overlay.wp-fade-out {
          opacity: 0;
        }

        .wp-overlay.wp-cursor {
          cursor: default;
        }

        .wp-artwork-area {
          position: absolute;
          inset: 0;
          display: flex;
          align-items: center;
          justify-content: center;
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

        /* --- Mode B overlay UI --- */
        .wp-ui {
          position: absolute;
          inset: 0;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          z-index: 2;
          pointer-events: none;
          opacity: 0;
          transition: opacity 400ms ease;
        }

        .wp-ui.wp-ui-show {
          opacity: 1;
        }

        .wp-ui.wp-ui-show > * {
          pointer-events: auto;
        }

        /* Top bar */
        .wp-top {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 12px 16px;
          background: linear-gradient(
            to bottom,
            rgba(0, 0, 0, 0.7) 0%,
            rgba(0, 0, 0, 0) 100%
          );
        }

        .wp-channel {
          color: rgba(255, 255, 255, 0.6);
          font-size: 13px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          max-width: calc(100% - 56px);
        }

        .wp-top-btns {
          display: flex;
          gap: 8px;
          margin-left: auto;
          flex-shrink: 0;
        }

        /* Bottom bar */
        .wp-bottom {
          display: flex;
          flex-direction: column;
          gap: 10px;
          padding: 16px;
          background: linear-gradient(
            to top,
            rgba(0, 0, 0, 0.7) 0%,
            rgba(0, 0, 0, 0) 100%
          );
        }

        /* Artist row */
        .wp-artist-row {
          display: flex;
          align-items: center;
          gap: 10px;
        }

        .wp-avatar-link {
          flex-shrink: 0;
          text-decoration: none;
          cursor: pointer;
        }

        .wp-avatar {
          width: 36px;
          height: 36px;
          border-radius: 50%;
          object-fit: cover;
          display: block;
        }

        .wp-avatar-placeholder {
          background: #1a1a24;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #6a6a80;
        }

        .wp-artist-info {
          display: flex;
          flex-direction: column;
          gap: 2px;
          min-width: 0;
        }

        .wp-artist-name {
          color: rgba(255, 255, 255, 0.9);
          font-size: 14px;
          font-weight: 600;
          text-decoration: none;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          cursor: pointer;
        }

        .wp-artist-name:hover {
          text-decoration: underline;
        }

        .wp-art-title {
          color: rgba(255, 255, 255, 0.5);
          font-size: 12px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          text-decoration: none;
          cursor: pointer;
        }

        .wp-art-title:hover {
          text-decoration: underline;
        }

        /* Technical info */
        .wp-tech {
          color: rgba(255, 255, 255, 0.4);
          font-size: 12px;
          display: flex;
          align-items: center;
          gap: 0;
          flex-wrap: wrap;
        }

        .wp-tech-dot {
          margin: 0 6px;
          opacity: 0.5;
        }

        .wp-tech-warn {
          color: #ff8080;
        }

        /* Controls */
        .wp-controls {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 24px;
          padding-top: 4px;
        }

        /* Shared button style */
        .wp-btn {
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
          -webkit-tap-highlight-color: transparent;
        }

        .wp-btn:hover {
          background: rgba(255, 255, 255, 0.2);
          color: rgba(255, 255, 255, 0.9);
        }

        /* Emoji reactions */
        .wp-reactions {
          display: flex;
          align-items: center;
          gap: 6px;
          flex-wrap: wrap;
        }

        .wp-reaction {
          display: flex;
          align-items: center;
          gap: 4px;
          padding: 4px 8px;
          border-radius: 16px;
          border: 1.5px solid transparent;
          background: rgba(255, 255, 255, 0.08);
          color: rgba(255, 255, 255, 0.7);
          font-size: 16px;
          cursor: pointer;
          transition: border-color 150ms ease, background 150ms ease;
          -webkit-tap-highlight-color: transparent;
        }

        .wp-reaction:hover {
          background: rgba(255, 255, 255, 0.14);
        }

        .wp-reaction-active {
          border-color: #00d4ff;
          background: rgba(0, 212, 255, 0.15);
        }

        .wp-reaction-count {
          font-size: 12px;
          color: rgba(255, 255, 255, 0.6);
          min-width: 8px;
          text-align: center;
        }

        .wp-comment-btn {
          margin-left: 4px;
        }

        /* Three-dot menu button */
        .wp-more-btn {
          position: absolute;
          right: 16px;
        }

        /* Menu overlay */
        .wp-menu-overlay {
          position: fixed;
          inset: 0;
          z-index: 50001;
        }

        .wp-menu {
          position: absolute;
          bottom: 80px;
          right: 16px;
          background: #1a1a24;
          border: 1px solid rgba(255, 255, 255, 0.15);
          border-radius: 8px;
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
          min-width: 200px;
          padding: 4px 0;
          max-height: 70vh;
          overflow-y: auto;
        }

        .wp-menu-item {
          display: block;
          width: 100%;
          padding: 10px 16px;
          background: none;
          border: none;
          color: #e8e8f0;
          font-size: 14px;
          text-align: left;
          cursor: pointer;
          white-space: nowrap;
        }

        .wp-menu-item:hover {
          background: rgba(255, 255, 255, 0.08);
        }

        .wp-menu-item.wp-menu-disabled {
          color: #6a6a80;
          cursor: not-allowed;
        }

        .wp-menu-item.wp-menu-disabled:hover {
          background: none;
        }

        .wp-menu-item-sub {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 12px;
        }

        .wp-menu-sep {
          height: 1px;
          background: rgba(255, 255, 255, 0.1);
          margin: 4px 0;
        }

        .wp-menu-sub-wrap {
          position: relative;
        }

        .wp-submenu {
          position: absolute;
          right: 100%;
          top: 0;
          background: #1a1a24;
          border: 1px solid rgba(255, 255, 255, 0.15);
          border-radius: 8px;
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
          min-width: 140px;
          padding: 4px 0;
        }

        /* Rotation menu */
        .wp-rotation-group {
          padding: 8px 16px;
        }

        .wp-rotation-label {
          display: block;
          font-size: 12px;
          color: rgba(255, 255, 255, 0.4);
          margin-bottom: 6px;
        }

        .wp-rotation-options {
          display: flex;
          gap: 6px;
        }

        .wp-rotation-btn {
          flex: 1;
          padding: 6px 0;
          border: 1px solid rgba(255, 255, 255, 0.15);
          border-radius: 4px;
          background: none;
          color: #e8e8f0;
          font-size: 13px;
          cursor: pointer;
        }

        .wp-rotation-btn:hover {
          background: rgba(255, 255, 255, 0.08);
        }

        .wp-rotation-btn.wp-rotation-active {
          border-color: #00d4ff;
          color: #00d4ff;
          background: rgba(0, 212, 255, 0.1);
        }

        .wp-empty {
          color: rgba(255, 255, 255, 0.4);
          font-size: 16px;
          text-align: center;
          z-index: 1;
        }
      `}</style>
    </div>,
    document.body,
  );
}
