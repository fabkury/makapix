export interface DivoomSession {
  token: string;
  userId: number;
  email: string;
}

export interface DivoomGalleryInfo {
  GalleryId: number;
  FileId: string;
  FileName?: string;
  Content?: string;
  FileTagArray?: string[];
  Date?: number;
  LikeCnt?: number;
  WatchCnt?: number;
  CommentCnt?: number;
  HideFlag?: number | boolean;
  FileSize?: number;
  IsAddRecommend?: number;
  IsAddNew?: number;
  [key: string]: unknown;
}

const API_BASE = 'https://app.divoom-gz.com';
const FILE_BASE = 'https://f.divoom-gz.com';

const DEFAULT_HEADERS: Record<string, string> = {
  'Content-Type': 'application/json',
  'User-Agent': 'Aurabox/3.1.10 (iPad; iOS 14.8; Scale/2.00)',
};

export type DivoomApiAction = 'login' | 'myUploads';

export class DivoomApiError extends Error {
  action: DivoomApiAction;
  code: number;

  constructor(action: DivoomApiAction, code: number) {
    super(`${action} failed with ReturnCode ${code}`);
    this.name = 'DivoomApiError';
    this.action = action;
    this.code = code;
  }
}

/**
 * Thrown when Divoom kept refusing us after every rate-limit wait we were
 * willing to make (see RATE_LIMIT_MAX_WAITS).
 */
export class DivoomRateLimitError extends Error {
  constructor() {
    super('Divoom is rate-limiting this connection. Wait a minute and try again.');
    this.name = 'DivoomRateLimitError';
  }
}

// ---------------------------------------------------------------------------
// Rate limiting (verified 2026-11-05 against app.divoom-gz.com)
//
// Divoom allows 30 requests per 60-second window per source IP. Refusals are
// HTTP 429 with {"ReturnCode":12} and carry NO CORS headers, so in a browser
// the fetch rejects with a bare `TypeError: Failed to fetch`. Refused requests
// count toward the window, so retrying immediately keeps us blocked.
//
// We keep a client-side sliding-window budget below Divoom's cap (shared by
// login and listing), and when we are refused anyway we wait out a full
// window before retrying.
// ---------------------------------------------------------------------------
const RATE_LIMIT_WINDOW_MS = 60_000;
const RATE_LIMIT_BUDGET = 25; // stay under Divoom's 30/min
const RATE_LIMIT_BACKOFF_MS = 60_000; // no Retry-After header; a full window
const RATE_LIMIT_MAX_WAITS = 3;

const requestTimestamps: number[] = [];

export type RateLimitWaitCallback = (secondsRemaining: number) => void;

export interface DivoomRequestOptions {
  signal?: AbortSignal;
  /** Called about once per second while we are waiting for Divoom's rate limit. */
  onRateLimitWait?: RateLimitWaitCallback;
}

function abortError(): Error {
  const err = new Error('Aborted');
  err.name = 'AbortError';
  return err;
}

/** Sleep for `ms`, ticking `onTick` every second, rejecting with AbortError if aborted. */
function sleepWithTicks(ms: number, opts: DivoomRequestOptions): Promise<void> {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + ms;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const onAbort = () => {
      if (timer) clearTimeout(timer);
      reject(abortError());
    };
    if (opts.signal?.aborted) {
      reject(abortError());
      return;
    }
    opts.signal?.addEventListener('abort', onAbort, { once: true });
    const tick = () => {
      const remaining = deadline - Date.now();
      if (remaining <= 0) {
        opts.signal?.removeEventListener('abort', onAbort);
        resolve();
        return;
      }
      opts.onRateLimitWait?.(Math.ceil(remaining / 1000));
      timer = setTimeout(tick, Math.min(1000, remaining));
    };
    tick();
  });
}

/** Block until our own request budget allows another call, then record it. */
async function acquireRequestSlot(opts: DivoomRequestOptions): Promise<void> {
  for (;;) {
    const now = Date.now();
    while (requestTimestamps.length && now - requestTimestamps[0] >= RATE_LIMIT_WINDOW_MS) {
      requestTimestamps.shift();
    }
    if (requestTimestamps.length < RATE_LIMIT_BUDGET) {
      requestTimestamps.push(now);
      return;
    }
    const waitMs = RATE_LIMIT_WINDOW_MS - (now - requestTimestamps[0]) + 50;
    await sleepWithTicks(waitMs, opts);
  }
}

/** True for the error shapes a Divoom refusal produces in a browser. */
function looksRateLimited(err: unknown): boolean {
  if (err instanceof DivoomApiError) return err.code === 12;
  if (err instanceof Error) {
    // CORS-less 429 => the browser hides the response: TypeError "Failed to fetch"
    // (Chrome), "NetworkError when attempting to fetch resource" (Firefox),
    // "Load failed" (Safari).
    return err.name === 'TypeError' || /status 429/.test(err.message);
  }
  return false;
}

/** Human-readable message for any error thrown by this module. */
export function describeDivoomError(err: unknown): string {
  if (err instanceof DivoomRateLimitError) return err.message;
  if (err instanceof DivoomApiError) {
    if (err.code === 12) return 'Divoom is rate-limiting this connection (ReturnCode 12). Wait a minute and try again.';
    return `Divoom returned ReturnCode ${err.code}.`;
  }
  if (err instanceof Error) {
    if (looksRateLimited(err)) {
      return 'Divoom refused the connection, usually a rate limit. Wait a minute and try again.';
    }
    return err.message;
  }
  return String(err);
}

async function postJsonOnce<T>(
  url: string,
  body: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<T> {
  const resp = await fetch(url, {
    method: 'POST',
    headers: DEFAULT_HEADERS,
    body: JSON.stringify(body),
    signal,
  });
  if (!resp.ok) {
    throw new Error(`Request failed with status ${resp.status}`);
  }
  return (await resp.json()) as T;
}

/**
 * POST to Divoom with our request budget applied, waiting out and retrying
 * rate-limit refusals. Throws DivoomRateLimitError once out of retries, and
 * rethrows anything else untouched (AbortError, non-429 HTTP errors…).
 */
async function postJson<T extends { ReturnCode: number }>(
  url: string,
  body: Record<string, unknown>,
  opts: DivoomRequestOptions = {},
): Promise<T> {
  let waits = 0;
  for (;;) {
    await acquireRequestSlot(opts);
    try {
      const response = await postJsonOnce<T>(url, body, opts.signal);
      if (response.ReturnCode === 12) {
        throw new DivoomApiError('myUploads', 12);
      }
      return response;
    } catch (err) {
      if ((err as Error)?.name === 'AbortError') throw err;
      if (!looksRateLimited(err)) throw err;
      if (waits >= RATE_LIMIT_MAX_WAITS) throw new DivoomRateLimitError();
      waits += 1;
      await sleepWithTicks(RATE_LIMIT_BACKOFF_MS, opts);
    }
  }
}

/**
 * Sign in to Divoom Cloud.
 *
 * `email` is Divoom's generic login identifier: the China app sends either a
 * phone number or an email address in the same `Email` field to this same
 * endpoint, and the account database is global across app hosts. Pass the
 * string the user typed straight through. ReturnCode 4 = identifier not
 * registered, 5 = wrong password.
 */
export async function divoomLogin(
  email: string,
  md5Password: string,
  opts: DivoomRequestOptions = {},
): Promise<DivoomSession> {
  const response = await postJson<{
    ReturnCode: number;
    UserId: number;
    Token: string;
  }>(
    `${API_BASE}/UserLogin`,
    {
      Email: email,
      Password: md5Password,
    },
    opts,
  );

  if (response.ReturnCode !== 0) {
    throw new DivoomApiError('login', response.ReturnCode);
  }

  return {
    token: response.Token,
    userId: response.UserId,
    email,
  };
}

export interface DivoomUploadsPage {
  /** Visible artworks on this page (HideFlag'd ones removed). */
  items: DivoomGalleryInfo[];
  /** How many entries Divoom actually returned, hidden ones included. Use this
   *  to advance the cursor; 0 means the end of the list. */
  received: number;
}

/**
 * One page of the user's uploads. Paging is cursor-like: ask for
 * [start, start+pageSize-1], then continue from `start + received`; the list
 * is finished when `received` is 0. Divoom may return fewer than `pageSize`
 * mid-list, and hidden artworks are dropped from `items`, so never infer the
 * end from `items.length`.
 */
export async function fetchMyUploads(
  session: DivoomSession,
  opts: { start: number; end: number } & DivoomRequestOptions,
): Promise<DivoomUploadsPage> {
  const payload = {
    StartNum: opts.start,
    EndNum: opts.end,
    Version: 99,
    FileSize: 0b1 | 0b10 | 0b100 | 0b1000 | 0b10000 | 0b100000,
    RefreshIndex: 0, // ignored by Divoom on listings (servoom CLOUD_API.md)
    FileSort: 0,
    Token: session.token,
    UserId: session.userId,
  };

  const response = await postJson<{
    ReturnCode: number;
    FileList?: DivoomGalleryInfo[];
    [key: string]: unknown;
  }>(`${API_BASE}/GetMyUploadListV3`, payload, { signal: opts.signal, onRateLimitWait: opts.onRateLimitWait });

  if (response.ReturnCode !== 0) {
    throw new DivoomApiError('myUploads', response.ReturnCode);
  }

  // Filter out artworks with HideFlag=true (treat as if never received)
  const list = response.FileList ?? [];
  const items = list.filter((item) => {
    const hide = item.HideFlag;
    // HideFlag can be a number (1=hidden) or boolean
    return hide !== true && hide !== 1;
  });
  return { items, received: list.length };
}

export async function downloadDivoomDat(fileId: string): Promise<Uint8Array> {
  const normalized = fileId.startsWith('/') ? fileId : `/${fileId}`;
  const resp = await fetch(`${FILE_BASE}${normalized}`);
  if (!resp.ok) {
    throw new Error(`File download failed with status ${resp.status}`);
  }
  const buffer = await resp.arrayBuffer();
  return new Uint8Array(buffer);
}


