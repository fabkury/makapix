import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/router';
import SparkMD5 from 'spark-md5';
import Layout from '../components/Layout';
import { authenticatedFetch, clearTokens } from '../lib/api';
import type { DivoomGalleryInfo, DivoomSession } from '../lib/divoom/divoomApi';
import { divoomLogin, downloadDivoomDat, fetchMyUploads, DivoomApiError } from '../lib/divoom/divoomApi';
import { PyodideDecoder } from '../lib/divoom/pyodideDecoder';

// SharedArrayBuffer requires COOP/COEP headers which are only applied on full page loads.
// Client-side navigation (router.push) retains the previous page's security context.
// Detect this and force a hard refresh to obtain the correct headers.
function useEnforceCrossOriginIsolation() {
  const [isReloading, setIsReloading] = useState(false);

  useEffect(() => {
    // Skip during SSR
    if (typeof window === 'undefined') return;

    // crossOriginIsolated is true when COOP+COEP headers are active
    if (!window.crossOriginIsolated) {
      setIsReloading(true);
      // Hard refresh to get proper headers from server
      window.location.reload();
    }
  }, []);

  return isReloading;
}

interface UploadedArtwork {
  id: number;
  public_sqid: string;
  title: string;
  art_url: string;
  canvas: string;
  width: number;
  height: number;
  public_visibility: boolean;
}

const PAGE_SIZE = 20;
const MAX_TITLE_LEN = 200;
const MAX_DESC_LEN = 5000;
const MAX_REFRESH_BLOCKS = 200; // safety guard against infinite loops
const SHORT_PAGE_RETRIES = 2;
const MAX_CONSECUTIVE_NO_NEW_PAGES = 5; // stop if API keeps returning duplicates
const STALL_ABORT_MS = 4000;

function yieldToBrowser(): Promise<void> {
  // Allow React to paint during long fetch loops
  return new Promise((resolve) => setTimeout(resolve, 0));
}

type SortField = 'name' | 'size' | 'uploaded' | 'likes';
type SortDir = 'asc' | 'desc';
type SortCriterion = { field: SortField; dir: SortDir };

const MAX_FILE_SIZE_BYTES = (() => {
  const raw = process.env.NEXT_PUBLIC_MAKAPIX_ARTWORK_SIZE_LIMIT_BYTES || '5242880';
  const n = Number(raw);
  return Number.isFinite(n) && n > 0 ? n : 5242880;
})();

function formatMiB(bytes: number): string {
  const mib = bytes / (1024 * 1024);
  if (Math.abs(mib - Math.round(mib)) < 1e-9) return `${Math.round(mib)} MiB`;
  return `${mib.toFixed(2)} MiB`;
}

function tagsToHashtagString(tags: unknown): string {
  if (!Array.isArray(tags)) return '';
  const parts = tags
    .map((t) => String(t).trim())
    .filter(Boolean)
    .map((t) => t.replace(/^#/, ''));
  return parts.join(', ');
}

function safeTitleFromItem(item: DivoomGalleryInfo | null): string {
  const raw = (item?.FileName || '').trim();
  if (raw) return raw.slice(0, MAX_TITLE_LEN);
  if (item?.GalleryId) return `Divoom #${item.GalleryId}`;
  return 'Divoom import';
}

function formatUploadedDateOnly(epochSeconds: number | undefined): string {
  if (!epochSeconds) return '—';
  return new Date(epochSeconds * 1000).toLocaleDateString();
}

function mapDivoomFileSizeLabel(fileSize: unknown): string {
  const n = typeof fileSize === 'number' ? fileSize : Number(fileSize);
  switch (n) {
    case 1:
      return '16 px';
    case 2:
      return '32 px';
    case 4:
      return '64 px';
    case 16:
      return '128 px';
    case 32:
      return '256 px';
    default:
      return 'Unk';
  }
}

function getNameForItem(item: DivoomGalleryInfo): string {
  return (item.FileName || '').trim() || `Divoom #${item.GalleryId}`;
}

function stableSort<T>(arr: T[], compare: (a: T, b: T) => number): T[] {
  return arr
    .map((item, idx) => ({ item, idx }))
    .sort((a, b) => {
      const c = compare(a.item, b.item);
      return c !== 0 ? c : a.idx - b.idx;
    })
    .map((x) => x.item);
}

function compareForCriterion(a: DivoomGalleryInfo, b: DivoomGalleryInfo, c: SortCriterion): number {
  const dirMul = c.dir === 'asc' ? 1 : -1;
  if (c.field === 'name') {
    return dirMul * getNameForItem(a).localeCompare(getNameForItem(b), undefined, { sensitivity: 'base' });
  }
  if (c.field === 'uploaded') {
    const av = typeof a.Date === 'number' ? a.Date : 0;
    const bv = typeof b.Date === 'number' ? b.Date : 0;
    return dirMul * (av - bv);
  }
  if (c.field === 'likes') {
    const av = typeof a.LikeCnt === 'number' ? a.LikeCnt : 0;
    const bv = typeof b.LikeCnt === 'number' ? b.LikeCnt : 0;
    return dirMul * (av - bv);
  }
  // size
  const av = typeof a.FileSize === 'number' ? a.FileSize : 0;
  const bv = typeof b.FileSize === 'number' ? b.FileSize : 0;
  return dirMul * (av - bv);
}

function defaultDirForField(field: SortField): SortDir {
  if (field === 'uploaded') return 'desc';
  if (field === 'likes') return 'desc';
  return 'asc';
}

function toArrayBuffer(view: Uint8Array): ArrayBuffer {
  const copy = new Uint8Array(view.byteLength);
  copy.set(view);
  return copy.buffer;
}

export default function DivoomImportPage() {
  const router = useRouter();
  const isReloading = useEnforceCrossOriginIsolation();

  // Makapix auth gate
  const [isAuthenticated, setIsAuthenticated] = useState(false);

  // Divoom credentials / session (memory-only)
  const [divoomEmail, setDivoomEmail] = useState('');
  const [divoomPassword, setDivoomPassword] = useState('');
  const [divoomSession, setDivoomSession] = useState<DivoomSession | null>(null);
  const [divoomLoginError, setDivoomLoginError] = useState<string | null>(null);

  // My uploads list (paged)
  const [page, setPage] = useState(1);
  const [allItems, setAllItems] = useState<DivoomGalleryInfo[]>([]);
  const [itemsLoading, setItemsLoading] = useState(false);
  const [itemsLoaded, setItemsLoaded] = useState(false);
  const [itemsError, setItemsError] = useState<string | null>(null);
  const [itemsProgress, setItemsProgress] = useState<string | null>(null);
  const itemsAbortRef = useRef<AbortController | null>(null);
  const itemsStallTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Panel 2 filters / sorting
  const [searchName, setSearchName] = useState('');
  const [onlyRecommended, setOnlyRecommended] = useState(false);
  const [onlyNew, setOnlyNew] = useState(false);
  const [sortCriteria, setSortCriteria] = useState<SortCriterion[]>([{ field: 'uploaded', dir: 'desc' }]);
  const [jumpPageInput, setJumpPageInput] = useState('');

  // Single selection across pages
  const [selected, setSelected] = useState<DivoomGalleryInfo | null>(null);
  const selectedId = selected?.GalleryId ?? null;

  // Decode + preview
  const decoder = useMemo(() => new PyodideDecoder(), []);
  const datCache = useRef<Map<number, Uint8Array>>(new Map());
  const webpCache = useRef<Map<number, Uint8Array>>(new Map());
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [decodeMeta, setDecodeMeta] = useState<{ frames: number; speed: number; w: number; h: number } | null>(null);
  const [decoding, setDecoding] = useState(false);
  const [decodeError, setDecodeError] = useState<string | null>(null);

  // Submission fields (prefilled, editable)
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [hashtags, setHashtags] = useState('');

  // Upload
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadNotice, setUploadNotice] = useState<string | null>(null);
  const [uploadedArtwork, setUploadedArtwork] = useState<UploadedArtwork | null>(null);
  const [lastUploadedGalleryId, setLastUploadedGalleryId] = useState<number | null>(null);

  const API_BASE_URL =
    typeof window !== 'undefined'
      ? process.env.NEXT_PUBLIC_API_BASE_URL || window.location.origin
      : '';

  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) {
      router.push('/auth');
    } else {
      setIsAuthenticated(true);
    }
  }, [router]);

  // Cleanup preview URL
  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const handleDivoomLogin = useCallback(async () => {
    setDivoomLoginError(null);
    setItemsError(null);
    setDecodeError(null);
    setUploadedArtwork(null);
    setUploadError(null);
    setUploadNotice(null);

    const email = divoomEmail.trim();
    if (!email || !divoomPassword) {
      setDivoomLoginError('Please enter your Divoom email and password.');
      return;
    }

    try {
      const md5 = SparkMD5.hash(divoomPassword);
      const session = await divoomLogin(email, md5);
      setDivoomSession(session);
      // Reset page state on login
      setPage(1);
      setAllItems([]);
      setItemsLoaded(false);
      setItemsProgress(null);
      setSelected(null);
      setPreviewUrl(null);
      setDecodeMeta(null);
      setTitle('');
      setDescription('');
      setHashtags('');
      setSearchName('');
      setOnlyRecommended(false);
      setOnlyNew(false);
      setSortCriteria([{ field: 'uploaded', dir: 'desc' }]);
      setJumpPageInput('');
    } catch (err) {
      if (err instanceof DivoomApiError) {
        setDivoomLoginError(`Login failed (ReturnCode ${err.code}). Please check your credentials.`);
      } else {
        setDivoomLoginError((err as Error).message);
      }
    }
  }, [divoomEmail, divoomPassword]);

  const cancelLoadingArtworks = useCallback(() => {
    if (itemsAbortRef.current) {
      itemsAbortRef.current.abort();
      itemsAbortRef.current = null;
    }
    if (itemsStallTimerRef.current) {
      clearTimeout(itemsStallTimerRef.current);
      itemsStallTimerRef.current = null;
    }
    setItemsLoading(false);
    setItemsProgress(null);
  }, []);

  const loadAllArtworks = useCallback(async () => {
    if (!divoomSession) return;

    // Cancel any in-flight load first
    cancelLoadingArtworks();
    const controller = new AbortController();
    itemsAbortRef.current = controller;
    // Safeguard: abort if we go too long without the unique artwork count increasing.
    const armStallTimer = () => {
      if (itemsStallTimerRef.current) clearTimeout(itemsStallTimerRef.current);
      itemsStallTimerRef.current = setTimeout(() => {
        // Equivalent to the user pressing "Cancel"
        controller.abort();
      }, STALL_ABORT_MS);
    };
    armStallTimer();

    setItemsLoading(true);
    setItemsLoaded(false);
    setItemsError(null);
    setItemsProgress('Loading artworks… 0 retrieved so far');
    setAllItems([]);
    setPage(1);

    const seen = new Map<number, DivoomGalleryInfo>(); // dedupe by GalleryId
    let lastPublishedCount = 0;
    try {
      for (let refreshIndex = 0; refreshIndex < MAX_REFRESH_BLOCKS; refreshIndex += 1) {
        let gotAnyInBlock = false;
        let consecutiveNoNewPages = 0;

        for (let withinBlockPage = 1; withinBlockPage < 100000; withinBlockPage += 1) {
          const start = (withinBlockPage - 1) * PAGE_SIZE + 1;
          const end = start + PAGE_SIZE - 1;

          let list: DivoomGalleryInfo[] = [];
          let attempt = 0;
          while (attempt <= SHORT_PAGE_RETRIES) {
            attempt += 1;
            list = await fetchMyUploads(divoomSession, { start, end, refreshIndex, signal: controller.signal });

            // Retry short pages (server sometimes returns fewer than requested)
            if (list.length === PAGE_SIZE || list.length === 0 || attempt > SHORT_PAGE_RETRIES) break;
          }

          if (list.length === 0) {
            if (!gotAnyInBlock) {
              // No data for this refresh block => we're done
              refreshIndex = MAX_REFRESH_BLOCKS; // break outer loop
            }
            break;
          }

          gotAnyInBlock = true;
          const before = seen.size;
          for (const item of list) {
            if (typeof item.GalleryId === 'number' && !seen.has(item.GalleryId)) {
              seen.set(item.GalleryId, item);
            }
          }
          const after = seen.size;
          const added = after - before;

          if (added === 0) {
            consecutiveNoNewPages += 1;
          } else {
            consecutiveNoNewPages = 0;
          }

          // Publish progress only when count actually changes (unique received),
          // and yield to avoid locking the UI during large imports.
          if (after !== lastPublishedCount) {
            lastPublishedCount = after;
            const merged = Array.from(seen.values());
            setAllItems(merged);
            setItemsProgress(`Loading artworks… ${merged.length} retrieved so far`);
            armStallTimer();
            await yieldToBrowser();
          }

          // If the API keeps returning non-empty pages but none are new, treat as end-of-data.
          if (consecutiveNoNewPages >= MAX_CONSECUTIVE_NO_NEW_PAGES) {
            refreshIndex = MAX_REFRESH_BLOCKS; // break outer loop
            break;
          }
        }
      }

      setAllItems(Array.from(seen.values()));
      setItemsLoaded(true);
      setItemsProgress(null);
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') {
        // User cancelled — keep whatever we have and allow interaction with the partial list.
        setItemsLoaded(true);
        setItemsProgress(null);
        return;
      }
      if (err instanceof DivoomApiError) {
        setItemsError(`Failed to load artworks (ReturnCode ${err.code}).`);
      } else {
        setItemsError((err as Error).message);
      }
    } finally {
      setItemsLoading(false);
      itemsAbortRef.current = null;
      if (itemsStallTimerRef.current) {
        clearTimeout(itemsStallTimerRef.current);
        itemsStallTimerRef.current = null;
      }
    }
  }, [cancelLoadingArtworks, divoomSession]);

  useEffect(() => {
    if (!divoomSession) return;
    loadAllArtworks();
  }, [divoomSession, loadAllArtworks]);

  const filteredSorted = useMemo(() => {
    let list = allItems;
    const q = searchName.trim().toLowerCase();
    if (q) {
      list = list.filter((it) => getNameForItem(it).toLowerCase().includes(q));
    }
    if (onlyRecommended) {
      list = list.filter((it) => Number((it as any).IsAddRecommend) === 1);
    }
    if (onlyNew) {
      list = list.filter((it) => Number((it as any).IsAddNew) === 1);
    }

    // Apply multi-sort: criterion[0] is primary, then 1, 2...
    // We implement it as a stable sort applied from the last criterion to the first.
    let out = [...list];
    for (let i = sortCriteria.length - 1; i >= 0; i -= 1) {
      const crit = sortCriteria[i];
      out = stableSort(out, (a, b) => compareForCriterion(a, b, crit));
    }
    return out;
  }, [allItems, onlyNew, onlyRecommended, searchName, sortCriteria]);

  const totalPages = useMemo(() => {
    return Math.max(1, Math.ceil(filteredSorted.length / PAGE_SIZE));
  }, [filteredSorted.length]);

  useEffect(() => {
    // Keep page in bounds when filters change
    setPage((p) => Math.min(Math.max(1, p), totalPages));
  }, [totalPages]);

  const pageItems = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return filteredSorted.slice(start, start + PAGE_SIZE);
  }, [filteredSorted, page]);

  const sortLabel = useMemo(() => {
    const fmt = (c: SortCriterion) => {
      const field =
        c.field === 'uploaded'
          ? 'Uploaded'
          : c.field === 'name'
            ? 'Name'
            : c.field === 'likes'
              ? 'Lks'
              : 'Size';
      const dir = c.dir === 'asc' ? '↑' : '↓';
      return `${field} ${dir}`;
    };
    return sortCriteria.length ? sortCriteria.map(fmt).join(', ') : '—';
  }, [sortCriteria]);

  const toggleSort = useCallback((field: SortField) => {
    setSortCriteria((prev) => {
      const idx = prev.findIndex((c) => c.field === field);
      if (idx === 0) {
        // Toggle direction on primary
        const next: SortCriterion[] = [...prev];
        next[0] = { field, dir: prev[0].dir === 'asc' ? 'desc' : 'asc' };
        return next;
      }
      if (idx > 0) {
        // Promote to primary, keep existing direction
        const existing = prev[idx];
        return [existing, ...prev.slice(0, idx), ...prev.slice(idx + 1)];
      }
      // Add as new primary with default dir
      return [{ field, dir: defaultDirForField(field) }, ...prev];
    });
  }, []);

  const handleJumpToPage = useCallback(() => {
    const n = Number(jumpPageInput);
    if (!Number.isFinite(n)) return;
    const target = Math.min(Math.max(1, Math.trunc(n)), totalPages);
    setPage(target);
  }, [jumpPageInput, totalPages]);

  const handleSelect = useCallback(
    async (item: DivoomGalleryInfo) => {
      setSelected(item);
      setUploadedArtwork(null);
      setUploadError(null);
      setUploadNotice(null);
      setDecodeError(null);

      // Prefill (editable)
      setTitle(safeTitleFromItem(item));
      setDescription(String(item.Content ?? '').slice(0, MAX_DESC_LEN));
      setHashtags(tagsToHashtagString(item.FileTagArray));

      // Decode preview (lossless animated WebP)
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
        setPreviewUrl(null);
      }
      setDecodeMeta(null);
      setDecoding(true);
      try {
        if (typeof (globalThis as any).SharedArrayBuffer === 'undefined') {
          throw new Error(
            'SharedArrayBuffer is not available in this browser context. Please reload the page (it requires COOP/COEP headers), or use a browser/device that supports SharedArrayBuffer.',
          );
        }
        const gid = item.GalleryId;
        let webp = webpCache.current.get(gid);
        if (!webp) {
          let dat = datCache.current.get(gid);
          if (!dat) {
            dat = await downloadDivoomDat(item.FileId);
            datCache.current.set(gid, dat);
          }
          const decoded = await decoder.decodeToWebp(dat);
          webp = decoded.webp;
          webpCache.current.set(gid, webp);
          setDecodeMeta({
            frames: decoded.totalFrames,
            speed: decoded.speed,
            w: decoded.columnCount * 16,
            h: decoded.rowCount * 16,
          });
        }
        const blob = new Blob([toArrayBuffer(webp)], { type: 'image/webp' });
        const url = URL.createObjectURL(blob);
        setPreviewUrl(url);
      } catch (err) {
        setDecodeError((err as Error).message);
      } finally {
        setDecoding(false);
      }
    },
    [decoder, previewUrl],
  );

  const handleLogoutDivoom = useCallback(() => {
    // NO persistence: wipe everything in-memory only.
    cancelLoadingArtworks();
    setDivoomSession(null);
    setDivoomPassword('');
    setDivoomLoginError(null);
    setAllItems([]);
    setItemsError(null);
    setItemsLoaded(false);
    setItemsProgress(null);
    setPage(1);
    setSelected(null);
    setDecoding(false);
    setDecodeError(null);
    setDecodeMeta(null);
    datCache.current.clear();
    webpCache.current.clear();
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setPreviewUrl(null);
    setTitle('');
    setDescription('');
    setHashtags('');
    setUploadedArtwork(null);
    setUploadError(null);
    setUploadNotice(null);
    setLastUploadedGalleryId(null);
    setSearchName('');
    setOnlyRecommended(false);
    setOnlyNew(false);
    setSortCriteria([{ field: 'uploaded', dir: 'desc' }]);
    setJumpPageInput('');
  }, [cancelLoadingArtworks, previewUrl]);

  const canSubmit =
    !!selected &&
    !decoding &&
    !!previewUrl &&
    selectedId !== lastUploadedGalleryId &&
    title.trim().length > 0 &&
    title.trim().length <= MAX_TITLE_LEN &&
    description.length <= MAX_DESC_LEN &&
    !uploading;

  const handleSubmitToMakapix = useCallback(async () => {
    if (!selected) return;
    if (selected.GalleryId === lastUploadedGalleryId) {
      setUploadError(null);
      setUploadNotice('You have just uploaded this artwork.');
      return;
    }
    const gid = selected.GalleryId;
    const webp = webpCache.current.get(gid);
    if (!webp) {
      setUploadError('Selected artwork is not decoded yet. Please wait.');
      setUploadNotice(null);
      return;
    }

    if (webp.length > MAX_FILE_SIZE_BYTES) {
      setUploadError(`Decoded WebP (${formatMiB(webp.length)}) exceeds maximum of ${formatMiB(MAX_FILE_SIZE_BYTES)}.`);
      return;
    }

    setUploading(true);
    setUploadError(null);
    setUploadNotice(null);
    setUploadedArtwork(null);

    try {
      const file = new File([toArrayBuffer(webp)], `${safeTitleFromItem(selected)}.webp`, { type: 'image/webp' });
      const formData = new FormData();
      formData.append('image', file);
      formData.append('title', title.trim());
      formData.append('description', description.trim());
      formData.append('hashtags', hashtags.trim());

      const response = await authenticatedFetch(`${API_BASE_URL}/api/post/upload`, {
        method: 'POST',
        body: formData,
      });

      if (response.status === 401) {
        clearTokens();
        router.push('/auth');
        return;
      }
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(errorData.detail || 'Upload failed');
      }

      const data = await response.json();
      setUploadedArtwork({
        id: data.post.id,
        public_sqid: data.post.public_sqid,
        title: data.post.title,
        art_url: data.post.art_url,
        canvas: data.post.canvas,
        width: data.post.width,
        height: data.post.height,
        public_visibility: data.post.public_visibility,
      });
      setLastUploadedGalleryId(selected.GalleryId);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Upload failed');
      setUploadNotice(null);
    } finally {
      setUploading(false);
    }
  }, [API_BASE_URL, description, hashtags, lastUploadedGalleryId, router, selected, title]);

  // Show loading while forcing reload for cross-origin isolation
  if (isReloading) {
    return (
      <Layout title="Import from Divoom" description="Import your Divoom Cloud artworks">
        <div className="container">
          <div className="loading">Preparing secure context…</div>
        </div>
      </Layout>
    );
  }

  if (!isAuthenticated) {
    return (
      <Layout title="Import from Divoom" description="Import your Divoom Cloud artworks">
        <div className="container">
          <div className="loading">Loading…</div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout title="Import from Divoom" description="Import your Divoom Cloud artworks">
      <div className="container">
        <div className="header-row">
          <h1 className="page-title">Import from Divoom</h1>
          <button className="back-btn" type="button" onClick={() => router.push('/submit')}>
            ← Back to Submit
          </button>
        </div>
        <div className="page-note">
          Makapix Club does not save your Divoom log in. You have to re-enter your credentials every time you open this tool.
        </div>

        <section className="panel">
          <h2 className="panel-title">1. Sign in to Divoom Cloud</h2>
          {divoomSession ? (
            <div className="status success">
              <div>
                Signed in as <strong>{divoomSession.email}</strong>
              </div>
              <button type="button" className="btn-secondary" onClick={handleLogoutDivoom}>
                Log out
              </button>
            </div>
          ) : (
            <div className="grid-form">
              <label>
                Email
                <input
                  type="email"
                  value={divoomEmail}
                  onChange={(e) => setDivoomEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                />
              </label>
              <label>
                Password
                <input
                  type="password"
                  value={divoomPassword}
                  onChange={(e) => setDivoomPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                />
              </label>
              <button type="button" className="btn-primary" onClick={handleDivoomLogin}>
                Sign in
              </button>
              {divoomLoginError && <div className="status error">{divoomLoginError}</div>}
              <div className="hint">
                Security note: your Divoom session is kept <strong>in-memory only</strong> and is cleared on refresh.
              </div>
            </div>
          )}
        </section>

        <section className="panel panel2-bar">
          <div className="panel2-content">
            <h2 className="panel-title">2. Choose an artwork ({allItems.length} artworks)</h2>
            {!divoomSession ? (
              <div className="muted">Sign in above to load your uploads.</div>
            ) : (
              <>
                {itemsLoading && (
                  <div className="status info">
                    <div>{itemsProgress || 'Loading artworks…'}</div>
                    <button type="button" className="btn-secondary" onClick={cancelLoadingArtworks}>
                      Cancel
                    </button>
                  </div>
                )}
                {itemsError && <div className="status error">{itemsError}</div>}

                {!itemsLoading && itemsLoaded && allItems.length === 0 && (
                  <div className="muted">No artworks found.</div>
                )}

                {!itemsLoading && itemsLoaded && allItems.length > 0 && (
                  <>
                    <div className="panel2-controls">
                      <label className="search-label">
                        Search
                        <input
                          type="text"
                          value={searchName}
                          onChange={(e) => setSearchName(e.target.value)}
                          placeholder="Filter by name…"
                        />
                      </label>

                      <label className="check">
                        <input
                          type="checkbox"
                          checked={onlyRecommended}
                          onChange={(e) => setOnlyRecommended(e.target.checked)}
                        />
                        Rec&apos;d
                      </label>

                      <label className="check">
                        <input type="checkbox" checked={onlyNew} onChange={(e) => setOnlyNew(e.target.checked)} />
                        New
                      </label>

                      <div className="sort-info">
                        Sort: <strong>{sortLabel}</strong>
                      </div>
                    </div>

                    <div className="pager">
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        disabled={page <= 1}
                      >
                        Previous
                      </button>
                      <div className="pager-info">
                        Page <strong>{page}</strong> of <strong>{totalPages}</strong>
                      </div>
                      <div className="pager-jump">
                        <input
                          type="number"
                          min={1}
                          max={totalPages}
                          value={jumpPageInput}
                          onChange={(e) => setJumpPageInput(e.target.value)}
                          placeholder="Page #"
                        />
                        <button type="button" className="btn-secondary" onClick={handleJumpToPage}>
                          Go
                        </button>
                      </div>
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                        disabled={page >= totalPages}
                      >
                        Next
                      </button>
                    </div>

                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th
                              className="col-title sortable"
                              role="button"
                              tabIndex={0}
                              onClick={() => toggleSort('name')}
                            >
                              Title
                            </th>
                            <th
                              className="col-uploaded sortable"
                              role="button"
                              tabIndex={0}
                              onClick={() => toggleSort('uploaded')}
                            >
                              Uploaded
                            </th>
                            <th
                              className="col-size sortable"
                              role="button"
                              tabIndex={0}
                              onClick={() => toggleSort('size')}
                            >
                              Size
                            </th>
                            <th
                              className="col-likes sortable"
                              role="button"
                              tabIndex={0}
                              onClick={() => toggleSort('likes')}
                            >
                              Lks
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {pageItems.length ? (
                            pageItems.map((item) => (
                              <tr
                                key={item.GalleryId}
                                className={`clickable-row ${item.GalleryId === selectedId ? 'active' : ''}`}
                                onClick={() => handleSelect(item)}
                                role="button"
                                tabIndex={0}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter' || e.key === ' ') {
                                    e.preventDefault();
                                    handleSelect(item);
                                  }
                                }}
                                aria-label={`Select ${getNameForItem(item)}`}
                              >
                                <td className="col-title" title={getNameForItem(item)}>
                                  {getNameForItem(item)}
                                </td>
                                <td className="col-uploaded">{formatUploadedDateOnly(item.Date)}</td>
                                <td className="col-size">{mapDivoomFileSizeLabel(item.FileSize)}</td>
                                <td className="col-likes">{typeof item.LikeCnt === 'number' ? item.LikeCnt : 0}</td>
                              </tr>
                            ))
                          ) : (
                            <tr>
                              <td colSpan={4} className="muted">
                                No items on this page.
                              </td>
                            </tr>
                          )}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </>
            )}
          </div>
        </section>

        <section className="panel">
          <h2 className="panel-title">3. Preview & submit to Makapix Club</h2>
          {!divoomSession ? (
            <div className="muted">Sign in above to load your uploads.</div>
          ) : !itemsLoaded ? (
            <div className="muted">Your artworks are still loading. Please wait for panel 2 to finish.</div>
          ) : allItems.length === 0 ? (
            <div className="muted">No artworks found.</div>
          ) : !selected ? (
            <div className="muted">Select one artwork above to preview and submit it.</div>
          ) : (
            <>
              <div className="preview-grid">
                <div className="preview-box">
                  {previewUrl ? (
                    <img src={previewUrl} alt="Selected Divoom artwork preview" className="preview-image pixel-art" />
                  ) : (
                    <div className="preview-placeholder">{decoding ? 'Decoding…' : 'No preview yet.'}</div>
                  )}
                  <div className="preview-meta">
                    <div className="preview-title">
                      <strong>{(selected.FileName || '').trim() || `Divoom #${selected.GalleryId}`}</strong>
                      <span className="badge">#{selected.GalleryId}</span>
                    </div>
                    {decodeMeta && (
                      <div className="muted">
                        {decodeMeta.w}×{decodeMeta.h} · {decodeMeta.frames} frames · {decodeMeta.speed} ms
                      </div>
                    )}
                    {decodeError && <div className="status error">{decodeError}</div>}
                  </div>
                </div>

                <div className="form">
                  <div className="form-field">
                    <label htmlFor="title">Title *</label>
                    <input
                      id="title"
                      type="text"
                      value={title}
                      onChange={(e) => setTitle(e.target.value)}
                      maxLength={MAX_TITLE_LEN}
                      required
                    />
                    <span className="char-count">
                      {title.length}/{MAX_TITLE_LEN}
                    </span>
                  </div>

                  <div className="form-field">
                    <label htmlFor="description">Description</label>
                    <textarea
                      id="description"
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      maxLength={MAX_DESC_LEN}
                      rows={10}
                    />
                    <span className="char-count">
                      {description.length}/{MAX_DESC_LEN}
                    </span>
                  </div>

                  <div className="form-field">
                    <label htmlFor="hashtags">Hashtags</label>
                    <input
                      id="hashtags"
                      type="text"
                      value={hashtags}
                      onChange={(e) => setHashtags(e.target.value)}
                      placeholder="pixel, retro, game (comma separated)"
                    />
                    <span className="field-hint">Auto-filled from Divoom tags; edit freely.</span>
                  </div>

                  {uploadNotice && <div className="status info">{uploadNotice}</div>}
                  {uploadError && <div className="status error">{uploadError}</div>}

                  <button type="button" className="submit-btn" onClick={handleSubmitToMakapix} disabled={!canSubmit}>
                    {uploading ? 'Uploading…' : '🚀 Submit'}
                  </button>

                  {uploadedArtwork && (
                    <div className="status success">
                      <div>
                        Uploaded!{' '}
                        <button
                          type="button"
                          className="link-btn"
                          onClick={() => router.push(`/p/${uploadedArtwork.public_sqid}`)}
                        >
                          View artwork
                        </button>
                      </div>
                      {!uploadedArtwork.public_visibility && (
                        <div className="muted">Your artwork is awaiting moderator approval for public visibility.</div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </section>
      </div>

      <style jsx>{`
        .container {
          max-width: 900px;
          margin: 0 auto;
          padding: 24px;
        }

        .loading {
          text-align: center;
          padding: 48px;
          color: var(--text-muted);
        }

        .header-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 18px;
        }
        .page-note {
          margin: -6px 0 18px;
          color: var(--text-muted);
          font-size: 0.9rem;
          line-height: 1.35;
        }

        .page-title {
          font-size: 1.75rem;
          font-weight: 700;
          color: var(--text-primary);
          margin: 0;
        }

        .back-btn {
          padding: 10px 14px;
          border-radius: 10px;
          background: var(--bg-tertiary);
          color: var(--text-secondary);
          transition: all var(--transition-fast);
        }
        .back-btn:hover {
          background: rgba(0, 212, 255, 0.12);
          box-shadow: var(--glow-cyan);
        }

        .panel {
          background: var(--bg-secondary);
          border: 1px solid rgba(255, 255, 255, 0.06);
          border-radius: 16px;
          padding: 18px;
          margin-bottom: 18px;
        }
        /* Panel 2: full-width bar, no border/radius; inner content stays constrained */
        .panel.panel2-bar {
          border: none;
          border-radius: 0;
          padding: 0;
          /* full-bleed within the page (ignores the container max-width) */
          width: 100vw;
          margin-left: calc(50% - 50vw);
          margin-right: calc(50% - 50vw);
        }
        .panel2-content {
          max-width: 900px;
          margin: 0 auto;
          padding: 18px 24px;
        }

        .panel-title {
          margin: 0 0 12px;
          color: var(--text-primary);
          font-size: 1.05rem;
          font-weight: 700;
        }

        .grid-form {
          display: grid;
          grid-template-columns: 1fr 1fr auto;
          gap: 12px;
          align-items: end;
        }

        .grid-form label {
          display: flex;
          flex-direction: column;
          gap: 6px;
          color: var(--text-secondary);
          font-size: 0.9rem;
          font-weight: 500;
        }

        .grid-form input {
          padding: 12px 14px;
          background: var(--bg-secondary);
          border: 1px solid var(--bg-tertiary);
          border-radius: 10px;
          color: var(--text-primary);
          transition: all var(--transition-fast);
        }

        .grid-form input:focus {
          outline: none;
          border-color: var(--accent-cyan);
          box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.1);
        }

        .hint {
          grid-column: 1 / -1;
          color: var(--text-muted);
          font-size: 0.85rem;
        }

        .status {
          padding: 12px 14px;
          border-radius: 12px;
          border: 1px solid rgba(255, 255, 255, 0.08);
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
        }
        .status.info {
          background: rgba(0, 212, 255, 0.08);
          border-color: rgba(0, 212, 255, 0.2);
          color: var(--text-secondary);
        }
        .status.error {
          background: rgba(239, 68, 68, 0.1);
          border-color: rgba(239, 68, 68, 0.25);
          color: #ef4444;
        }
        .status.success {
          background: rgba(34, 197, 94, 0.1);
          border-color: rgba(34, 197, 94, 0.25);
          color: var(--text-secondary);
          flex-direction: column;
          align-items: flex-start;
        }

        .muted {
          color: var(--text-muted);
        }

        .btn-primary {
          padding: 12px 16px;
          border-radius: 12px;
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
          font-weight: 700;
          transition: all var(--transition-fast);
          height: 44px;
        }
        .btn-primary:hover {
          box-shadow: 0 0 30px rgba(255, 110, 180, 0.35);
          transform: translateY(-1px);
        }

        .btn-secondary {
          padding: 10px 14px;
          border-radius: 10px;
          background: var(--bg-tertiary);
          color: var(--text-secondary);
          transition: all var(--transition-fast);
        }
        .btn-secondary:hover:not(:disabled) {
          background: rgba(180, 78, 255, 0.18);
          box-shadow: var(--glow-purple);
        }
        .btn-secondary:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .pager {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 12px;
        }
        .pager-info {
          color: var(--text-secondary);
        }
        .pager-jump {
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .pager-jump input {
          width: 86px;
          padding: 10px 12px;
          background: var(--bg-secondary);
          border: 1px solid var(--bg-tertiary);
          border-radius: 10px;
          color: var(--text-primary);
        }

        .panel2-controls {
          display: flex;
          flex-wrap: wrap;
          gap: 12px;
          align-items: end;
          margin-bottom: 12px;
        }
        .search-label {
          display: flex;
          flex-direction: column;
          gap: 6px;
          color: var(--text-secondary);
          font-size: 0.9rem;
          font-weight: 500;
          flex: 1 1 280px;
          min-width: 240px;
        }
        .search-label input {
          padding: 12px 14px;
          background: var(--bg-secondary);
          border: 1px solid var(--bg-tertiary);
          border-radius: 10px;
          color: var(--text-primary);
          transition: all var(--transition-fast);
        }
        .check {
          display: flex;
          align-items: center;
          gap: 8px;
          color: var(--text-secondary);
          font-size: 0.9rem;
          user-select: none;
        }
        .sort-info {
          color: var(--text-muted);
          font-size: 0.85rem;
          margin-left: auto;
          flex: 1 1 220px;
          text-align: right;
        }

        .table-wrap {
          overflow-x: auto;
          -webkit-overflow-scrolling: touch;
          border-radius: 12px;
          border: 1px solid rgba(255, 255, 255, 0.06);
        }

        table {
          width: 100%;
          border-collapse: collapse;
          table-layout: fixed;
        }

        th,
        td {
          padding: 10px 12px;
          text-align: left;
          border-bottom: 1px solid rgba(255, 255, 255, 0.06);
          color: var(--text-secondary);
          font-size: 0.9rem;
        }
        th {
          color: var(--text-primary);
          font-weight: 700;
          background: rgba(255, 255, 255, 0.03);
        }
        th.sortable {
          cursor: pointer;
          user-select: none;
        }
        tr.active td {
          background: rgba(0, 212, 255, 0.06);
        }

        tr.clickable-row {
          cursor: pointer;
        }

        tr.clickable-row:hover td {
          background: rgba(255, 255, 255, 0.03);
        }

        .col-title {
          width: auto;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .col-uploaded {
          width: 120px;
          white-space: nowrap;
        }
        .col-size {
          width: 76px;
          white-space: nowrap;
        }
        .col-likes {
          width: 70px;
          white-space: nowrap;
          text-align: right;
        }
        td.col-likes,
        th.col-likes {
          text-align: right;
        }

        .preview-grid {
          display: grid;
          grid-template-columns: 320px 1fr;
          gap: 16px;
          align-items: start;
        }

        .preview-box {
          background: var(--bg-tertiary);
          border-radius: 14px;
          overflow: hidden;
          border: 1px solid rgba(255, 255, 255, 0.06);
        }

        .preview-image {
          width: 100%;
          height: auto;
          display: block;
          image-rendering: pixelated !important;
        }

        .preview-placeholder {
          height: 240px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: var(--text-muted);
        }

        .preview-meta {
          padding: 12px;
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .preview-title {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 8px;
          color: var(--text-primary);
        }

        .badge {
          font-size: 0.8rem;
          color: var(--text-muted);
          background: rgba(255, 255, 255, 0.06);
          padding: 4px 8px;
          border-radius: 999px;
        }

        .form {
          display: flex;
          flex-direction: column;
          gap: 14px;
        }

        .form-field {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .form-field label {
          color: var(--text-secondary);
          font-size: 0.9rem;
          font-weight: 500;
        }

        .form-field input,
        .form-field textarea {
          padding: 12px 14px;
          background: var(--bg-secondary);
          border: 1px solid var(--bg-tertiary);
          border-radius: 10px;
          color: var(--text-primary);
          transition: all var(--transition-fast);
        }

        .form-field textarea {
          min-height: 200px;
          resize: vertical;
          font-family: inherit;
          line-height: 1.5;
        }

        .form-field input:focus,
        .form-field textarea:focus {
          outline: none;
          border-color: var(--accent-cyan);
          box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.1);
        }

        .char-count,
        .field-hint {
          font-size: 0.75rem;
          color: var(--text-muted);
          text-align: right;
        }
        .field-hint {
          text-align: left;
        }

        .submit-btn {
          width: 100%;
          padding: 16px;
          background: linear-gradient(135deg, var(--accent-pink), var(--accent-purple));
          color: white;
          font-size: 1.05rem;
          font-weight: 700;
          border-radius: 12px;
          transition: all var(--transition-fast);
        }
        .submit-btn:hover:not(:disabled) {
          box-shadow: 0 0 30px rgba(255, 110, 180, 0.4);
          transform: translateY(-1px);
        }
        .submit-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .link-btn {
          background: transparent;
          border: none;
          color: var(--accent-cyan);
          font-weight: 700;
          cursor: pointer;
          padding: 0;
          text-decoration: underline;
        }

        @media (max-width: 840px) {
          .grid-form {
            grid-template-columns: 1fr;
          }
          .btn-primary {
            width: 100%;
          }
          .preview-grid {
            grid-template-columns: 1fr;
          }
          table {
            table-layout: auto;
          }
          .sort-info {
            text-align: left;
            margin-left: 0;
          }
        }
      `}</style>
    </Layout>
  );
}


