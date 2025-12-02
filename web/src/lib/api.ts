export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

const publicBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost/api";

// Token refresh state to prevent multiple simultaneous refresh attempts
let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

/**
 * Decode a JWT token and extract its payload
 */
function decodeJwtPayload(token: string): { exp?: number; iat?: number } | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = JSON.parse(atob(parts[1]));
    return payload;
  } catch {
    return null;
  }
}

/**
 * Check if the access token is expired or about to expire (within 60 seconds)
 */
export function isTokenExpired(token: string, bufferSeconds = 60): boolean {
  const payload = decodeJwtPayload(token);
  if (!payload?.exp) return true;
  
  const now = Math.floor(Date.now() / 1000);
  return payload.exp <= now + bufferSeconds;
}

/**
 * Get the stored access token from localStorage
 */
export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

/**
 * Get the stored refresh token from localStorage
 */
export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("refresh_token");
}

/**
 * Store tokens in localStorage
 */
export function storeTokens(accessToken: string, refreshToken?: string | null): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("access_token", accessToken);
  if (refreshToken) {
    localStorage.setItem("refresh_token", refreshToken);
  }
}

/**
 * Clear all auth tokens from localStorage
 */
export function clearTokens(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("user_id");
  localStorage.removeItem("user_handle");
}

/**
 * Attempt to refresh the access token using the refresh token
 * Returns true if successful, false otherwise
 */
export async function refreshAccessToken(): Promise<boolean> {
  // If already refreshing, wait for the existing refresh to complete
  if (isRefreshing && refreshPromise) {
    return refreshPromise;
  }

  const refreshToken = getRefreshToken();
  if (!refreshToken) {
    return false;
  }

  isRefreshing = true;
  refreshPromise = (async () => {
    try {
      const response = await fetch(`${publicBaseUrl}/api/auth/refresh`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) {
        // Refresh failed - clear tokens
        clearTokens();
        return false;
      }

      const data = await response.json();
      
      // Store the new tokens
      storeTokens(data.token, data.refresh_token);
      
      // Also update user_id if provided
      if (data.user_id) {
        localStorage.setItem("user_id", data.user_id);
      }

      return true;
    } catch (error) {
      console.error("Failed to refresh token:", error);
      clearTokens();
      return false;
    } finally {
      isRefreshing = false;
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

/**
 * Make an authenticated API request with automatic token refresh
 * If the token is expired or about to expire, it will attempt to refresh first
 * If the request returns 401, it will try to refresh and retry once
 */
export async function authenticatedFetch(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  let accessToken = getAccessToken();

  // Check if token needs refresh before making the request
  if (accessToken && isTokenExpired(accessToken)) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      accessToken = getAccessToken();
    } else {
      // Could not refresh - return a 401-like response to trigger login redirect
      return new Response(null, { status: 401, statusText: "Token refresh failed" });
    }
  }

  // Make the request with the current token
  const makeRequest = async (token: string | null): Promise<Response> => {
    const headers: HeadersInit = {
      ...options.headers,
    };

    if (token) {
      (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
    }

    return fetch(url, {
      ...options,
      headers,
    });
  };

  let response = await makeRequest(accessToken);

  // If we get a 401, try to refresh the token and retry once
  if (response.status === 401 && accessToken) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      accessToken = getAccessToken();
      response = await makeRequest(accessToken);
    }
  }

  return response;
}

/**
 * Make an authenticated JSON request with automatic token refresh
 */
export async function authenticatedRequestJson<TResponse>(
  path: string,
  options: RequestInit = {},
  method: HttpMethod = "GET"
): Promise<TResponse> {
  const url = path.startsWith("http") ? path : `${publicBaseUrl}${path}`;
  
  const response = await authenticatedFetch(url, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed (${response.status}): ${body}`);
  }

  return response.json() as Promise<TResponse>;
}

/**
 * Make an authenticated POST request with JSON body
 */
export async function authenticatedPostJson<TResponse>(
  path: string,
  payload: unknown
): Promise<TResponse> {
  return authenticatedRequestJson<TResponse>(
    path,
    { body: JSON.stringify(payload) },
    "POST"
  );
}

// ============================================================================
// Legacy API functions (kept for backward compatibility)
// ============================================================================

export async function requestJson<TResponse>(
  path: string,
  options: RequestInit = {},
  method: HttpMethod = "GET",
): Promise<TResponse> {
  const url = `${publicBaseUrl}${path}`;
  const response = await fetch(url, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed (${response.status}): ${body}`);
  }

  return response.json() as Promise<TResponse>;
}

export async function postJson<TResponse>(
  path: string,
  payload: unknown,
): Promise<TResponse> {
  return requestJson<TResponse>(path, { body: JSON.stringify(payload) }, "POST");
}

// ============================================================================
// Player API functions
// ============================================================================

export interface Player {
  id: string;
  player_key: string;
  name: string | null;
  device_model: string | null;
  firmware_version: string | null;
  registration_status: string;
  connection_status: string;
  last_seen_at: string | null;
  current_post_id: number | null;
  cert_expires_at: string | null;
  registered_at: string | null;
  created_at: string;
}

export interface PlayerProvisionResponse {
  player_key: string;
  registration_code: string;
  registration_code_expires_at: string;
  mqtt_broker: { host: string; port: number };
}

export interface PlayerRegisterRequest {
  registration_code: string;
  name: string;
}

export interface PlayerCommandRequest {
  command_type: "swap_next" | "swap_prev" | "show_artwork";
  post_id?: number;
}

export interface PlayerCommandResponse {
  command_id: string;
  status: "sent";
}

export interface PlayerCommandAllResponse {
  sent_count: number;
  commands: PlayerCommandResponse[];
}

export interface PlayerRenewCertResponse {
  cert_expires_at: string;
  message: string;
}

export interface TLSCertBundle {
  ca_pem: string;
  cert_pem: string;
  key_pem: string;
  broker: { host: string; port: number };
}

/**
 * List all players for a user
 */
export async function listPlayers(sqid: string): Promise<{ items: Player[] }> {
  return authenticatedRequestJson<{ items: Player[] }>(`/api/u/${sqid}/player`);
}

/**
 * Get a single player
 */
export async function getPlayer(sqid: string, playerId: string): Promise<Player> {
  return authenticatedRequestJson<Player>(`/api/u/${sqid}/player/${playerId}`);
}

/**
 * Register a player using registration code
 */
export async function registerPlayer(payload: PlayerRegisterRequest): Promise<Player> {
  return authenticatedPostJson<Player>("/api/player/register", payload);
}

/**
 * Update player name
 */
export async function updatePlayer(
  sqid: string,
  playerId: string,
  name: string
): Promise<Player> {
  return authenticatedRequestJson<Player>(
    `/api/u/${sqid}/player/${playerId}`,
    { body: JSON.stringify({ name }) },
    "PATCH"
  );
}

/**
 * Delete a player
 */
export async function deletePlayer(sqid: string, playerId: string): Promise<void> {
  const url = `/api/u/${sqid}/player/${playerId}`;
  const response = await authenticatedFetch(`${publicBaseUrl}${url}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Request failed (${response.status}): ${body}`);
  }
}

/**
 * Send command to a player
 */
export async function sendPlayerCommand(
  sqid: string,
  playerId: string,
  command: PlayerCommandRequest
): Promise<PlayerCommandResponse> {
  return authenticatedPostJson<PlayerCommandResponse>(
    `/api/u/${sqid}/player/${playerId}/command`,
    command
  );
}

/**
 * Send command to all user's players
 */
export async function sendCommandToAllPlayers(
  sqid: string,
  command: PlayerCommandRequest
): Promise<PlayerCommandAllResponse> {
  return authenticatedPostJson<PlayerCommandAllResponse>(
    `/api/u/${sqid}/player/command/all`,
    command
  );
}

/**
 * Renew player certificate
 */
export async function renewPlayerCert(
  sqid: string,
  playerId: string
): Promise<PlayerRenewCertResponse> {
  return authenticatedPostJson<PlayerRenewCertResponse>(
    `/api/u/${sqid}/player/${playerId}/renew-cert`,
    {}
  );
}

/**
 * Download player certificates
 */
export async function downloadPlayerCerts(
  sqid: string,
  playerId: string
): Promise<TLSCertBundle> {
  return authenticatedRequestJson<TLSCertBundle>(
    `/api/u/${sqid}/player/${playerId}/certs`
  );
}
