import { defineConfig } from '@playwright/test';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// Load env files if present: .env.e2e (committed; Basic Auth creds) and
// .env.e2e.local (gitignored; test user creds). Previously only the .local
// file was auto-loaded, so `npx playwright test` outside `make e2e` (which
// sources .env.e2e) silently lacked the Caddy Basic Auth credentials.
for (const name of ['.env.e2e', '.env.e2e.local']) {
  const envFile = resolve(__dirname, name);
  if (!existsSync(envFile)) continue;
  for (const line of readFileSync(envFile, 'utf-8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    const value = trimmed.slice(eq + 1).trim().replace(/^['"]|['"]$/g, '');
    if (!(key in process.env)) process.env[key] = value;
  }
}

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
      ? { httpCredentials: { username: basicUser, password: basicPass } }
      : {}),
  },
  outputDir: './test-results',
  reporter: [['html', { outputFolder: './playwright-report' }]],
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
});
