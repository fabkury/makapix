import type { Page } from '@playwright/test';

/**
 * Encode a JSON object as a base64url string (JWT segments use base64url).
 */
function base64UrlEncode(value: Record<string, unknown> | string): string {
  const text = typeof value === 'string' ? value : JSON.stringify(value);
  return Buffer.from(text, 'utf8')
    .toString('base64')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

/**
 * Build a well-formed JWT with a far-future `exp` claim.
 *
 * The signature is not verified on the frontend — the web app only decodes the
 * payload to check expiry — so any signature string works. Tests that need
 * server-side validation must stub those endpoints.
 */
export function makeFakeAccessToken(userId = '00000000-0000-0000-0000-000000000001'): string {
  const now = Math.floor(Date.now() / 1000);
  const header = base64UrlEncode({ alg: 'HS256', typ: 'JWT' });
  const payload = base64UrlEncode({
    user_id: userId,
    type: 'access',
    iat: now,
    exp: now + 60 * 60, // 1 hour
  });
  return `${header}.${payload}.signature`;
}

/**
 * Seed an authenticated session in the browser before navigation.
 *
 * Writes an access token and the associated public sqid into localStorage via
 * addInitScript so the very first request after goto already sees a logged-in
 * user. The token does not need to validate against the backend — most tests
 * stub the API calls this token would be used against.
 */
export async function seedAuthToken(
  page: Page,
  opts: { token?: string; publicSqid?: string } = {},
): Promise<void> {
  const token = opts.token || makeFakeAccessToken();
  const publicSqid = opts.publicSqid || 'e2e-viewer';
  await page.addInitScript(
    ({ t, s }) => {
      try {
        window.localStorage.setItem('access_token', t);
        window.localStorage.setItem('public_sqid', s);
      } catch {
        // localStorage may be unavailable; tests that require auth will fail
      }
    },
    { t: token, s: publicSqid },
  );
}
