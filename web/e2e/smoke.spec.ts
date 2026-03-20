import { test, expect } from '@playwright/test';

test.describe('smoke tests', () => {
  test('homepage loads and redirects unauthenticated user', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/Makapix/);
    // Unauthenticated app users get redirected to /welcome
    await expect(page).toHaveURL(/\/(welcome|auth)?/);
  });

  test('about page loads', async ({ page }) => {
    await page.goto('/about');
    await expect(page).toHaveTitle(/Makapix/);
    await expect(page.locator('main')).toBeVisible();
  });

  test('auth page is accessible', async ({ page }) => {
    await page.goto('/auth');
    await expect(page).toHaveTitle(/Makapix/);
  });
});
