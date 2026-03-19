import { test, expect } from '@playwright/test';

test('homepage loads', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/Makapix/);
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
