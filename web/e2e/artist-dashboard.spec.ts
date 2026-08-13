import { test, expect, type Page, type Route } from '@playwright/test';
import { seedAuthToken } from './helpers/auth';

/**
 * Rebuilt Artist Dashboard (docs/artwork-views/): metrics-kit KPIs incl.
 * Impressions, D13 approximate-uniques hint, flag+name countries,
 * per-artwork table links, pagination. All API calls stubbed.
 */

const SQID = 'e2e-artist';

function daily(views: number, impressions: number) {
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

function postItem(id: number) {
  return {
    post_id: id,
    public_sqid: `post-${id}`,
    title: `Artwork ${id}`,
    created_at: '2026-07-01T00:00:00Z',
    total_views: 10 + id,
    unique_viewers: 10 + id,
    total_impressions: 100 + id,
    total_reactions: 2,
    total_comments: 1,
    total_views_authenticated: 5,
    unique_viewers_authenticated: 5,
    total_impressions_authenticated: 50,
    total_reactions_authenticated: 1,
    total_comments_authenticated: 0,
  };
}

function dashboardFixture(page_num: number) {
  return {
    artist_stats: {
      user_id: 1,
      user_key: '00000000-0000-0000-0000-000000000001',
      total_posts: 25,
      total_views: 77,
      unique_viewers: 60,
      total_impressions: 900,
      views_by_country: { BR: 40, US: 37 },
      views_by_device: { desktop: 50, player: 27 },
      daily_views: daily(77, 900),
      total_reactions: 12,
      reactions_by_emoji: { '🔥': 12 },
      total_comments: 4,
      total_views_authenticated: 30,
      unique_viewers_authenticated: 25,
      total_impressions_authenticated: 400,
      views_by_country_authenticated: { BR: 30 },
      views_by_device_authenticated: { desktop: 30 },
      daily_views_authenticated: daily(30, 400),
      total_reactions_authenticated: 8,
      reactions_by_emoji_authenticated: { '🔥': 8 },
      total_comments_authenticated: 2,
      first_post_at: '2026-01-01T00:00:00Z',
      latest_post_at: '2026-08-01T00:00:00Z',
      computed_at: new Date().toISOString(),
    },
    posts: [postItem(page_num === 1 ? 1 : 21), postItem(page_num === 1 ? 2 : 22)],
    total_posts: 25,
    page: page_num,
    page_size: 20,
    has_more: page_num === 1,
  };
}

async function stubDashboard(page: Page) {
  await seedAuthToken(page);
  await page.route('**/api/**', (route: Route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }),
  );
  await page.route('**/api/auth/me', (route: Route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        user: { id: 1, public_sqid: SQID, handle: 'e2e-artist' },
        roles: [],
      }),
    }),
  );
  await page.route('**/api/user/*/artist-dashboard*', (route: Route) => {
    const url = new URL(route.request().url());
    const pageNum = Number(url.searchParams.get('page') || '1');
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(dashboardFixture(pageNum)),
    });
  });
}

test('renders KPI tiles, impressions, and flagged countries', async ({
  page,
}) => {
  await stubDashboard(page);
  await page.goto(`/u/${SQID}/dashboard`);

  await expect(page.getByText('Views (30d)')).toBeVisible();
  await expect(page.getByText('Impressions (30d)')).toBeVisible();
  await expect(page.getByText('900', { exact: true })).toBeVisible();
  await expect(page.locator('[title*="Approximate"]').first()).toBeAttached();
  await expect(page.getByText('🇧🇷 Brazil')).toBeVisible();

  // Per-artwork table: title links to the permalink, Impressions column shown.
  const link = page.getByRole('link', { name: 'Artwork 1' });
  await expect(link).toHaveAttribute('href', '/p/post-1');
  await expect(
    page.getByText('Impressions', { exact: true }).first(),
  ).toBeVisible();
});

test('pagination requests the next page', async ({ page }) => {
  await stubDashboard(page);
  await page.goto(`/u/${SQID}/dashboard`);
  await expect(page.getByText('Artwork 1')).toBeVisible();

  const nextPage = page.waitForRequest((req) => req.url().includes('page=2'));
  await page.getByRole('button', { name: 'Next →' }).click();
  await nextPage;
  await expect(page.getByText('Artwork 21')).toBeVisible();
});
