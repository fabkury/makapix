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
 * 
 * NOTE: Refresh tokens are now stored in HttpOnly cookies and not accessible to JavaScript.
 * This function returns null as refresh tokens are handled server-side via cookies.
 */
export function getRefreshToken(): string | null {
  // Refresh token is now in HttpOnly cookie, not accessible to JavaScript
  return null;
}

/**
 * Store tokens in localStorage
 *
 * NOTE: Refresh tokens are now stored in HttpOnly cookies and should not be stored in localStorage.
 * Only the access token is stored in localStorage (short-lived).
 */
export function storeTokens(accessToken: string, refreshToken?: string | null): void {
  if (typeof window === "undefined") return;
  localStorage.setItem("access_token", accessToken);
  // Refresh token is now stored in HttpOnly cookie, not in localStorage
  // Clean up old refresh token if it exists (migration from old system)
  localStorage.removeItem("refresh_token");
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
 * 
 * IMPORTANT: This function is conservative about clearing tokens.
 * We only clear tokens on definitive auth failures (401/403), not on
 * transient errors like network issues or server errors (5xx).
 * This prevents session loss due to temporary connectivity problems.
 */
export async function refreshAccessToken(): Promise<boolean> {
  // If already refreshing, wait for the existing refresh to complete
  if (isRefreshing && refreshPromise) {
    console.log("[Auth] Refresh already in progress, waiting...");
    return refreshPromise;
  }

  // Refresh token is now in HttpOnly cookie, so we don't need to check for it
  // The cookie will be sent automatically with credentials: "include"

  isRefreshing = true;
  refreshPromise = (async () => {
    try {
      console.log("[Auth] Attempting to refresh access token...");
      const response = await fetch(`${publicBaseUrl}/api/auth/refresh`, {
        method: "POST",
        credentials: "include", // CRITICAL: Include cookies (refresh token is in cookie)
        headers: {
          "Content-Type": "application/json",
        },
        // No body needed - refresh token is in HttpOnly cookie
      });

      if (!response.ok) {
        const errorText = await response.text().catch(() => "Unknown error");
        console.error(`[Auth] Refresh failed (${response.status}): ${errorText}`);
        
        // Only clear tokens on definitive auth failures
        // 401 = Invalid/expired token (server confirmed it's bad)
        // 403 = User banned/deactivated
        // Do NOT clear on 5xx errors - those are server issues, token might still be valid
        if (response.status === 401 || response.status === 403) {
          console.log("[Auth] Definitive auth failure, clearing tokens");
          clearTokens();
        } else {
          console.log("[Auth] Server error, keeping tokens for retry");
        }
        return false;
      }

      const data = await response.json();
      
      // Validate the response has required fields
      if (!data.token) {
        console.error("[Auth] Refresh response missing access token");
        // This is a server bug, but we shouldn't clear tokens - 
        // the old refresh token might still work (grace period)
        return false;
      }
      
      // Store the new access token (refresh token is automatically updated in cookie by server)
      storeTokens(data.token);
      console.log("[Auth] Tokens refreshed successfully");
      
      // Update all user data from response
      if (data.user_id) {
        localStorage.setItem("user_id", String(data.user_id));
      }
      if (data.user_key) {
        localStorage.setItem("user_key", data.user_key);
      }
      if (data.public_sqid) {
        localStorage.setItem("public_sqid", data.public_sqid);
      }
      if (data.user_handle) {
        localStorage.setItem("user_handle", data.user_handle);
      }

      return true;
    } catch (error) {
      // Network errors, timeouts, etc. - don't clear tokens!
      // The refresh token might still be valid, and the server has a grace period
      console.error("[Auth] Failed to refresh token (network/transient error):", error);
      console.log("[Auth] Keeping tokens - error may be transient, will retry later");
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
    console.log("[Auth] Access token expired, attempting pre-request refresh");
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      accessToken = getAccessToken();
    } else {
      // Refresh failed - refresh token may have been revoked or expired
      // Refresh token is in cookie, so we can't check it directly
      console.log("[Auth] Refresh failed, returning 401");
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
      credentials: "include", // CRITICAL: Include cookies for all authenticated requests
      headers,
    });
  };

  let response = await makeRequest(accessToken);

  // If we get a 401, try to refresh the token and retry once
  if (response.status === 401 && accessToken) {
    console.log("[Auth] Got 401 from API, attempting token refresh");
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      accessToken = getAccessToken();
      console.log("[Auth] Refresh successful, retrying request");
      response = await makeRequest(accessToken);
    } else {
      console.log("[Auth] Refresh failed after 401");
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

/**
 * Logout the current user by calling the logout endpoint.
 * This revokes the refresh token in the database and clears the cookie.
 * 
 * Note: The logout endpoint requires authentication, but we handle failures gracefully.
 * Even if the API call fails (e.g., expired access token), we still clear local storage.
 */
export async function logout(): Promise<void> {
  try {
    // Try to call logout API with authentication
    // This will revoke the refresh token in the database and clear the cookie
    const response = await authenticatedFetch(`${publicBaseUrl}/api/auth/logout`, {
      method: "POST",
      credentials: "include", // CRITICAL: Include cookies
      headers: {
        "Content-Type": "application/json",
      },
    });
    
    // Logout endpoint returns 204 on success, but we don't need to check
    // If it fails (401, etc.), we'll still clear local storage
    if (!response.ok && response.status !== 401) {
      console.warn(`[Auth] Logout API returned ${response.status}, but continuing with cleanup`);
    }
  } catch (error) {
    console.error("[Auth] Logout API call failed:", error);
    // Continue with local cleanup even if API call fails
  } finally {
    // Always clear local storage regardless of API call success
    // This ensures the user appears logged out even if the API call failed
    clearTokens();
  }
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
