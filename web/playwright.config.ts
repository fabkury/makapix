import { defineConfig } from '@playwright/test';

const baseURL = process.env.BASE_URL || 'https://development.makapix.club';

// HTTP Basic Auth credentials for the development environment (Caddy basicauth).
// Set E2E_BASIC_USER and E2E_BASIC_PASS env vars, or defaults to 'developer'.
const basicUser = process.env.E2E_BASIC_USER || 'developer';
const basicPass = process.env.E2E_BASIC_PASS || '';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: 1,
  use: {
    baseURL,
    ignoreHTTPSErrors: true,
    screenshot: 'only-on-failure',
    ...(basicPass
      ? {
          extraHTTPHeaders: {
            Authorization: `Basic ${Buffer.from(`${basicUser}:${basicPass}`).toString('base64')}`,
          },
        }
      : {}),
  },
  outputDir: './test-results',
  reporter: [['html', { outputFolder: './playwright-report' }]],
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
});
