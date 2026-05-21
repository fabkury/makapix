import { test, expect } from '@playwright/test';

test.describe('global layout', () => {
  test('header renders with logo and navigation', async ({ page }) => {
    await page.goto('/about');
    const header = page.locator('header.header');
    await expect(header).toBeVisible();

    // Logo is the menu trigger
    const logo = header.locator('button.logo-link');
    await expect(logo).toBeVisible();
    await expect(logo).toHaveAttribute('aria-haspopup', 'menu');

    // Navigation bar is present
    const nav = header.locator('.nav');
    await expect(nav).toBeVisible();
  });

  test('navigation items are present', async ({ page }) => {
    await page.goto('/about');
    const navItems = page.locator('header .nav .nav-item');
    await expect(navItems).not.toHaveCount(0);
  });

  test('clicking the logo opens the menu', async ({ page }) => {
    await page.goto('/auth');
    await page.locator('header button.logo-link').click();
    await expect(page.locator('.menu-panel[role="menu"]')).toBeVisible();
  });
});
