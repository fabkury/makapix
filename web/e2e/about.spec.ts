import { test, expect } from '@playwright/test';

test.describe('about page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/about');
  });

  test('displays tab navigation with all tabs', async ({ page }) => {
    const tabs = page.locator('.tabs-list .tab-trigger');
    const expectedTabs = ['about', 'features', 'rules', 'moderation', 'licenses'];

    for (const value of expectedTabs) {
      await expect(tabs.filter({ has: page.locator(`[data-value="${value}"]`) }).or(
        page.locator(`.tab-trigger[value="${value}"]`)
      ).or(
        tabs.filter({ hasText: new RegExp(value, 'i') })
      )).toBeVisible();
    }
  });

  test('about tab is active by default', async ({ page }) => {
    const aboutTab = page.locator('.tab-trigger').first();
    await expect(aboutTab).toHaveAttribute('data-state', 'active');
  });

  test('switching tabs changes visible content', async ({ page }) => {
    // Click on the features tab
    await page.locator('.tab-trigger').filter({ hasText: /features/i }).click();

    // Features content should appear
    await expect(
      page.locator('.artist-section').or(page.locator('text=Artist')).first()
    ).toBeVisible();
  });

  test('rules tab shows reputation tier table', async ({ page }) => {
    await page.locator('.tab-trigger').filter({ hasText: /rules/i }).click();
    await expect(page.locator('.tier-table').or(page.locator('table')).first()).toBeVisible();
  });

  test('licenses tab shows license information', async ({ page }) => {
    const licensesTab = page.locator('.tab-trigger').filter({ hasText: /licenses/i });
    await licensesTab.click();
    await expect(licensesTab).toHaveAttribute('data-state', 'active');
    await expect(page.locator('.license-item').first()).toBeVisible();
  });

  test('contains Discord and GitHub links', async ({ page }) => {
    await expect(page.locator('a[href*="discord"]').or(page.locator('text=Discord').first())).toBeVisible();
    await expect(page.locator('a[href*="github"]').or(page.locator('text=GitHub').first())).toBeVisible();
  });
});
