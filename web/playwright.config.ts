import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright configuration for the AC005 e2e audit (T-WEBE2E).
 *
 * Self-contained run: `npm run e2e` (or `npx playwright test`)
 *   1. globalSetup   — boots the mock backend on :8000
 *                      (NERVE_MOCK_INFER=1 .venv/bin/python -m uvicorn backend.api.app:app)
 *   2. webServer     — boots the Vite dev server on :3000 with
 *                      VITE_API_BASE=/api so the API client uses the REAL
 *                      backend (not the in-browser mock fixtures)
 *   3. tests         — 10 view-render tests + Ask round-trip (chromium only)
 *   4. globalTeardown — stops the backend.
 *
 * Chromium-only by design (CI speed); the mock backend has no /ws route and
 * no view currently consumes the realtime socket, so no other engine is
 * needed for this audit.
 * @see https://playwright.dev/docs/test-configuration
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  timeout: 30_000,
  globalSetup: './tests/e2e/global-setup.mjs',
  globalTeardown: './tests/e2e/global-teardown.mjs',
  use: {
    baseURL: 'http://localhost:3000',
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  webServer: {
    command: 'npx vite --port 3000 --strictPort',
    url: 'http://localhost:3000',
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      VITE_API_BASE: '/api',
    },
  },
})
