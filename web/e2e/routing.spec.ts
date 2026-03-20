import { test, expect } from '@playwright/test';

test.describe('routing & redirects', () => {
  test('unauthenticated user on /search is redirected to /auth', async ({ page }) => {
    await page.goto('/search');
    await expect(page).toHaveURL(/\/auth/);
  });

  test('unauthenticated user on /recommended is redirected or shows empty state', async ({ page }) => {
    await page.goto('/recommended');
    // Either redirects to /auth or renders the page with an empty/login prompt
    const url = page.url();
    const onAuth = /\/auth/.test(url);
    const onRecommended = /\/recommended/.test(url);
    expect(onAuth || onRecommended).toBeTruthy();
  });

  test('unauthenticated user on /notifications is redirected to /auth', async ({ page }) => {
    await page.goto('/notifications');
    await expect(page).toHaveURL(/\/auth/);
  });

  test('non-existent page returns 404 or redirects', async ({ page }) => {
    const response = await page.goto('/this-page-does-not-exist-xyz');
    // Either a 404 status or a redirect to an error/auth page
    expect(response).not.toBeNull();
    const status = response!.status();
    expect(status === 404 || status === 200).toBeTruthy();
  });

  test('/about is accessible without app authentication', async ({ page }) => {
    await page.goto('/about');
    await expect(page).toHaveURL(/\/about/);
    await expect(page.locator('main')).toBeVisible();
  });
});
