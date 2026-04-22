import { test, expect, type Page, type Route } from '@playwright/test';
import { seedAuthToken } from './helpers/auth';

// Any sqid-shaped string works; the API is stubbed so backend state is irrelevant.
const TARGET_SQID = 'e2e-reactor';
const VIEWER_SQID = 'e2e-viewer';

/* ------------------------------------------------------------------ */
/* Fixture factories                                                   */
/* ------------------------------------------------------------------ */

function buildProfile(sqid: string) {
  return {
    id: 1,
    user_key: '00000000-0000-0000-0000-000000000001',
    public_sqid: sqid,
    handle: `reactor_${sqid}`,
    bio: null,
    tagline: null,
    website: null,
    avatar_url: null,
    badges: [],
    reputation: 0,
    hidden_by_user: false,
    hidden_by_mod: false,
    non_conformant: false,
    deactivated: false,
    created_at: '2025-01-01T00:00:00Z',
    tag_badges: [],
    stats: {
      total_posts: 0,
      total_reactions_received: 0,
      total_views: 0,
      follower_count: 0,
    },
    is_following: false,
    is_own_profile: false,
    highlights: [],
  };
}

function buildReactedPost(id: number) {
  return {
    id,
    public_sqid: `post-${id}`,
    title: `Post ${id}`,
    art_url: `https://example.com/post-${id}.png`,
    width: 64,
    height: 64,
    owner_id: 2,
    owner_handle: 'artist',
    reacted_at: '2026-04-20T00:00:00Z',
    emoji: '❤️',
    created_at: '2026-04-19T00:00:00Z',
    frame_count: 1,
    files: [],
  };
}

function buildPlayer(status: 'online' | 'offline' = 'online') {
  return {
    id: '00000000-0000-0000-0000-00000000aaaa',
    name: 'Test Player',
    connection_status: status,
    device_model: 'TestDevice',
    firmware_version: '1.0.0',
    registration_status: 'registered',
    owner_id: 1,
    current_post_id: null,
    last_seen_at: '2026-04-22T00:00:00Z',
    created_at: '2026-01-01T00:00:00Z',
  };
}

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

type Stubs = {
  profile?: boolean;
  reactedItems?: ReturnType<typeof buildReactedPost>[];
  players?: ReturnType<typeof buildPlayer>[];
  onCommand?: (body: unknown) => void;
};

async function installStubs(page: Page, stubs: Stubs = {}): Promise<void> {
  if (stubs.profile !== false) {
    await page.route('**/api/user/u/*/profile', async (route: Route) => {
      const url = route.request().url();
      const match = url.match(/\/api\/user\/u\/([^/]+)\/profile/);
      const sqid = match ? match[1] : TARGET_SQID;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(buildProfile(sqid)),
      });
    });
  }

  await page.route('**/api/user/u/*/reacted-posts*', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: stubs.reactedItems ?? [],
        next_cursor: null,
      }),
    });
  });

  await page.route('**/api/user/u/*/badge-grants*', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([]),
    });
  });

  await page.route('**/api/u/*/player', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: stubs.players ?? [] }),
    });
  });

  if (stubs.onCommand) {
    await page.route(
      '**/api/u/*/player/*/command',
      async (route: Route) => {
        stubs.onCommand!(route.request().postDataJSON());
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            command_id: '00000000-0000-0000-0000-000000000bbb',
            status: 'sent',
          }),
        });
      },
    );
  }

  // Catch-all for /api/post etc. so the gallery tab doesn't hang on real data.
  await page.route('**/api/post*', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ items: [], next_cursor: null }),
    });
  });
}

/* ------------------------------------------------------------------ */
/* Specs                                                               */
/* ------------------------------------------------------------------ */

test.describe('profile Favourites tab', () => {
  test('Favourites tab is visible on another profile without authentication', async ({
    page,
  }) => {
    await installStubs(page);
    await page.goto(`/u/${TARGET_SQID}`);

    const galleryTab = page.getByRole('button', { name: '🖼️' });
    const favouritesTab = page.getByRole('button', { name: '⚡' });
    await expect(galleryTab).toBeVisible();
    await expect(favouritesTab).toBeVisible();
  });

  test('Favourites tab remains visible when authenticated', async ({ page }) => {
    await seedAuthToken(page, { publicSqid: VIEWER_SQID });
    await installStubs(page);
    await page.goto(`/u/${TARGET_SQID}`);

    await expect(page.getByRole('button', { name: '⚡' })).toBeVisible();
  });

  test('switching to Favourites loads the reacted-posts feed', async ({ page }) => {
    const items = [buildReactedPost(1), buildReactedPost(2), buildReactedPost(3)];
    await installStubs(page, { reactedItems: items });

    const waitForReacted = page.waitForResponse(
      (r) => /\/reacted-posts/.test(r.url()) && r.status() === 200,
    );
    await page.goto(`/u/${TARGET_SQID}`);
    await page.getByRole('button', { name: '⚡' }).click();
    const resp = await waitForReacted;
    const body = await resp.json();
    expect(body.items).toHaveLength(3);
  });

  test('Favourites with no reactions returns an empty response', async ({ page }) => {
    await installStubs(page, { reactedItems: [] });

    const waitForReacted = page.waitForResponse(
      (r) => /\/reacted-posts/.test(r.url()) && r.status() === 200,
    );
    await page.goto(`/u/${TARGET_SQID}`);
    await page.getByRole('button', { name: '⚡' }).click();
    const resp = await waitForReacted;
    const body = await resp.json();
    expect(body.items).toEqual([]);
  });
});

test.describe('PlayerBar channel wiring', () => {
  test('Gallery sends by_user; Favourites sends reactions', async ({ page }) => {
    const commands: Array<Record<string, unknown>> = [];
    await seedAuthToken(page, { publicSqid: VIEWER_SQID });
    await installStubs(page, {
      players: [buildPlayer('online')],
      onCommand: (body) => {
        if (body && typeof body === 'object') {
          commands.push(body as Record<string, unknown>);
        }
      },
    });

    await page.goto(`/u/${TARGET_SQID}`);

    const sendBtn = page.locator('button.send-to-player-btn');
    await expect(sendBtn).toBeVisible({ timeout: 15_000 });

    // Gallery tab (default) → legacy by_user channel command.
    await sendBtn.click();
    await expect
      .poll(() => commands.length, { timeout: 10_000 })
      .toBeGreaterThanOrEqual(1);
    const galleryCmd = commands[0];
    expect(galleryCmd.command_type).toBe('play_channel');
    expect(galleryCmd.channel_name).toBe('by_user');
    expect(galleryCmd.user_sqid).toBe(TARGET_SQID);

    // Switch to Favourites.
    await page.getByRole('button', { name: '⚡' }).click();

    // Click Send again → reactions channel command.
    await sendBtn.click();
    await expect
      .poll(() => commands.length, { timeout: 10_000 })
      .toBeGreaterThanOrEqual(2);
    const reactionsCmd = commands[commands.length - 1];
    expect(reactionsCmd.command_type).toBe('play_channel');
    expect(reactionsCmd.channel_name).toBe('reactions');
    expect(reactionsCmd.user_sqid).toBe(TARGET_SQID);
  });

  test('PlayerBar does not appear when the viewer has no online players', async ({
    page,
  }) => {
    await seedAuthToken(page, { publicSqid: VIEWER_SQID });
    await installStubs(page, { players: [] });

    await page.goto(`/u/${TARGET_SQID}`);

    // Give the client a moment to settle; the PlayerBar should never render.
    await page.waitForTimeout(750);
    await expect(page.locator('button.send-to-player-btn')).toHaveCount(0);
  });
});
