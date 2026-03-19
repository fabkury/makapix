import { test, expect } from '@playwright/test';

test.describe('auth page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/auth');
  });

  test('displays login form with email and password fields', async ({ page }) => {
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
  });

  test('displays login submit button', async ({ page }) => {
    await expect(
      page.locator('form').getByRole('button', { name: /log\s*in/i })
    ).toBeVisible();
  });

  test('has a register/signup toggle', async ({ page }) => {
    // There should be a way to switch to register mode
    const toggle = page.getByText(/don.*t have an account/i)
      .or(page.getByText(/sign up/i))
      .or(page.getByText(/register/i));
    await expect(toggle.first()).toBeVisible();
  });

  test('shows GitHub OAuth option', async ({ page }) => {
    await expect(
      page.getByRole('button', { name: /github/i })
        .or(page.locator('a').filter({ hasText: /github/i }))
        .first()
    ).toBeVisible();
  });

  test('login with empty fields stays on page', async ({ page }) => {
    await page.locator('form').getByRole('button', { name: /log\s*in/i }).click();
    // Should remain on auth page (no redirect)
    await expect(page).toHaveURL(/\/auth/);
  });
});
