import { test, expect, type Page } from '@playwright/test';

const E2E_USER_EMAIL = process.env.E2E_USER_EMAIL;
const E2E_USER_PASSWORD = process.env.E2E_USER_PASSWORD;
const HAS_AUTH_CREDS = Boolean(E2E_USER_EMAIL && E2E_USER_PASSWORD);

async function loginViaApi(page: Page): Promise<{ token: string; userId: number; handle: string }> {
  const res = await page.request.post('/api/auth/login', {
    data: { email: E2E_USER_EMAIL!, password: E2E_USER_PASSWORD! },
  });
  if (!res.ok()) {
    throw new Error(`Login failed: ${res.status()} ${await res.text()}`);
  }
  const body = await res.json();
  return { token: body.token, userId: body.user_id, handle: body.user_handle };
}

async function seedAuthStorage(
  page: Page,
  auth: { token: string; userId: number; handle: string }
) {
  await page.addInitScript((a) => {
    localStorage.setItem('access_token', a.token);
    localStorage.setItem('user_id', String(a.userId));
    localStorage.setItem('user_handle', a.handle);
  }, auth);
}

test.describe('header kebab menu (unauthenticated)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/about');
  });

  test('kebab button is visible with correct aria attributes', async ({ page }) => {
    const trigger = page.locator('header button.menu-trigger');
    await expect(trigger).toBeVisible();
    await expect(trigger).toHaveAttribute('aria-label', 'More');
    await expect(trigger).toHaveAttribute('aria-haspopup', 'menu');
    await expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  test('clicking the kebab opens the panel with the engaged highlight', async ({ page }) => {
    const trigger = page.locator('header button.menu-trigger');
    await trigger.click();
    await expect(trigger).toHaveAttribute('aria-expanded', 'true');
    await expect(trigger).toHaveClass(/menu-trigger-open/);
    await expect(page.locator('.menu-panel[role="menu"]')).toBeVisible();
  });

  test('panel contains Players and About; no Log out when signed out', async ({ page }) => {
    await page.locator('header button.menu-trigger').click();
    const panel = page.locator('.menu-panel[role="menu"]');
    await expect(panel.getByRole('menuitem', { name: 'Players' })).toBeVisible();
    await expect(panel.getByRole('menuitem', { name: 'About' })).toBeVisible();
    await expect(panel.getByRole('menuitem', { name: 'Log out' })).toHaveCount(0);
  });

  test('pressing Escape closes the panel', async ({ page }) => {
    const trigger = page.locator('header button.menu-trigger');
    await trigger.click();
    await expect(page.locator('.menu-panel')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(page.locator('.menu-panel')).toHaveCount(0);
    await expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  test('clicking outside the panel closes it', async ({ page }) => {
    await page.locator('header button.menu-trigger').click();
    await expect(page.locator('.menu-panel')).toBeVisible();
    // Click in the middle of the page, well outside the header and panel
    await page.mouse.click(100, 400);
    await expect(page.locator('.menu-panel')).toHaveCount(0);
  });

  test('clicking Players navigates to /players and closes the menu', async ({ page }) => {
    await page.locator('header button.menu-trigger').click();
    await page.locator('.menu-panel a[href="/players"]').click();
    await expect(page).toHaveURL(/\/players/);
    await expect(page.locator('.menu-panel')).toHaveCount(0);
  });

  test('clicking About navigates to /about from another page', async ({ page }) => {
    await page.goto('/players');
    await page.locator('header button.menu-trigger').click();
    await page.locator('.menu-panel a[href="/about"]').click();
    await expect(page).toHaveURL(/\/about/);
    await expect(page.locator('.menu-panel')).toHaveCount(0);
  });
});

test.describe('header kebab menu (authenticated)', () => {
  test('shows Log out and clears auth state when clicked', async ({ page }) => {
    test.skip(
      !HAS_AUTH_CREDS,
      'Set E2E_USER_EMAIL and E2E_USER_PASSWORD (e.g. via web/.env.e2e.local) to run this test'
    );
    const auth = await loginViaApi(page);
    await seedAuthStorage(page, auth);
    await page.goto('/about');

    const trigger = page.locator('header button.menu-trigger');
    await trigger.click();
    const panel = page.locator('.menu-panel[role="menu"]');
    await expect(panel).toBeVisible();

    const logoutItem = panel.getByRole('menuitem', { name: 'Log out' });
    await expect(logoutItem).toBeVisible();

    // Confirm token is present before logout
    const tokenBefore = await page.evaluate(() => localStorage.getItem('access_token'));
    expect(tokenBefore).toBeTruthy();

    // Clicking Log out fires the logout API and redirects to /welcome
    const [logoutResponse] = await Promise.all([
      page.waitForResponse(
        (r) => r.url().includes('/api/auth/logout') && r.request().method() === 'POST'
      ),
      logoutItem.click(),
    ]);
    expect(logoutResponse.status()).toBeLessThan(500);

    await expect(page).toHaveURL(/\/welcome/);

    // Token is cleared
    const tokenAfter = await page.evaluate(() => localStorage.getItem('access_token'));
    expect(tokenAfter).toBeNull();
  });
});
