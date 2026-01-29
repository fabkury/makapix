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

async function postJson<T>(
  url: string,
  body: Record<string, unknown>,
  opts?: { signal?: AbortSignal },
): Promise<T> {
  const resp = await fetch(url, {
    method: 'POST',
    headers: DEFAULT_HEADERS,
    body: JSON.stringify(body),
    signal: opts?.signal,
  });
  if (!resp.ok) {
    throw new Error(`Request failed with status ${resp.status}`);
  }
  return (await resp.json()) as T;
}

export async function divoomLogin(email: string, md5Password: string): Promise<DivoomSession> {
  const response = await postJson<{
    ReturnCode: number;
    UserId: number;
    Token: string;
  }>(`${API_BASE}/UserLogin`, {
    Email: email,
    Password: md5Password,
  });

  if (response.ReturnCode !== 0) {
    throw new DivoomApiError('login', response.ReturnCode);
  }

  return {
    token: response.Token,
    userId: response.UserId,
    email,
  };
}

export async function fetchMyUploads(
  session: DivoomSession,
  opts: { start: number; end: number; refreshIndex?: number; signal?: AbortSignal },
): Promise<DivoomGalleryInfo[]> {
  const payload = {
    StartNum: opts.start,
    EndNum: opts.end,
    Version: 99,
    FileSize: 0b1 | 0b10 | 0b100 | 0b1000 | 0b10000 | 0b100000,
    RefreshIndex: opts.refreshIndex ?? 0,
    FileSort: 0,
    Token: session.token,
    UserId: session.userId,
  };

  const response = await postJson<{
    ReturnCode: number;
    FileList?: DivoomGalleryInfo[];
    [key: string]: unknown;
  }>(`${API_BASE}/GetMyUploadListV3`, payload, { signal: opts.signal });

  if (response.ReturnCode !== 0) {
    throw new DivoomApiError('myUploads', response.ReturnCode);
  }

  // Filter out artworks with HideFlag=true (treat as if never received)
  const list = response.FileList ?? [];
  return list.filter((item) => {
    const hide = item.HideFlag;
    // HideFlag can be a number (1=hidden) or boolean
    return hide !== true && hide !== 1;
  });
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


