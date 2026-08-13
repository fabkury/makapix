import { test, expect, type Page, type Route } from '@playwright/test';
import { seedAuthToken } from './helpers/auth';

/**
 * Rebuilt per-artwork StatsPanel (docs/artwork-views/): Views vs Impressions
 * as separate metrics, canonical + legacy views_by_type payloads render
 * without error, auth toggle swaps field sets, refresh hits ?refresh=true.
 * All API calls are stubbed; only the deployed page bundle is exercised.
 */

const SQID = 'e2e-statpost';
const POST_ID = 4242;

const TINY_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
  'base64',
);

function dailySeries(views: number, impressions: number) {
  const out = [];
  for (let i = 29; i >= 0; i--) {
    const d = new Date(Date.now() - i * 86400_000);
    out.push({
      date: d.toISOString().slice(0, 10),
      views: i === 0 ? views : 0,
      unique_viewers: i === 0 ? views : 0,
      impressions: i === 0 ? impressions : 0,
    });
  }
  return out;
}

function statsFixture(viewsByType: Record<string, number>) {
  const views = viewsByType.view ?? viewsByType.intentional ?? 0;
  const impressions = Object.entries(viewsByType)
    .filter(([k]) => k !== 'view' && k !== 'intentional')
    .reduce((a, [, v]) => a + v, 0);
  return {
    post_id: POST_ID,
    total_views: views,
    unique_viewers: views,
    total_impressions: impressions,
    views_by_country: { US: views },
    views_by_device: { desktop: views },
    views_by_type: viewsByType,
    daily_views: dailySeries(views, impressions),
    total_reactions: 3,
    reactions_by_emoji: { '❤️': 3 },
    total_comments: 1,
    total_views_authenticated: Math.floor(views / 2),
    unique_viewers_authenticated: Math.floor(views / 2),
    total_impressions_authenticated: Math.floor(impressions / 2),
    views_by_country_authenticated: { US: Math.floor(views / 2) },
    views_by_device_authenticated: { desktop: Math.floor(views / 2) },
    views_by_type_authenticated: {},
    daily_views_authenticated: dailySeries(
      Math.floor(views / 2),
      Math.floor(impressions / 2),
    ),
    total_reactions_authenticated: 2,
    reactions_by_emoji_authenticated: { '❤️': 2 },
    total_comments_authenticated: 1,
    first_view_at: '2026-07-01T00:00:00Z',
    last_view_at: new Date().toISOString(),
    computed_at: new Date().toISOString(),
  };
}

const postFixture = {
  id: POST_ID,
  public_sqid: SQID,
  storage_key: '00000000-0000-0000-0000-00000000aaaa',
  title: 'Stats Target',
  description: '',
  hashtags: [],
  mod_hashtags: [],
  art_url: 'https://example.com/stats-target.png',
  width: 64,
  height: 64,
  frame_count: 1,
  kind: 'artwork',
  owner_id: 1,
  owner: { id: 1, handle: 'e2e', public_sqid: 'e2e-viewer', avatar_url: null },
  created_at: '2026-07-01T00:00:00Z',
  promoted: false,
  visible: true,
  public_visibility: true,
  hidden_by_user: false,
  hidden_by_mod: false,
  view_count: 40,
  has_mkpx: false,
  license: null,
};

async function stubPage(page: Page, viewsByType: Record<string, number>) {
  await seedAuthToken(page);
  // Catch-all first (lowest priority — later routes win).
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
  await page.route(`**/api/p/${SQID}`, (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(postFixture),
    }),
  );
  await page.route('**/api/post/*/widget-data', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ reactions: null, comments: [], views_count: 40 }),
    }),
  );
  await page.route('**/api/post/*/view', (route: Route) =>
    route.fulfill({ status: 201, body: '' }),
  );
  await page.route('**/api/post/*/stats*', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(statsFixture(viewsByType)),
    }),
  );
}

async function openStatsPanel(page: Page) {
  await page.goto(`/p/${SQID}`);
  await page.getByRole('button', { name: 'More options' }).click();
  await page.getByRole('button', { name: '📈 Statistics' }).click();
  await expect(page.getByText('📊 Artwork Statistics')).toBeVisible();
}

test('shows Views and Impressions as separate KPIs with canonical payload', async ({
  page,
}) => {
  await stubPage(page, { view: 40, impression: 400 });
  await openStatsPanel(page);

  await expect(page.getByText('Views (30d)')).toBeVisible();
  await expect(page.getByText('Impressions (30d)')).toBeVisible();
  await expect(page.getByText('400', { exact: true })).toBeVisible();
  // The approximate-uniques disclaimer (D13) rides the KpiCard title attr.
  await expect(
    page.locator('[title*="Approximate"]').first(),
  ).toBeAttached();
  // Country rows use flag + display name, not raw ISO codes.
  await expect(page.getByText('🇺🇸 United States')).toBeVisible();
});

test('auth toggle swaps to authenticated-only figures', async ({ page }) => {
  await stubPage(page, { view: 40, impression: 400 });
  await openStatsPanel(page);

  await page.getByLabel('Include unauthenticated traffic').uncheck();
  await expect(page.getByText('200', { exact: true })).toBeVisible(); // 400/2
});

test('legacy views_by_type keys render without the old taxonomy', async ({
  page,
}) => {
  await stubPage(page, { intentional: 10, widget: 5, listing: 3 });
  await openStatsPanel(page);

  await expect(page.getByText('Views (30d)')).toBeVisible();
  // The deleted taxonomy labels must not resurface.
  await expect(page.getByText('Direct Click')).toHaveCount(0);
  await expect(page.getByText('Widget')).toHaveCount(0);
});

test('refresh requests a cache-busting recompute', async ({ page }) => {
  await stubPage(page, { view: 40, impression: 400 });
  await openStatsPanel(page);

  const refreshRequest = page.waitForRequest((req) =>
    req.url().includes('refresh=true'),
  );
  await page.getByRole('button', { name: 'Refresh cache' }).click();
  await refreshRequest;
});
