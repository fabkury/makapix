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
