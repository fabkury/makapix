import { test, expect } from '@playwright/test';

test.describe('global layout', () => {
  test('header renders with logo and navigation', async ({ page }) => {
    await page.goto('/about');
    const header = page.locator('header.header');
    await expect(header).toBeVisible();

    // Logo links to /about
    const logo = header.locator('.logo-link');
    await expect(logo).toBeVisible();
    await expect(logo).toHaveAttribute('href', '/about');

    // Navigation bar is present
    const nav = header.locator('.nav');
    await expect(nav).toBeVisible();
  });

  test('navigation items are present', async ({ page }) => {
    await page.goto('/about');
    const navItems = page.locator('header .nav .nav-item');
    await expect(navItems).not.toHaveCount(0);
  });

  test('logo navigates to about page', async ({ page }) => {
    await page.goto('/auth');
    await page.locator('header .logo-link').click();
    await expect(page).toHaveURL(/\/about/);
  });
});
