import { test, expect, type Page, type Route } from '@playwright/test';
import { seedAuthToken } from './helpers/auth';

/**
 * Social-notification badge over the SSE stream.
 *
 * Spec (a) stubs the API (fake token + page.route) and exercises the client
 * plumbing deterministically: `connected` greeting seeds the badge, a live
 * `notification` frame increments it, and a duplicate id is ignored.
 *
 * Spec (b) is a real-login smoke (gated on E2E_USER_* creds, like
 * menu.spec.ts) proving a real bearer authenticates the stream end to end.
 *
 * Note the SSE stub must be STATEFUL: route.fulfill delivers a complete body,
 * so the hook sees the stream end and reconnects with backoff. Reconnects get
 * `connected` with the post-increment count — replaying the original count
 * would legitimately reset the badge and flake the test.
 */

const E2E_USER_EMAIL = process.env.E2E_USER_EMAIL;
const E2E_USER_PASSWORD = process.env.E2E_USER_PASSWORD;
const HAS_AUTH_CREDS = Boolean(E2E_USER_EMAIL && E2E_USER_PASSWORD);

const NOTIFICATION_ITEM = {
  id: '11111111-2222-3333-4444-555555555555',
  user_id: 1,
  notification_type: 'reaction',
  post_id: 5,
  actor_handle: 'fan',
  actor_avatar_url: null,
  actor_public_sqid: 'fan1',
  emoji: '❤️',
  comment_preview: null,
  content_title: 'Art',
  content_sqid: 'abc',
  content_art_url: null,
  is_read: false,
  created_at: new Date().toISOString(),
};

test.describe('notification badge (stubbed SSE)', () => {
  test('greeting seeds, live frame increments, duplicate id ignored', async ({
    page,
  }) => {
    // All routes and the auth seed must be registered BEFORE page.goto.
    await seedAuthToken(page);

    // Without this stub, Layout's /api/auth/me probe 401s on the fake token,
    // clears localStorage, and unmounts the badge mid-test.
    await page.route('**/api/auth/me', (route: Route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          user: { id: 1, public_sqid: 'e2e-viewer', handle: 'e2e' },
          roles: [],
        }),
      }),
    );

    await page.route('**/api/v1/social-notifications/unread-count', (route: Route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ unread_count: 3 }),
      }),
    );

    let sseRequests = 0;
    await page.route('**/api/v1/realtime/notifications', async (route: Route) => {
      sseRequests += 1;
      const first = sseRequests === 1;
      const body = first
        ? `event: connected\ndata: {"unread_count": 3}\n\n` +
          `: keepalive\n\n` +
          `event: notification\ndata: ${JSON.stringify(NOTIFICATION_ITEM)}\n\n` +
          // Same id again — the dedupe probe. Must NOT double-count.
          `event: notification\ndata: ${JSON.stringify(NOTIFICATION_ITEM)}\n\n`
        : `event: connected\ndata: {"unread_count": 4}\n\n`;
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body,
      });
    });

    await page.goto('/about');

    const bell = page.locator('a[href="/notifications"]');
    const badge = bell.locator('.badge');

    // 3 (greeting) + 1 (notification) and NOT +2 (duplicate ignored).
    await expect(badge).toHaveText('4');
    await expect(bell).toHaveAttribute('aria-label', 'Notifications (4 unread)');

    // Survive at least one stream-end/reconnect cycle without corrupting state.
    await page.waitForTimeout(1500);
    await expect(badge).toHaveText('4');
    expect(sseRequests).toBeGreaterThanOrEqual(1);
  });
});

test.describe('notification SSE (real login)', () => {
  test.skip(
    !HAS_AUTH_CREDS,
    'Set E2E_USER_EMAIL / E2E_USER_PASSWORD in web/.env.e2e.local to run',
  );

  async function loginViaApi(
    page: Page,
  ): Promise<{ token: string; userId: number; handle: string }> {
    const res = await page.request.post('/api/auth/login', {
      data: { email: E2E_USER_EMAIL!, password: E2E_USER_PASSWORD! },
    });
    if (!res.ok()) {
      throw new Error(`Login failed: ${res.status()} ${await res.text()}`);
    }
    const body = await res.json();
    return { token: body.token, userId: body.user_id, handle: body.user_handle };
  }

  test('real bearer opens the stream', async ({ page }) => {
    const auth = await loginViaApi(page);
    await page.addInitScript((a) => {
      localStorage.setItem('access_token', a.token);
      localStorage.setItem('user_id', String(a.userId));
      localStorage.setItem('user_handle', a.handle);
    }, auth);

    const ssePromise = page.waitForResponse(
      (r) =>
        r.url().includes('/api/v1/realtime/notifications') && r.status() === 200,
    );

    await page.goto('/');

    const sseResponse = await ssePromise;
    expect(sseResponse.headers()['content-type']).toContain('text/event-stream');
    // The bell renders for a logged-in user; a badge count is data-dependent,
    // so only assert presence of the link.
    await expect(page.locator('a[href="/notifications"]')).toBeVisible();
  });
});
