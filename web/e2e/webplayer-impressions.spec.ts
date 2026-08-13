import { test, expect, type Page, type Route, type Request } from '@playwright/test';
import { seedAuthToken } from './helpers/auth';

/**
 * View/Impression firing semantics (docs/artwork-views/ D4/D8):
 * - The Web Player emits ONE Impression per artwork appearance (the 30s
 *   screen-time re-fire is gone) with an explicit intent field.
 * - A permalink visit registers a body-less View POST after the 2s dwell.
 * All API calls are stubbed; page.clock drives the timers.
 */

const TINY_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
  'base64',
);

const ARTWORK = {
  id: 7001,
  public_sqid: 'wp-art-1',
  title: 'Rotation Piece',
  art_url: 'https://example.com/wp-art-1.png',
  width: 64,
  height: 64,
  frame_count: 1,
  created_at: '2026-07-01T00:00:00Z',
  files: [],
  owner: { id: 2, handle: 'someone-else', avatar_url: null, public_sqid: 'other-artist' },
  owner_id: 2,
  reaction_count: 0,
  comment_count: 0,
  kind: 'artwork',
};

function viewPosts(requests: Request[]) {
  return requests.filter((r) => r.url().includes('/view') && r.method() === 'POST');
}

async function stubApis(page: Page, viewRequests: Request[]) {
  await page.route('**/api/**', (route: Route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }),
  );
  await page.route('**/example.com/**', (route: Route) =>
    route.fulfill({ status: 200, contentType: 'image/png', body: TINY_PNG }),
  );
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
  await page.route('**/api/post?**', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [ARTWORK], next_cursor: null, total: 1 }),
    }),
  );
  // Registered last so it outranks the /api/post?** and catch-all globs.
  await page.route('**/api/post/*/view', (route: Route) => {
    viewRequests.push(route.request());
    route.fulfill({ status: 201, body: '' });
  });
}

test('web player fires one impression per appearance, no 30s re-fire', async ({
  page,
}) => {
  const views: Request[] = [];
  await page.clock.install();
  await seedAuthToken(page);
  // Dwell 0 = rotation disabled: the artwork stays on screen indefinitely.
  // The pre-redesign player would re-fire every 30s in this state.
  await page.addInitScript(() => {
    try {
      window.localStorage.setItem('wp_dwell_sec', '0');
    } catch {
      /* ignore */
    }
  });
  await stubApis(page, views);

  await page.goto('/');
  await page.getByRole('button', { name: 'Open Web Player' }).click();

  // Past the 2s appearance guard: exactly one POST, explicit impression intent.
  await page.clock.runFor(4000);
  await expect.poll(() => viewPosts(views).length).toBe(1);
  const body = viewPosts(views)[0].postDataJSON() as Record<string, unknown>;
  expect(body.intent).toBe('impression');
  expect(body).toHaveProperty('channel');

  // Far past the old 30s re-fire window: still exactly one.
  await page.clock.runFor(65_000);
  expect(viewPosts(views).length).toBe(1);
});

test('permalink visit registers a body-less View after the dwell', async ({
  page,
}) => {
  const views: Request[] = [];
  await page.clock.install();
  await seedAuthToken(page);
  await stubApis(page, views);
  await page.route('**/api/p/*', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        ...ARTWORK,
        view_count: 3,
        description: '',
        hashtags: [],
        mod_hashtags: [],
        storage_key: '00000000-0000-0000-0000-00000000bbbb',
        promoted: false,
        visible: true,
        public_visibility: true,
        hidden_by_user: false,
        hidden_by_mod: false,
        has_mkpx: false,
        license: null,
      }),
    }),
  );

  await page.goto(`/p/${ARTWORK.public_sqid}`);
  await page.clock.runFor(4000);

  await expect.poll(() => viewPosts(views).length).toBe(1);
  // Body-less POST = an Artwork View (D4).
  expect(viewPosts(views)[0].postData()).toBeFalsy();
});
